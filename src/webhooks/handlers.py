"""
Event handlers - pluggable processors for webhook events.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from .models import EventFilter, HandlerResult, WebhookEvent
from .swe_agent_client import submit_task
from .ticket_parser import parse_ticket_from_event

logger = logging.getLogger(__name__)

VYOM_PART_DON_ID = "don:core:dvrv-in-1:devo/2sRI6Hepzz:runnable/277"


class BaseEventHandler(ABC):
    """Interface for event handlers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique handler name for logging and results."""
        ...

    @property
    def event_filter(self) -> EventFilter:
        """Override to declare which events this handler processes.
        Default: accept everything."""
        return EventFilter()

    def accepts(self, event: WebhookEvent) -> bool:
        """Check event against declared filter. Override for custom logic."""
        f = self.event_filter
        if f.sources and event.source not in f.sources:
            return False
        if f.event_types and event.event_type not in f.event_types:
            return False
        if f.parts and event.applies_to_part not in f.parts:
            return False
        return True

    @abstractmethod
    async def handle(self, event: WebhookEvent) -> HandlerResult:
        """Process a webhook event and return a result."""
        ...


def _extract_devrev_summary(payload: Dict[str, Any]) -> str:
    """Extract human-readable summary from a DevRev webhook payload.

    DevRev nests event data under the event type key:
    - timeline_entry_created -> .timeline_entry_created.entry
    - work_created -> .work_created.work
    - work_updated -> .work_updated.work (+ .work_updated.old_work)
    """
    event_type = payload.get("type", "")
    parts = []

    # --- timeline_entry events (comments, status changes) ---
    entry_data = payload.get(event_type, {})
    entry = entry_data.get("entry", {})
    if entry:
        # Ticket ID
        obj_id = entry.get("object_display_id", "")
        if obj_id:
            parts.append(obj_id)

        # Who
        who = entry.get("created_by", {}).get("display_name", "")
        if who:
            parts.append(f"by={who}")

        # What kind of entry
        entry_type = entry.get("type", "")
        if entry_type:
            parts.append(entry_type)

        # Body snippet
        body = entry.get("body", "")
        if body:
            clean = body.replace("\n", " ").strip()[:100]
            parts.append(f'"{clean}"')

        return " | ".join(parts) if parts else "(no details)"

    # --- work events (created, updated, deleted) ---
    work = entry_data.get("work", {}) or entry_data.get("old_work", {})
    if work:
        # Ticket ID
        display_id = work.get("display_id", "")
        if display_id:
            parts.append(display_id)

        # Title
        title = work.get("title", "")
        if title:
            parts.append(f'"{title[:80]}"')

        # Who modified
        modified_by = work.get("modified_by", {}).get("display_name", "")
        if modified_by:
            parts.append(f"by={modified_by}")

        # Stage
        stage = work.get("stage", {}).get("name", "")
        if stage:
            parts.append(f"stage={stage}")

        # Owner
        owned_by = work.get("owned_by", [])
        if owned_by:
            owners = [o.get("display_name", "") for o in owned_by if o.get("display_name")]
            if owners:
                parts.append(f"owner={','.join(owners)}")

        # Product/part
        part = work.get("applies_to_part", {}).get("name", "")
        if part:
            parts.append(f"part={part}")

        return " | ".join(parts) if parts else "(no details)"

    return "(no details)"


class AgenticSDLCHandler(BaseEventHandler):
    """Handles tickets assigned to Vyom (RUNN-277) for agentic SDLC execution."""

    name = "agentic_sdlc"

    @property
    def event_filter(self) -> EventFilter:
        return EventFilter(
            parts=[VYOM_PART_DON_ID],
            event_types=["work_created"],
        )

    async def handle(self, event: WebhookEvent) -> HandlerResult:
        ticket = parse_ticket_from_event(event.raw_payload)
        if not ticket:
            logger.warning("agentic_sdlc: could not parse ticket from event")
            return HandlerResult(
                handler_name=self.name, success=False, message="failed to parse ticket"
            )

        if not ticket.repositories:
            logger.warning(
                f"[agentic_sdlc] {ticket.ticket_display_id} has no repositories — skipping submission"
            )
            return HandlerResult(
                handler_name=self.name,
                success=True,
                message="skipped: no repositories in ticket",
            )

        # Build prompt with DevRev ticket reference so Claude can post updates via MCP
        prompt_parts = [
            f"DevRev Ticket: {ticket.ticket_display_id} ({ticket.ticket_id})",
            f"\nTask: {ticket.title}",
            f"\n{ticket.task_description}",
        ]
        if ticket.acceptance_criteria:
            prompt_parts.append(f"\nAcceptance Criteria:\n{ticket.acceptance_criteria}")
        if ticket.extra_context:
            ctx_lines = ["\n---\nAdditional Context:"]
            for section, content in ticket.extra_context.items():
                ctx_lines.append(f"\n{section.replace('_', ' ').title()}:\n{content}")
            prompt_parts.append("\n".join(ctx_lines))
        prompt = "\n".join(prompt_parts)

        repo_urls = [r["repository_url"] for r in ticket.repositories]
        mode = "multi-repo" if len(ticket.repositories) >= 2 else ("single-repo" if ticket.repositories else "clean-slate")
        logger.info(
            f"[agentic_sdlc] {ticket.ticket_display_id} | "
            f'"{ticket.title}" | '
            f"repos={repo_urls} | "
            f"skills={ticket.skills} | "
            f"agent={ticket.agent} | "
            f"mode={mode} | "
            f"submitting to swe-agent API"
        )

        try:
            result = await submit_task(
                repositories=ticket.repositories,
                prompt=prompt,
                skills=ticket.skills,
                agent=ticket.agent,
                source_id=ticket.ticket_display_id,
                connector="devrev",
                user_email=ticket.reporter_email,
            )
            task_id = result.get("task_id", "")
            status = result.get("status", "unknown")
            logger.info(
                f"[agentic_sdlc] {ticket.ticket_display_id} → "
                f"task_id={task_id} status={status}"
            )
            return HandlerResult(
                handler_name=self.name,
                success=status != "failed",
                message=f"task_id={task_id}",
            )
        except Exception as e:
            logger.error(f"[agentic_sdlc] {ticket.ticket_display_id} → API call failed: {e}")
            return HandlerResult(
                handler_name=self.name, success=False, message=str(e)
            )


class LoggingHandler(BaseEventHandler):
    """Logs events matching configured parts with human-readable DevRev context."""

    name = "logging"

    @property
    def event_filter(self) -> EventFilter:
        return EventFilter(
            parts=[VYOM_PART_DON_ID],
        )

    async def handle(self, event: WebhookEvent) -> HandlerResult:
        summary = _extract_devrev_summary(event.raw_payload)
        part_tag = f" part={event.applies_to_part}" if event.applies_to_part else ""
        logger.info(
            f"[{event.source}] {event.event_type}{part_tag} | {summary}"
        )
        return HandlerResult(handler_name=self.name, success=True)
