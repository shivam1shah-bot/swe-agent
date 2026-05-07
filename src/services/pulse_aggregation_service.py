"""
pulse_aggregation_service.py — Business logic for aggregating AI usage data.

Cost calculation uses GROUP BY model + Python pricing (single source of truth).

TODO: Migrate to BaseService pattern (class PulseAggregationService(BaseService))
      to align with codebase conventions — structured logging, health checks,
      lifecycle management, and session abstraction via Repository pattern.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Integer, case, desc, func, union
from sqlalchemy.orm import Session

from src.utils.pricing import cost_from_tokens as calc_cost, sum_token_count as sum_tokens, cache_savings
from src.models.pulse_turn import PulseTurn
from src.models.pulse_commit import PulseCommit
from src.models.pulse_commit_prompt import PulseCommitPrompt

logger = logging.getLogger(__name__)

_SECONDS_PER_DAY = 86400
_SECONDS_PER_WEEK = 604800
_MAX_WEEKLY_BUCKETS = 16
_TOP_PROMPTS_PER_PERSON = 20


def _tok_dict(row: Any) -> dict[str, int]:
    """Build normalized tokens dict, casting to int.

    MySQL SUM() on INT columns returns Decimal, which cannot be multiplied
    with float in Python. Explicit int() cast prevents TypeError in pricing.
    """
    return {
        "input_tokens": int(row.input_tokens or 0),
        "output_tokens": int(row.output_tokens or 0),
        "cache_read_tokens": int(row.cache_read_tokens or 0),
        "cache_creation_tokens": int(row.cache_creation_tokens or 0),
    }


def _cutoff_ts(days: Optional[int]) -> Optional[float]:
    if days is None:
        return None
    return time.time() - days * _SECONDS_PER_DAY


def _apply_turn_filters(q: Any, days: Optional[int], repo: Optional[str] = None, email: Optional[str] = None) -> Any:
    cutoff = _cutoff_ts(days)
    if cutoff is not None:
        q = q.filter(PulseTurn.unix_ts > cutoff)
    if repo:
        q = q.filter(PulseTurn.repo == repo)
    if email:
        q = q.filter(PulseTurn.author_email == email.strip().lower())
    return q


def _apply_commit_filters(q: Any, days: Optional[int], repo: Optional[str] = None) -> Any:
    cutoff = _cutoff_ts(days)
    if cutoff is not None:
        q = q.filter(PulseCommit.unix_ts > cutoff)
    if repo:
        q = q.filter(PulseCommit.repo == repo)
    return q


def _cost_from_model_groups(rows: Any) -> tuple[float, int, float]:
    total_cost = 0.0
    total_tokens = 0
    total_cache_saved = 0.0
    for r in rows:
        tok = _tok_dict(r)
        model = r.model or ""
        total_cost += calc_cost(tok, model)
        total_tokens += sum_tokens(tok)
        total_cache_saved += cache_savings(tok, model)
    return total_cost, total_tokens, total_cache_saved


def _safe_week_key(unix_ts: float) -> Optional[str]:
    """Convert unix timestamp to ISO week key in UTC, returning None on invalid values."""
    try:
        if unix_ts < 0:
            return None
        dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
        return f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
    except (ValueError, OSError):
        logger.warning("Skipping row with invalid unix_ts: %s", unix_ts)
        return None


def _turn_to_prompt_dict(t: PulseTurn) -> dict[str, Any]:
    """Convert a PulseTurn row to the standard prompt response dict."""
    tok = _tok_dict(t)
    model = t.model or ""
    cost = calc_cost(tok, model)
    return {
        "prompt": (t.user_prompt or "").strip(),
        "cost_usd": round(cost, 6),
        "total_tokens": sum_tokens(tok),
        "input_tokens": tok["input_tokens"],
        "output_tokens": tok["output_tokens"],
        "cache_read_tokens": tok["cache_read_tokens"],
        "cache_creation_tokens": tok["cache_creation_tokens"],
        "model": model,
        "turn_type": t.turn_type or "text",
        "tools_used": t.tools_used or [],
        "skill_invoked": t.skill_invoked,
        "assistant_preview": (t.assistant_preview or "")[:300],
        "repo": t.repo,
        "branch": t.branch or "",
        "timestamp": t.user_prompt_ts or t.timestamp or "",
        "author": t.author_email or "",
    }


# ---------------------------------------------------------------------------
# aggregate_overview — extracted sub-functions
# ---------------------------------------------------------------------------

def _overview_cost_metrics(db: Session, days: Optional[int]) -> dict:
    """Return cost, tokens, prompts, model distribution from model-grouped turns."""
    model_token_q = _apply_turn_filters(
        db.query(
            PulseTurn.model,
            func.sum(PulseTurn.input_tokens).label("input_tokens"),
            func.sum(PulseTurn.output_tokens).label("output_tokens"),
            func.sum(PulseTurn.cache_read_tokens).label("cache_read_tokens"),
            func.sum(PulseTurn.cache_creation_tokens).label("cache_creation_tokens"),
            func.count(PulseTurn.id).label("cnt"),
        ).group_by(PulseTurn.model),
        days,
    )
    model_groups = model_token_q.all()
    total_cost, total_tokens, total_cache_saved = _cost_from_model_groups(model_groups)
    total_prompts = sum(r.cnt for r in model_groups)
    model_distribution = {(r.model or "unknown"): r.cnt for r in model_groups}
    return {
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "total_cache_saved": total_cache_saved,
        "total_prompts": total_prompts,
        "model_distribution": model_distribution,
    }


def _overview_line_counts(db: Session, days: Optional[int]) -> dict:
    """Return AI vs human line totals from commits."""
    commit_agg = _apply_commit_filters(
        db.query(
            func.coalesce(func.sum(PulseCommit.ai_lines), 0),
            func.coalesce(func.sum(PulseCommit.human_lines), 0),
        ),
        days,
    ).one()
    ai = int(commit_agg[0])
    human = int(commit_agg[1])
    total = ai + human
    return {
        "total_ai_lines": ai,
        "total_human_lines": human,
        "ai_percentage": round(ai / total * 100, 1) if total else 0,
    }


def _overview_weekly(db: Session, days: Optional[int]) -> list[dict]:
    """Build weekly trend data using SQL GROUP BY (week_bucket, model).

    Groups at the DB level to avoid loading all rows into Python.
    Uses floor(unix_ts / 604800) as a portable week bucket (works on MySQL and SQLite).
    Picks min(unix_ts) per bucket to derive the ISO week key in Python.
    """
    week_bucket = func.cast(PulseTurn.unix_ts / _SECONDS_PER_WEEK, Integer)
    weekly_turn_q = _apply_turn_filters(
        db.query(
            week_bucket.label("wk_bucket"),
            func.min(PulseTurn.unix_ts).label("min_ts"),
            PulseTurn.model,
            func.sum(PulseTurn.input_tokens).label("input_tokens"),
            func.sum(PulseTurn.output_tokens).label("output_tokens"),
            func.sum(PulseTurn.cache_read_tokens).label("cache_read_tokens"),
            func.sum(PulseTurn.cache_creation_tokens).label("cache_creation_tokens"),
            func.count(PulseTurn.id).label("cnt"),
        ).filter(PulseTurn.unix_ts.isnot(None))
         .group_by(week_bucket, PulseTurn.model),
        days,
    )

    weekly: dict[str, Any] = {}
    for row in weekly_turn_q.all():
        wk = _safe_week_key(row.min_ts)
        if wk is None:
            continue
        if wk not in weekly:
            weekly[wk] = {"cost": 0.0, "prompts": 0, "ai_lines": 0, "tokens": 0}
        tok = _tok_dict(row)
        weekly[wk]["cost"] += calc_cost(tok, row.model or "")
        weekly[wk]["prompts"] += row.cnt
        weekly[wk]["tokens"] += sum_tokens(tok)

    # Add AI lines per week from commits (also grouped at DB level)
    commit_week_bucket = func.cast(PulseCommit.unix_ts / _SECONDS_PER_WEEK, Integer)
    weekly_commit_q = _apply_commit_filters(
        db.query(
            commit_week_bucket.label("wk_bucket"),
            func.min(PulseCommit.unix_ts).label("min_ts"),
            func.coalesce(func.sum(PulseCommit.ai_lines), 0).label("ai_lines"),
        ).filter(PulseCommit.unix_ts.isnot(None), PulseCommit.ai_lines > 0)
         .group_by(commit_week_bucket),
        days,
    )
    for row in weekly_commit_q.all():
        wk = _safe_week_key(row.min_ts)
        if wk is None:
            continue
        if wk not in weekly:
            weekly[wk] = {"cost": 0.0, "prompts": 0, "ai_lines": 0, "tokens": 0}
        weekly[wk]["ai_lines"] += int(row.ai_lines or 0)

    return [{"week": wk, **v} for wk, v in sorted(weekly.items())]


def aggregate_overview(db: Session, days: Optional[int]) -> dict:
    cost_metrics = _overview_cost_metrics(db, days)
    line_counts = _overview_line_counts(db, days)

    turn_type_q = _apply_turn_filters(
        db.query(PulseTurn.turn_type, func.count(PulseTurn.id)).group_by(PulseTurn.turn_type),
        days,
    )
    turn_type_dist = {(tt or "text"): cnt for tt, cnt in turn_type_q.all()}

    repo_count_q = _apply_turn_filters(
        db.query(func.count(func.distinct(PulseTurn.repo))),
        days,
    )
    repo_count = repo_count_q.scalar() or 0

    weekly_list = _overview_weekly(db, days)

    return {
        "total_cost_usd": round(cost_metrics["total_cost"], 2),
        "total_tokens": cost_metrics["total_tokens"],
        "total_prompts": cost_metrics["total_prompts"],
        "total_ai_lines": line_counts["total_ai_lines"],
        "total_human_lines": line_counts["total_human_lines"],
        "ai_percentage": line_counts["ai_percentage"],
        "cache_saved_usd": round(max(0, cost_metrics["total_cache_saved"]), 2),
        "repo_count": repo_count,
        "model_distribution": cost_metrics["model_distribution"],
        "turn_type_dist": turn_type_dist,
        "weekly": weekly_list[-_MAX_WEEKLY_BUCKETS:],
    }


# ---------------------------------------------------------------------------
# aggregate_repos — SQL-level sort and pagination
# ---------------------------------------------------------------------------

def _repos_enrich_contributors(db: Session, page: list[dict], days: Optional[int]) -> None:
    """Populate contributor_list for repos on the current page."""
    page_repos = [r["repo"] for r in page]
    if not page_repos:
        return
    contrib_detail_q = _apply_turn_filters(
        db.query(
            PulseTurn.repo,
            PulseTurn.author_email,
            PulseTurn.model,
            func.count(PulseTurn.id).label("prompts"),
            func.sum(PulseTurn.input_tokens).label("input_tokens"),
            func.sum(PulseTurn.output_tokens).label("output_tokens"),
            func.sum(PulseTurn.cache_read_tokens).label("cache_read_tokens"),
            func.sum(PulseTurn.cache_creation_tokens).label("cache_creation_tokens"),
        ).filter(PulseTurn.repo.in_(page_repos))
         .group_by(PulseTurn.repo, PulseTurn.author_email, PulseTurn.model),
        days,
    )
    by_repo_author: dict[str, dict[str, dict]] = {}
    for r in contrib_detail_q.all():
        if not r.author_email:
            continue
        key = r.repo
        if key not in by_repo_author:
            by_repo_author[key] = {}
        a = r.author_email
        if a not in by_repo_author[key]:
            by_repo_author[key][a] = {"email": a, "prompts": 0, "tokens": 0, "cost_usd": 0.0}
        tok = _tok_dict(r)
        by_repo_author[key][a]["prompts"] += r.prompts
        by_repo_author[key][a]["tokens"] += sum_tokens(tok)
        by_repo_author[key][a]["cost_usd"] += calc_cost(tok, r.model or "")

    for repo_result in page:
        authors = by_repo_author.get(repo_result["repo"], {})
        cl = sorted(authors.values(), key=lambda x: -x["cost_usd"])
        for c in cl:
            c["cost_usd"] = round(c["cost_usd"], 2)
        repo_result["contributor_list"] = cl


def aggregate_repos(db: Session, sort: str, days: Optional[int], limit: int, offset: int) -> dict:
    # --- Total: distinct repos across both tables (consistent regardless of sort) ---
    turn_repos = _apply_turn_filters(db.query(PulseTurn.repo), days)
    commit_repos = _apply_commit_filters(db.query(PulseCommit.repo), days)
    all_repos_sub = union(turn_repos, commit_repos).subquery()
    total = db.query(func.count()).select_from(all_repos_sub).scalar() or 0

    # --- SQL sort + pagination to get the page of repo names ---
    cost_proxy = (
        func.sum(PulseTurn.input_tokens) * 3
        + func.sum(PulseTurn.output_tokens) * 15
        + func.sum(PulseTurn.cache_read_tokens)
        + func.sum(PulseTurn.cache_creation_tokens) * 4
    )

    if sort in ("ai_pct", "ai_lines"):
        # Sort from commits table
        if sort == "ai_pct":
            order_expr = desc(
                func.sum(PulseCommit.ai_lines) * 100.0
                / func.nullif(func.sum(PulseCommit.ai_lines) + func.sum(PulseCommit.human_lines), 0)
            )
        else:
            order_expr = desc(func.coalesce(func.sum(PulseCommit.ai_lines), 0))

        page_q = _apply_commit_filters(
            db.query(PulseCommit.repo)
            .group_by(PulseCommit.repo)
            .order_by(order_expr),
            days,
        ).offset(offset).limit(limit)
    else:
        # Sort from turns table (cost, tokens, prompts)
        turn_sort_map = {
            "tokens": desc(
                func.sum(PulseTurn.input_tokens) + func.sum(PulseTurn.output_tokens)
                + func.sum(PulseTurn.cache_read_tokens) + func.sum(PulseTurn.cache_creation_tokens)
            ),
            "prompts": desc(func.count(PulseTurn.id)),
        }
        order_expr = turn_sort_map.get(sort, desc(cost_proxy))

        page_q = _apply_turn_filters(
            db.query(PulseTurn.repo)
            .group_by(PulseTurn.repo)
            .order_by(order_expr),
            days,
        ).offset(offset).limit(limit)

    page_repo_names = [r.repo for r in page_q.all()]

    if not page_repo_names:
        return {"repos": [], "total": total, "offset": offset, "limit": limit}

    # --- Accurate cost/tokens for page repos only (GROUP BY repo, model) ---
    turn_q = _apply_turn_filters(
        db.query(
            PulseTurn.repo,
            PulseTurn.model,
            func.count(PulseTurn.id).label("total_prompts"),
            func.sum(PulseTurn.input_tokens).label("input_tokens"),
            func.sum(PulseTurn.output_tokens).label("output_tokens"),
            func.sum(PulseTurn.cache_read_tokens).label("cache_read_tokens"),
            func.sum(PulseTurn.cache_creation_tokens).label("cache_creation_tokens"),
            func.sum(case(
                (PulseTurn.turn_type.in_(["write", "mixed"]), 1),
                else_=0,
            )).label("write_prompts"),
        ).filter(PulseTurn.repo.in_(page_repo_names))
         .group_by(PulseTurn.repo, PulseTurn.model),
        days,
    )
    repo_data: dict[str, dict] = {}
    for r in turn_q.all():
        if r.repo not in repo_data:
            repo_data[r.repo] = {
                "total_prompts": 0, "total_tokens": 0, "total_cost": 0.0,
                "write_prompts": 0, "read_prompts": 0, "models": set(),
            }
        d = repo_data[r.repo]
        tok = _tok_dict(r)
        d["total_prompts"] += r.total_prompts
        d["total_tokens"] += sum_tokens(tok)
        d["total_cost"] += calc_cost(tok, r.model or "")
        d["write_prompts"] += r.write_prompts or 0
        d["read_prompts"] += (r.total_prompts - (r.write_prompts or 0))
        if r.model:
            d["models"].add(r.model)

    # --- Contributor counts for page repos only ---
    contrib_q = _apply_turn_filters(
        db.query(
            PulseTurn.repo,
            func.count(func.distinct(PulseTurn.author_email)).label("contributors"),
        ).filter(PulseTurn.repo.in_(page_repo_names))
         .group_by(PulseTurn.repo),
        days,
    )
    contrib_map = {r.repo: r.contributors for r in contrib_q.all()}

    # --- Commit data for page repos only ---
    commit_q = _apply_commit_filters(
        db.query(
            PulseCommit.repo,
            func.count(PulseCommit.id).label("commits"),
            func.coalesce(func.sum(PulseCommit.ai_lines), 0).label("ai_lines"),
            func.coalesce(func.sum(PulseCommit.human_lines), 0).label("human_lines"),
        ).filter(PulseCommit.repo.in_(page_repo_names))
         .group_by(PulseCommit.repo),
        days,
    )
    commit_map = {r.repo: r for r in commit_q.all()}

    # --- Build results in SQL-determined order ---
    results = []
    for rank_idx, repo_name in enumerate(page_repo_names, start=offset + 1):
        td = repo_data.get(repo_name) or {
            "total_prompts": 0, "total_tokens": 0, "total_cost": 0.0,
            "write_prompts": 0, "read_prompts": 0, "models": set(),
        }
        cd = commit_map.get(repo_name)
        ai_lines = int(cd.ai_lines) if cd else 0
        hum_lines = int(cd.human_lines) if cd else 0
        total_l = ai_lines + hum_lines

        results.append({
            "rank": rank_idx,
            "repo": repo_name,
            "total_prompts": td["total_prompts"],
            "write_prompts": td["write_prompts"],
            "read_prompts": td["read_prompts"],
            "total_cost_usd": round(td["total_cost"], 2),
            "total_tokens": td["total_tokens"],
            "ai_lines": ai_lines,
            "human_lines": hum_lines,
            "ai_percentage": round(ai_lines / total_l * 100, 1) if total_l else 0,
            "commits": cd.commits if cd else 0,
            "contributors": contrib_map.get(repo_name, 0),
            "contributor_list": [],
            "models": sorted(td.get("models", set())),
        })

    _repos_enrich_contributors(db, results, days)

    return {"repos": results, "total": total, "offset": offset, "limit": limit}


# ---------------------------------------------------------------------------
# aggregate_commits
# ---------------------------------------------------------------------------

def aggregate_commits(db: Session, sort: str, days: Optional[int], repo: Optional[str], limit: int, offset: int) -> dict:
    count_q = _apply_commit_filters(db.query(func.count(PulseCommit.id)), days, repo=repo)
    total = count_q.scalar() or 0

    sort_col_map = {
        "tokens": desc(PulseCommit.input_tokens + PulseCommit.output_tokens + PulseCommit.cache_read_tokens + PulseCommit.cache_creation_tokens),
        "ai_lines": desc(PulseCommit.ai_lines),
        "ai_pct": desc(PulseCommit.ai_percentage),
        "prompts": desc(PulseCommit.prompt_count),
        "date": desc(PulseCommit.unix_ts),
    }
    order = sort_col_map.get(sort, desc(PulseCommit.estimated_cost_usd))

    commits_q = _apply_commit_filters(db.query(PulseCommit), days, repo=repo)
    commits = (
        commits_q
        .order_by(order)
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Manually fetch prompts for all commits
    commit_ids = [c.id for c in commits]
    prompts_by_commit: dict[str, list[PulseCommitPrompt]] = {}
    if commit_ids:
        all_prompts = db.query(PulseCommitPrompt).filter(PulseCommitPrompt.commit_id.in_(commit_ids)).all()
        for cp in all_prompts:
            prompts_by_commit.setdefault(cp.commit_id, []).append(cp)

    # Manually fetch turns for prompts
    turn_ids = [cp.turn_id for cp in all_prompts if cp.turn_id] if commit_ids else []
    turns_by_id: dict[str, PulseTurn] = {}
    if turn_ids:
        for t in db.query(PulseTurn).filter(PulseTurn.id.in_(turn_ids)).all():
            turns_by_id[t.id] = t

    ts_set: set[str] = set()
    for c in commits:
        for cp in prompts_by_commit.get(c.id, []):
            if cp.turn_id is None and cp.timestamp:
                ts_set.add(cp.timestamp)
                if len(cp.timestamp) > 19:
                    ts_set.add(cp.timestamp[:19])

    fallback_by_ts: dict[str, PulseTurn] = {}
    if ts_set:
        for t in db.query(PulseTurn).filter(PulseTurn.user_prompt_ts.in_(ts_set)).all():
            if t.user_prompt_ts:
                fallback_by_ts[t.user_prompt_ts] = t
                if len(t.user_prompt_ts) > 19:
                    fallback_by_ts[t.user_prompt_ts[:19]] = t
        unmatched_ts = ts_set - set(fallback_by_ts.keys())
        if unmatched_ts:
            for t in db.query(PulseTurn).filter(PulseTurn.assistant_turn_ts.in_(unmatched_ts)).all():
                if t.assistant_turn_ts:
                    fallback_by_ts[t.assistant_turn_ts] = t
                    if len(t.assistant_turn_ts) > 19:
                        fallback_by_ts[t.assistant_turn_ts[:19]] = t

    all_commits = []
    for rank_idx, c in enumerate(commits, start=offset + 1):
        tok_total = int(c.input_tokens or 0) + int(c.output_tokens or 0) + int(c.cache_read_tokens or 0) + int(c.cache_creation_tokens or 0)

        enriched_prompts = []
        for cp in prompts_by_commit.get(c.id, []):
            turn = turns_by_id.get(cp.turn_id) if cp.turn_id else None
            if turn:
                full = turn
            elif cp.timestamp:
                cp_ts = cp.timestamp
                full = fallback_by_ts.get(cp_ts) or (fallback_by_ts.get(cp_ts[:19]) if len(cp_ts) > 19 else None)
            else:
                full = None

            if full:
                t_tok = _tok_dict(full)
            else:
                t_tok = {}

            enriched_prompts.append({
                "prompt": cp.prompt or "",
                "model": cp.model or (full.model if full else "") or "",
                "turn_type": cp.turn_type or (full.turn_type if full else "") or "",
                "cost_usd": cp.cost_usd if cp.cost_usd is not None else (round(calc_cost(t_tok, full.model) if full else 0, 6)),
                "timestamp": cp.timestamp or "",
                "author": (full.author_email if full else "") or "",
                "branch": (full.branch if full else "") or "",
                "tools_used": (full.tools_used if full else []) or [],
                "skill_invoked": full.skill_invoked if full else None,
                "assistant_preview": (full.assistant_preview or "") if full else "",
                "total_tokens": sum_tokens(t_tok) if full else 0,
                "input_tokens": t_tok.get("input_tokens", 0),
                "output_tokens": t_tok.get("output_tokens", 0),
                "cache_read_tokens": t_tok.get("cache_read_tokens", 0),
                "cache_creation_tokens": t_tok.get("cache_creation_tokens", 0),
            })

        all_commits.append({
            "rank": rank_idx,
            "commit_sha": (c.commit_hash or "")[:10],
            "commit_message": c.commit_message or "",
            "commit_author": c.commit_author or "",
            "author_email": c.author_email or "",
            "repo": c.repo,
            "branch": c.branch or "",
            "timestamp": c.timestamp or "",
            "total_tokens": tok_total,
            "input_tokens": int(c.input_tokens or 0),
            "output_tokens": int(c.output_tokens or 0),
            "cache_read": int(c.cache_read_tokens or 0),
            "cache_creation": int(c.cache_creation_tokens or 0),
            "cost_usd": round(c.estimated_cost_usd or 0, 4),
            "ai_lines": int(c.ai_lines or 0),
            "human_lines": int(c.human_lines or 0),
            "ai_percentage": float(c.ai_percentage or 0),
            "prompt_count": int(c.prompt_count or 0),
            "prompts": enriched_prompts,
        })

    return {"commits": all_commits, "total": total, "offset": offset, "limit": limit}


# ---------------------------------------------------------------------------
# aggregate_prompts
# ---------------------------------------------------------------------------

def aggregate_prompts(db: Session, sort: str, days: Optional[int], repo: Optional[str], email: Optional[str], limit: int, offset: int = 0) -> dict:
    base_q = _apply_turn_filters(db.query(PulseTurn), days, repo=repo, email=email)
    base_q = base_q.filter(
        PulseTurn.user_prompt.isnot(None),
        func.trim(PulseTurn.user_prompt) != "",
    )

    total = base_q.count()

    cost_proxy = (
        PulseTurn.input_tokens * 3
        + PulseTurn.output_tokens * 15
        + PulseTurn.cache_read_tokens
        + PulseTurn.cache_creation_tokens * 4
    )
    sort_col_map = {
        "cost": desc(cost_proxy),
        "tokens": desc(PulseTurn.input_tokens + PulseTurn.output_tokens + PulseTurn.cache_read_tokens + PulseTurn.cache_creation_tokens),
        "output": desc(PulseTurn.output_tokens),
        "newest": desc(PulseTurn.unix_ts),
    }
    order = sort_col_map.get(sort, sort_col_map["cost"])

    turns = base_q.order_by(order).offset(offset).limit(limit).all()

    results = []
    for rank_idx, t in enumerate(turns, start=offset + 1):
        d = _turn_to_prompt_dict(t)
        d["rank"] = rank_idx
        d["prompt_id"] = t.prompt_id or ""
        results.append(d)

    return {"prompts": results, "total": total, "offset": offset, "limit": limit}


# ---------------------------------------------------------------------------
# aggregate_people
# ---------------------------------------------------------------------------

def aggregate_people(db: Session, sort: str, days: Optional[int], repo: Optional[str], limit: int = 20, offset: int = 0) -> dict:
    # --- Total: distinct people across both tables (consistent regardless of sort) ---
    turn_emails = _apply_turn_filters(db.query(PulseTurn.author_email), days, repo=repo)
    commit_emails = _apply_commit_filters(db.query(PulseCommit.author_email), days, repo=repo)
    all_emails_sub = union(turn_emails, commit_emails).subquery()
    total = db.query(func.count()).select_from(all_emails_sub).scalar() or 0

    # --- SQL sort + pagination to get page of people ---
    cost_proxy = (
        func.sum(PulseTurn.input_tokens) * 3
        + func.sum(PulseTurn.output_tokens) * 15
        + func.sum(PulseTurn.cache_read_tokens)
        + func.sum(PulseTurn.cache_creation_tokens) * 4
    )

    if sort == "lines":
        # Sort by ai_lines from commits
        page_q = _apply_commit_filters(
            db.query(PulseCommit.author_email)
            .group_by(PulseCommit.author_email)
            .order_by(desc(func.coalesce(func.sum(PulseCommit.ai_lines), 0))),
            days, repo=repo,
        ).offset(offset).limit(limit)
    else:
        # Sort by turn-derived metrics (cost, tokens, prompts)
        turn_sort_map = {
            "tokens": desc(
                func.sum(PulseTurn.input_tokens) + func.sum(PulseTurn.output_tokens)
                + func.sum(PulseTurn.cache_read_tokens) + func.sum(PulseTurn.cache_creation_tokens)
            ),
            "prompts": desc(func.count(PulseTurn.id)),
        }
        order_expr = turn_sort_map.get(sort, desc(cost_proxy))

        page_q = _apply_turn_filters(
            db.query(PulseTurn.author_email)
            .group_by(PulseTurn.author_email)
            .order_by(order_expr),
            days, repo=repo,
        ).offset(offset).limit(limit)

    page_emails = [r.author_email or "unknown" for r in page_q.all()]

    if not page_emails:
        return {"people": [], "total": total, "offset": offset, "limit": limit}

    # --- Accurate turn data for page people only (GROUP BY email, model) ---
    turn_q = _apply_turn_filters(
        db.query(
            PulseTurn.author_email,
            PulseTurn.model,
            func.count(PulseTurn.id).label("total_prompts"),
            func.sum(PulseTurn.input_tokens).label("input_tokens"),
            func.sum(PulseTurn.output_tokens).label("output_tokens"),
            func.sum(PulseTurn.cache_read_tokens).label("cache_read_tokens"),
            func.sum(PulseTurn.cache_creation_tokens).label("cache_creation_tokens"),
            func.sum(case(
                (PulseTurn.turn_type.in_(["write", "mixed"]), 1),
                else_=0,
            )).label("write_prompts"),
        ).filter(PulseTurn.author_email.in_(page_emails))
         .group_by(PulseTurn.author_email, PulseTurn.model),
        days, repo=repo,
    )

    by_email: dict[str, dict] = {}
    for r in turn_q.all():
        author = r.author_email or "unknown"
        if author not in by_email:
            by_email[author] = {
                "total_cost": 0.0, "total_tokens": 0, "total_prompts": 0,
                "write_prompts": 0, "read_prompts": 0,
            }
        tok = _tok_dict(r)
        d = by_email[author]
        d["total_cost"] += calc_cost(tok, r.model or "")
        d["total_tokens"] += sum_tokens(tok)
        d["total_prompts"] += r.total_prompts
        d["write_prompts"] += r.write_prompts or 0
        d["read_prompts"] += (r.total_prompts - (r.write_prompts or 0))

    # --- Repos per person (page only) ---
    repo_q = _apply_turn_filters(
        db.query(PulseTurn.author_email, PulseTurn.repo)
        .filter(PulseTurn.author_email.in_(page_emails))
        .distinct(),
        days, repo=repo,
    )
    repos_by_email: dict[str, set] = {}
    for r in repo_q.all():
        author = r.author_email or "unknown"
        repos_by_email.setdefault(author, set()).add(r.repo)

    # --- Commit data per person (page only) ---
    commit_q = _apply_commit_filters(
        db.query(
            PulseCommit.author_email,
            func.count(PulseCommit.id).label("commits"),
            func.coalesce(func.sum(PulseCommit.ai_lines), 0).label("ai_lines"),
        ).filter(PulseCommit.author_email.in_(page_emails))
         .group_by(PulseCommit.author_email),
        days, repo=repo,
    )
    commit_by_email: dict[str, dict] = {}
    for r in commit_q.all():
        author = r.author_email or "unknown"
        commit_by_email[author] = {"commits": r.commits, "ai_lines": int(r.ai_lines)}

    # --- Build results in SQL-determined order ---
    results = []
    for rank_idx, email_addr in enumerate(page_emails, start=offset + 1):
        d = by_email.get(email_addr) or {
            "total_cost": 0.0, "total_tokens": 0, "total_prompts": 0,
            "write_prompts": 0, "read_prompts": 0,
        }
        cd = commit_by_email.get(email_addr, {"commits": 0, "ai_lines": 0})
        results.append({
            "rank": rank_idx,
            "email": email_addr,
            "total_cost_usd": round(d["total_cost"], 2),
            "total_tokens": d["total_tokens"],
            "total_prompts": d["total_prompts"],
            "write_prompts": d["write_prompts"],
            "read_prompts": d["read_prompts"],
            "ai_lines": cd["ai_lines"],
            "commits": cd["commits"],
            "repos": sorted(repos_by_email.get(email_addr, set())),
            "top_prompts": [],
        })

    # --- Top prompts for page people (already bounded by LIMIT) ---
    if page_emails:
        cost_proxy_single = (
            PulseTurn.input_tokens * 3
            + PulseTurn.output_tokens * 15
            + PulseTurn.cache_read_tokens
            + PulseTurn.cache_creation_tokens * 4
        )
        prompts_q = _apply_turn_filters(
            db.query(PulseTurn).filter(
                PulseTurn.author_email.in_(page_emails),
                PulseTurn.user_prompt.isnot(None),
                PulseTurn.user_prompt != "",
            ),
            days, repo=repo,
        ).order_by(desc(cost_proxy_single)).limit(_TOP_PROMPTS_PER_PERSON * len(page_emails))

        prompts_by_email: dict[str, list] = {}
        for t in prompts_q.all():
            pd = _turn_to_prompt_dict(t)
            author = pd["author"]
            if author not in prompts_by_email:
                prompts_by_email[author] = []
            if len(prompts_by_email[author]) < _TOP_PROMPTS_PER_PERSON:
                prompts_by_email[author].append(pd)

        for person in results:
            person["top_prompts"] = prompts_by_email.get(person["email"], [])

    return {"people": results, "total": total, "offset": offset, "limit": limit}
