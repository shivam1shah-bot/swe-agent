"""
Tests for pulse_ingest_service.py.

Covers: turn dedup, update-if-fresher, edit insert, commit+prompts atomicity,
        turn_id FK resolution, rollback on error, IntegrityError fallback.
"""

from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.pulse_turn import PulseTurn
from src.models.pulse_edit import PulseEdit
from src.models.pulse_commit import PulseCommit
from src.models.pulse_commit_prompt import PulseCommitPrompt
from src.services.pulse_ingest_service import ingest_turn, ingest_edit, ingest_commit
from .conftest import make_turn_record, make_commit_record


class TestIngestTurn:

    def test_new_turn_is_inserted(self, db):
        ingest_turn(db, make_turn_record())

        assert db.query(PulseTurn).count() == 1
        row = db.query(PulseTurn).first()
        assert row.prompt_id == "turn-001"
        assert row.repo == "repo-a"
        assert row.input_tokens == 1000
        assert row.output_tokens == 500

    def test_duplicate_prompt_id_with_lower_tokens_is_skipped(self, db):
        ingest_turn(db, make_turn_record(tokens={"input_tokens": 1000, "output_tokens": 500,
                                                   "cache_read_tokens": 0, "cache_creation_tokens": 0}))
        ingest_turn(db, make_turn_record(tokens={"input_tokens": 999, "output_tokens": 400,
                                                   "cache_read_tokens": 0, "cache_creation_tokens": 0}))

        assert db.query(PulseTurn).count() == 1
        assert db.query(PulseTurn).first().output_tokens == 500

    def test_duplicate_prompt_id_with_higher_tokens_updates_record(self, db):
        ingest_turn(db, make_turn_record(tokens={"input_tokens": 1000, "output_tokens": 300,
                                                   "cache_read_tokens": 0, "cache_creation_tokens": 0}))
        ingest_turn(db, make_turn_record(
            tokens={"input_tokens": 1000, "output_tokens": 800,
                    "cache_read_tokens": 2000, "cache_creation_tokens": 0},
            assistant_preview="Updated full response...",
            turn_type="mixed",
        ))

        assert db.query(PulseTurn).count() == 1
        row = db.query(PulseTurn).first()
        assert row.output_tokens == 800
        assert row.cache_read_tokens == 2000
        assert row.assistant_preview == "Updated full response..."
        assert row.turn_type == "mixed"

    def test_turn_without_prompt_id_inserts_distinct_turns(self, db):
        ingest_turn(db, make_turn_record(prompt_id=None, user_prompt_ts="2026-03-10T10:00:00Z"))
        ingest_turn(db, make_turn_record(prompt_id=None, user_prompt_ts="2026-03-10T11:00:00Z"))

        assert db.query(PulseTurn).count() == 2

    def test_turn_without_prompt_id_deduplicates_same_ts_author_repo(self, db):
        ingest_turn(db, make_turn_record(prompt_id=None))
        ingest_turn(db, make_turn_record(prompt_id=None))

        assert db.query(PulseTurn).count() == 1

    def test_turn_defaults_repo_to_unknown_when_missing(self, db):
        record = make_turn_record()
        del record["repo"]
        ingest_turn(db, record)

        assert db.query(PulseTurn).first().repo == "unknown"

    def test_rollback_on_db_error(self, db):
        with patch.object(db, "commit", side_effect=RuntimeError("simulated db error")):
            with pytest.raises(RuntimeError, match="simulated db error"):
                ingest_turn(db, make_turn_record())

        assert db.query(PulseTurn).count() == 0

    def test_integrity_error_fallback_updates_fresher_record(self, db):
        """Simulate a race: pre-check finds no row, but INSERT hits IntegrityError
        because a concurrent insert beat us. The fallback should update-if-fresher."""
        # Insert the "winner" row directly
        ingest_turn(db, make_turn_record(tokens={"input_tokens": 100, "output_tokens": 200,
                                                  "cache_read_tokens": 0, "cache_creation_tokens": 0}))
        assert db.query(PulseTurn).count() == 1

        real_query = db.query
        real_commit = db.commit
        query_call_count = {"n": 0}
        commit_call_count = {"n": 0}

        def query_side_effect(*args, **kwargs):
            result = real_query(*args, **kwargs)
            if args and args[0] is PulseTurn:
                query_call_count["n"] += 1
                if query_call_count["n"] == 1:
                    # First PulseTurn query (pre-check) returns empty to simulate race
                    mock_query = MagicMock()
                    mock_query.filter.return_value.first.return_value = None
                    return mock_query
            return result

        def commit_side_effect():
            commit_call_count["n"] += 1
            if commit_call_count["n"] == 1:
                # First commit (the INSERT) raises IntegrityError
                real_query(PulseTurn)  # keep session alive
                db.rollback()
                raise IntegrityError("duplicate", {}, None)
            real_commit()

        fresher_record = make_turn_record(
            tokens={"input_tokens": 500, "output_tokens": 900,
                    "cache_read_tokens": 3000, "cache_creation_tokens": 100},
            cost_usd=0.05,
            assistant_preview="Updated via IntegrityError path",
            turn_type="mixed",
        )

        with patch.object(db, "query", side_effect=query_side_effect), \
             patch.object(db, "commit", side_effect=commit_side_effect):
            ingest_turn(db, fresher_record)

        assert db.query(PulseTurn).count() == 1
        row = db.query(PulseTurn).first()
        assert row.output_tokens == 900
        assert row.input_tokens == 500
        assert row.cache_read_tokens == 3000
        assert row.cache_creation_tokens == 100
        assert row.cost_usd == 0.05
        assert row.assistant_preview == "Updated via IntegrityError path"
        assert row.turn_type == "mixed"

    def test_integrity_error_fallback_skips_stale_record(self, db):
        """IntegrityError fallback should skip update when incoming tokens are lower."""
        ingest_turn(db, make_turn_record(tokens={"input_tokens": 100, "output_tokens": 900,
                                                  "cache_read_tokens": 0, "cache_creation_tokens": 0}))

        real_query = db.query
        real_commit = db.commit
        query_call_count = {"n": 0}
        commit_call_count = {"n": 0}

        def query_side_effect(*args, **kwargs):
            result = real_query(*args, **kwargs)
            if args and args[0] is PulseTurn:
                query_call_count["n"] += 1
                if query_call_count["n"] == 1:
                    mock_query = MagicMock()
                    mock_query.filter.return_value.first.return_value = None
                    return mock_query
            return result

        def commit_side_effect():
            commit_call_count["n"] += 1
            if commit_call_count["n"] == 1:
                db.rollback()
                raise IntegrityError("duplicate", {}, None)
            real_commit()

        stale_record = make_turn_record(
            tokens={"input_tokens": 50, "output_tokens": 100,
                    "cache_read_tokens": 0, "cache_creation_tokens": 0},
        )

        with patch.object(db, "query", side_effect=query_side_effect), \
             patch.object(db, "commit", side_effect=commit_side_effect):
            ingest_turn(db, stale_record)

        row = db.query(PulseTurn).first()
        assert row.output_tokens == 900  # unchanged


class TestIngestEdit:

    def _edit_record(self, **overrides):
        record = {
            "prompt_id": "turn-001",
            "session_id": "sess-001",
            "repo": "repo-a",
            "branch": "main",
            "author_email": "alice@company.com",
            "timestamp": "2026-03-10T10:00:03Z",
            "unix_ts": 1741600803.0,
            "tool_category": "write",
            "tool_name": "Edit",
            "file_edited": "src/auth.py",
            "files_changed": ["src/auth.py"],
            "files_new": [],
            "lines_added_by_ai": 42,
            "lines_removed_by_ai": 10,
            "diff_stats": {"src/auth.py": {"added": 42, "removed": 10}},
            "model": "claude-sonnet-4-6",
            "prompt": "refactor auth",
            "skill_invoked": None,
            "assistant_preview": "I'll refactor...",
            "session_cost_usd": 0.005,
            "tokens": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
            },
        }
        record.update(overrides)
        return record

    def test_edit_is_inserted(self, db):
        ingest_edit(db, self._edit_record())

        assert db.query(PulseEdit).count() == 1
        row = db.query(PulseEdit).first()
        assert row.tool_name == "Edit"
        assert row.file_edited == "src/auth.py"
        assert row.lines_added_by_ai == 42

    def test_edit_always_inserts_no_dedup(self, db):
        ingest_edit(db, self._edit_record())
        ingest_edit(db, self._edit_record())

        assert db.query(PulseEdit).count() == 2

    def test_edit_rollback_on_db_error(self, db):
        with patch.object(db, "commit", side_effect=RuntimeError("db error")):
            with pytest.raises(RuntimeError):
                ingest_edit(db, self._edit_record())

        assert db.query(PulseEdit).count() == 0


class TestIngestCommit:

    def test_commit_is_inserted(self, db):
        ingest_commit(db, make_commit_record())

        assert db.query(PulseCommit).count() == 1
        row = db.query(PulseCommit).first()
        assert row.commit_hash == "abc123def456abc123def456abc123def456abc1"
        assert row.ai_lines == 40
        assert row.ai_percentage == 80.0

    def test_commit_prompts_are_inserted_as_children(self, db):
        record = make_commit_record()
        record["prompts_used"] = [
            {"prompt": "first prompt", "timestamp": "2026-03-10T10:00:00Z",
             "model": "claude-sonnet-4-6", "turn_type": "write", "cost_usd": 0.003,
             "tools_used": ["Read"], "skill_invoked": None, "assistant_preview": "..."},
            {"prompt": "second prompt", "timestamp": "2026-03-10T10:01:00Z",
             "model": "claude-sonnet-4-6", "turn_type": "text", "cost_usd": 0.002,
             "tools_used": [], "skill_invoked": None, "assistant_preview": "..."},
        ]
        ingest_commit(db, record)

        assert db.query(PulseCommitPrompt).count() == 2
        prompt_texts = {p.prompt for p in db.query(PulseCommitPrompt).all()}
        assert prompt_texts == {"first prompt", "second prompt"}

    def test_duplicate_commit_hash_is_skipped(self, db):
        ingest_commit(db, make_commit_record())
        ingest_commit(db, make_commit_record())

        assert db.query(PulseCommit).count() == 1

    def test_commit_with_empty_hash_is_skipped(self, db):
        ingest_commit(db, make_commit_record(commit_hash=""))

        assert db.query(PulseCommit).count() == 0

    def test_commit_and_prompts_are_atomic(self, db):
        record = make_commit_record()
        record["prompts_used"] = [{"prompt": "p1", "timestamp": "2026-03-10T10:00:00Z",
                                    "model": "claude-sonnet-4-6", "turn_type": "write",
                                    "cost_usd": 0.003, "tools_used": [],
                                    "skill_invoked": None, "assistant_preview": ""}]

        with patch.object(db, "commit", side_effect=RuntimeError("network error")):
            with pytest.raises(RuntimeError, match="network error"):
                ingest_commit(db, record)

        assert db.query(PulseCommit).count() == 0
        assert db.query(PulseCommitPrompt).count() == 0

    def test_commit_rollback_on_db_error(self, db):
        with patch.object(db, "commit", side_effect=RuntimeError("db error")):
            with pytest.raises(RuntimeError):
                ingest_commit(db, make_commit_record())

        ingest_commit(db, make_commit_record(commit_hash="different-hash-111"))
        assert db.query(PulseCommit).count() == 1

    def test_turn_id_fk_is_set_when_matching_turn_exists(self, db):
        ingest_turn(db, make_turn_record(
            prompt_id="turn-for-commit",
            assistant_turn_ts="2026-03-10T10:00:05Z",
        ))

        record = make_commit_record(commit_hash="hash-with-turn-id")
        record["prompts_used"] = [{
            "prompt": "write login",
            "timestamp": "2026-03-10T10:00:05Z",
            "model": "claude-sonnet-4-6",
            "turn_type": "write",
            "cost_usd": 0.005,
            "tools_used": ["Edit"],
            "skill_invoked": None,
            "assistant_preview": "...",
        }]
        ingest_commit(db, record)

        cp = db.query(PulseCommitPrompt).first()
        assert cp is not None
        assert cp.turn_id is not None

        turn = db.query(PulseTurn).filter(PulseTurn.prompt_id == "turn-for-commit").first()
        assert cp.turn_id == turn.id
