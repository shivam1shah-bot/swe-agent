"""
Slack router for FastAPI.

  POST /api/v1/slack/commands  — Slash command handler (/vyom ...)
  POST /api/v1/slack/events    — Events API (url_verification, app_mention)

All requests are verified via HMAC-SHA256 before processing.
Slack requires a <3s response; heavy work is queued and results posted via response_url.
"""

from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.providers.logger import Logger
from src.providers.slack import get_slack_client, is_slack_enabled
from src.providers.slack.exceptions import SlackNotConfiguredError

logger = Logger("SlackRouter")

router = APIRouter()

def _help_text(command: str = "/vyom") -> str:
    return (
        f"*Vyom — AI Engineering Assistant*\n\n"
        f"*Slash commands ({command}):*\n"
        f"• `{command} run <description> repo:<github_url>` — Clone a repo, make changes, open a draft PR\n"
        f"• `{command} ticket:<id> skills:a,b,c` — Fetch a DevRev ticket and implement it across relevant repos\n"
        f"• `{command} status <task_id>` — Check the status of a running or completed task\n"
        f"• `{command} help` — Show this message\n\n"
        f"*Conversational (@vyom):*\n"
        f"• Mention `@vyom` with any question or task — no commands needed\n"
        f"• Add `skills:skill-name` to use a specific skill\n\n"
        f"*Examples:*\n"
        f"`{command} run add structured logging to payment link creation repo:https://github.com/razorpay/payment-links`\n"
        f"`{command} ticket:ISS-123 skills:banking-org-onboarding`\n"
        f"`{command} status abc-123-def`\n"
        f"`@vyom explain the payment link creation flow`\n"
        f"`@vyom skills:python-code-review review my PR changes`"
    )

# Keep backward-compatible alias used by socket_mode.py
_HELP_TEXT = _help_text()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_slack() -> None:
    if not is_slack_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack integration is not enabled. Set slack.enabled = true in config.",
        )


async def _read_and_verify(request: Request) -> str:
    """Read raw body and verify Slack HMAC-SHA256 signature. Returns body string."""
    _require_slack()
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    logger.info("Incoming Slack request", extra={
        "timestamp_header": timestamp or "MISSING",
        "signature_header": signature[:20] + "..." if signature else "MISSING",
        "headers": str(dict(request.headers)),
    })

    if not get_slack_client().verify_signature(body_str, timestamp, signature):
        logger.warning("Slack signature verification failed", extra={"path": str(request.url.path)})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Slack signature")

    return body_str


def _parse_form(body_str: str) -> Dict[str, str]:
    """Parse application/x-www-form-urlencoded into a flat dict."""
    return {k: v[0] for k, v in urllib.parse.parse_qs(body_str, keep_blank_values=True).items()}


def _parse_slash_command(text: str) -> Dict[str, Any]:
    """
    Parse slash-command text into a structured action dict.

      help / (empty)               → {"action": "help"}
      run <desc> repo:<url>        → {"action": "run", "description": ..., "repository_url": ...}
      anything else                → {"action": "unknown", "raw": ...}
    """
    text = (text or "").strip()

    if not text or text.lower() == "help":
        return {"action": "help"}

    if text.lower().startswith("run "):
        repo_url = None
        description_tokens = []
        for token in text[4:].strip().split():
            if token.startswith("repo:"):
                repo_url = token[5:]
            else:
                description_tokens.append(token)
        return {
            "action": "run",
            "description": " ".join(description_tokens),
            "repository_url": repo_url,
        }

    if text.lower().startswith("status "):
        task_id = text[7:].strip()
        return {"action": "status", "task_id": task_id}

    # ticket:<id> [skills:a,b,c]
    # repo is auto-determined from the ticket content
    tokens = text.split()
    ticket_id = None
    skills = []
    other_tokens = []
    for token in tokens:
        if token.lower().startswith("ticket:"):
            ticket_id = token[7:].strip()
        elif token.lower().startswith("skills:"):
            skills = [s.strip() for s in token[7:].split(",") if s.strip()]
        else:
            other_tokens.append(token)
    if ticket_id:
        return {
            "action": "ticket",
            "ticket_id": ticket_id,
            "skills": skills,
        }

    return {"action": "unknown", "raw": text}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/commands")
async def handle_slash_command(request: Request, background_tasks: BackgroundTasks):
    """
    Handle /vyom slash commands from Slack.

    Responds within 3 seconds with an acknowledgement, then posts the result
    back to Slack via response_url once the task completes.
    """
    body_str = await _read_and_verify(request)
    form = _parse_form(body_str)

    user_id = form.get("user_id", "")
    user_name = form.get("user_name", "unknown")
    channel_id = form.get("channel_id", "")
    channel_name = form.get("channel_name", "")
    response_url = form.get("response_url", "")
    text = form.get("text", "")

    logger.info("Slack slash command received", extra={"user": user_name, "text": text[:100]})

    parsed = _parse_slash_command(text)
    action = parsed["action"]

    if action == "help":
        return JSONResponse({"response_type": "ephemeral", "text": _HELP_TEXT})

    if action == "unknown":
        return JSONResponse({
            "response_type": "ephemeral",
            "text": f"Unknown command: `{parsed.get('raw', '')}`. Try `/vyom help`.",
        })

    # action == "run"
    task_description = parsed.get("description", "").strip()
    repository_url = parsed.get("repository_url", "")

    if not task_description:
        return JSONResponse({
            "response_type": "ephemeral",
            "text": "Please include a task description.\nUsage: `/vyom run <description> repo:<github_url>`",
        })

    if not repository_url:
        return JSONResponse({
            "response_type": "ephemeral",
            "text": "Please include a `repo:` argument.\nUsage: `/vyom run <description> repo:<github_url>`",
        })

    try:
        from src.tasks.queue_integration import TaskQueueIntegration

        parameters = {
            "repository_url": repository_url,
            "prompt": task_description,
        }
        slack_metadata = {
            "source": "slack",
            "slack_user_id": user_id,
            "slack_user_name": user_name,
            "slack_channel_id": channel_id,
            "slack_channel_name": channel_name,
            "slack_response_url": response_url,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }

        integration = TaskQueueIntegration()
        task_id = integration.submit_agents_catalogue_task(
            usecase_name="autonomous-agent",
            parameters=parameters,
            metadata=slack_metadata,
        )

        if not task_id:
            return JSONResponse({
                "response_type": "ephemeral",
                "text": ":x: Failed to submit task to queue. Please try again.",
            })

        logger.info("Slack task queued", extra={
            "task_id": task_id, "user": user_name, "repository_url": repository_url,
        })

        return JSONResponse({
            "response_type": "in_channel",
            "text": (
                f":robot_face: Task queued by <@{user_id}>!\n"
                f"*Task ID:* `{task_id}`\n"
                f"*Repo:* {repository_url}\n"
                f"*Description:* {task_description}\n\n"
                "I'll post the result here when it's done."
            ),
        })

    except Exception as exc:
        logger.exception(f"Failed to enqueue Slack task: {exc}")
        return JSONResponse({
            "response_type": "ephemeral",
            "text": f":x: Failed to queue task: {str(exc)[:200]}",
        })


@router.post("/events")
async def handle_events(request: Request):
    """
    Handle Slack Events API callbacks.

    Supported events:
      - url_verification: Handshake when first configuring the endpoint.
      - app_mention: Bot @mentioned in a channel.
    """
    body_str = await _read_and_verify(request)

    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    # URL verification handshake
    if payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload.get("challenge", "")})

    event = payload.get("event", {})
    if event.get("type") == "app_mention":
        channel = event.get("channel", "")
        user = event.get("user", "")
        thread_ts = event.get("thread_ts") or event.get("ts")

        logger.info("Slack app_mention received", extra={"channel": channel, "user": user})

        try:
            get_slack_client().send_message(
                channel=channel,
                text=(
                    f"Hi <@{user}>! :wave: I'm Vyom, your AI engineering assistant.\n\n"
                    "• Ask me anything by mentioning `@vyom <your question or task>`\n"
                    "• Add `skills:skill-name` to use a specific skill\n"
                    "• Use `/vyom help` for slash command options\n\n"
                    "*Examples:*\n"
                    "`@vyom explain the payment link creation flow`\n"
                    "`@vyom skills:python-code-review review my changes`\n"
                    "`/vyom run fix login bug repo:https://github.com/razorpay/api`"
                ),
                thread_ts=thread_ts,
            )
        except SlackNotConfiguredError:
            pass
        except Exception as exc:
            logger.warning(f"Failed to reply to app_mention: {exc}")

    return JSONResponse({"ok": True})
