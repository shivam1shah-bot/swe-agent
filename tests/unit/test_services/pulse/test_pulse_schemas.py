"""
Tests for Pydantic schema validators in pulse_schemas.py.
"""

import pytest
from pydantic import ValidationError
from src.models.pulse_schemas import TurnIngest, EditIngest, CommitIngest, TokensPayload


class TestTokensPayload:

    def test_defaults_to_zero(self):
        t = TokensPayload()
        assert t.input_tokens == 0
        assert t.output_tokens == 0
        assert t.cache_read_tokens == 0
        assert t.cache_creation_tokens == 0


class TestTurnIngest:

    def test_empty_repo_raises(self):
        with pytest.raises(ValidationError, match="repo must not be empty"):
            TurnIngest(repo="")

    def test_whitespace_repo_raises(self):
        with pytest.raises(ValidationError, match="repo must not be empty"):
            TurnIngest(repo="   ")

    def test_valid_repo_stripped(self):
        t = TurnIngest(repo="  my-repo  ")
        assert t.repo == "my-repo"

    def test_invalid_turn_type_raises(self):
        with pytest.raises(ValidationError, match="turn_type must be one of"):
            TurnIngest(turn_type="invalid")

    def test_none_turn_type_accepted(self):
        t = TurnIngest()
        assert t.turn_type is None

    def test_valid_turn_types(self):
        for tt in ("write", "read", "mixed", "text"):
            t = TurnIngest(turn_type=tt)
            assert t.turn_type == tt

    def test_default_repo_is_unknown(self):
        t = TurnIngest()
        assert t.repo == "unknown"

    def test_minimal_payload_accepted(self):
        t = TurnIngest()
        assert t.prompt_id is None
        assert t.model is None


class TestEditIngest:

    def test_empty_repo_raises(self):
        with pytest.raises(ValidationError, match="repo must not be empty"):
            EditIngest(repo="")

    def test_whitespace_repo_raises(self):
        with pytest.raises(ValidationError, match="repo must not be empty"):
            EditIngest(repo="   ")

    def test_valid_payload(self):
        e = EditIngest(repo="my-repo", tool_name="Edit")
        assert e.repo == "my-repo"
        assert e.tool_name == "Edit"


class TestCommitIngest:

    def test_empty_hash_raises(self):
        with pytest.raises(ValidationError, match="commit_hash must not be empty"):
            CommitIngest(commit_hash="")

    def test_whitespace_hash_raises(self):
        with pytest.raises(ValidationError, match="commit_hash must not be empty"):
            CommitIngest(commit_hash="   ")

    def test_empty_repo_raises(self):
        with pytest.raises(ValidationError, match="repo must not be empty"):
            CommitIngest(commit_hash="abc123", repo="")

    def test_valid_commit_hash_stripped(self):
        c = CommitIngest(commit_hash="  abc123  ")
        assert c.commit_hash == "abc123"

    def test_minimal_payload(self):
        c = CommitIngest(commit_hash="abc123")
        assert c.repo == "unknown"
        assert c.files_changed == 0
        assert c.prompt_count == 0
