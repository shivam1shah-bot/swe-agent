"""
Task Processor for SWE Agent worker system.
Handles the actual execution of queued tasks.
"""

import logging
import os
import sys
import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union
from pathlib import Path

# Add the project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.autonomous_agent import AutonomousAgentTool
from src.tasks import task_manager
from src.models.task import TaskStatus
from src.providers.config_loader import get_config
from src.constants.github_bots import GitHubBot, DEFAULT_BOT

logger = logging.getLogger(__name__)


class TaskProcessor:
    """
    Processes different types of SWE Agent tasks.
    Each task type has its own handler method.
    """
    
    def __init__(self):
        """Initialize the task processor with necessary tools."""
        self.config = get_config()
        self.task_handlers = {
            "autonomous_agent": self._handle_autonomous_agent,
            "agents_catalogue_execution": self._handle_agents_catalogue_execution,
            "github_token_refresh": self._handle_github_token_refresh,
            "comment_analysis": self._handle_comment_analysis,
        }
        
        # Initialize tools that might be needed for task processing
        # Let each tool handle its own configuration with sensible defaults
        self.autonomous_agent_tool = AutonomousAgentTool()
        
        # Worker instance for cancellation monitoring
        self.worker_instance = None
        
        logger.info("TaskProcessor initialized")
    
    def set_worker_instance(self, worker_instance):
        """Set worker instance for cancellation monitoring."""
        self.worker_instance = worker_instance
        logger.debug("Worker instance set for task processor")
    
    def _set_thread_local_context(self, task_id: str):
        """Set thread-local context for subprocess tracking.
        
        This allows subprocess execution (e.g., claude_code.py) to access
        the task_id and worker_instance for process registration and cancellation.
        
        Args:
            task_id: The current task ID to set in thread-local storage
        """
        import threading
        current_thread = threading.current_thread()
        current_thread.task_id = task_id
        current_thread.worker_instance = self.worker_instance
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task based on its type.
        
        Args:
            task_data: Task data from the queue
            
        Returns:
            Dict containing the result of task processing
        """
        task_type = task_data.get('task_type', 'unknown')
        task_id = task_data.get('task_id')

        logger.info(f"Processing task {task_id} of type {task_type}")

        # Task types that don't use database tracking
        NO_DB_TRACKING_TYPES = ['comment_analysis']
        uses_db_tracking = task_type not in NO_DB_TRACKING_TYPES

        if not uses_db_tracking:
            logger.info(f"Task {task_id} uses correlation-only tracking (no database updates)")

        try:
            # Check task status BEFORE updating to RUNNING (skip for non-DB tasks)
            if task_id and uses_db_tracking:
                current_status = task_manager.get_task_status(task_id)
                if current_status:
                    # Skip processing if task is already in terminal state
                    terminal_states = ['cancelled', 'failed', 'completed']
                    if current_status.lower() in terminal_states:
                        logger.info(f"Task {task_id} already in terminal state '{current_status}', skipping processing")
                        return {
                            'success': True,  # Return success to delete queue message
                            'skipped': True,
                            'reason': f'task_already_{current_status.lower()}',
                            'task_id': task_id,
                            'task_type': task_type
                        }

                # Update task status to running only if not in terminal state
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.RUNNING,
                    0
                )

            # Additional cancellation check (skip for non-DB tasks)
            if task_id and uses_db_tracking and await self._is_task_cancelled(task_id):
                logger.info(f"Task {task_id} was cancelled before processing started")
                return {
                    'success': True,  # Return success to delete queue message
                    'skipped': True,
                    'reason': 'task_cancelled_before_processing',
                    'task_id': task_id,
                    'task_type': task_type,
                    'cancelled': True
                }
            
            # Route to appropriate handler based on task type
            if task_type in self.task_handlers:
                handler = self.task_handlers[task_type]
                logger.info(f"Found handler for {task_type}: {handler.__name__}")

                # Check if handler is async and await if necessary
                import asyncio
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(task_data)
                else:
                    result = handler(task_data)
                    
                logger.info(f"Handler completed for {task_type}")
            else:
                logger.warning(f"No handler found for {task_type}, using generic")
                result = self._process_generic_task(task_data)
            
            # Check if task was cancelled during processing (skip for non-DB tasks)
            if task_id and uses_db_tracking and await self._is_task_cancelled(task_id):
                logger.info(f"Task {task_id} was cancelled during processing")
                return {
                    'success': False,
                    'error': 'Task was cancelled during processing',
                    'task_id': task_id,
                    'task_type': task_type,
                    'cancelled': True
                }

            # Update task status and save result data (skip for non-DB tasks)
            if task_id and uses_db_tracking and result.get('success', False):
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    100,
                    result  # Save the complete result data
                )
            elif task_id and uses_db_tracking:
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    0,
                    result  # Save the error result data
                )

            # Log result summary for visibility
            if task_id and result.get('success', False):
                inner_result = ((result.get('result') or {}).get('agent_result') or {}).get('result') or {}
                content = inner_result.get('content', '') if isinstance(inner_result, dict) else ''
                if content:
                    logger.info(f"Task {task_id} result summary:\n{content[:500]}")

            # Notify Slack — run in thread executor to avoid blocking the async event loop
            # (_notify_slack performs synchronous DB queries and HTTP requests)
            import asyncio as _asyncio
            loop = _asyncio.get_event_loop()
            await loop.run_in_executor(None, self._notify_slack, task_data, result)

            return result
            
        except Exception as e:
            error_msg = f"Error processing task {task_id}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())

            # Update task status to failed (skip for non-DB tasks)
            if task_id and uses_db_tracking:
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    0
                )
            
            return {
                'success': False,
                'error': error_msg,
                'task_id': task_id,
                'task_type': task_type
            }
    
    async def _is_task_cancelled(self, task_id: str) -> bool:
        """
        Check if a task has been cancelled by querying the database and worker registry.
        
        Args:
            task_id: The task ID to check
            
        Returns:
            True if the task status is 'cancelled', False otherwise
        """
        try:
            # First check worker's cancellation registry (faster)
            if self.worker_instance and self.worker_instance.is_task_cancellation_requested(task_id):
                logger.info(f"Task {task_id} cancellation detected via worker registry")
                return True
            
            # Fall back to database check
            task_status = task_manager.get_task_status(task_id)
            
            if task_status and task_status.lower() == 'cancelled':
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check cancellation status for task {task_id}: {e}")
            return False  # Assume not cancelled if we can't check

    @staticmethod
    def _extract_inner_failure(result: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Return a failure message if the task result contains a silent inner failure,
        or None when the result is genuinely successful.

        Outer success=True can mask agent-level failures.  Three nested paths are
        checked in order of specificity:

        Path 1 — direct inner failure
            result['result']['success'] == False
            → message / error from that dict

        Path 2 — agents_catalogue wrapper (clean-slate, catalogue tasks)
            result['result']['agent_result']['success'] == False
            → error / message from agent_result, fallback to parent message

        Path 3 — Claude Code stream-json is_error flag
            result['result']['result']['raw_response']['is_error'] == True
            → result text from claude_raw or raw_response
        """
        inner_result = (result or {}).get('result') or {}
        if not isinstance(inner_result, dict):
            return None

        # Path 1
        if not inner_result.get('success', True):
            return (
                inner_result.get('message')
                or inner_result.get('error')
                or 'Task failed internally'
            )

        # Path 2
        agent_result = inner_result.get('agent_result') or {}
        if isinstance(agent_result, dict) and not agent_result.get('success', True):
            return (
                agent_result.get('error')
                or agent_result.get('message')
                or inner_result.get('message')
                or 'Task failed internally'
            )

        # Path 3
        claude_raw = inner_result.get('result') or {}
        if isinstance(claude_raw, dict):
            raw_resp = claude_raw.get('raw_response') or {}
            if isinstance(raw_resp, dict) and raw_resp.get('is_error'):
                msg = (
                    claude_raw.get('result')
                    or raw_resp.get('result')
                    or 'Claude execution reported an error'
                )
                return str(msg)[:500] if isinstance(msg, str) else 'Claude execution reported an error'

        return None

    def _notify_slack(self, task_data: Dict[str, Any], result: Optional[Dict[str, Any]]) -> None:
        """
        Post a threaded completion notification to Slack when a task finishes.

        Uses chat.postMessage with thread_ts to reply in the same thread as the
        original "Task queued" message. Falls back to response_url if no thread_ts.
        Converts Markdown to Slack mrkdwn format before posting.
        """
        logger.info(f"_notify_slack called for task {task_data.get('task_id')}")
        try:
            metadata = task_data.get('metadata') or {}
            response_url = metadata.get('slack_response_url', '')
            channel_id = metadata.get('slack_channel_id', '')
            thread_ts = metadata.get('slack_thread_ts', '')
            task_id = task_data.get('task_id', 'unknown')

            # Read slack_notify_channel from task_metadata (set from dashboard Schedule)
            slack_notify_channel = ""
            try:
                import json as _json
                from src.providers.database.connection import get_engine as _get_engine
                from sqlalchemy import text as _text
                _engine = _get_engine()
                with _engine.connect() as _conn:
                    _row = _conn.execute(_text("SELECT task_metadata FROM tasks WHERE id=:id"), {"id": task_id}).fetchone()
                    if _row and _row[0]:
                        _meta = _json.loads(_row[0])
                        slack_notify_channel = _meta.get("slack_notify_channel", "")
            except Exception as _e:
                logger.warning(f"Could not read slack_notify_channel: {_e}")

            logger.info(f"_notify_slack: response_url={bool(response_url)} channel_id={bool(channel_id)} slack_notify_channel={slack_notify_channel!r} post_channel will be={channel_id or slack_notify_channel!r}")
            if not response_url and not channel_id and not slack_notify_channel:
                return

            success = bool(result and result.get('success', False))
            ticket_id = metadata.get('devrev_ticket_id', '')
            ticket_link = f"<https://app.devrev.ai/razorpay/works/{ticket_id}|{ticket_id}>" if ticket_id else ""

            # Detect silent inner failures even when the outer success flag is True.
            inner_failure_msg = self._extract_inner_failure(result) if success else None
            if inner_failure_msg:
                success = False

            if success:
                outer = (result or {}).get('result') or {}

                # agents_catalogue_execution path: outer['agent_result']['result']['content']
                agent_result = outer.get('agent_result') or {}
                inner = agent_result.get('result') or {}
                claude_text = inner.get('content', '') if isinstance(inner, dict) else ''

                # autonomous_agent path (ticket command): outer['result']['content']
                if not claude_text:
                    inner2 = outer.get('result') or {}
                    claude_text = inner2.get('content', '') if isinstance(inner2, dict) else ''

                from src.providers.slack.provider import md_to_slack
                import re

                # Extract GitHub PR links
                pr_links = re.findall(r'https://github\.com/[^\s\)>]+/pull/\d+', claude_text)
                pr_section = ''
                if pr_links:
                    unique_prs = list(dict.fromkeys(pr_links))
                    pr_lines = '\n'.join(f'• <{url}|{url.split("/")[-3]}/pull/{url.split("/")[-1]}>' for url in unique_prs)
                    pr_section = f"\n\n*PRs Created:*\n{pr_lines}"

                header = ":white_check_mark: *Task completed!*"
                if ticket_link:
                    header += f"  |  *Ticket:* {ticket_link}"

                if claude_text and claude_text.strip():
                    # Strip leading completion status lines
                    _completion_kw = ('task completed', 'successfully completed', '✅', ':white_check_mark:', 'task complete')
                    lines = claude_text.strip().splitlines()
                    while lines and (
                        not lines[0].strip() or
                        any(kw in lines[0].lower() for kw in _completion_kw)
                    ):
                        lines.pop(0)
                    claude_text = '\n'.join(lines).strip()
                    formatted = md_to_slack(claude_text)
                    sum_lines = formatted.splitlines()
                    while sum_lines and (
                        not sum_lines[0].strip() or
                        any(kw in sum_lines[0].lower() for kw in _completion_kw)
                    ):
                        sum_lines.pop(0)
                    formatted = '\n'.join(sum_lines).strip()
                    text = f"{header}\n\n{formatted[:2500]}{pr_section}"
                    # Store remaining content for thread chunks
                    overflow = formatted[2500:] if len(formatted) > 2500 else ''
                else:
                    text = f"{header}{pr_section if pr_section else ''}"
                    overflow = ''
            else:
                header = ":x: *Task failed.*"
                if ticket_link:
                    header += f"  |  *Ticket:* {ticket_link}"

                # Build the error detail from most-specific to least-specific source:
                # 1. inner_failure_msg  — detected from nested result (silent failure)
                # 2. result['error']    — explicit error key on outer result
                # 3. result['message']  — message field that may describe the failure
                error_detail = (
                    inner_failure_msg
                    or (result or {}).get('error')
                    or (result or {}).get('message')
                    or 'Unknown error'
                )
                text = f"{header}\nError: {str(error_detail)[:500]}"
                overflow = ''

            # Post/update result via Slack API.
            # If there's a thinking_ts (from @mention), update that message instead of posting new.
            thinking_ts = metadata.get('slack_thinking_ts', '')
            # For dashboard-scheduled tasks, use slack_notify_channel as the target
            post_channel = channel_id or slack_notify_channel
            posted = False
            if post_channel and (thread_ts or thinking_ts or slack_notify_channel):
                try:
                    import requests as _requests
                    bot_token = self.config.get('slack', {}).get('bot_token', '')
                    if bot_token:
                        headers = {
                            'Authorization': f'Bearer {bot_token}',
                            'Content-Type': 'application/json; charset=utf-8',
                        }
                        _requests.post(
                            'https://slack.com/api/conversations.join',
                            headers=headers, json={'channel': post_channel}, timeout=5.0,
                        )
                        # Update the "Thinking..." message if from @mention, else post new
                        if thinking_ts:
                            resp = _requests.post(
                                'https://slack.com/api/chat.update',
                                headers=headers,
                                json={'channel': post_channel, 'ts': thinking_ts, 'text': text},
                                timeout=10.0,
                            )
                        else:
                            msg_body = {'channel': post_channel, 'text': text}
                            if thread_ts:
                                msg_body['thread_ts'] = thread_ts
                            resp = _requests.post(
                                'https://slack.com/api/chat.postMessage',
                                headers=headers, json=msg_body, timeout=10.0,
                            )
                        resp_data = resp.json()
                        if resp_data.get('ok'):
                            posted = True
                            # Get thread_ts of the posted message for overflow chunks
                            parent_ts = resp_data.get('ts') or thinking_ts or thread_ts

                            # Post remaining content in thread chunks (2500 chars each)
                            if success and overflow and parent_ts:
                                chunk_size = 2500
                                remaining = overflow
                                chunk_num = 1
                                while remaining.strip():
                                    # Split on paragraph boundary if possible
                                    chunk = remaining[:chunk_size]
                                    split_at = chunk.rfind('\n\n')
                                    if split_at > chunk_size // 2:
                                        chunk = remaining[:split_at]
                                        remaining = remaining[split_at:].strip()
                                    else:
                                        remaining = remaining[chunk_size:].strip()
                                    chunk_num += 1
                                    _requests.post(
                                        'https://slack.com/api/chat.postMessage',
                                        headers=headers,
                                        json={'channel': post_channel, 'text': chunk.strip(), 'thread_ts': parent_ts},
                                        timeout=10.0,
                                    )
                        else:
                            logger.warning(f"Slack post failed: {resp.json().get('error')}")
                except Exception as e:
                    logger.warning(f"Slack post failed: {e}")

            if not posted and response_url:
                try:
                    import requests as _requests
                    _requests.post(
                        response_url,
                        json={"text": text, "response_type": "in_channel"},
                        timeout=10.0,
                    )
                except Exception as e:
                    logger.warning(f"Slack response_url fallback failed for task {task_id}: {e}")

            logger.info(f"Slack completion notification sent for task {task_id}")

            # Clean up Slack attachment files from EFS after task completes
            attachment_paths = metadata.get("slack_attachment_paths", [])
            if attachment_paths:
                import os as _os
                for path in attachment_paths:
                    try:
                        if path and _os.path.exists(path):
                            _os.remove(path)
                            logger.info(f"Deleted Slack attachment: {path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete Slack attachment {path}: {e}")

        except Exception as exc:
            logger.warning(f"Failed to send Slack notification for task {task_data.get('task_id')}: {exc}", exc_info=True)

    async def _handle_autonomous_agent(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an autonomous agent task with cancellation support."""
        try:
            task_id = task_data.get('task_id')
            logger.info(f"Processing autonomous agent task {task_id}")
            
            # Set thread-local context for subprocess tracking
            self._set_thread_local_context(task_id)
            
            # Extract parameters from task data
            parameters = task_data.get('parameters', {})
            
            # Create context from task data for consistency and logging correlation
            from src.providers.context import ContextManager, TaskContextRegistry, WORKER_CONTEXT
            
            ctx = ContextManager.create_task_context(task_data)
            
            # Enhance context with worker instance for subprocess tracking
            enhanced_worker_context = ctx.get(WORKER_CONTEXT, {})
            enhanced_worker_context.update({
                "worker_instance": self.worker_instance,
                "worker_id": self.worker_instance.worker_id if self.worker_instance else None
            })
            ctx = ctx.with_value(WORKER_CONTEXT, enhanced_worker_context)
            
            # Register context for cross-thread access
            TaskContextRegistry.register_task_context(task_id, ctx)
            
            # Add cancellation support with 15 minute timeout for autonomous agent tasks
            ctx, cancel = ctx.with_timeout(900.0).with_cancel()
            
            # Get logging context for correlation
            log_ctx = ctx.get_logging_context()
            
            # Required parameters for autonomous agent
            required_params = ['repository_url', 'task_description']
            for param in required_params:
                if param not in parameters:
                    logger.error(f"Missing required parameter: {param}", extra=log_ctx)
                    return {
                        'success': False,
                        'error': f"Missing required parameter: {param}",
                        'task_id': task_id
                    }
            
            # Check for cancellation before starting
            if task_id and await self._is_task_cancelled(task_id):
                logger.info(f"Autonomous agent task {task_id} was cancelled before execution", extra=log_ctx)
                return {
                    'success': False,
                    'error': 'Task was cancelled before execution',
                    'task_id': task_id,
                    'cancelled': True
                }
            
            # Check context before execution
            if ctx.done():
                if ctx.is_cancelled():
                    error_msg = "Context was cancelled before autonomous agent execution"
                elif ctx.is_expired():
                    error_msg = "Context expired before autonomous agent execution"
                else:
                    error_msg = "Context is done before autonomous agent execution"
                
                logger.warning(error_msg, extra=log_ctx)
                return {
                    'success': False,
                    'error': error_msg,
                    'task_id': task_id,
                    'correlation_id': ctx.get('log_correlation_id')
                }
            
            # Execute the autonomous agent with cancellation awareness
            # Note: The actual tool execution is synchronous, but we can check
            # for cancellation before and after the main execution
            logger.info(f"Starting autonomous agent execution for task {task_id}", extra=log_ctx)
            
            # Add task_id and agent_name to parameters for logging and metrics
            execution_parameters = parameters.copy()
            execution_parameters["task_id"] = task_id

            # Propagate agent identity for Claude metrics tracking.
            # The task metadata carries `usecase_name` from the API request;
            # fall back to the task_type so the label is never "unknown".
            metadata = task_data.get('metadata', {})
            execution_parameters.setdefault(
                "agent_name",
                metadata.get('usecase_name') or task_data.get('task_type', 'autonomous-agent'),
            )

            # Execute the autonomous agent
            result = self.autonomous_agent_tool.execute(execution_parameters)
            
            # Check for cancellation after execution
            if task_id and await self._is_task_cancelled(task_id):
                logger.info(f"Autonomous agent task {task_id} was cancelled after execution", extra=log_ctx)
                return {
                    'success': False,
                    'error': 'Task was cancelled after execution',
                    'task_id': task_id,
                    'cancelled': True
                }
            
            # Check context status after execution
            if ctx.done():
                if ctx.is_cancelled():
                    logger.warning(f"Autonomous agent execution completed but context was cancelled", extra=log_ctx)
                elif ctx.is_expired():
                    logger.warning(f"Autonomous agent execution completed but context expired", extra=log_ctx)
            
            # Guard: propagate inner failure to the task layer.
            # Without this, a dict like {"success": False, "error": "..."} returned
            # by _run_agent() would be silently wrapped as success=True below.
            if isinstance(result, dict) and not result.get('success', True):
                error_msg = result.get('error', 'Autonomous agent execution failed')
                logger.error(f"Autonomous agent task {task_id} failed: {error_msg}", extra=log_ctx)
                return {
                    'success': False,
                    'error': error_msg,
                    'result': result,
                    'task_id': task_id,
                    'correlation_id': ctx.get('log_correlation_id')
                }

            logger.info(f"Autonomous agent task {task_id} completed successfully", extra=log_ctx)
            return {
                'success': True,
                'result': result,
                'message': 'Autonomous agent task completed',
                'task_id': task_id,
                'correlation_id': ctx.get('log_correlation_id')
            }
            
        except Exception as e:
            # Try to get correlation context even if context creation failed
            correlation_id = None
            try:
                if 'ctx' in locals():
                    correlation_id = ctx.get('log_correlation_id')
            except:
                pass
                
            logger.error(f"Error in autonomous agent task: {e}", extra={'correlation_id': correlation_id})
            return {
                'success': False,
                'error': str(e),
                'task_id': task_data.get('task_id'),
                'correlation_id': correlation_id
            }
        finally:
            # Clean up task context registry
            task_id = task_data.get('task_id')
            if task_id:
                TaskContextRegistry.cleanup_task(task_id)
    
    async def _handle_agents_catalogue_execution(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an agents catalogue execution task with cancellation support."""
        try:
            task_id = task_data.get('task_id')
            logger.info(f"Processing agents catalogue execution task {task_id}")
            
            # Set thread-local context for subprocess tracking
            self._set_thread_local_context(task_id)
            
            parameters = task_data.get('parameters', {})
            metadata = task_data.get('metadata', {})
            usecase_name = metadata.get('usecase_name', 'unknown')
            
            logger.info(f"Executing agents catalogue service: {usecase_name}")
            
            # Check for cancellation before starting
            if task_id and await self._is_task_cancelled(task_id):
                logger.info(f"Agents catalogue task {task_id} was cancelled before execution")
                return {
                    'success': False,
                    'error': 'Task was cancelled before execution',
                    'task_id': task_id,
                    'cancelled': True
                }
            
            # Create context from task data using the new context system
            from src.providers.context import ContextManager, TaskContextRegistry, WORKER_CONTEXT

            ctx = ContextManager.create_task_context(task_data)

            # Enhance context with worker instance for subprocess tracking
            enhanced_worker_context = ctx.get(WORKER_CONTEXT, {})
            enhanced_worker_context.update({
                "worker_instance": self.worker_instance,
                "worker_id": self.worker_instance.worker_id if self.worker_instance else None
            })
            ctx = ctx.with_value(WORKER_CONTEXT, enhanced_worker_context)

            # Register context for cross-thread access
            TaskContextRegistry.register_task_context(task_id, ctx)
            logger.debug(f"Enhanced context registered for task {task_id}")
            
            # Add cancellation support with 10 minute timeout for agents catalogue tasks
            ctx, cancel = ctx.with_timeout(600.0).with_cancel()
            
            # Log with correlation context
            log_ctx = ctx.get_logging_context()
            logger.info(f"Created execution context for agents catalogue task", extra=log_ctx)
            
            # Get the service from the registry
            import src.services.agents  # noqa: F401 — ensures agent services are registered
            from src.services.agents_catalogue import get_service_for_usecase
            
            service = get_service_for_usecase(usecase_name)
            
            if not service:
                error_msg = f"Service '{usecase_name}' not found in registry"
                logger.error(error_msg, extra=log_ctx)
                return {
                    'success': False,
                    'error': error_msg,
                    'task_id': task_id
                }

            logger.info(f"Found service: {service.__class__.__name__}", extra=log_ctx)
            
            # Check context before execution
            if ctx.done():
                if ctx.is_cancelled():
                    error_msg = "Context was cancelled before service execution"
                elif ctx.is_expired():
                    error_msg = "Context expired before service execution"
                else:
                    error_msg = "Context is done before service execution"
                
                logger.warning(error_msg, extra=log_ctx)
                return {
                    'success': False,
                    'error': error_msg,
                    'task_id': task_id,
                    'context_status': service.get_context_status(ctx) if hasattr(service, 'get_context_status') else {}
                }
            
            # Execute the service's async_execute method with context
            logger.info(f"Executing service with context", extra=log_ctx)
            # Handle both sync and async implementations
            import asyncio
            if asyncio.iscoroutinefunction(service.async_execute):
                service_result = await service.async_execute(parameters, ctx)
            else:
                service_result = service.async_execute(parameters, ctx)
            
            # Check for cancellation after execution
            if task_id and await self._is_task_cancelled(task_id):
                logger.info(f"Agents catalogue task {task_id} was cancelled after execution", extra=log_ctx)
                return {
                    'success': False,
                    'error': 'Task was cancelled after execution',
                    'task_id': task_id,
                    'cancelled': True
                }
            
            # Check context status after execution
            if ctx.done():
                context_status = service.get_context_status(ctx) if hasattr(service, 'get_context_status') else {}
                
                if ctx.is_cancelled():
                    logger.warning(f"Service execution completed but context was cancelled", extra=log_ctx)
                    return {
                        'success': False,
                        'error': 'Context was cancelled during execution',
                        'task_id': task_id,
                        'result': service_result,
                        'context_status': context_status
                    }
                elif ctx.is_expired():
                    logger.warning(f"Service execution completed but context expired", extra=log_ctx)
                    return {
                        'success': False,
                        'error': 'Context expired during execution',
                        'task_id': task_id,
                        'result': service_result,
                        'context_status': context_status
                    }
            
            logger.info(f"Service execution completed for {usecase_name}", extra=log_ctx)
            
            # Consider 'completed' as successful status (config_generated is now handled via workflow_type)
            successful_statuses = ['completed']
            success_status = service_result.get('status') in successful_statuses
            logger.info(f"Agents catalogue service {usecase_name} completed successfully: {success_status}", extra=log_ctx)
            
            return {
                'success': service_result.get('status') in successful_statuses,
                'result': service_result,
                'message': f'Agents catalogue execution completed for {usecase_name}',
                'task_id': task_id,
                'correlation_id': ctx.get('log_correlation_id')
            }
            
        except Exception as e:
            logger.error(f"Error in agents catalogue execution: {e}")
            return {
                'success': False,
                'error': str(e),
                'task_id': task_data.get('task_id')
            }
        finally:
            # Clean up task context registry
            task_id = task_data.get('task_id')
            if task_id:
                TaskContextRegistry.cleanup_task(task_id)
    
    def _process_generic_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a generic/unknown task type."""
        try:
            logger.info(f"Processing generic task: {task_data.get('task_type', 'unknown')}")
            
            # For generic tasks, just return success with the input data
            result = {
                'processed': True,
                'input_data': task_data.get('parameters', {}),
                'timestamp': datetime.now().isoformat()
            }
            
            return {
                'success': True,
                'result': result,
                'message': f"Generic task {task_data.get('task_type', 'unknown')} completed",
                'task_id': task_data.get('task_id')
            }
            
        except Exception as e:
            logger.error(f"Error in generic task: {e}")
            return {
                'success': False,
                'error': str(e),
                'task_id': task_data.get('task_id')
            }
    
    async def _handle_github_token_refresh(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle GitHub token refresh task with smart TTL-based refresh logic.
        
        Only refreshes token if it expires within 15 minutes, otherwise reschedules.
        Supports queue-only operation without database overhead.
        
        Args:
            task_data: Task data from the queue
            
        Returns:
            Dict containing the result of token refresh processing
        """
        task_id = task_data.get('task_id', 'github_token_refresh')
        
        try:
            logger.info(f"Processing GitHub token refresh task {task_id}")
            
            # Import here to avoid circular imports
            import asyncio
            import json
            import time
            from datetime import datetime, timezone, timedelta
            from src.providers.cache.redis_client import get_redis_client
            
            cache = get_redis_client()
            environment = self.config.get("environment", {}).get("name", "dev")
            
            # Check if this is a queue-only task (no database operations)
            parameters = task_data.get('parameters', {})
            is_queue_only = parameters.get('queue_only', False)
            
            # Update task status in DB only for non-queue-only tasks (e.g., manual triggers)
            if not is_queue_only:
                task_manager.update_task_status(task_id, TaskStatus.RUNNING, 0)

            # Get bot name from parameters or use default
            # Convert string back to enum if serialized via JSON/SQS
            bot_name_raw = parameters.get('bot_name', DEFAULT_BOT)
            if isinstance(bot_name_raw, str):
                bot_name = GitHubBot(bot_name_raw)
            else:
                bot_name = bot_name_raw

            # Check current token TTL first (bot-specific keys)
            cache_key = f"github:token:{bot_name.value if hasattr(bot_name, 'value') else bot_name}"
            metadata_key = f"github:token:metadata:{bot_name.value if hasattr(bot_name, 'value') else bot_name}"
            cached_token = cache.get(cache_key)
            cached_metadata = cache.get(metadata_key)

            if cached_token:
                token_ttl = cache.get_ttl(cache_key)

                # Guard against None (Redis error), -1 (no expiry), -2 (key not found)
                if token_ttl is None or token_ttl < 0:
                    token_ttl = 0  # Treat as expired - trigger immediate refresh

                logger.info(f"Current token TTL for {bot_name}: {token_ttl} seconds ({token_ttl // 60} minutes)")

                # Only refresh if token expires within 15 minutes (900 seconds)
                if token_ttl > 900:
                    logger.info(f"Token still has {token_ttl // 60} minutes left, rescheduling check")

                    # Schedule next check in 10 minutes using direct queue submission
                    success = await self._schedule_next_refresh_check(delay_seconds=600, bot_name=bot_name)
                    
                    result = {
                        'success': True,
                        'action': 'rescheduled',
                        'message': f'Token has {token_ttl // 60} minutes remaining, rescheduled check',
                        'task_id': task_id,
                        'ttl_remaining_seconds': token_ttl,
                        'ttl_remaining_minutes': token_ttl // 60,
                        'next_check_scheduled': success,
                        'environment': environment
                    }
                    
                    # Update task status for non-queue-only tasks
                    if not is_queue_only:
                        task_manager.update_task_status(
                            task_id, 
                            TaskStatus.COMPLETED, 
                            100, 
                            f"Token still valid, rescheduled check"
                        )
                    
                    return result
            
            logger.info("Token refresh needed - TTL < 15 minutes or no cached token found")

            # Use same logic as GitHubAuthService - check if GitHub app config is available for this bot
            github_app_config = self.config.get("github", {}).get(bot_name.value, {})
            has_github_app = all([
                github_app_config.get("app_id"),
                github_app_config.get("private_key"),
                github_app_config.get("installation_id")
            ])

            # Generate token based on GitHub app availability (not just environment)
            if has_github_app:
                logger.info(f"GitHub app configuration detected for {bot_name} - generating app token")
                result = await self._generate_github_app_token(bot_name=bot_name)
            else:
                logger.info(f"No GitHub app configuration for {bot_name} - trying personal token")
                result = await self._generate_personal_token(bot_name=bot_name)
            
            if not result["success"]:
                logger.error(f"Token generation failed: {result.get('error')}")

                # For failed refresh, try to schedule retry in 5 minutes
                retry_success = await self._schedule_next_refresh_check(delay_seconds=300, bot_name=bot_name)
                
                error_result = {
                    'success': False,
                    'error': result.get('error', 'Token generation failed'),
                    'task_id': task_id,
                    'environment': environment,
                    'retry_scheduled': retry_success
                }
                
                # Update task status for non-queue-only tasks
                if not is_queue_only:
                    task_manager.update_task_status(
                        task_id, 
                        TaskStatus.FAILED, 
                        0, 
                        f"Token refresh failed: {result.get('error')}"
                    )
                
                return error_result
            
            token = result["token"]
            metadata = result.get("metadata", {})
            
            # Calculate proper cache TTL based on actual token expiry
            cache_ttl = 3000  # Default 50 minutes
            
            # For GitHub App tokens, use actual expiry time if available
            if metadata.get('token_type') == 'github_app':
                expires_at_timestamp = metadata.get('expires_at_timestamp')
                if expires_at_timestamp:
                    # Calculate TTL to refresh 5 minutes before actual expiry
                    current_time = int(time.time())
                    time_until_expiry = expires_at_timestamp - current_time
                    # Cache TTL should be 5 minutes less than actual expiry
                    cache_ttl = max(time_until_expiry - 300, 300)  # Minimum 5 minutes
                    logger.info(f"Using calculated cache TTL: {cache_ttl} seconds based on token expiry")

            # Cache the token and metadata (bot-specific keys)
            cache_key = f"github:token:{bot_name.value if hasattr(bot_name, 'value') else bot_name}"
            metadata_key = f"github:token:metadata:{bot_name.value if hasattr(bot_name, 'value') else bot_name}"
            cache.set(cache_key, token, ttl=cache_ttl)
            cache.set(metadata_key, json.dumps(metadata), ttl=cache_ttl)

            logger.info(f"Cached GitHub token for {bot_name} with TTL {cache_ttl} seconds ({cache_ttl // 60} minutes)")

            # Setup CLI tools with new token ONLY if this worker handles this bot
            # This prevents credential collision in multi-bot deployments where
            # different workers handle different GitHub bots
            # Note: DEFAULT_BOT is imported at module level (line 22)
            worker_bot = getattr(self.worker_instance, 'github_bot', DEFAULT_BOT) if self.worker_instance else DEFAULT_BOT

            if bot_name == worker_bot:
                cli_setup_success = await self._setup_cli_tools_with_new_token(bot_name=bot_name)
                if not cli_setup_success:
                    logger.warning(f"CLI tools setup failed after token refresh for {bot_name}")
            else:
                logger.info(f"Skipping CLI setup for {bot_name} - this worker handles {worker_bot}")
                cli_setup_success = True  # Not a failure, just not applicable
            
            # Schedule next check in 10 minutes for all GitHub App tokens
            next_check_scheduled = False
            if metadata.get('token_type') == 'github_app' and token.startswith('ghs_'):
                logger.info("GitHub app token refreshed - scheduling next check in 10 minutes")
                next_check_scheduled = await self._schedule_next_refresh_check(delay_seconds=600, bot_name=bot_name)
            else:
                logger.info(f"Token type '{metadata.get('token_type')}' does not require automatic refresh")
            
            success_result = {
                'success': True,
                'action': 'refreshed',
                'message': 'GitHub token refreshed successfully',
                'task_id': task_id,
                'token_type': metadata.get('token_type', 'unknown'),
                'token_prefix': token[:10] + '...' if len(token) > 10 else token,
                'expires_at': metadata.get('expires_at'),
                'cache_ttl_seconds': cache_ttl,
                'cache_ttl_minutes': cache_ttl // 60,
                'next_check_scheduled': next_check_scheduled,
                'environment': environment,
                'metadata': metadata
            }
            
            # Update task status for non-queue-only tasks
            if not is_queue_only:
                task_manager.update_task_status(
                    task_id, 
                    TaskStatus.COMPLETED, 
                    100, 
                    "Token refreshed successfully"
                )
            
            return success_result

        except Exception as e:
            logger.error(f"GitHub token refresh task failed: {e}")

            # Update task status for non-queue-only tasks
            if not task_data.get('parameters', {}).get('queue_only', False):
                task_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    0,
                    f"Task failed: {str(e)}"
                )

            return {
                'success': False,
                'error': str(e),
                'task_id': task_id
            }

        finally:
            # Clear deduplication flag to allow next scheduling cycle
            try:
                from src.providers.cache.redis_client import get_redis_client

                # Get bot name from parameters
                parameters = task_data.get('parameters', {})
                bot_name_raw = parameters.get('bot_name', DEFAULT_BOT)
                bot_name_str = bot_name_raw.value if hasattr(bot_name_raw, 'value') else bot_name_raw

                cache = get_redis_client()
                dedup_key = f"github:refresh:scheduled:{bot_name_str}"

                deleted = cache.delete(dedup_key)
                if deleted:
                    logger.debug(f"Cleared dedup flag {dedup_key} after task completion")
                else:
                    logger.debug(f"Dedup flag {dedup_key} not found (already expired via TTL)")

            except Exception as e:
                logger.warning(
                    f"Failed to clear dedup flag after task completion: {e}. "
                    "Flag will auto-expire via TTL"
                )
                # Not critical - TTL ensures cleanup
            
    async def _schedule_next_refresh_check(self, delay_seconds: int = 600, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> bool:
        """
        Schedule the next refresh check with deduplication.

        Uses Redis flag to prevent duplicate scheduling across pods.
        Only one refresh task can be scheduled per bot at any time.

        Args:
            delay_seconds: Seconds until task execution (default 600 = 10 min)
            bot_name: GitHub bot to refresh token for

        Returns:
            True if scheduled successfully OR already scheduled (not an error)
            False only on actual failure
        """
        try:
            import time
            import asyncio
            from datetime import datetime, timezone, timedelta
            from src.worker.queue_manager import QueueManager
            from src.providers.cache.redis_client import get_redis_client

            # Extract bot name string
            bot_name_str = bot_name.value if hasattr(bot_name, 'value') else bot_name

            # DEDUPLICATION CHECK
            cache = get_redis_client()
            dedup_key = f"github:refresh:scheduled:{bot_name_str}"

            # Check if already scheduled
            existing = cache.get(dedup_key)
            if existing:
                logger.info(
                    f"GitHub refresh already scheduled for {bot_name_str}, "
                    f"skipping duplicate (dedup_key={dedup_key})"
                )
                return True  # NOT an error - successfully avoided duplicate

            # Set deduplication flag with TTL
            # TTL = delay + grace period (accounts for processing time + jitter)
            ttl = delay_seconds + 120
            cache.set(dedup_key, "scheduled", ttl=ttl)
            logger.debug(f"Set dedup flag {dedup_key} with TTL={ttl}s")

            # Create task data (unchanged from original)
            queue_manager = QueueManager()
            task_data = {
                'task_type': 'github_token_refresh',
                'task_id': f'github-refresh-{bot_name_str}-{int(time.time())}',
                'parameters': {
                    'scheduled_for': (
                        datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                    ).isoformat(),
                    'queue_only': True,
                    'bot_name': bot_name_str,
                    'refresh_cycle': True
                },
                'delay_seconds': delay_seconds,
                'priority': 0,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'submitted_by': 'github_refresh_system'
            }

            # Send to queue
            success = await asyncio.to_thread(queue_manager.send_task, task_data)

            if success:
                logger.info(
                    f"Scheduled GitHub token refresh for {bot_name_str} "
                    f"in {delay_seconds}s (dedup_key={dedup_key}, ttl={ttl}s)"
                )
            else:
                # Failed to send - clear flag so retry can happen
                cache.delete(dedup_key)
                logger.error(
                    f"Failed to send refresh task for {bot_name_str}, "
                    f"cleared dedup flag to allow retry"
                )

            return success

        except Exception as e:
            logger.error(f"Error scheduling next refresh check: {e}", exc_info=True)

            # Clear flag on error to allow retry
            try:
                bot_name_str = bot_name.value if hasattr(bot_name, 'value') else bot_name
                cache = get_redis_client()
                dedup_key = f"github:refresh:scheduled:{bot_name_str}"
                cache.delete(dedup_key)
                logger.debug(f"Cleared dedup flag {dedup_key} after error")
            except Exception as cleanup_error:
                logger.warning(f"Failed to clear dedup flag after error: {cleanup_error}")
                # Not critical - TTL will expire anyway

            return False
    
    async def _generate_github_app_token(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> Dict[str, Any]:
        """
        Generate GitHub App installation token for specified bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum (or string)

        Returns:
            Dict with success status, token, and metadata
        """
        try:
            import jwt
            import aiohttp
            import time
            from datetime import datetime, timezone, timedelta

            # Get GitHub App configuration for specified bot
            app_config = self.config.get("github", {}).get(bot_name.value, {})
            app_id = app_config.get("app_id")
            private_key = app_config.get("private_key")
            installation_id = app_config.get("installation_id")
            
            if not all([app_id, private_key, installation_id]):
                missing = []
                if not app_id:
                    missing.append("app_id")
                if not private_key:
                    missing.append("private_key")
                if not installation_id:
                    missing.append("installation_id")

                return {
                    "success": False,
                    "error": f"GitHub App configuration incomplete for {bot_name} - missing: {', '.join(missing)}"
                }
            
            # Generate JWT token
            # Note: app_id must be a string for JWT issuer field
            now = int(time.time())
            payload = {
                'iat': now,
                'exp': now + 600,  # 10 minutes
                'iss': str(app_id)  # Ensure app_id is string (may be int in config)
            }
            
            # Format private key
            formatted_key = self._format_private_key(private_key)
            if not formatted_key:
                return {
                    "success": False,
                    "error": "Failed to format private key"
                }
            
            # Load private key and generate JWT
            from cryptography.hazmat.primitives import serialization
            try:
                private_key_obj = serialization.load_pem_private_key(
                    formatted_key.encode('utf-8'),
                    password=None,
                )
                jwt_token = jwt.encode(payload, private_key_obj, algorithm='RS256')
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to generate JWT: {str(e)}"
                }
            
            # Get installation token
            url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
            headers = {
                'Authorization': f'Bearer {jwt_token}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'swe-agent'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers) as response:
                    if response.status == 201:
                        data = await response.json()
                        token = data.get('token')
                        expires_at = data.get('expires_at')
                        
                        if not token:
                            return {
                                "success": False,
                                "error": "No token in GitHub API response"
                            }
                        
                        # Parse the expiry time to Unix timestamp for better TTL calculation
                        expires_at_timestamp = None
                        if expires_at:
                            try:
                                from dateutil import parser
                                expiry_dt = parser.isoparse(expires_at)
                                expires_at_timestamp = int(expiry_dt.timestamp())
                                logger.debug(f"GitHub App token expires at: {expires_at} (timestamp: {expires_at_timestamp})")
                            except Exception as e:
                                logger.warning(f"Failed to parse expires_at '{expires_at}': {e}")
                        
                        # Get user information for the app
                        user_info = await self._get_github_app_user_info(token)
                        
                        metadata = {
                            "token_type": "github_app",
                            "expires_at": expires_at,  # Keep original ISO format for display
                            "expires_at_timestamp": expires_at_timestamp,  # Unix timestamp for TTL calculations
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "user_login": user_info.get("login", "razorpay-swe-agent"),
                            "user_email": user_info.get("email", "swe-agent@razorpay.com"),
                            "app_id": app_id,
                            "installation_id": installation_id,
                            "bot_name": bot_name
                        }

                        logger.info(f"Generated GitHub App token for {bot_name}, user: {metadata['user_login']}")
                        
                        return {
                            "success": True,
                            "token": token,
                            "metadata": metadata
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"GitHub API error: HTTP {response.status} - {error_text}"
                        }
                        
        except Exception as e:
            logger.error(f"GitHub App token generation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _generate_personal_token(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> Dict[str, Any]:
        """
        Handle personal token for development environments (bot-specific cache).

        Args:
            bot_name: Bot identifier from GitHubBot enum (or string)

        Returns:
            Dict with success status, token, and metadata
        """
        try:
            from datetime import datetime, timezone

            # Get token from configuration only
            token = self.config.get("github", {}).get("token")
            
            if not token:
                return {
                    "success": False,
                    "error": "No personal token found in configuration (github.token)"
                }
            
            # Validate the token
            user_info = await self._get_github_user_info(token)
            if not user_info:
                return {
                    "success": False,
                    "error": "Failed to validate personal token"
                }
            
            # Detect token type
            token_type = "personal_classic"
            if token.startswith('github_pat_'):
                token_type = "personal_fine_grained"
            
            metadata = {
                "token_type": token_type,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "user_login": user_info.get("login", "unknown"),
                "user_email": user_info.get("email") or f"{user_info.get('login', 'unknown')}@razorpay.com",
                "expires_at": None  # Personal tokens may not have expiry
            }
            
            logger.info(f"Using personal token for user: {metadata['user_login']}")
            
            return {
                "success": True,
                "token": token,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Personal token handling failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_private_key(self, private_key: str) -> Optional[str]:
        """Format and validate private key."""
        try:
            if not private_key or not isinstance(private_key, str):
                logger.error("Private key is empty or not a string")
                return None
            
            # Case 1: Handle literal \n sequences (original format)
            formatted_key = private_key.replace('\\n', '\n')
            
            # Case 2: Handle trailing backslashes followed by newlines (base64 decoded format)
            # Remove trailing backslashes at the end of lines
            if '\\' in formatted_key and '\n' in formatted_key:
                lines = formatted_key.split('\n')
                cleaned_lines = []
                for line in lines:
                    # Remove trailing backslash if present
                    if line.endswith('\\'):
                        cleaned_lines.append(line[:-1])
                    else:
                        cleaned_lines.append(line)
                formatted_key = '\n'.join(cleaned_lines)
                logger.debug("Removed trailing backslashes from private key lines")
            
            # Ensure proper PEM format
            if not formatted_key.startswith('-----BEGIN'):
                logger.error("Private key does not appear to be in PEM format")
                return None
                
            if not formatted_key.endswith('-----END RSA PRIVATE KEY-----\n') and not formatted_key.endswith('-----END PRIVATE KEY-----\n'):
                # Add newline if missing
                if formatted_key.endswith('-----END RSA PRIVATE KEY-----') or formatted_key.endswith('-----END PRIVATE KEY-----'):
                    formatted_key += '\n'
                else:
                    logger.error("Private key does not have proper PEM ending")
                    return None
                
            logger.debug(f"Formatted private key has {len(formatted_key)} characters and {formatted_key.count(chr(10))} newlines")
            
            # Basic validation - check for required PEM structure
            required_parts = ['-----BEGIN', '-----END']
            for part in required_parts:
                if part not in formatted_key:
                    logger.error(f"Private key missing required part: {part}")
                    return None
            
            return formatted_key
            
        except Exception as e:
            logger.error(f"Error formatting private key: {e}")
            return None
    
    async def _get_github_app_user_info(self, token: str) -> Dict[str, Any]:
        """Get user info for GitHub App token."""
        default_info = {
            "login": "razorpay-swe-agent",
            "email": "swe-agent@razorpay.com"
        }
        
        try:
            import aiohttp
            
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'swe-agent'
            }
            
            async with aiohttp.ClientSession() as session:
                # Try to get app installation info
                async with session.get('https://api.github.com/installation/repositories', headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to get GitHub App info: HTTP {response.status}")
                        
        except Exception as e:
            logger.warning(f"Failed to get GitHub App user info: {e}")
        
        return default_info
    
    async def _get_github_user_info(self, token: str) -> Optional[Dict[str, Any]]:
        """Get user info for personal token."""
        try:
            import aiohttp
            
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'swe-agent'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.github.com/user', headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Failed to get user info: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Failed to get GitHub user info: {e}")
            return None
            
    async def _setup_cli_tools_with_new_token(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> bool:
        """
        Setup git and gh CLI tools with newly refreshed token for specified bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum

        Returns:
            True if setup was successful
        """
        try:
            from src.providers.github.auth_service import GitHubAuthService

            auth_service = GitHubAuthService()

            # Setup git config for this bot
            git_result = await auth_service.setup_git_config(bot_name=bot_name)
            git_success = git_result.get("success", False)

            # Setup gh CLI authentication for this bot
            gh_result = await auth_service.ensure_gh_auth(bot_name=bot_name)
            gh_success = gh_result.get("success", False)
            
            overall_success = git_success and gh_success
            
            if overall_success:
                logger.info("CLI tools configured successfully with new token")
            else:
                logger.warning(f"CLI setup partial failure - git: {git_success}, gh: {gh_success}")
                
            return overall_success
            
        except Exception as e:
            logger.error(f"Failed to setup CLI tools: {e}")
            return False
    
    async def _handle_comment_analysis(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle comment analysis task.

        Executes the comment analyzer framework to analyze PR comments
        from AI sub-agents and post GitHub commit status.

        Args:
            task_data: Task data containing repository, pr_number, commit_sha, etc.

        Returns:
            Dict containing success status and result
        """
        try:
            # Extract parameters
            repository = task_data.get("repository")
            pr_number = task_data.get("pr_number")
            commit_sha = task_data.get("commit_sha")
            sub_agent_identifier = task_data.get("sub_agent_identifier", "rcore-v2")
            severity_threshold = task_data.get("severity_threshold", 9)
            blocking_enabled = task_data.get("blocking_enabled", False)
            include_extensions = task_data.get("include_file_extensions", [])
            exclude_extensions = task_data.get("exclude_file_extensions", [])
            exclude_patterns = task_data.get("exclude_file_patterns", [])
            run_url = task_data.get("run_url", "")

            logger.info("="*80)
            logger.info(f"COMMENT ANALYSIS TASK STARTED")
            logger.info("="*80)
            logger.info(f"Repository: {repository}")
            logger.info(f"PR Number: #{pr_number}")
            logger.info(f"Commit SHA: {commit_sha}")
            logger.info(f"Sub-agent Identifier: {sub_agent_identifier}")
            logger.info(f"Severity Threshold: {severity_threshold}")
            logger.info(f"Blocking Enabled: {blocking_enabled}")
            logger.info(f"Include Extensions: {include_extensions}")
            logger.info(f"Exclude Extensions: {exclude_extensions}")
            logger.info(f"Exclude Patterns: {exclude_patterns}")
            logger.info(f"Run URL: {run_url}")
            logger.info("="*80)

            # Get GitHub token
            logger.info("Step 1: Getting GitHub token...")
            from src.providers.github.auth_service import GitHubAuthService
            auth_service = GitHubAuthService()
            github_token = await auth_service.get_token("default")

            if not github_token:
                error_msg = "Failed to get GitHub token"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            logger.info("✓ GitHub token obtained successfully")

            # Import and run the framework orchestrator
            import sys
            import os

            # Environment variables to be set and cleaned up
            ENV_VARS = [
                "GITHUB_TOKEN", "PR_NUMBER", "REPOSITORY", "GITHUB_SHA",
                "SUB_AGENT_IDENTIFIER", "SEVERITY_THRESHOLD", "BLOCKING_ENABLED",
                "INCLUDE_FILE_EXTENSIONS", "EXCLUDE_FILE_EXTENSIONS",
                "EXCLUDE_FILE_PATTERNS", "RUN_URL",
            ]

            try:
                logger.info("\nStep 2: Setting environment variables for framework...")
                # Set environment variables for the framework
                os.environ["GITHUB_TOKEN"] = github_token
                os.environ["PR_NUMBER"] = str(pr_number)
                os.environ["REPOSITORY"] = repository
                os.environ["GITHUB_SHA"] = commit_sha
                os.environ["SUB_AGENT_IDENTIFIER"] = sub_agent_identifier
                os.environ["SEVERITY_THRESHOLD"] = str(severity_threshold)
                os.environ["BLOCKING_ENABLED"] = "true" if blocking_enabled else "false"
                os.environ["INCLUDE_FILE_EXTENSIONS"] = ",".join(include_extensions) if include_extensions else ""
                os.environ["EXCLUDE_FILE_EXTENSIONS"] = ",".join(exclude_extensions) if exclude_extensions else ""
                os.environ["EXCLUDE_FILE_PATTERNS"] = ",".join(exclude_patterns) if exclude_patterns else ""
                os.environ["RUN_URL"] = run_url

                # Run the framework
                logger.info("\nStep 3: Running comment analyzer framework...")
                logger.info("="*80)
                from src.services.comment_analyzer.generic_orchestrator import GenericOrchestrator
                orchestrator = GenericOrchestrator()
                exit_code = orchestrator.run()

                # Check exit code and return appropriate result
                if exit_code == 0:
                    logger.info(
                        f"Comment analysis completed successfully for {repository}#{pr_number}",
                        extra={"repository": repository, "pr_number": pr_number}
                    )
                    return {
                        "success": True,
                        "message": f"Analysis completed for {repository}#{pr_number}"
                    }
                else:
                    logger.error(
                        f"Comment analysis failed (exit {exit_code}) for {repository}#{pr_number}",
                        extra={"repository": repository, "pr_number": pr_number}
                    )
                    return {
                        "success": False,
                        "error": f"Analysis failed with exit code {exit_code}"
                    }

            except SystemExit as e:
                # Catch unexpected SystemExit (should not happen with refactored code)
                logger.error(
                    f"Unexpected SystemExit caught during comment analysis for {repository}#{pr_number}: {e.code}",
                    extra={"repository": repository, "pr_number": pr_number}
                )
                return {
                    "success": False,
                    "error": f"Unexpected exit with code {e.code}"
                }

            except Exception as e:
                error_msg = f"Failed to execute comment analysis: {str(e)}"
                logger.exception(error_msg)
                return {"success": False, "error": error_msg}

            finally:
                # Clean up environment variables to prevent cross-contamination between tasks
                logger.debug("Cleaning up environment variables...")
                for var in ENV_VARS:
                    os.environ.pop(var, None)

        except Exception as e:
            error_msg = f"Failed to execute comment analysis: {str(e)}"
            logger.exception(error_msg)
            return {"success": False, "error": error_msg}

    def get_supported_task_types(self) -> list:
        """Get list of supported task types."""
        return list(self.task_handlers.keys()) + ['generic'] 