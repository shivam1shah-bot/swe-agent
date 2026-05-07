"""
Tests for pulse_aggregation_service.py.

Covers: overview aggregation, repos breakdown, prompts listing,
        people breakdown, days filter, empty DB edge cases.
"""

import time

from src.services.pulse_ingest_service import ingest_turn, ingest_commit
from src.services.pulse_aggregation_service import (
    aggregate_overview,
    aggregate_repos,
    aggregate_commits,
    aggregate_prompts,
    aggregate_people,
)
from .conftest import make_turn_record, make_commit_record


class TestAggregateOverview:

    def test_empty_db_returns_zeroed_totals(self, db):
        result = aggregate_overview(db, days=None)
        assert result["total_cost_usd"] == 0
        assert result["total_prompts"] == 0
        assert result["total_tokens"] == 0
        assert result["total_ai_lines"] == 0
        assert result["ai_percentage"] == 0
        assert result["repo_count"] == 0

    def test_single_turn_calculates_cost(self, db):
        ingest_turn(db, make_turn_record(
            model="claude-sonnet-4",
            tokens={"input_tokens": 1000, "output_tokens": 500,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0},
        ))
        result = aggregate_overview(db, days=None)
        assert result["total_prompts"] == 1
        assert result["total_cost_usd"] > 0
        assert result["total_tokens"] == 1500
        assert result["repo_count"] == 1

    def test_model_distribution_tracks_models(self, db):
        ingest_turn(db, make_turn_record(prompt_id="t1", model="claude-sonnet-4"))
        ingest_turn(db, make_turn_record(prompt_id="t2", model="claude-opus-4"))
        result = aggregate_overview(db, days=None)
        assert "claude-sonnet-4" in result["model_distribution"]
        assert "claude-opus-4" in result["model_distribution"]
        assert result["total_prompts"] == 2

    def test_commit_lines_aggregated(self, db):
        ingest_commit(db, make_commit_record())
        result = aggregate_overview(db, days=None)
        assert result["total_ai_lines"] == 40
        assert result["total_human_lines"] == 10
        assert result["ai_percentage"] == 80.0

    def test_days_filter_excludes_old_records(self, db):
        old_ts = time.time() - 86400 * 60  # 60 days ago
        ingest_turn(db, make_turn_record(prompt_id="old", unix_ts=old_ts))
        ingest_turn(db, make_turn_record(prompt_id="new", unix_ts=time.time()))
        result = aggregate_overview(db, days=7)
        assert result["total_prompts"] == 1

    def test_weekly_list_populated(self, db):
        ingest_turn(db, make_turn_record(unix_ts=time.time()))
        result = aggregate_overview(db, days=None)
        assert len(result["weekly"]) >= 1
        week = result["weekly"][0]
        assert "week" in week
        assert "cost" in week
        assert "prompts" in week
        assert week["prompts"] == 1


class TestAggregateRepos:

    def test_empty_db(self, db):
        result = aggregate_repos(db, sort="cost", days=None, limit=20, offset=0)
        assert result["repos"] == []
        assert result["total"] == 0

    def test_single_repo_returned(self, db):
        ingest_turn(db, make_turn_record(repo="my-repo"))
        result = aggregate_repos(db, sort="cost", days=None, limit=20, offset=0)
        assert result["total"] == 1
        assert result["repos"][0]["repo"] == "my-repo"
        assert result["repos"][0]["total_prompts"] == 1
        assert result["repos"][0]["rank"] == 1

    def test_sort_by_prompts(self, db):
        ingest_turn(db, make_turn_record(prompt_id="t1", repo="low"))
        ingest_turn(db, make_turn_record(prompt_id="t2", repo="high"))
        ingest_turn(db, make_turn_record(prompt_id="t3", repo="high"))
        result = aggregate_repos(db, sort="prompts", days=None, limit=20, offset=0)
        assert result["repos"][0]["repo"] == "high"
        assert result["repos"][0]["total_prompts"] == 2

    def test_pagination(self, db):
        ingest_turn(db, make_turn_record(prompt_id="t1", repo="repo-a"))
        ingest_turn(db, make_turn_record(prompt_id="t2", repo="repo-b"))
        ingest_turn(db, make_turn_record(prompt_id="t3", repo="repo-c"))
        result = aggregate_repos(db, sort="cost", days=None, limit=2, offset=0)
        assert len(result["repos"]) == 2
        assert result["total"] == 3

    def test_commit_data_merged(self, db):
        ingest_turn(db, make_turn_record(repo="repo-a"))
        ingest_commit(db, make_commit_record(repo="repo-a"))
        result = aggregate_repos(db, sort="cost", days=None, limit=20, offset=0)
        repo = result["repos"][0]
        assert repo["ai_lines"] == 40
        assert repo["commits"] == 1


    def test_sort_by_tokens(self, db):
        ingest_turn(db, make_turn_record(
            prompt_id="t1", repo="low-tok",
            tokens={"input_tokens": 10, "output_tokens": 5,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0},
        ))
        ingest_turn(db, make_turn_record(
            prompt_id="t2", repo="high-tok",
            tokens={"input_tokens": 50000, "output_tokens": 20000,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0},
        ))
        result = aggregate_repos(db, sort="tokens", days=None, limit=20, offset=0)
        assert result["repos"][0]["repo"] == "high-tok"

    def test_offset_beyond_total_returns_empty(self, db):
        ingest_turn(db, make_turn_record(repo="only-repo"))
        result = aggregate_repos(db, sort="cost", days=None, limit=20, offset=100)
        assert result["repos"] == []
        assert result["total"] == 1


class TestAggregateCommits:

    def test_empty_db(self, db):
        result = aggregate_commits(db, sort="cost", days=None, repo=None, limit=20, offset=0)
        assert result["commits"] == []
        assert result["total"] == 0

    def test_commit_returned_with_prompts(self, db):
        ingest_turn(db, make_turn_record())
        ingest_commit(db, make_commit_record())
        result = aggregate_commits(db, sort="cost", days=None, repo=None, limit=20, offset=0)
        assert result["total"] == 1
        commit = result["commits"][0]
        assert commit["commit_sha"] == "abc123def4"
        assert commit["ai_lines"] == 40
        assert len(commit["prompts"]) == 1

    def test_repo_filter(self, db):
        ingest_commit(db, make_commit_record(commit_hash="hash1", repo="repo-a"))
        ingest_commit(db, make_commit_record(commit_hash="hash2", repo="repo-b"))
        result = aggregate_commits(db, sort="cost", days=None, repo="repo-a", limit=20, offset=0)
        assert result["total"] == 1
        assert result["commits"][0]["repo"] == "repo-a"

    def test_sort_by_date(self, db):
        ingest_commit(db, make_commit_record(commit_hash="old", unix_ts=1000000.0))
        ingest_commit(db, make_commit_record(commit_hash="new", unix_ts=9999999.0))
        result = aggregate_commits(db, sort="date", days=None, repo=None, limit=20, offset=0)
        assert result["commits"][0]["commit_sha"] == "new"[:10]

    def test_commit_pagination_offset(self, db):
        ingest_commit(db, make_commit_record(commit_hash="c1"))
        ingest_commit(db, make_commit_record(commit_hash="c2"))
        result = aggregate_commits(db, sort="cost", days=None, repo=None, limit=1, offset=1)
        assert len(result["commits"]) == 1
        assert result["total"] == 2

    def test_assistant_turn_ts_fallback(self, db):
        """When turn_id is NULL, commit prompts fall back to timestamp matching via assistant_turn_ts."""
        ingest_turn(db, make_turn_record(
            prompt_id="t-fallback",
            user_prompt_ts="2026-03-10T10:00:00Z",
            assistant_turn_ts="2026-03-10T10:00:05Z",
            user_prompt="fallback prompt",
        ))
        ingest_commit(db, make_commit_record(
            commit_hash="fb-hash",
            prompts_used=[{
                "prompt": "fallback prompt",
                "timestamp": "2026-03-10T10:00:05Z",
                "model": "claude-sonnet-4-6",
                "turn_type": "write",
                "cost_usd": 0.005,
                "tools_used": ["Edit"],
                "skill_invoked": None,
                "assistant_preview": "Sure...",
            }],
        ))
        result = aggregate_commits(db, sort="cost", days=None, repo=None, limit=20, offset=0)
        commit = result["commits"][0]
        assert len(commit["prompts"]) == 1
        assert commit["prompts"][0]["author"] == "alice@company.com"


class TestAggregatePrompts:

    def test_empty_db(self, db):
        result = aggregate_prompts(db, sort="cost", days=None, repo=None, email=None, limit=20, offset=0)
        assert result["prompts"] == []
        assert result["total"] == 0

    def test_prompts_returned(self, db):
        ingest_turn(db, make_turn_record(user_prompt="write a function"))
        result = aggregate_prompts(db, sort="cost", days=None, repo=None, email=None, limit=20, offset=0)
        assert result["total"] == 1
        assert result["prompts"][0]["prompt"] == "write a function"

    def test_empty_prompts_excluded(self, db):
        ingest_turn(db, make_turn_record(prompt_id="t1", user_prompt=""))
        ingest_turn(db, make_turn_record(prompt_id="t2", user_prompt="real prompt"))
        result = aggregate_prompts(db, sort="cost", days=None, repo=None, email=None, limit=20, offset=0)
        assert result["total"] == 1

    def test_email_filter(self, db):
        ingest_turn(db, make_turn_record(prompt_id="t1", author_email="alice@co.com"))
        ingest_turn(db, make_turn_record(prompt_id="t2", author_email="bob@co.com"))
        result = aggregate_prompts(db, sort="cost", days=None, repo=None, email="alice@co.com", limit=20, offset=0)
        assert result["total"] == 1
        assert result["prompts"][0]["author"] == "alice@co.com"


class TestAggregatePeople:

    def test_empty_db(self, db):
        result = aggregate_people(db, sort="cost", days=None, repo=None, limit=20, offset=0)
        assert result["people"] == []
        assert result["total"] == 0

    def test_single_person(self, db):
        ingest_turn(db, make_turn_record(author_email="alice@co.com"))
        result = aggregate_people(db, sort="cost", days=None, repo=None, limit=20, offset=0)
        assert result["total"] == 1
        person = result["people"][0]
        assert person["email"] == "alice@co.com"
        assert person["total_prompts"] == 1
        assert person["rank"] == 1

    def test_top_prompts_limited_to_20(self, db):
        for i in range(25):
            ingest_turn(db, make_turn_record(
                prompt_id=f"t{i}",
                author_email="alice@co.com",
                user_prompt=f"prompt number {i}",
            ))
        result = aggregate_people(db, sort="cost", days=None, repo=None, limit=20, offset=0)
        person = result["people"][0]
        assert len(person["top_prompts"]) == 20

    def test_sort_by_tokens(self, db):
        ingest_turn(db, make_turn_record(
            prompt_id="t1", author_email="low@co.com",
            tokens={"input_tokens": 10, "output_tokens": 5,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0},
        ))
        ingest_turn(db, make_turn_record(
            prompt_id="t2", author_email="high@co.com",
            tokens={"input_tokens": 50000, "output_tokens": 20000,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0},
        ))
        result = aggregate_people(db, sort="tokens", days=None, repo=None, limit=20, offset=0)
        assert result["people"][0]["email"] == "high@co.com"

    def test_people_offset_beyond_total(self, db):
        ingest_turn(db, make_turn_record(author_email="only@co.com"))
        result = aggregate_people(db, sort="cost", days=None, repo=None, limit=20, offset=100)
        assert result["people"] == []
        assert result["total"] == 1

    def test_multiple_people_sorted_by_cost(self, db):
        ingest_turn(db, make_turn_record(
            prompt_id="t1", author_email="cheap@co.com",
            tokens={"input_tokens": 100, "output_tokens": 50,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0},
        ))
        ingest_turn(db, make_turn_record(
            prompt_id="t2", author_email="expensive@co.com",
            tokens={"input_tokens": 100000, "output_tokens": 50000,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0},
        ))
        result = aggregate_people(db, sort="cost", days=None, repo=None, limit=20, offset=0)
        assert result["people"][0]["email"] == "expensive@co.com"
        assert result["people"][1]["email"] == "cheap@co.com"
