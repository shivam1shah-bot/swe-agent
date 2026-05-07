"""
HTTP client for the SWE Agent API — submits tasks via the multi-repo endpoint.

Configuration is read from environment variables:
    SWE_AGENT_API__BASE_URL  - e.g. https://swe-agent-api.concierge.stage.razorpay.in
    SWE_AGENT_API__USERNAME  - basic auth username
    SWE_AGENT_API__PASSWORD  - basic auth password

Uses only stdlib (urllib) to avoid extra dependencies in the webhook receiver image.
"""

import asyncio
import base64
import json
import logging
import os
import urllib.request
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

MULTI_REPO_PATH = "/api/v1/agents/multi-repo"

# Read config once at module load — env vars don't change at runtime
_BASE_URL = os.environ.get("SWE_AGENT_API__BASE_URL", "").rstrip("/")
_AUTH_HEADER = "Basic " + base64.b64encode(
    f"{os.environ.get('SWE_AGENT_API__USERNAME', '')}:{os.environ.get('SWE_AGENT_API__PASSWORD', '')}".encode()
).decode("ascii")


def _post(path: str, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous HTTP POST to a SWE Agent API endpoint."""
    if not _BASE_URL:
        raise RuntimeError("SWE_AGENT_API__BASE_URL not configured")

    url = f"{_BASE_URL}{path}"
    logger.info(
        f"SWE Agent API request: POST {path} payload={json.dumps(payload_dict, indent=2)}"
    )

    req = urllib.request.Request(
        url,
        data=json.dumps(payload_dict).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": _AUTH_HEADER,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            logger.info(
                f"SWE Agent API accepted task: task_id={body.get('task_id')} status={body.get('status')}"
            )
            return body
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        logger.error(f"SWE Agent API returned {e.code}: {error_body}")
        return {
            "status": "failed",
            "message": f"API error {e.code}: {error_body[:200]}",
        }


async def submit_task(
    repositories: List[Dict[str, str]],
    prompt: str,
    skills: List[str],
    agent: str = "",
    source_id: str = "",
    connector: str = "devrev",
    user_email: str = "",
) -> Dict[str, Any]:
    """Submit a task — always routes through multi-repo endpoint.

    Even single-repo tasks use the multi-repo path so that:
      - The agent gets a shared workspace with permissive git instructions
      - The agent body (from claude-plugins) can freely clone additional repos
      - PRs can be opened across any number of repositories
    """
    payload: Dict[str, Any] = {
        "prompt": prompt,
        "repositories": repositories,
        "skills": skills,
        "connector": connector,
    }
    if agent:
        payload["agent"] = agent
    if source_id:
        payload["source_id"] = source_id
    if user_email:
        payload["user_email"] = user_email
    return await asyncio.to_thread(_post, MULTI_REPO_PATH, payload)
