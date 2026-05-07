"""
pulse_ingest_service.py — Handles data ingestion for Pulse (AI usage tracking).

TODO: Migrate to BaseService pattern (class PulseIngestService(BaseService))
      to align with codebase conventions — structured logging, health checks,
      lifecycle management, and session abstraction via Repository pattern.
"""

import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.pulse_turn import PulseTurn
from src.models.pulse_edit import PulseEdit
from src.models.pulse_commit import PulseCommit
from src.models.pulse_commit_prompt import PulseCommitPrompt

logger = logging.getLogger(__name__)


def _update_turn_fields(existing: PulseTurn, record: dict, tok: dict) -> None:
    """Apply token/cost/metadata fields from *record* onto an existing row."""
    existing.input_tokens = tok.get("input_tokens", 0)
    existing.output_tokens = tok.get("output_tokens", 0)
    existing.cache_read_tokens = tok.get("cache_read_tokens", 0)
    existing.cache_creation_tokens = tok.get("cache_creation_tokens", 0)
    existing.cost_usd = record.get("cost_usd")
    existing.assistant_preview = record.get("assistant_preview")
    existing.tools_used = record.get("tools_used", [])
    existing.turn_type = record.get("turn_type")


def ingest_turn(db: Session, record: dict) -> None:
    """Insert a turn record, skipping duplicates.

    If prompt_id already exists and the incoming record has more output_tokens
    (fresher snapshot), update the token/cost fields.
    """
    try:
        author_email = record.get("author_email")
        if author_email:
            record["author_email"] = author_email.strip().lower()

        prompt_id = record.get("prompt_id")
        if prompt_id:
            existing = db.query(PulseTurn).filter(PulseTurn.prompt_id == prompt_id).first()
            if existing:
                new_out = record.get("tokens", {}).get("output_tokens", 0)
                if new_out > (existing.output_tokens or 0):
                    tok = record.get("tokens", {})
                    _update_turn_fields(existing, record, tok)
                    db.commit()
                    logger.debug("Updated turn %s: output_tokens -> %s", prompt_id, new_out)
                else:
                    logger.debug("Skipping stale duplicate turn: %s", prompt_id)
                return
        else:
            # Secondary dedup when prompt_id is absent: match by timestamp + author + repo
            user_prompt_ts = record.get("user_prompt_ts")
            author_email = record.get("author_email")
            repo = record.get("repo", "unknown")
            if user_prompt_ts and author_email:
                existing = db.query(PulseTurn).filter(
                    PulseTurn.user_prompt_ts == user_prompt_ts,
                    PulseTurn.author_email == author_email,
                    PulseTurn.repo == repo,
                ).first()
                if existing:
                    logger.debug("Skipping duplicate turn (ts+author match): %s / %s", user_prompt_ts, author_email)
                    return

        tok = record.get("tokens", {})
        turn = PulseTurn(
            prompt_id=prompt_id,
            session_id=record.get("session_id"),
            repo=record.get("repo", "unknown"),
            branch=record.get("branch"),
            author_email=record.get("author_email"),
            user_prompt=record.get("user_prompt"),
            user_prompt_ts=record.get("user_prompt_ts"),
            assistant_turn_ts=record.get("assistant_turn_ts"),
            timestamp=record.get("timestamp"),
            unix_ts=record.get("unix_ts"),
            model=record.get("model"),
            turn_type=record.get("turn_type"),
            tools_used=record.get("tools_used", []),
            skill_invoked=record.get("skill_invoked"),
            cost_usd=record.get("cost_usd"),
            assistant_preview=record.get("assistant_preview"),
            input_tokens=tok.get("input_tokens", 0),
            output_tokens=tok.get("output_tokens", 0),
            cache_read_tokens=tok.get("cache_read_tokens", 0),
            cache_creation_tokens=tok.get("cache_creation_tokens", 0),
        )
        db.add(turn)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if prompt_id:
                existing = db.query(PulseTurn).filter(PulseTurn.prompt_id == prompt_id).first()
                if existing:
                    new_out = tok.get("output_tokens", 0)
                    if new_out > (existing.output_tokens or 0):
                        _update_turn_fields(existing, record, tok)
                        db.commit()
                    logger.debug("Handled duplicate turn via IntegrityError: %s", prompt_id)
            return
    except Exception:
        db.rollback()
        raise


def ingest_edit(db: Session, record: dict) -> None:
    """Insert an edit record. No deduplication — every edit is a new row."""
    try:
        author_email = record.get("author_email")
        if author_email:
            record["author_email"] = author_email.strip().lower()

        tok = record.get("tokens", {})
        edit = PulseEdit(
            prompt_id=record.get("prompt_id"),
            session_id=record.get("session_id"),
            repo=record.get("repo", "unknown"),
            branch=record.get("branch"),
            author_email=record.get("author_email"),
            timestamp=record.get("timestamp"),
            unix_ts=record.get("unix_ts"),
            tool_category=record.get("tool_category"),
            tool_name=record.get("tool_name"),
            file_edited=record.get("file_edited"),
            files_changed=record.get("files_changed", []),
            files_new=record.get("files_new", []),
            lines_added_by_ai=record.get("lines_added_by_ai", 0),
            lines_removed_by_ai=record.get("lines_removed_by_ai", 0),
            diff_stats=record.get("diff_stats"),
            model=record.get("model"),
            prompt=record.get("prompt"),
            skill_invoked=record.get("skill_invoked"),
            assistant_preview=record.get("assistant_preview"),
            input_tokens=tok.get("input_tokens", 0),
            output_tokens=tok.get("output_tokens", 0),
            cache_read_tokens=tok.get("cache_read_tokens", 0),
            cache_creation_tokens=tok.get("cache_creation_tokens", 0),
            session_cost_usd=record.get("session_cost_usd"),
        )
        db.add(edit)
        db.commit()
    except Exception:
        db.rollback()
        raise


def ingest_commit(db: Session, record: dict) -> None:
    """Insert a commit record with its prompts atomically, skipping duplicates."""
    commit_hash = record.get("commit_hash", "")
    if not commit_hash:
        logger.debug("Skipping commit with empty commit_hash")
        return

    try:
        author_email = record.get("author_email")
        if author_email:
            record["author_email"] = author_email.strip().lower()

        tok = record.get("tokens_used", {})
        attr = record.get("attribution", {})

        commit = PulseCommit(
            commit_hash=commit_hash,
            repo=record.get("repo", "unknown"),
            branch=record.get("branch"),
            author_email=record.get("author_email"),
            commit_author=record.get("commit_author"),
            commit_message=record.get("commit_message"),
            commit_timestamp=record.get("commit_timestamp"),
            timestamp=record.get("timestamp"),
            unix_ts=record.get("unix_ts"),
            files_changed=record.get("files_changed", 0),
            diff_summary=record.get("diff_summary"),
            prompt_count=record.get("prompt_count", 0),
            input_tokens=tok.get("input", 0),
            output_tokens=tok.get("output", 0),
            cache_read_tokens=tok.get("cache_read", 0),
            cache_creation_tokens=tok.get("cache_creation", 0),
            estimated_cost_usd=record.get("estimated_cost_usd", 0.0),
            total_lines_added=attr.get("total_lines_added", 0),
            ai_lines=attr.get("ai_lines", 0),
            human_lines=attr.get("human_lines", 0),
            ai_percentage=attr.get("ai_percentage", 0.0),
            file_attribution=record.get("file_attribution"),
        )
        db.add(commit)
        db.flush()

        # Resolve turn_ids in a single query
        prompts_used = record.get("prompts_used", [])
        ts_values = set()
        for p in prompts_used:
            ts = (p.get("timestamp") or "").strip()
            if ts:
                ts_values.add(ts)

        turn_by_ts: dict[str, str] = {}
        if ts_values:
            for t_id, t_ts in db.query(PulseTurn.id, PulseTurn.user_prompt_ts).filter(
                PulseTurn.user_prompt_ts.in_(ts_values)
            ).all():
                if t_ts:
                    turn_by_ts[t_ts.strip()] = t_id
            unmatched = ts_values - set(turn_by_ts.keys())
            if unmatched:
                for t_id, t_ts in db.query(PulseTurn.id, PulseTurn.assistant_turn_ts).filter(
                    PulseTurn.assistant_turn_ts.in_(unmatched)
                ).all():
                    if t_ts:
                        turn_by_ts[t_ts.strip()] = t_id

        for p in prompts_used:
            p_ts = (p.get("timestamp") or "").strip()
            cp = PulseCommitPrompt(
                commit_id=commit.id,
                turn_id=turn_by_ts.get(p_ts),
                prompt=p.get("prompt"),
                timestamp=p.get("timestamp"),
                model=p.get("model"),
                turn_type=p.get("turn_type"),
                cost_usd=p.get("cost_usd", 0.0),
                tools_used=p.get("tools_used", []),
                skill_invoked=p.get("skill_invoked"),
                assistant_preview=p.get("assistant_preview"),
            )
            db.add(cp)

        db.commit()
    except IntegrityError:
        db.rollback()
        logger.debug("Skipping duplicate commit: %s", commit_hash)
    except Exception:
        db.rollback()
        raise
