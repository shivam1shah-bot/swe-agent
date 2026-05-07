"""
Shared fixtures for Pulse tests.

Uses SQLite in-memory with StaticPool so all connections share the same DB.
MySQL-specific features (JSON operators, etc.) are not used in the ORM queries,
so SQLAlchemy's generic JSON type works fine on SQLite.

Import strategy: We import pulse services via importlib with a temporary
sys.modules stub for src.services, then restore the original state.
This prevents src/services/__init__.py from loading heavy dependencies
(CacheService, redis, prometheus) while avoiding module cache pollution
that would break other test files.
"""

import sys
import types
import importlib

# ---------------------------------------------------------------------------
# Safe import of pulse services without triggering heavy src.services __init__
# ---------------------------------------------------------------------------
_original_services = sys.modules.get("src.services")
_was_present = "src.services" in sys.modules

# Temporarily stub src.services so importing pulse submodules skips __init__
_stub = types.ModuleType("src.services")
_stub.__path__ = [str(__import__("pathlib").Path(__file__).resolve().parents[4] / "src" / "services")]
_stub.__package__ = "src.services"
sys.modules["src.services"] = _stub

# Force-import the two pulse service modules under the stub
import src.services.pulse_ingest_service  # noqa: E402
import src.services.pulse_aggregation_service  # noqa: E402

# Restore original state so other tests are not affected
if _was_present:
    sys.modules["src.services"] = _original_services
else:
    del sys.modules["src.services"]

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from src.models.base import Base  # noqa: E402


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate only Pulse tables before each test."""
    from src.models.pulse_turn import PulseTurn  # noqa: F401
    from src.models.pulse_commit import PulseCommit  # noqa: F401
    from src.models.pulse_commit_prompt import PulseCommitPrompt  # noqa: F401
    from src.models.pulse_edit import PulseEdit  # noqa: F401

    pulse_tables = [
        Base.metadata.tables["pulse_commit_prompts"],
        Base.metadata.tables["pulse_commits"],
        Base.metadata.tables["pulse_turns"],
        Base.metadata.tables["pulse_edits"],
    ]
    # Drop in FK-safe order, then recreate
    Base.metadata.drop_all(bind=engine, tables=pulse_tables)
    Base.metadata.create_all(bind=engine, tables=pulse_tables)


@pytest.fixture
def db(reset_db):
    """Yield a SQLAlchemy session for direct service function calls."""
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()


def make_turn_record(**overrides) -> dict:
    """Minimal valid turn payload dict."""
    record = {
        "prompt_id": "turn-001",
        "session_id": "sess-001",
        "repo": "repo-a",
        "branch": "main",
        "author_email": "alice@company.com",
        "user_prompt": "write a login function",
        "user_prompt_ts": "2026-03-10T10:00:00Z",
        "assistant_turn_ts": "2026-03-10T10:00:05Z",
        "timestamp": "2026-03-10T10:00:05Z",
        "unix_ts": 1741600805.0,
        "model": "claude-sonnet-4-6",
        "turn_type": "write",
        "tools_used": ["Edit", "Read"],
        "skill_invoked": None,
        "cost_usd": 0.005,
        "assistant_preview": "Sure, here's a login function...",
        "tokens": {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_tokens": 2000,
            "cache_creation_tokens": 0,
        },
    }
    record.update(overrides)
    return record


def make_commit_record(**overrides) -> dict:
    """Minimal valid commit payload dict."""
    record = {
        "commit_hash": "abc123def456abc123def456abc123def456abc1",
        "repo": "repo-a",
        "branch": "main",
        "author_email": "alice@company.com",
        "commit_author": "Alice",
        "commit_message": "Add login function",
        "commit_timestamp": "2026-03-10T10:05:00Z",
        "timestamp": "2026-03-10T10:05:00Z",
        "unix_ts": 1741601100.0,
        "files_changed": 2,
        "diff_summary": "Added auth/login.py",
        "prompt_count": 1,
        "estimated_cost_usd": 0.005,
        "tokens_used": {"input": 1000, "output": 500, "cache_read": 2000, "cache_creation": 0},
        "attribution": {"total_lines_added": 50, "ai_lines": 40, "human_lines": 10, "ai_percentage": 80.0},
        "file_attribution": {"auth/login.py": {"ai": 40, "human": 10}},
        "prompts_used": [
            {
                "prompt": "write a login function",
                "timestamp": "2026-03-10T10:00:05Z",
                "model": "claude-sonnet-4-6",
                "turn_type": "write",
                "cost_usd": 0.005,
                "tools_used": ["Edit"],
                "skill_invoked": None,
                "assistant_preview": "Sure, here's a login function...",
            }
        ],
    }
    record.update(overrides)
    return record
