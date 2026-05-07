"""
Slack Socket Mode client.

Establishes an outbound WebSocket connection to Slack — no public URL needed.
Slack sends slash commands and events through this connection.

Start via start_socket_mode() during application lifespan.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from slack_sdk.socket_mode.builtin import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.web import WebClient  # used for app_mention replies and Socket Mode client

from src.providers.logger import Logger

logger = Logger("SlackSocketMode")

_client: Optional[SocketModeClient] = None

# Cache of valid skill names from the last successful registry fetch.
# Used as a fallback when the skills API is temporarily unreachable so that
# skill validation is fail-closed (cached known-good set) rather than open.
_skills_cache: Optional[set] = None


def _handle_request(client: SocketModeClient, req: SocketModeRequest) -> None:
    """Route incoming Socket Mode requests to the appropriate handler."""
    logger.info(f"Socket Mode request received: type={req.type} payload_keys={list((req.payload or {}).keys())}")

    if req.type == "slash_commands":
        _ack(client, req)
        _handle_slash_command(client, req)

    elif req.type == "events_api":
        _ack(client, req)
        event = (req.payload or {}).get("event", {})
        event_type = event.get("type", "unknown")
        logger.info(f"Event received: event_type={event_type} user={event.get('user')} channel={event.get('channel')} text={str(event.get('text',''))[:80]}")
        if event_type == "app_mention":
            try:
                _handle_app_mention(client, event)
            except Exception as exc:
                logger.exception(f"_handle_app_mention raised: {exc}")
    else:
        logger.info(f"Unhandled Socket Mode type: {req.type}")


def _ack(client: SocketModeClient, req: SocketModeRequest) -> None:
    """Send an empty acknowledgement to Slack."""
    client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))


def _get_user_email(user_id: str) -> str:
    """
    Fetch a Slack user's email using the User OAuth Token (xoxp-).
    Returns empty string if token not configured or lookup fails.
    """
    try:
        import requests as _requests
        from src.providers.config_loader import get_config
        user_token = get_config().get("slack", {}).get("user_token", "").strip()
        if not user_token:
            return ""
        resp = _requests.get(
            "https://slack.com/api/users.info",
            headers={"Authorization": f"Bearer {user_token}"},
            params={"user": user_id},
            timeout=5,
        )
        data = resp.json()
        if data.get("ok"):
            return data.get("user", {}).get("profile", {}).get("email", "")
    except Exception as exc:
        logger.warning(f"Failed to fetch Slack user email for {user_id}: {exc}")
    return ""


def _store_slack_connector(task_id: str, user_email: str, user_name: str,
                            channel_name: str, source_id: str = None, skills: list = None,
                            user_id: str = None) -> None:
    """Store connector=slack metadata in the DB task record."""
    from src.utils.connector import store_connector_metadata, CONNECTOR_SLACK
    extra = {"channel_name": channel_name, "user_id": user_id or user_email}
    if skills:
        extra["skills"] = skills
    store_connector_metadata(
        task_id=task_id,
        connector_name=CONNECTOR_SLACK,
        user_email=user_email,
        user_name=user_name,
        source_id=source_id,
        extra=extra,
    )


def _handle_slash_command(client: SocketModeClient, req: SocketModeRequest) -> None:
    """Process slash commands received via Socket Mode."""
    from src.api.routers.slack import _parse_slash_command, _help_text

    payload = req.payload or {}
    user_id = payload.get("user_id", "")
    user_name = payload.get("user_name", "unknown")
    channel_id = payload.get("channel_id", "")
    channel_name = payload.get("channel_name", "")
    response_url = payload.get("response_url", "")
    text = payload.get("text", "")
    command = payload.get("command", "/vyom")

    # Fetch user email via User OAuth Token for metadata storage
    user_email = _get_user_email(user_id)

    logger.info("Socket Mode slash command received", extra={"user": user_name, "email": user_email, "command": command, "text": text[:100]})

    parsed = _parse_slash_command(text)
    action = parsed["action"]

    if action == "help":
        _respond(response_url, _help_text(command), ephemeral=True)
        return

    if action == "ticket":
        ticket_id = parsed.get("ticket_id", "").strip()
        if not ticket_id:
            _respond(response_url, "Please provide a ticket ID.\nUsage: `/vyom ticket:ISS-123`", ephemeral=True)
            return

        skills = parsed.get("skills", [])
        if not skills:
            _respond(
                response_url,
                (
                    f":x: Skills are required for the ticket command.\n"
                    f"Usage: `/vyom ticket:{ticket_id} skills:<skill1>,<skill2>`\n\n"
                    f"*Example:*\n"
                    f"`/vyom ticket:{ticket_id} skills:banking-org-onboarding`"
                ),
                ephemeral=True,
            )
            return

        # Validate skills against the registered skills list
        invalid = _validate_skills(skills)
        if invalid:
            _respond(
                response_url,
                (
                    f":x: Invalid skill(s): `{'`, `'.join(invalid)}`\n"
                    f"These skills are not registered in razorpay/agent-skills.\n"
                    f"Use `/vyom help` or check the skills catalogue for valid names."
                ),
                ephemeral=True,
            )
            return

        # Post ack first to capture thread_ts
        thread_ts = None
        try:
            msg = client.web_client.chat_postMessage(
                channel=channel_id,
                text=f":hourglass: Queueing ticket task `{ticket_id}`...",
            )
            thread_ts = msg.get("ts")
        except Exception:
            pass

        # Build a prompt that tells the agent to use DevRev MCP to fetch the ticket,
        # determine ALL repos that need changes, and create PRs in each.
        prompt = (
            f"Work on DevRev ticket {ticket_id}.\n\n"
            f"IMPORTANT: Always clone repositories into the current working directory (use `pwd` first "
            f"to confirm you are in the temp workspace). NEVER cd into /app before cloning.\n\n"
            f"Steps:\n"
            f"1. Run `pwd` to confirm the current workspace directory. All repos must be cloned here.\n"
            f"2. Use DevRev MCP tool (mcp__devrev-mcp__get_ticket or mcp__devrev-mcp__get_issue) "
            f"to fetch ticket {ticket_id} and read the full title, description, and requirements.\n"
            f"3. From the ticket, identify ALL GitHub repositories in the razorpay org that need changes.\n"
            f"4. For each repository:\n"
            f"   a. Clone into the current workspace (NOT /app): "
            f"gh repo clone razorpay/<repo> -- --depth 1 --single-branch --branch master\n"
            f"   b. cd into the cloned repo directory\n"
            f"   c. Create a feature branch referencing the ticket\n"
            f"   d. Implement the required changes\n"
            f"   e. Commit, push, and create a DRAFT PR referencing ticket {ticket_id}\n"
            f"   f. cd back to the workspace root before cloning the next repo\n"
            f"5. Post a comment on the DevRev ticket with links to all PRs created."
        )

        try:
            from src.tasks.queue_integration import TaskQueueIntegration

            # No repository_url — agent determines repos from ticket via DevRev MCP.
            # autonomous-agent-clean-slate: starts in a fresh temp dir (auto-cleaned up),
            # no base repo pre-cloned, agent clones only what the ticket requires.
            parameters = {"prompt": prompt}
            if skills:
                parameters["skills"] = skills

            slack_metadata = {
                "source": "slack",
                "slack_user_id": user_id,
                "slack_user_name": user_name,
                "slack_user_email": user_email,
                "slack_channel_id": channel_id,
                "slack_channel_name": channel_name,
                "slack_response_url": response_url,
                "slack_thread_ts": thread_ts,
                "devrev_ticket_id": ticket_id,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            }

            integration = TaskQueueIntegration()
            task_id = integration.submit_agents_catalogue_task(
                usecase_name="autonomous-agent-clean-slate",
                parameters=parameters,
                metadata=slack_metadata,
            )
            if task_id:
                _store_slack_connector(task_id, user_email, user_name, channel_name,
                                       source_id=ticket_id, skills=skills, user_id=user_id)

            if task_id:
                skills_str = f"\n*Skills:* {', '.join(skills)}" if skills else ""
                ack = (
                    f":robot_face: Ticket task queued by <@{user_id}>!\n"
                    f"*Ticket:* `{ticket_id}`\n"
                    f"*Task ID:* `{task_id}`{skills_str}\n\n"
                    "Agent will fetch ticket details from DevRev and create PRs in the relevant repos. "
                    "I'll reply here when it's done."
                )
                if thread_ts:
                    try:
                        client.web_client.chat_update(channel=channel_id, ts=thread_ts, text=ack)
                    except Exception:
                        _respond(response_url, ack, ephemeral=False)
                else:
                    _respond(response_url, ack, ephemeral=False)
                logger.info("Ticket task queued", extra={"task_id": task_id, "ticket": ticket_id, "skills": skills})
            else:
                _respond(response_url, ":x: Failed to queue task. Please try again.", ephemeral=True)

        except Exception as exc:
            logger.exception(f"Failed to handle ticket command: {exc}")
            _respond(response_url, f":x: Error: {str(exc)[:200]}", ephemeral=True)
        return

    if action == "status":
        task_id = parsed.get("task_id", "").strip()
        if not task_id:
            _respond(response_url, "Please provide a task ID.\nUsage: `/vyom status <task_id>`", ephemeral=True)
            return

        try:
            from src.tasks import task_manager
            task = task_manager.get_task(task_id)

            status = task.get("status", "unknown")
            name = task.get("name", "")
            created_at = task.get("created_at", "")
            updated_at = task.get("updated_at", "")
            params = task.get("parameters", {})
            repo = params.get("repository_url", "")

            status_emoji = {
                "created": ":white_circle:",
                "pending": ":hourglass:",
                "running": ":gear:",
                "completed": ":white_check_mark:",
                "failed": ":x:",
                "cancelled": ":no_entry:",
            }.get(status, ":white_circle:")

            text = (
                f"{status_emoji} *Task Status*\n"
                f"*ID:* `{task_id}`\n"
                f"*Status:* `{status}`\n"
                f"*Task:* {name}\n"
            )
            if repo:
                text += f"*Repo:* {repo}\n"
            if created_at:
                text += f"*Created:* {created_at}\n"
            if updated_at:
                text += f"*Updated:* {updated_at}\n"

            # Show result summary if completed/failed
            result = task.get("result") or {}
            if status == "completed":
                agent_result = (result.get("result") or {}).get("agent_result") or {}
                inner = (agent_result.get("result") or {})
                content = inner.get("content", "") if isinstance(inner, dict) else ""
                if content:
                    from src.providers.slack.provider import md_to_slack
                    text += f"\n*Summary:*\n{md_to_slack(content.strip())[:800]}"
            elif status == "failed":
                error = result.get("error", "")
                if error:
                    text += f"\n*Error:* {str(error)[:200]}"

            _respond(response_url, text, ephemeral=True)

        except Exception as exc:
            _respond(response_url, f":x: Could not fetch task `{task_id}`: {str(exc)[:200]}", ephemeral=True)
        return

    if action == "unknown":
        _respond(response_url, f"Unknown command: `{parsed.get('raw', '')}`. Try `/vyom help`.", ephemeral=True)
        return

    # action == "run"
    task_description = parsed.get("description", "").strip()
    repository_url = parsed.get("repository_url", "")

    if not task_description:
        _respond(response_url, "Please include a task description.\nUsage: `/vyom run <description> repo:<github_url>`", ephemeral=True)
        return

    if not repository_url:
        _respond(response_url, "Please include a `repo:` argument.\nUsage: `/vyom run <description> repo:<github_url>`", ephemeral=True)
        return

    # Enqueue via the agents catalogue autonomous-agent service — the proper
    # path that validates the repo, clones it, and runs Claude Code correctly.
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
                "slack_user_email": user_email,
            "slack_channel_id": channel_id,
            "slack_channel_name": channel_name,
            "slack_response_url": response_url,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }

        integration = TaskQueueIntegration()
        # Post "Task queued" ack via chat.postMessage to capture thread_ts for threading.
        # Bot must be in the channel — try joining first if needed.
        # Fall back to response_url if both fail (e.g. private channel, no invite).
        thread_ts = None
        try:
            # Try to join the channel so the bot can post and get thread_ts
            try:
                client.web_client.conversations_join(channel=channel_id)
            except Exception:
                pass  # Already a member or private channel — proceed anyway

            msg = client.web_client.chat_postMessage(
                channel=channel_id,
                text=(
                    f":robot_face: Task received from <@{user_id}>!\n"
                    f"*Repo:* {repository_url}\n"
                    f"*Task:* {task_description}\n\n"
                    "Queuing... I'll reply here with the result."
                ),
            )
            thread_ts = msg.get("ts")
        except Exception as e:
            logger.warning(f"chat.postMessage failed, falling back to response_url: {e}")

        if thread_ts:
            slack_metadata["slack_thread_ts"] = thread_ts

        task_id = integration.submit_agents_catalogue_task(
            usecase_name="autonomous-agent",
            parameters=parameters,
            metadata=slack_metadata,
        )

        if task_id:
            _store_slack_connector(task_id, user_email, user_name, channel_name, user_id=user_id)
            # Update the ack message with the actual task ID (edit in place)
            if thread_ts:
                try:
                    client.web_client.chat_update(
                        channel=channel_id,
                        ts=thread_ts,
                        text=(
                            f":robot_face: Task queued by <@{user_id}>!\n"
                            f"*Task ID:* `{task_id}`\n"
                            f"*Repo:* {repository_url}\n"
                            f"*Description:* {task_description}\n\n"
                            "I'll reply here when it's done."
                        ),
                    )
                except Exception:
                    pass
            else:
                _respond(
                    response_url,
                    (
                        f":robot_face: Task queued by <@{user_id}>!\n"
                        f"*Task ID:* `{task_id}`\n"
                        f"*Repo:* {repository_url}\n"
                        f"*Description:* {task_description}\n\n"
                        "I'll post the result here when it's done."
                    ),
                    ephemeral=False,
                )

            logger.info("Slack Socket Mode task queued", extra={
                "task_id": task_id, "user": user_name, "repo": repository_url, "thread_ts": thread_ts,
            })
        else:
            _respond(response_url, ":x: Failed to submit task to queue. Please try again.", ephemeral=True)

    except Exception as exc:
        logger.exception(f"Failed to handle Socket Mode slash command: {exc}")
        _respond(response_url, f":x: Error: {str(exc)[:200]}", ephemeral=True)


# ---------------------------------------------------------------------------
# DevRev ticket helpers
# ---------------------------------------------------------------------------

def _validate_skills(skills: list) -> list:
    """
    Validate skill names against the registered skills in razorpay/agent-skills.
    Returns list of invalid skill names (empty list means all valid).

    Fail-closed: if the skills API is unreachable, falls back to the last
    successfully fetched skill set (cached). If no cache is available yet,
    only format validation is applied (fail-open) so that first-boot requests
    are not blocked.
    """
    global _skills_cache
    import re
    import requests as _requests

    # Format check first — skill names must be alphanumeric + hyphens only
    invalid_format = [s for s in skills if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]*', s)]
    if invalid_format:
        return invalid_format

    try:
        from src.providers.config_loader import get_config
        config = get_config()
        base_url = config.get("app", {}).get("api_base_url", "http://localhost:8002")
        # Use admin Basic Auth for internal API call
        auth_users = config.get("auth", {}).get("users", {})
        auth = ("admin", auth_users.get("admin", "admin123"))

        resp = _requests.get(
            f"{base_url}/api/v1/agent-skills/global/list",
            auth=auth,
            timeout=5,
        )
        if resp.ok:
            valid_names = {s.get("name", "").lower() for s in resp.json() if isinstance(s, dict) and s.get("name")}
            if valid_names:
                _skills_cache = valid_names  # Update cache on success
                return [s for s in skills if s.lower() not in valid_names]
    except Exception as exc:
        logger.warning(f"Could not validate skills against registry: {exc}")
        if _skills_cache is not None:
            # Fail-closed: use last known valid skill set
            logger.warning("Using cached skill list for validation (registry unreachable)")
            return [s for s in skills if s.lower() not in _skills_cache]
        # No cache yet — fall through to format-only validation (fail-open at startup)
        logger.warning("No skill cache available; applying format-only validation")

    return []  # If API unreachable and no cache, allow through after format check


def _fetch_devrev_ticket(ticket_id: str) -> dict:
    """
    Fetch a DevRev work item by display ID (e.g. ISS-1611038).

    Returns: {title, body, part_name, github_url, display_id}
    Raises ValueError on auth/not-found errors.
    """
    import requests as _requests, os, re

    token = os.environ.get("DEVREV_API_TOKEN", "")
    if not token:
        from src.providers.config_loader import get_config
        token = get_config().get("devrev", {}).get("api_token", "")
    if not token:
        raise ValueError("DEVREV_API_TOKEN is not configured.")

    resp = _requests.get(
        f"https://api.devrev.ai/works.get?id={ticket_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if resp.status_code == 401:
        raise ValueError("DevRev authentication failed. Check DEVREV_API_TOKEN.")
    if resp.status_code == 404:
        raise ValueError(f"Ticket '{ticket_id}' not found in DevRev.")
    if not resp.ok:
        raise ValueError(f"DevRev API error {resp.status_code}: {resp.text[:200]}")

    work = resp.json().get("work", {})
    title = work.get("title", "")
    body = work.get("body", "") or ""
    part = work.get("applies_to_part") or {}
    part_name = part.get("name", "")

    # 1. Look for GitHub URLs in the ticket body
    github_url = None
    matches = re.findall(r"https://github\.com/razorpay/[\w._-]+", body)
    if matches:
        github_url = matches[0].rstrip("/")

    # 2. Fallback: derive from part name ("Payment Links" → "payment-links")
    if not github_url and part_name:
        slug = part_name.lower().replace(" ", "-").replace("_", "-")
        github_url = f"https://github.com/razorpay/{slug}"

    return {
        "title": title,
        "body": body,
        "part_name": part_name,
        "github_url": github_url,
        "display_id": work.get("display_id", ticket_id),
    }


def _handle_ticket_command(
    client: SocketModeClient,
    ticket_id: str,
    skills: list,
    user_id: str,
    user_name: str,
    channel_id: str,
    channel_name: str,
    response_url: str,
    thread_ts,
) -> None:
    """Fetch a DevRev ticket and queue an autonomous agent task from its content."""
    from src.providers.config_loader import get_config
    from src.tasks.queue_integration import TaskQueueIntegration

    config = get_config()

    # Use provided skills or fall back to config default
    if not skills:
        default_str = config.get("slack", {}).get("default_skills", "").strip()
        skills = [s.strip() for s in default_str.split(",") if s.strip()] if default_str else []

    try:
        ticket = _fetch_devrev_ticket(ticket_id)
    except ValueError as exc:
        _respond(response_url, f":x: Could not fetch ticket `{ticket_id}`: {exc}", ephemeral=True)
        return

    title = ticket["title"]
    body = ticket["body"]
    repository_url = ticket["github_url"]
    display_id = ticket["display_id"]

    # Build prompt from ticket
    prompt = f"DevRev Ticket: {display_id}\nTitle: {title}\n\n{body}".strip()

    # If repo couldn't be auto-determined, instruct agent to figure it out
    if not repository_url:
        prompt += (
            "\n\nIMPORTANT: Identify the appropriate GitHub repository in the razorpay org "
            "based on the ticket context above. Clone it and implement the changes."
        )
        repository_url = "https://github.com/razorpay/payment-links"  # placeholder so validation passes

    logger.info("Ticket command", extra={
        "ticket": display_id, "title": title, "repo": repository_url, "skills": skills, "user": user_name,
    })

    parameters = {"repository_url": repository_url, "prompt": prompt}
    if skills:
        parameters["skills"] = skills

    slack_metadata = {
        "source": "slack",
        "slack_user_id": user_id,
        "slack_user_name": user_name,
                "slack_user_email": user_email,
        "slack_channel_id": channel_id,
        "slack_channel_name": channel_name,
        "slack_response_url": response_url,
        "slack_thread_ts": thread_ts,
        "devrev_ticket_id": display_id,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }

    integration = TaskQueueIntegration()
    task_id = integration.submit_agents_catalogue_task(
        usecase_name="autonomous-agent",
        parameters=parameters,
        metadata=slack_metadata,
    )

    if task_id:
        _store_slack_connector(task_id, user_email, user_name, channel_name,
                               source_id=display_id, skills=skills, user_id=user_id)
        skills_str = f"\n*Skills:* {', '.join(skills)}" if skills else ""
        ack = (
            f":robot_face: Ticket task queued by <@{user_id}>!\n"
            f"*Ticket:* `{display_id}` — {title}\n"
            f"*Task ID:* `{task_id}`\n"
            f"*Repo:* {repository_url}{skills_str}\n\n"
            "I'll reply here when it's done."
        )
        if thread_ts:
            try:
                client.web_client.chat_update(channel=channel_id, ts=thread_ts, text=ack)
            except Exception:
                _respond(response_url, ack, ephemeral=False)
        else:
            _respond(response_url, ack, ephemeral=False)
        logger.info("Ticket task queued", extra={"task_id": task_id, "ticket": display_id})
    else:
        _respond(response_url, ":x: Failed to queue task. Please try again.", ephemeral=True)


def _handle_app_mention(client: SocketModeClient, event: dict) -> None:
    """
    Handle @vyom mentions as a conversational agent.
    Fetches thread history for multi-turn context, queues an agent task,
    posts response back in the same thread.
    """
    import re

    channel = event.get("channel", "")
    user_id = event.get("user", "")
    msg_ts = event.get("ts", "")
    thread_ts = event.get("thread_ts") or msg_ts

    # Strip bot mention to get the actual message
    raw_text = event.get("text", "")
    message = re.sub(r"<@[A-Z0-9]+>", "", raw_text).strip()

    # Extract skills: @vyom skills:a,b,c <rest of message>
    skills = []
    skills_match = re.search(r'\bskills:([\w,._-]+)', message, re.IGNORECASE)
    if skills_match:
        skills = [s.strip() for s in skills_match.group(1).split(',') if s.strip()]
        message = re.sub(r'\bskills:[\w,._-]+', '', message, flags=re.IGNORECASE).strip()

    if not message and not skills:
        try:
            client.web_client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=(
                    f"Hi <@{user_id}>! :wave: I\'m Vyom, your AI engineering assistant.\n\n"
                    "*What I can do:*\n"
                    "\u2022 Answer questions about the codebase, architecture, or workflows\n"
                    "\u2022 Debug issues and suggest fixes\n"
                    "\u2022 Implement changes in a GitHub repo and open a draft PR\n"
                    "\u2022 Run skills like code reviews, onboarding checks, and more\n"
                    "\u2022 Fetch and implement DevRev tickets across multiple repos\n\n"
                    "*How to use me:*\n"
                    "\u2022 Just mention `@vyom <your question or task>` — I maintain thread context\n"
                    "\u2022 Add `skills:skill-name` to invoke a specific skill\n"
                    "\u2022 Use `/vyom help` for structured slash commands\n\n"
                    "*Examples:*\n"
                    "\u2022 `@vyom explain the payment link creation flow`\n"
                    "\u2022 `@vyom add structured logging to payment-links repo`\n"
                    "\u2022 `@vyom skills:python-code-review review my PR changes`\n"
                    "\u2022 `@vyom skills:banking-org-onboarding fix onboarding issue`\n"
                    "\u2022 `/vyom run fix the login bug repo:https://github.com/razorpay/api`\n"
                    "\u2022 `/vyom ticket:ISS-123 skills:banking-org-onboarding`"
                ),
            )
        except Exception as exc:
            logger.warning(f"Failed to reply to empty mention: {exc}")
        return

    logger.info("Conversational mention received", extra={"user": user_id, "msg_preview": message[:100], "skills": skills})

    # Post a thinking indicator in the thread
    thinking_ts = None
    try:
        resp = client.web_client.chat_postMessage(
            channel=channel, thread_ts=thread_ts, text=":thinking_face: Thinking..."
        )
        thinking_ts = resp.get("ts")
    except Exception:
        pass

    try:
        bot_user_id = client.web_client.auth_test().get("user_id", "")
        user_name = _get_user_display_name(user_id) or user_id
        user_email = _get_user_email(user_id)

        history, attachment_paths = _fetch_thread_history(client, channel, thread_ts, bot_user_id)
        prompt = _build_conversation_prompt(history, message, user_name)

        slack_metadata = {
            "source": "slack",
            "slack_user_id": user_id,
            "slack_user_name": user_name,
            "slack_user_email": user_email,
            "slack_channel_id": channel,
            "slack_channel_name": channel,
            "slack_response_url": "",
            "slack_thread_ts": thread_ts,
            "slack_thinking_ts": thinking_ts or "",
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "slack_attachment_paths": attachment_paths,
        }

        parameters: dict = {"prompt": prompt}
        if skills:
            parameters["skills"] = skills

        from src.tasks.queue_integration import TaskQueueIntegration
        integration = TaskQueueIntegration()
        task_id = integration.submit_agents_catalogue_task(
            usecase_name="autonomous-agent-clean-slate",
            parameters=parameters,
            metadata=slack_metadata,
        )

        if task_id:
            _store_slack_connector(task_id, user_email, user_name, channel, user_id=user_id)
            logger.info("Conversational task queued", extra={"task_id": task_id, "user": user_id, "skills": skills})
        else:
            raise Exception("Failed to queue conversational task")

    except Exception as exc:
        logger.exception(f"Failed to handle app mention: {exc}")
        error_text = f":x: Sorry, something went wrong: {str(exc)[:200]}"
        try:
            if thinking_ts:
                client.web_client.chat_update(channel=channel, ts=thinking_ts, text=error_text)
            else:
                client.web_client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=error_text)
        except Exception:
            pass


def _respond(response_url: str, text: str, *, ephemeral: bool = True) -> None:
    """
    Post a slash command response via response_url.

    This works regardless of whether the bot is in the channel — no channel
    membership required. Ephemeral responses are only visible to the user.
    """
    import requests as _requests
    try:
        _requests.post(
            response_url,
            json={
                "text": text,
                "response_type": "ephemeral" if ephemeral else "in_channel",
            },
            timeout=10.0,
        )
    except Exception as exc:
        logger.warning(f"Failed to post to response_url: {exc}")


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def start_socket_mode(bot_token: str, app_token: str) -> bool:
    """
    Start the Socket Mode client in a background daemon thread.

    Returns True if started successfully.
    """
    global _client

    try:
        _client = SocketModeClient(
            app_token=app_token,
            web_client=WebClient(token=bot_token),
        )
        _client.socket_mode_request_listeners.append(_handle_request)
        _client.connect()
        logger.info("Slack Socket Mode client connected")
        return True
    except Exception as exc:
        logger.error(f"Failed to start Slack Socket Mode: {exc}")
        return False


def stop_socket_mode() -> None:
    """Disconnect the Socket Mode client."""
    global _client
    if _client:
        try:
            _client.close()
            logger.info("Slack Socket Mode client disconnected")
        except Exception as exc:
            logger.warning(f"Error stopping Socket Mode client: {exc}")
        _client = None


# ---------------------------------------------------------------------------
# Conversational bot helpers
# ---------------------------------------------------------------------------

def _download_slack_file(url: str, bot_token: str, dest_path: str) -> bool:
    """Download a Slack private file using the bot token. Returns True on success."""
    try:
        import requests as _requests
        resp = _requests.get(
            url,
            headers={"Authorization": f"Bearer {bot_token}"},
            timeout=15,
            stream=True,
        )
        if resp.status_code == 200:
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        logger.warning(f"Failed to download Slack file: HTTP {resp.status_code}")
    except Exception as exc:
        logger.warning(f"Error downloading Slack file: {exc}")
    return False


def _fetch_thread_history(client: SocketModeClient, channel: str, thread_ts: str, bot_user_id: str) -> tuple:
    """Fetch thread messages and any downloaded attachment paths.

    Returns (history, attachment_paths) where:
    - history: list of {role, content} dicts
    - attachment_paths: list of local file paths to delete after task completes

    Tries bot token first; falls back to user token (xoxp-) if missing_scope.
    """
    import re as _re
    import os
    import tempfile

    def _parse(resp, bot_token):
        history = []
        downloaded_paths = []
        for msg in resp.get("messages", []):
            text = _re.sub(r"<@[A-Z0-9]+>", "", msg.get("text", "")).strip()
            is_bot = bool(msg.get("bot_id")) or msg.get("user") == bot_user_id
            content_parts = [text] if text else []

            # Download images and file attachments
            for f in msg.get("files", []):
                mimetype = f.get("mimetype", "")
                name = f.get("name", "file")
                url = f.get("url_private_download") or f.get("url_private", "")
                if not url or not bot_token:
                    continue
                ext = os.path.splitext(name)[1] or ""
                attachments_dir = "/app/uploads/slack_attachments"
                os.makedirs(attachments_dir, exist_ok=True)
                tmp = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=ext,
                    prefix="slack_attachment_",
                    dir=attachments_dir,
                )
                tmp.close()
                if _download_slack_file(url, bot_token, tmp.name):
                    if mimetype.startswith("image/"):
                        content_parts.append(f"[Image attached — path: {tmp.name}]")
                    else:
                        content_parts.append(f"[File attached ({mimetype or name}) — path: {tmp.name}]")
                    downloaded_paths.append(tmp.name)
                    logger.info(f"Downloaded Slack attachment: {name} → {tmp.name}")
                else:
                    # Clean up temp file if download failed
                    try:
                        os.remove(tmp.name)
                    except OSError:
                        pass

            if content_parts:
                history.append({
                    "role": "assistant" if is_bot else "user",
                    "content": "\n".join(content_parts),
                })
        return history, downloaded_paths

    bot_token = client.web_client.token

    # Try bot token first
    try:
        resp = client.web_client.conversations_replies(channel=channel, ts=thread_ts, limit=50)
        return _parse(resp, bot_token)
    except Exception as exc:
        if "missing_scope" not in str(exc):
            logger.warning(f"Failed to fetch thread history: {exc}")
            return [], []

    # Fallback: use user token (xoxp-) which has broader read permissions
    try:
        from src.providers.config_loader import get_config
        import slack_sdk
        user_token = get_config().get("slack", {}).get("user_token", "").strip()
        if not user_token:
            logger.warning("Failed to fetch thread history: missing_scope and no user_token configured")
            return [], []
        user_client = slack_sdk.WebClient(token=user_token)
        resp = user_client.conversations_replies(channel=channel, ts=thread_ts, limit=50)
        return _parse(resp, user_token)
    except Exception as exc:
        logger.warning(f"Failed to fetch thread history with user token: {exc}")
        return [], []


def _build_conversation_prompt(history: list, current_message: str, user_name: str) -> str:
    """Build a prompt including thread history for conversational context."""
    system = (
        "You are Vyom, an AI coding assistant in Razorpay's Slack workspace. "
        "You help engineers with coding tasks, debugging, architecture questions, "
        "and can implement changes and create PRs in GitHub repositories.\n"
        "Be concise and conversational. Ask clarifying questions when needed. "
        "Format responses for Slack using *bold*, bullet points, and code blocks.\n"
        "IMPORTANT: The conversation history shown below IS the current Slack thread. "
        "When the engineer refers to 'this thread', 'this conversation', or 'above messages', "
        "they are referring to the messages in this history — you already have full context.\n"
        "If any message contains '[Image attached — path: ...]' or '[File attached ... — path: ...]', "
        "use the Read tool to view those files — they are real files on disk.\n"
    )
    conversation = ""
    if len(history) > 1:
        conversation = "\nCurrent Slack thread:\n"
        for msg in history[:-1]:
            role = "Engineer" if msg["role"] == "user" else "Vyom"
            conversation += f"{role}: {msg['content']}\n"
    return f"{system}{conversation}\nEngineer ({user_name}): {current_message}\n\nVyom:"


def _get_user_display_name(user_id: str) -> str:
    """Fetch Slack display name for a user using user_token or bot_token."""
    try:
        from src.providers.config_loader import get_config
        import requests as _requests
        cfg = get_config().get("slack", {})
        token = cfg.get("user_token", "").strip() or cfg.get("bot_token", "").strip()
        resp = _requests.get(
            "https://slack.com/api/users.info",
            headers={"Authorization": f"Bearer {token}"},
            params={"user": user_id},
            timeout=5,
        )
        if resp.ok and resp.json().get("ok"):
            profile = resp.json().get("user", {}).get("profile", {})
            return profile.get("display_name") or profile.get("real_name", "")
    except Exception:
        pass
    return ""
