"""
Ticket body parser - extracts structured fields from DevRev ticket markdown body.

Expected ticket body format:

    ## Repositories
    razorpay/scrooge, razorpay/pg-router

    ## Global Skills
    cell-readiness, db-network-optimizer

    ## Task Description
    Support Amount filter in the bulk fetch API of refunds.
    Since amount filter is not indexed in DB, do filtering in the app.

    ## Acceptance Criteria
    All builds pass on the PR.
    New SLIT tests are successfully executed.

Repositories can be:
    - Comma-separated short names: razorpay/scrooge, razorpay/pg-router
    - Full URLs: https://github.com/razorpay/scrooge
    - With optional branch: razorpay/scrooge (branch: feature/xyz)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GITHUB_BASE_URL = "https://github.com/"

# Map section header (lowercased) → canonical field name
_SECTION_ALIASES: Dict[str, str] = {
    "repositories": "repositories",
    "repository": "repositories",
    "repos": "repositories",
    "global skills": "skills",
    "skills": "skills",
    "agent": "agent",
    "global agent": "agent",
    "task description": "task_description",
    "description": "task_description",
    "requirements": "task_description",
    "acceptance criteria": "acceptance_criteria",
}


@dataclass
class ParsedTicket:
    """Structured representation of a DevRev ticket for agent execution."""

    title: str
    repositories: List[Dict[str, str]]  # [{"repository_url": ..., "branch": ...}]
    skills: List[str]
    agent: str  # agent name from claude-plugins (e.g. "gng-readiness")
    task_description: str
    acceptance_criteria: str
    ticket_id: str  # DON ID e.g. "don:core:...:issue/1641378"
    ticket_display_id: str  # e.g. "ISS-1641378"
    extra_context: Dict[str, str] = field(default_factory=dict)  # unrecognized sections
    reporter_email: str = ""  # email of the DevRev user who created the ticket


def parse_ticket_body(body: str) -> Dict[str, Any]:
    """Parse markdown body into structured fields.

    Returns dict with keys: repositories, skills, task_description, acceptance_criteria.
    Missing sections return empty lists/strings.
    """
    # Normalize vertical tabs (DevRev sometimes uses \u000b)
    body = body.replace("\u000b", "\n")

    sections = _split_sections(body)

    _known = {"repositories", "skills", "agent", "task_description", "acceptance_criteria"}

    repositories = _parse_repositories(sections.get("repositories", ""))
    skills = _parse_comma_or_list(sections.get("skills", ""))
    agent = sections.get("agent", "").strip()
    task_description = sections.get("task_description", "").strip()
    acceptance_criteria = sections.get("acceptance_criteria", "").strip()
    extra_context = {k: v.strip() for k, v in sections.items() if k not in _known and v.strip()}

    return {
        "repositories": repositories,
        "skills": skills,
        "agent": agent,
        "task_description": task_description,
        "acceptance_criteria": acceptance_criteria,
        "extra_context": extra_context,
    }


def parse_ticket_from_event(raw_payload: Dict[str, Any]) -> Optional[ParsedTicket]:
    """Extract a ParsedTicket from a DevRev work_created webhook payload."""
    event_type = raw_payload.get("type", "")
    event_data = raw_payload.get(event_type, {})
    work = event_data.get("work", {})

    if not work:
        logger.warning("No work object in payload")
        return None

    title = work.get("title", "")
    body = work.get("body", "")
    ticket_id = work.get("id", "")
    ticket_display_id = work.get("display_id", "")
    reporter_email = work.get("created_by", {}).get("email", "")

    if not body:
        logger.warning(f"Ticket {ticket_display_id} has empty body, skipping")
        return None

    parsed = parse_ticket_body(body)

    return ParsedTicket(
        title=title,
        repositories=parsed["repositories"],
        skills=parsed["skills"],
        agent=parsed["agent"],
        task_description=parsed["task_description"],
        acceptance_criteria=parsed["acceptance_criteria"],
        ticket_id=ticket_id,
        ticket_display_id=ticket_display_id,
        extra_context=parsed["extra_context"],
        reporter_email=reporter_email,
    )


def _normalize_header(text: str) -> str:
    """Lowercase and strip trailing punctuation/backslashes from a section header."""
    return text.strip().rstrip(":\\").strip().lower()


def _split_sections(body: str) -> Dict[str, str]:
    """Split markdown body by ## headers into canonical section names."""
    sections: Dict[str, str] = {}
    current_key = ""
    current_lines: List[str] = []

    for line in body.splitlines():
        stripped = line.strip()
        # Match ## Header format
        header_match = re.match(r"^##\s+(.+)$", stripped)
        if header_match:
            if current_key:
                sections[current_key] = "\n".join(current_lines)
            raw_header = _normalize_header(header_match.group(1))
            current_key = _SECTION_ALIASES.get(raw_header, raw_header)
            current_lines = []
        # Also match plain-text known section names (DevRev form format, no ## prefix)
        elif _normalize_header(stripped) in _SECTION_ALIASES:
            if current_key:
                sections[current_key] = "\n".join(current_lines)
            current_key = _SECTION_ALIASES[_normalize_header(stripped)]
            current_lines = []
        else:
            current_lines.append(line)

    if current_key:
        sections[current_key] = "\n".join(current_lines)

    return sections


def _parse_repositories(text: str) -> List[Dict[str, str]]:
    """Parse repositories from comma-separated short names or full URLs.

    Supported formats:
        razorpay/scrooge, razorpay/pg-router
        razorpay/scrooge (branch: feature/xyz)
        https://github.com/razorpay/scrooge
        - https://github.com/razorpay/scrooge (branch: feature/xyz)
    """
    repos: List[Dict[str, str]] = []

    # First, join all non-empty lines and split by comma
    flat = " ".join(line.strip().lstrip("- ").strip() for line in text.splitlines() if line.strip())
    if not flat:
        return repos

    # Split by comma for comma-separated format
    tokens = [t.strip() for t in flat.split(",") if t.strip()]

    for token in tokens:
        # Extract optional (branch: xxx)
        branch_match = re.match(r"^(.+?)\s*\(branch:\s*(\S+)\)\s*$", token)
        if branch_match:
            name = branch_match.group(1).strip()
            branch = branch_match.group(2)
        else:
            name = token
            branch = ""

        # Strip markdown link format: [text](url) → url
        md_link_match = re.match(r"^\[.*?\]\((.+?)\)\s*$", name)
        if md_link_match:
            name = md_link_match.group(1)

        # Strip angle-bracket link format DevRev uses: <https://github.com/...>
        name = re.sub(r"^<(.+)>$", r"\1", name)

        # Strip /tree/<branch> suffix from GitHub URLs (branch goes in task description)
        name = re.sub(r"/tree/[^/\s]+$", "", name)

        # Normalize to full URL
        if name.startswith("http"):
            url = name
        else:
            # Short name like "razorpay/scrooge" → full GitHub URL
            url = GITHUB_BASE_URL + name

        repo: Dict[str, str] = {"repository_url": url}
        if branch:
            repo["branch"] = branch
        repos.append(repo)

    return repos


def _parse_comma_or_list(text: str) -> List[str]:
    """Parse items from comma-separated values or markdown list items.

    Handles:
        cell-readiness, db-network-optimizer
        - cell-readiness
        - db-network-optimizer
    """
    flat = " ".join(line.strip().lstrip("- ").strip() for line in text.splitlines() if line.strip())
    if not flat:
        return []
    return [item.strip() for item in flat.split(",") if item.strip()]
