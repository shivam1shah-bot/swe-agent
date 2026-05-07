"""
Pydantic request and response models for Pulse endpoints.
"""

import json
from typing import Annotated, Any, Optional
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator


# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Reusable sub-models
# ---------------------------------------------------------------------------

# Max lengths for ingest payload fields
_MAX_SHORT = 256        # IDs, emails, branches, model names
_MAX_MEDIUM = 1_000     # commit messages, file paths, timestamps
_MAX_LONG = 10_000      # user prompts, assistant previews
_MAX_DIFF = 50_000      # diff summaries
_MAX_LIST = 200         # tools_used, files_changed, prompts_used
_MAX_JSON_BYTES = 32_768  # 32 KB cap for unbounded JSON fields

# Constrained string type for list items — prevents multi-MB strings per element
BoundedStr = Annotated[str, StringConstraints(max_length=_MAX_MEDIUM)]


def _validate_not_empty(v: str, field_name: str) -> str:
    stripped = v.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    return stripped


def _check_json_size(v: Any, field_name: str, max_bytes: int = _MAX_JSON_BYTES) -> Any:
    """Reject JSON-serialisable values that exceed max_bytes when serialised."""
    if v is None:
        return v
    if len(json.dumps(v, default=str)) > max_bytes:
        raise ValueError(f"{field_name} exceeds max allowed size of {max_bytes} bytes")
    return v


class TokensPayload(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_creation_tokens: int = Field(default=0, ge=0)


class TurnIngest(BaseModel):
    prompt_id: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    session_id: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    repo: str = Field(default="unknown", max_length=_MAX_SHORT)
    branch: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    author_email: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    user_prompt: Optional[str] = Field(default=None, max_length=_MAX_LONG)
    user_prompt_ts: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    assistant_turn_ts: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    timestamp: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    unix_ts: Optional[float] = None
    model: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    turn_type: Optional[str] = None
    tools_used: list[BoundedStr] = Field(default_factory=list, max_length=_MAX_LIST)
    skill_invoked: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    cost_usd: Optional[float] = Field(default=None, ge=0)
    assistant_preview: Optional[str] = Field(default=None, max_length=_MAX_LONG)
    tokens: TokensPayload = Field(default_factory=TokensPayload)

    @field_validator("repo")
    @classmethod
    def repo_not_empty(cls, v: str) -> str:
        return _validate_not_empty(v, "repo")

    @field_validator("turn_type")
    @classmethod
    def valid_turn_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"write", "read", "mixed", "text"}
        if v not in allowed:
            raise ValueError(f"turn_type must be one of {allowed}")
        return v


class EditIngest(BaseModel):
    prompt_id: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    session_id: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    repo: str = Field(default="unknown", max_length=_MAX_SHORT)
    branch: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    author_email: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    timestamp: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    unix_ts: Optional[float] = None
    tool_category: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    tool_name: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    file_edited: Optional[str] = Field(default=None, max_length=_MAX_MEDIUM)
    files_changed: list[BoundedStr] = Field(default_factory=list, max_length=_MAX_LIST)
    files_new: list[BoundedStr] = Field(default_factory=list, max_length=_MAX_LIST)
    lines_added_by_ai: int = Field(default=0, ge=0)
    lines_removed_by_ai: int = Field(default=0, ge=0)
    diff_stats: Optional[dict[str, Any]] = None
    model: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    prompt: Optional[str] = Field(default=None, max_length=_MAX_LONG)
    skill_invoked: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    assistant_preview: Optional[str] = Field(default=None, max_length=_MAX_LONG)
    session_cost_usd: Optional[float] = Field(default=None, ge=0)
    tokens: TokensPayload = Field(default_factory=TokensPayload)

    @field_validator("repo")
    @classmethod
    def repo_not_empty(cls, v: str) -> str:
        return _validate_not_empty(v, "repo")

    @field_validator("diff_stats")
    @classmethod
    def diff_stats_bounded(cls, v: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        return _check_json_size(v, "diff_stats")


class CommitTokensPayload(BaseModel):
    input: int = Field(default=0, ge=0)
    output: int = Field(default=0, ge=0)
    cache_read: int = Field(default=0, ge=0)
    cache_creation: int = Field(default=0, ge=0)


class AttributionPayload(BaseModel):
    total_lines_added: int = Field(default=0, ge=0)
    ai_lines: int = Field(default=0, ge=0)
    human_lines: int = Field(default=0, ge=0)
    ai_percentage: float = Field(default=0.0, ge=0, le=100)


class CommitPromptPayload(BaseModel):
    prompt: Optional[str] = Field(default=None, max_length=_MAX_LONG)
    timestamp: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    model: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    turn_type: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    cost_usd: float = Field(default=0.0, ge=0)
    tools_used: list[BoundedStr] = Field(default_factory=list, max_length=_MAX_LIST)
    skill_invoked: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    assistant_preview: Optional[str] = Field(default=None, max_length=_MAX_LONG)


class CommitIngest(BaseModel):
    commit_hash: str = Field(max_length=_MAX_SHORT)
    repo: str = Field(default="unknown", max_length=_MAX_SHORT)
    branch: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    author_email: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    commit_author: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    commit_message: Optional[str] = Field(default=None, max_length=_MAX_MEDIUM)
    commit_timestamp: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    timestamp: Optional[str] = Field(default=None, max_length=_MAX_SHORT)
    unix_ts: Optional[float] = None
    files_changed: int = Field(default=0, ge=0)
    diff_summary: Optional[str] = Field(default=None, max_length=_MAX_DIFF)
    prompt_count: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    tokens_used: CommitTokensPayload = Field(default_factory=CommitTokensPayload)
    attribution: AttributionPayload = Field(default_factory=AttributionPayload)
    file_attribution: Optional[dict[str, Any]] = None
    prompts_used: list[CommitPromptPayload] = Field(default_factory=list, max_length=_MAX_LIST)

    @field_validator("repo")
    @classmethod
    def repo_not_empty(cls, v: str) -> str:
        return _validate_not_empty(v, "repo")

    @field_validator("commit_hash")
    @classmethod
    def hash_not_empty(cls, v: str) -> str:
        return _validate_not_empty(v, "commit_hash")

    @field_validator("file_attribution")
    @classmethod
    def file_attribution_bounded(cls, v: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        return _check_json_size(v, "file_attribution")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PulseHealthResponse(BaseModel):
    status: str
    service: str


class IngestResponse(BaseModel):
    status: str


# --- Overview ---

class WeeklyEntry(BaseModel):
    week: str
    cost: float
    prompts: int
    ai_lines: int
    tokens: int


class OverviewResponse(BaseModel):
    total_cost_usd: float
    total_tokens: int
    total_prompts: int
    total_ai_lines: int
    total_human_lines: int
    ai_percentage: float
    cache_saved_usd: float
    repo_count: int
    model_distribution: dict[str, int]
    turn_type_dist: dict[str, int]
    weekly: list[WeeklyEntry]


# --- Repos ---

class ContributorEntry(BaseModel):
    email: str
    prompts: int
    tokens: int
    cost_usd: float


class RepoEntry(BaseModel):
    rank: int
    repo: str
    total_prompts: int
    write_prompts: int
    read_prompts: int
    total_cost_usd: float
    total_tokens: int
    ai_lines: int
    human_lines: int
    ai_percentage: float
    commits: int
    contributors: int
    contributor_list: list[ContributorEntry]
    models: list[str]


class ReposResponse(BaseModel):
    repos: list[RepoEntry]
    total: int
    offset: int
    limit: int


# --- Commits ---

class CommitPromptEntry(BaseModel):
    prompt: str
    model: str
    turn_type: str
    cost_usd: float
    timestamp: str
    author: str
    branch: str
    tools_used: list[Any]
    skill_invoked: Optional[str]
    assistant_preview: str
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int


class CommitEntry(BaseModel):
    rank: int
    commit_sha: str
    commit_message: str
    commit_author: str
    author_email: str
    repo: str
    branch: str
    timestamp: str
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read: int
    cache_creation: int
    cost_usd: float
    ai_lines: int
    human_lines: int
    ai_percentage: float
    prompt_count: int
    prompts: list[CommitPromptEntry]


class CommitsResponse(BaseModel):
    commits: list[CommitEntry]
    total: int
    offset: int
    limit: int


# --- Prompts ---

class PromptEntry(BaseModel):
    rank: int
    prompt_id: str
    prompt: str
    cost_usd: float
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    model: str
    turn_type: str
    tools_used: list[Any]
    skill_invoked: Optional[str]
    assistant_preview: str
    repo: str
    branch: str
    timestamp: str
    author: str


class PromptsResponse(BaseModel):
    prompts: list[PromptEntry]
    total: int
    offset: int
    limit: int


# --- People ---

class PersonPromptEntry(BaseModel):
    prompt: str
    cost_usd: float
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    model: str
    turn_type: str
    tools_used: list[Any]
    skill_invoked: Optional[str]
    assistant_preview: str
    repo: str
    branch: str
    timestamp: str
    author: str


class PersonEntry(BaseModel):
    rank: int
    email: str
    total_cost_usd: float
    total_tokens: int
    total_prompts: int
    write_prompts: int
    read_prompts: int
    ai_lines: int
    commits: int
    repos: list[str]
    top_prompts: list[PersonPromptEntry]


class PeopleResponse(BaseModel):
    people: list[PersonEntry]
    total: int
    offset: int
    limit: int
