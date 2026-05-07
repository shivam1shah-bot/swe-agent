"""
Claude Code tool.
This module provides Claude Code integration for the AI Agent.
"""

import logging
import os
import json
import subprocess
import tempfile
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.tools.base import BaseTool
from src.providers.config_loader import get_config, get_aws_config, get_claude_code_config
from src.utils.process_manager import ProcessManager
from src.providers.telemetry.domain.claude import (
    track_claude_execution,
    track_mcp_interaction,
)

logger = logging.getLogger(__name__)

# Singleton instance
_claude_code_instance = None

# Registry to track MCP registration
_registered_mcps = set()

class ClaudeCodeTool(BaseTool):
    """
    Claude Code Tool.

    Provides access to Claude Code capabilities through the Claude Code SDK.
    """

    @classmethod
    def get_instance(cls, config: Dict[str, Any] = None) -> 'ClaudeCodeTool':
        """
        Get the singleton instance of the Claude Code Tool.

        Args:
            config: Optional configuration for the tool if it doesn't exist ye

        Returns:
            ClaudeCodeTool: The singleton instance
        """
        global _claude_code_instance
        if _claude_code_instance is None:
            logger.info("Creating new ClaudeCodeTool instance")
            _claude_code_instance = cls(config)
        return _claude_code_instance

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Claude Code Tool.

        Args:
            config: Configuration for the Claude Code Tool
        """
        # Initialize config if None
        if config is None:
            config = {}

        super().__init__("claude_code", "Claude Code integration for code generation and analysis", config)

        # Get the path to the MCP configuration file
        self.mcp_config_path = config.get("mcp_config_path") or os.path.join(
            Path(__file__).parent.parent.parent, "providers", "mcp", "mcp-servers.json"
        )

        # Get the allowed tools configuration (using expanded tools set)
        # Note: Wildcards are NOT supported for MCP tools - each tool must be listed explicitly.
        # Tool names sourced from live session init log (mcp_servers connected at runtime).
        # Current total: 112 tools — Anthropic API hard limit is 128.
        self.allowed_tools = config.get("allowed_tools", "Skill,Task,Bash,Glob,Grep,LS,exit_plan_mode,Read,Edit,MultiEdit,Write,NotebookRead,NotebookEdit,TodoWrite,ListMcpResourcesTool,ReadMcpResourceTool,mcp__memory__create_entities,mcp__memory__create_relations,mcp__memory__add_observations,mcp__memory__delete_entities,mcp__memory__delete_observations,mcp__memory__delete_relations,mcp__memory__read_graph,mcp__memory__search_nodes,mcp__memory__open_nodes,mcp__sequentialthinking__sequentialthinking,mcp__grafana__get_alert_rule_by_uid,mcp__grafana__get_annotation_tags,mcp__grafana__get_annotations,mcp__grafana__get_assertions,mcp__grafana__get_dashboard_by_uid,mcp__grafana__get_dashboard_panel_queries,mcp__grafana__get_dashboard_property,mcp__grafana__get_dashboard_summary,mcp__grafana__get_datasource_by_name,mcp__grafana__get_datasource_by_uid,mcp__grafana__get_sift_analysis,mcp__grafana__get_sift_investigation,mcp__grafana__list_alert_rules,mcp__grafana__list_contact_points,mcp__grafana__list_datasources,mcp__grafana__list_prometheus_label_names,mcp__grafana__list_prometheus_label_values,mcp__grafana__list_prometheus_metric_metadata,mcp__grafana__list_prometheus_metric_names,mcp__grafana__list_sift_investigations,mcp__grafana__query_prometheus,mcp__grafana__query_prometheus_histogram,mcp__grafana__search_dashboards,mcp__grafana__search_folders,mcp__devrev-mcp__add_comment,mcp__devrev-mcp__create_contact,mcp__devrev-mcp__create_enhancement,mcp__devrev-mcp__create_incident,mcp__devrev-mcp__create_issue,mcp__devrev-mcp__create_ticket,mcp__devrev-mcp__fetch_object_context,mcp__devrev-mcp__get_enhancement,mcp__devrev-mcp__get_incident,mcp__devrev-mcp__get_issue,mcp__devrev-mcp__get_org_user,mcp__devrev-mcp__get_part,mcp__devrev-mcp__get_self,mcp__devrev-mcp__get_sprint_board,mcp__devrev-mcp__get_ticket,mcp__devrev-mcp__get_tool_metadata,mcp__devrev-mcp__get_valid_stage_transitions,mcp__devrev-mcp__hybrid_search,mcp__devrev-mcp__link_conversation_with_ticket,mcp__devrev-mcp__link_incident_with_issue,mcp__devrev-mcp__link_incident_with_ticket,mcp__devrev-mcp__link_issue_with_issue,mcp__devrev-mcp__link_meeting_with_ticket,mcp__devrev-mcp__link_ticket_with_issue,mcp__devrev-mcp__list_enhancements,mcp__devrev-mcp__list_issues,mcp__devrev-mcp__list_sprint,mcp__devrev-mcp__update_account,mcp__devrev-mcp__update_contact,mcp__devrev-mcp__update_conversation,mcp__devrev-mcp__update_enhancement,mcp__devrev-mcp__update_incident,mcp__devrev-mcp__update_issue,mcp__devrev-mcp__update_opportunity,mcp__devrev-mcp__update_ticket,mcp__blade-mcp__hi_blade,mcp__blade-mcp__create_new_blade_project,mcp__blade-mcp__create_blade_cursor_rules,mcp__blade-mcp__get_blade_component_docs,mcp__blade-mcp__get_blade_pattern_docs,mcp__blade-mcp__get_blade_general_docs,mcp__blade-mcp__get_figma_to_code,mcp__blade-mcp__get_blade_changelog,mcp__blade-mcp__publish_lines_of_code_metric,mcp__slack__channels_list,mcp__slack__conversations_add_message,mcp__slack__conversations_history,mcp__slack__conversations_mark,mcp__slack__conversations_replies,mcp__slack__conversations_search_messages,mcp__slack__conversations_unreads,mcp__slack__usergroups_create,mcp__slack__usergroups_list,mcp__slack__usergroups_me,mcp__slack__usergroups_update,mcp__slack__usergroups_users_update,mcp__slack__users_search,mcp__coralogix-server__get_logs,mcp__coralogix-server__get_datetime,mcp__coralogix-server__get_schemas")

        # Get the max turns configuration (default: 650)
        self.max_turns = config.get("max_turns", 650)

        # Get the output format (default: json)
        self.output_format = config.get("output_format", "json")

        # Set additional environment variables if needed
        self.env_vars = config.get("env_vars", {})

        # Get global config (optional, for other configurations)
        self.global_config = get_config()

        # Get Claude Code agent configuration
        self.claude_config = get_claude_code_config()

        # Claude configuration with sensible defaults, configurable per client
        # These defaults are optimized for production autonomous agent usage
        self.provider = self.claude_config.get("provider", "bedrock")

        self.anthropic_model = config.get("anthropic_model", "claude-sonnet-4-6")  # Latest Claude model

        self.disable_prompt_caching = config.get("disable_prompt_caching", True)  # Disable for consistency

        # Skip permissions configuration (for unattended operation)
        self.skip_permissions = config.get("skip_permissions", True)  # Default to unattended mode

        # MCP debug configuration (for debugging MCP issues)
        self.mcp_debug = config.get("mcp_debug", False)  # Default to production mode (no debug)

        # Silence noisy loggers
        self._configure_logging(config)

        # Check if claude command is available
        self._check_claude_command()

        # Verify and setup MCPs
        self._verify_mcps()

        # Setup Vertex AI credentials if using Vertex AI provider
        if self.provider == "vertex_ai":
            self._setup_vertex_ai_credentials()

        logger.info("Claude Code Tool initialized")

    def _configure_logging(self, config: Dict[str, Any]) -> None:
        """Configure logging to silence noisy loggers."""
        # Get the list of noisy loggers to silence
        noisy_loggers = config.get("silence_loggers", [
            "sqlalchemy.engine",
            "urllib3.connectionpool",
            "botocore.hooks",
            "botocore.auth",
            "botocore.endpoint",
            "botocore.credentials",
            "botocore.utils",
            "httpx"
        ])

        # Set the log level for these loggers to WARNING or higher
        for logger_name in noisy_loggers:
            log = logging.getLogger(logger_name)
            log.setLevel(logging.WARNING)
            # Ensure all handlers also respect this level
            for handler in log.handlers:
                handler.setLevel(logging.WARNING)

        logger.debug(f"Silenced noisy loggers: {', '.join(noisy_loggers)}")

    def _check_claude_command(self):
        """Check if the claude command is available in the system."""
        # Skip for non-worker containers (no claude CLI installed)
        if os.environ.get('CONTAINER_TYPE', 'worker') != 'worker':
            return
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"Claude Code version: {result.stdout.strip()}")
            else:
                logger.warning("Claude Code is not available or returned an error.")
        except Exception as e:
            logger.warning(f"Failed to check Claude Code availability: {e}")

    def _setup_vertex_ai_credentials(self):
        """Setup Vertex AI credentials file during initialization."""
        try:
            gcp_config = self.claude_config.get("gcp", {})
            credentials_json = gcp_config.get("credentials_json")

            if not credentials_json:
                logger.warning("Vertex AI provider selected but no GCP credentials found in config")
                return

            # Write credentials to the default path
            default_creds_path = "/root/.config/gcloud/application_default_credentials.json"
            os.makedirs(os.path.dirname(default_creds_path), exist_ok=True)

            with open(default_creds_path, 'w') as f:
                f.write(credentials_json)

            logger.info(f"Vertex AI credentials written to {default_creds_path}")

            # Set environment variable for all future subprocess calls
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = default_creds_path

        except Exception as e:
            logger.error(f"Failed to setup Vertex AI credentials: {e}")

    def _verify_mcps(self):
        """Verify that all MCPs from mcp-servers.json are properly registered."""
        # Skip for non-worker containers (no claude CLI installed)
        if os.environ.get('CONTAINER_TYPE', 'worker') != 'worker':
            return
        try:
            # Read the MCPs from the config file
            with open(self.mcp_config_path, 'r') as f:
                mcp_config = json.load(f)

            if "mcpServers" not in mcp_config:
                logger.warning(f"Invalid MCP config file format: {self.mcp_config_path}")
                return

            # Check if GitHub token is available for GitHub MCP
            if "github" in mcp_config["mcpServers"]:
                github_token = self.global_config.get("github.token")
                if not github_token:
                    logger.error("GitHub MCP is configured but GitHub token is missing from configuration.")

            # Force re-registration of MCPs if specified in config
            force_reset = self.config.get("force_reset_mcps", False)
            if force_reset:
                logger.info("Forcing reset of all MCPs")
                self._reset_mcps()

            # Get list of currently registered MCPs
            registered_mcps = self._get_registered_mcps()

            # Compare and add missing MCPs, track outcomes
            already_registered = []
            newly_registered = []
            failed_to_register = []

            for mcp_name, mcp_def in mcp_config["mcpServers"].items():
                if mcp_name in registered_mcps:
                    already_registered.append(mcp_name)
                else:
                    logger.info(f"Adding missing MCP: {mcp_name}")
                    self._add_mcp(mcp_name, mcp_def)
                    # Check if registration succeeded
                    if self.is_mcp_registered(mcp_name):
                        newly_registered.append(mcp_name)
                    else:
                        failed_to_register.append(mcp_name)

            # Summary log
            total = len(mcp_config["mcpServers"])
            logger.info(
                f"MCP verification complete: {total} configured, "
                f"{len(already_registered)} already registered, "
                f"{len(newly_registered)} newly registered, "
                f"{len(failed_to_register)} failed",
                extra={
                    "already_registered": already_registered,
                    "newly_registered": newly_registered,
                    "failed_to_register": failed_to_register,
                }
            )
            if failed_to_register:
                logger.warning(
                    f"Failed to register MCPs: {failed_to_register}. "
                    f"Skills depending on these MCPs will have degraded functionality."
                )

        except Exception as e:
            logger.exception(f"Error verifying MCPs: {e}")

    def _get_registered_mcps(self) -> List[str]:
        """Get a list of currently registered MCPs."""
        try:
            with track_mcp_interaction("all", action="list"):
                result = subprocess.run(
                    ["claude", "mcp", "list"],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    logger.warning(f"Failed to list MCPs: {result.stderr}")
                    return []

                # Parse the list output to get registered MCPs
                registered_mcps = []
                for line in result.stdout.strip().split('\n'):
                    if not line or line.startswith("Usage:") or "No MCP servers" in line:
                        continue

                    # Extract MCP name (everything before the first colon)
                    mcp_name = line.split(':', 1)[0].strip()
                    if mcp_name:
                        registered_mcps.append(mcp_name)

                return registered_mcps

        except Exception as e:
            logger.warning(f"Error getting registered MCPs: {e}")
            return []

    def _reset_mcps(self):
        """Remove all previously registered MCPs so the next run starts clean."""
        try:
            registered_mcps = self._get_registered_mcps()

            # Track per-MCP outcomes and log a single summary after the loop
            removed, failed = [], []
            for mcp_name in registered_mcps:
                with track_mcp_interaction(mcp_name, action="remove"):
                    remove_cmd = ["claude", "mcp", "remove", mcp_name]
                    remove_result = subprocess.run(remove_cmd, capture_output=True, text=True)
                    if remove_result.returncode == 0:
                        removed.append(mcp_name)
                    else:
                        failed.append((mcp_name, remove_result.stderr.strip()))

            if failed:
                logger.warning(f"Failed to remove {len(failed)} MCPs: {failed}")

        except Exception as e:
            logger.exception(f"Error resetting MCPs: {e}")

    def _add_mcp(self, mcp_name: str, mcp_def: Dict[str, Any]):
        """
        Register a single MCP with the Claude CLI.

        Supports three transport types:
          - streamable-http / http  — HTTP transport with optional auth headers
          - sse                     — Server-Sent Events transport
          - stdio (default)         — subprocess-based transport

        Environment variable references (``${VAR}``) in header values and env
        blocks are resolved at registration time.  Missing vars are logged as a
        batch summary *after* the loop rather than per-iteration to avoid
        excessive log volume.
        """
        try:
            if self.is_mcp_registered(mcp_name):
                return

            with track_mcp_interaction(mcp_name, action="add"):
                import copy
                mcp_def_copy = copy.deepcopy(mcp_def)

                cmd = ["claude", "mcp", "add"]
                transport_type = mcp_def_copy.get("type", "stdio")

                # --- HTTP / streamable-http transport ---
                if transport_type == "streamable-http" or mcp_def_copy.get("streamable"):
                    cmd.extend(["--transport", "http"])
                    url = mcp_def_copy.get("url")
                    if not url:
                        logger.error(f"HTTP MCP {mcp_name} missing required 'url' field")
                        return
                    cmd.extend([mcp_name, url])

                    # Resolve env-var placeholders in headers and attach to command
                    headers = mcp_def_copy.get("headers", {})
                    cmd, missing = self._resolve_and_attach_headers(cmd, headers)
                    if missing:
                        logger.warning(f"MCP {mcp_name}: unresolved env vars in HTTP headers: {missing}")

                # --- SSE transport ---
                elif transport_type == "sse":
                    cmd.extend(["--transport", "sse"])
                    url = mcp_def_copy.get("url")
                    if not url:
                        logger.error(f"SSE MCP {mcp_name} missing required 'url' field")
                        return
                    cmd.extend([mcp_name, url])

                    headers = mcp_def_copy.get("headers", {})
                    cmd, missing = self._resolve_and_attach_headers(cmd, headers)
                    if missing:
                        logger.warning(f"MCP {mcp_name}: unresolved env vars in SSE headers: {missing}")

                # --- STDIO transport (default) ---
                else:
                    command = mcp_def_copy.get("command")
                    args = mcp_def_copy.get("args", [])
                    if not command:
                        logger.error(f"STDIO MCP {mcp_name} missing required 'command' field")
                        return

                    is_mcp_remote = (command == "npx" and args and args[0] == "mcp-remote")

                    # Build the name + command portion first, then attach env vars.
                    # Claude CLI expects: claude mcp add <name> -e KEY=val -- <command> <args>
                    # mcp-remote servers inherit env from the process, so skip -e.
                    env_vars = mcp_def_copy.get("env", {})
                    cmd.append(mcp_name)
                    if env_vars and not is_mcp_remote:
                        cmd, missing = self._resolve_and_attach_env_vars(cmd, mcp_name, env_vars)
                        if missing:
                            logger.warning(f"MCP {mcp_name}: unresolved env vars: {missing}")
                    cmd.extend(["--", command] + args)

                # Execute the registration command
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0 or "already exists" in result.stderr:
                    self.mark_mcp_registered(mcp_name)
                else:
                    logger.warning(f"Failed to add MCP {mcp_name}: {result.stderr}")

        except Exception as e:
            logger.exception(f"Error adding MCP {mcp_name}: {e}")

    # ------------------------------------------------------------------
    # Helpers — keep env-var resolution out of _add_mcp to reduce noise
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_env_placeholder(value: str) -> tuple:
        """
        If *value* is an env-var placeholder (``${VAR}``), resolve it.

        Returns:
            (resolved_value, env_var_name_or_None)
            *env_var_name* is non-None only when the placeholder could NOT
            be resolved, signaling the caller to collect it for a batch log.
        """
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var_name = value[2:-1]
            actual = os.getenv(env_var_name)
            if actual:
                return actual, None
            return value, env_var_name  # unresolved
        return value, None

    def _resolve_and_attach_headers(self, cmd: list, headers: Dict[str, str]) -> tuple:
        """
        Resolve env-var placeholders in *headers* and append ``--header``
        flags to *cmd*.

        Returns:
            (cmd, list_of_unresolved_env_var_names)
        """
        missing = []
        for header_name, header_value in headers.items():
            resolved, unresolved_name = self._resolve_env_placeholder(header_value)
            if unresolved_name:
                missing.append(unresolved_name)
            cmd.extend(["--header", f"{header_name}: {resolved}"])
        return cmd, missing

    def _resolve_and_attach_env_vars(self, cmd: list, mcp_name: str, env_vars: Dict[str, str]) -> tuple:
        """
        Resolve env-var placeholders in *env_vars* and append ``-e``
        flags to *cmd*.

        Special-cases ``GITHUB_PERSONAL_ACCESS_TOKEN``: if the placeholder
        cannot be resolved from the OS environment, falls back to the
        ``github.token`` value from app configuration.

        Returns:
            (cmd, list_of_unresolved_env_var_names)
        """
        missing = []
        for env_var, env_value in env_vars.items():
            resolved, unresolved_name = self._resolve_env_placeholder(env_value)
            if unresolved_name:
                # Fallback: try <MCP_NAME>_TOKEN convention
                alt = os.getenv(mcp_name.upper() + "_TOKEN")
                if alt:
                    resolved = alt
                    unresolved_name = None

            # Special case: GitHub PAT from app config as last-resort fallback
            if env_var == "GITHUB_PERSONAL_ACCESS_TOKEN" and isinstance(resolved, str) and resolved.startswith("${"):
                github_token = self.global_config.get("github.token")
                if github_token:
                    resolved = github_token
                    os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
                    unresolved_name = None

            if unresolved_name:
                missing.append(unresolved_name)
            cmd.extend(["-e", f"{env_var}={resolved}"])
        return cmd, missing

    @track_claude_execution(action="execute", provider="auto")
    async def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a Claude Code command (async version).

        Args:
            params: Parameters for the execution
                - action: The action to perform (run_prompt, continue_session)
                - prompt: The prompt to send to Claude Code
                - session_id: Optional session ID to resume a conversation
                - system_prompt: Optional system prompt to override the defaul
                - append_system_prompt: Optional instructions to append to the system promp
                - output_file: Optional file path to write Claude output directly using stream-json forma
            context: Optional execution contex

        Returns:
            Dict[str, Any]: The response from Claude Code
        """
        action = params.get("action", "run_prompt")
        logger.info(f"Executing action: {action}")

        # Extract agent_name from params for metrics
        agent_name = params.get("agent_name", "unknown")

        if action == "run_prompt":
            logger.info(f"Running prompt with length: {len(params.get('prompt', ''))}")
            result = await self._run_prompt(params)
            return result
        elif action == "continue_session":
            session_id = params.get("session_id", "")
            logger.info(f"Continuing session: {session_id}")
            result = await self._continue_session(params)
            return result
        else:
            logger.warning(f"Unsupported action: {action}")
            return {"error": f"Unsupported action: {action}"}

    @track_claude_execution(action="execute_sync", provider="auto")
    def execute_sync(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a Claude Code command (synchronous version).

        Args:
            params: Parameters for the execution
                - action: The action to perform (run_prompt, continue_session)
                - prompt: The prompt to send to Claude Code
                - session_id: Optional session ID to resume a conversation
                - system_prompt: Optional system prompt to override the defaul
                - append_system_prompt: Optional instructions to append to the system promp
                - output_file: Optional file path to write Claude output directly using stream-json forma
            context: Optional execution contex

        Returns:
            Dict[str, Any]: The response from Claude Code
        """
        action = params.get("action", "run_prompt")
        logger.info(f"Starting ClaudeCodeTool.execute_sync() with action: {action}")

        # Extract agent_name from params for metrics
        agent_name = params.get("agent_name", "unknown")

        if action == "run_prompt":
            prompt_length = len(params.get('prompt', ''))
            logger.info(f"Running prompt with length: {prompt_length}")
            result = self._run_prompt_sync(params)
            logger.info(f"_run_prompt_sync returned with result type: {type(result).__name__}")
            return result
        elif action == "continue_session":
            session_id = params.get("session_id", "")
            logger.info(f"Continuing session: {session_id}")
            result = self._continue_session_sync(params)
            logger.info(f"_continue_session_sync returned with result type: {type(result).__name__}")
            return result
        else:
            logger.warning(f"Unsupported action: {action}")
            return {"error": f"Unsupported action: {action}"}

    def _run_async_safely(self, coro):
        """
        Safely run an async coroutine from sync context.

        Handles two cases:
        1. Already in an event loop (worker context) - use ThreadPoolExecutor
        2. No event loop running - use asyncio.run()

        This is necessary because asyncio.run() cannot be called from within
        an already-running event loop (e.g., when the worker is async).
        """
        import asyncio
        try:
            asyncio.get_running_loop()
            # We're in an async context, run in a separate thread with its own loop
            from concurrent.futures import ThreadPoolExecutor

            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            return asyncio.run(coro)

    async def _run_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a prompt with Claude Code."""
        prompt = params.get("prompt")
        output_file = params.get("output_file")
        working_directory = params.get("working_directory")

        if not prompt:
            logger.error("Error: Prompt is required")
            return {"error": "Prompt is required"}

        try:
            logger.info(f"Building command for run_prompt action")

            # Check if prompt is too large for command line arguments
            # Unix ARG_MAX is typically 128KB-2MB, we'll use 64KB as safe threshold
            prompt_size = len(prompt.encode('utf-8'))
            use_stdin_for_prompt = prompt_size > 65536  # 64KB threshold
            
            if use_stdin_for_prompt:
                logger.info(f"Prompt size ({prompt_size} bytes) exceeds command line limit, using stdin")

            # If output_file is provided, use stream-json format
            use_stream_format = output_file is not None

            if use_stream_format:
                logger.info(f"Using stream-json format with output file: {output_file}")
                cmd = ["claude", "-p", "--verbose", "--output-format", "stream-json"]
            else:
                cmd = ["claude", "-p", "--print", "--output-format", self.output_format]

            # If using stdin for prompt, use text input format
            if use_stdin_for_prompt:
                cmd.extend(["--input-format", "text"])

            # Add MCP configuration
            logger.info(f"Using MCP config from: {self.mcp_config_path}")
            cmd.extend(["--mcp-config", self.mcp_config_path])

            # Add allowed tools (with optional additional tools)
            allowed_tools = self.allowed_tools
            additional_tools = params.get("additional_allowed_tools")
            if additional_tools:
                allowed_tools = f"{allowed_tools},{additional_tools}"
            logger.debug(f"Setting allowed tools: {allowed_tools}")
            cmd.extend(["--allowedTools", allowed_tools])

            # Add max turns
            logger.info(f"Setting max turns: {self.max_turns}")
            cmd.extend(["--max-turns", str(self.max_turns)])

            # Add system prompt if provided
            system_prompt = params.get("system_prompt")
            if system_prompt:
                logger.info(f"Adding system prompt (length: {len(system_prompt)})")
                cmd.extend(["--system-prompt", system_prompt])

            # Add append system prompt if provided
            append_prompt = params.get("append_system_prompt")
            if append_prompt:
                logger.info(f"Appending to system prompt: {append_prompt}")
                cmd.extend(["--append-system-prompt", append_prompt])

            # Add the prompt - either as argument or prepare for stdin
            if not use_stdin_for_prompt:
                cmd.append(prompt)

            logger.info(f"Final command: {' '.join(cmd[:5])}... (truncated)")

            # Execute the command with appropriate environment
            logger.info(f"Executing Claude command")
            _agent_name = params.get("agent_name")
            if use_stdin_for_prompt:
                # Use plain text stdin for large prompts
                logger.info(f"Passing large prompt via stdin as plain text")
                result = await self._execute_claude_command(cmd, output_file, working_directory=working_directory, stdin_input=prompt, agent_name=_agent_name)
            else:
                result = await self._execute_claude_command(cmd, output_file, working_directory=working_directory, agent_name=_agent_name)

            # If output was written directly to file, parse the final result from file
            if output_file:
                logger.info(f"Output written directly to file: {output_file}")
                if result.returncode == 0:
                    # Parse the final result from the stream-json file
                    try:
                        parsed_result = self._parse_claude_output_from_file(output_file)
                        logger.info(f"Successfully parsed result from output file")
                        return parsed_result
                    except Exception as e:
                        logger.error(f"Error parsing result from output file: {e}")
                        return {
                            "error": "Failed to parse result from output file",
                            "message": str(e),
                            "output_file": output_file
                        }
                else:
                    return {
                        "error": "Claude Code execution failed",
                        "message": result.stderr,
                        "output_file": output_file
                    }

            # Otherwise process the result as before
            if result.returncode != 0:
                logger.error(f"Execution failed with return code {result.returncode}: {result.stderr}")
                return {
                    "error": "Claude Code execution failed",
                    "message": result.stderr
                }

            logger.info(f"Command executed successfully, stdout length: {len(result.stdout)}")

            # Parse the output based on the forma
            return self._parse_claude_output(result.stdout)

        except Exception as e:
            logger.exception(f"Error executing Claude Code: {e}")
            return {
                "error": "Claude Code execution error",
                "message": str(e)
            }

    async def _continue_session(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Continue a session with Claude Code."""
        prompt = params.get("prompt", "")
        session_id = params.get("session_id")
        output_file = params.get("output_file")
        working_directory = params.get("working_directory")

        if not session_id:
            logger.error("Error: Session ID is required for continuing a session")
            return {"error": "Session ID is required for continuing a session"}

        logger.info(f"Building command for continue_session action, session_id: {session_id}")

        # If output_file is provided, use stream-json forma
        use_stream_format = output_file is not None

        if use_stream_format:
            logger.info(f"Using stream-json format with output file: {output_file}")
            cmd = ["claude", "-p", "--verbose", "--output-format", "stream-json"]
        else:
            cmd = ["claude", "-p", "--print", "--output-format", self.output_format]

        # Add MCP configuration
        logger.info(f"Using MCP config from: {self.mcp_config_path}")
        cmd.extend(["--mcp-config", self.mcp_config_path])

        # Add allowed tools (with optional additional tools)
        allowed_tools = self.allowed_tools
        additional_tools = params.get("additional_allowed_tools")
        if additional_tools:
            allowed_tools = f"{allowed_tools},{additional_tools}"
        logger.debug(f"Setting allowed tools: {allowed_tools}")
        cmd.extend(["--allowedTools", allowed_tools])

        # Add max turns
        logger.info(f"Setting max turns: {self.max_turns}")
        cmd.extend(["--max-turns", str(self.max_turns)])

        # Add session ID
        cmd.extend(["--resume", session_id])

        # Add the prompt if provided
        if prompt:
            logger.info(f"Adding prompt for session (length: {len(prompt)})")
            cmd.append(prompt)
        else:
            logger.info(f"No prompt provided for session continuation")

        logger.info(f"Final command: {' '.join(cmd[:5])}... (truncated)")

        try:
            # Execute the command with appropriate environment
            logger.info(f"Executing Claude command")
            result = await self._execute_claude_command(cmd, output_file, working_directory=working_directory, agent_name=params.get("agent_name"))

            # If output was written directly to file, parse the final result from file
            if output_file:
                logger.info(f"Output written directly to file: {output_file}")
                if result.returncode == 0:
                    # Parse the final result from the stream-json file
                    try:
                        parsed_result = self._parse_claude_output_from_file(output_file)
                        logger.info(f"Successfully parsed result from output file")
                        return parsed_result
                    except Exception as e:
                        logger.error(f"Error parsing result from output file: {e}")
                        return {
                            "error": "Failed to parse result from output file",
                            "message": str(e),
                            "output_file": output_file
                        }
                else:
                    return {
                        "error": "Claude Code execution failed",
                        "message": result.stderr,
                        "output_file": output_file
                    }

            # Otherwise process the result as before
            if result.returncode != 0:
                logger.error(f"Execution failed with return code {result.returncode}: {result.stderr}")
                return {
                    "error": "Claude Code execution failed",
                    "message": result.stderr
                }

            logger.info(f"Command executed successfully, stdout length: {len(result.stdout)}")

            # Parse the output based on the forma
            return self._parse_claude_output(result.stdout)

        except Exception as e:
            logger.exception(f"Error executing Claude Code: {e}")
            return {
                "error": "Claude Code execution error",
                "message": str(e)
            }

    def _run_prompt_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a prompt with Claude Code (synchronous version)."""
        prompt = params.get("prompt")
        output_file = params.get("output_file")
        task_id = params.get("task_id")  # Extract task_id for subprocess tracking
        working_directory = params.get("working_directory")
        enable_agent_teams = params.get("enable_agent_teams", False)

        logger.info(f"Starting _run_prompt_sync")

        if not prompt:
            logger.error("Error: Prompt is required")
            return {"error": "Prompt is required"}

        try:
            logger.info(f"Building command for run_prompt action")

            # Check if prompt is too large for command line arguments
            # Unix ARG_MAX is typically 128KB-2MB, we'll use 64KB as safe threshold
            prompt_size = len(prompt.encode('utf-8'))
            use_stdin_for_prompt = prompt_size > 65536  # 64KB threshold
            
            if use_stdin_for_prompt:
                logger.info(f"Prompt size ({prompt_size} bytes) exceeds command line limit, using stdin")

            # If output_file is provided, use stream-json format
            use_stream_format = output_file is not None

            if use_stream_format:
                logger.info(f"Using stream-json format with output file: {output_file}")
                cmd = ["claude", "-p", "--verbose", "--output-format", "stream-json"]
            else:
                cmd = ["claude", "-p", "--print", "--output-format", self.output_format]

            # If using stdin for prompt, use text input format
            if use_stdin_for_prompt:
                cmd.extend(["--input-format", "text"])

            # Add MCP configuration
            logger.info(f"Using MCP config from: {self.mcp_config_path}")
            cmd.extend(["--mcp-config", self.mcp_config_path])

            # Add allowed tools (with optional additional tools)
            allowed_tools = self.allowed_tools
            additional_tools = params.get("additional_allowed_tools")
            if additional_tools:
                allowed_tools = f"{allowed_tools},{additional_tools}"
            logger.debug(f"Setting allowed tools: {allowed_tools}")
            cmd.extend(["--allowedTools", allowed_tools])

            # Add max turns
            logger.info(f"Setting max turns: {self.max_turns}")
            cmd.extend(["--max-turns", str(self.max_turns)])

            # Add system prompt if provided
            system_prompt = params.get("system_prompt")
            if system_prompt:
                logger.info(f"Adding system prompt (length: {len(system_prompt)})")
                cmd.extend(["--system-prompt", system_prompt])

            # Add append system prompt if provided
            append_prompt = params.get("append_system_prompt")
            if append_prompt:
                logger.info(f"Appending to system prompt: {append_prompt}")
                cmd.extend(["--append-system-prompt", append_prompt])

            # Add the prompt - either as argument or prepare for stdin
            if not use_stdin_for_prompt:
                cmd.append(prompt)

            logger.info(f"Command built successfully: {' '.join(cmd[:5])}... (truncated)")

            # Execute the command with appropriate environment
            logger.info(f"About to execute Claude command via _execute_claude_command")
            agent_teams_env = {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"} if enable_agent_teams else {}
            _agent_name = params.get("agent_name")
            if use_stdin_for_prompt:
                # Use plain text stdin for large prompts
                logger.info(f"Passing large prompt via stdin as plain text")
                result = self._run_async_safely(
                    self._execute_claude_command(cmd, output_file, task_id, working_directory, stdin_input=prompt,
                                                 extra_env=agent_teams_env, agent_name=_agent_name)
                )
            else:
                result = self._run_async_safely(
                    self._execute_claude_command(cmd, output_file, task_id, working_directory,
                                                 extra_env=agent_teams_env, agent_name=_agent_name)
                )
            logger.info(f"_execute_claude_command returned with return_code: {result.returncode}")

            # If output was written directly to file, parse the final result from file
            if output_file:
                logger.info(f"Output written directly to file: {output_file}")
                if result.returncode == 0:
                    # Parse the final result from the stream-json file
                    try:
                        parsed_result = self._parse_claude_output_from_file(output_file)
                        logger.info(f"Successfully parsed result from output file")
                        return parsed_result
                    except Exception as e:
                        logger.error(f"Error parsing result from output file: {e}")
                        return {
                            "error": "Failed to parse result from output file",
                            "message": str(e),
                            "output_file": output_file
                        }
                else:
                    return {
                        "error": "Claude Code execution failed",
                        "message": result.stderr,
                        "output_file": output_file
                    }

            # Otherwise process the result as before
            if result.returncode != 0:
                logger.error(f"Execution failed with return code {result.returncode}: {result.stderr}")
                return {
                    "error": "Claude Code execution failed",
                    "message": result.stderr
                }

            logger.info(f"Command executed successfully, stdout length: {len(result.stdout)}")

            # Parse the output based on the forma
            return self._parse_claude_output(result.stdout)

        except Exception as e:
            logger.exception(f"Error executing Claude Code: {e}")
            return {
                "error": "Claude Code execution error",
                "message": str(e)
            }

    def _continue_session_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Continue a session with Claude Code (synchronous version)."""
        prompt = params.get("prompt", "")
        session_id = params.get("session_id")
        output_file = params.get("output_file")
        working_directory = params.get("working_directory")

        if not session_id:
            logger.error("Error: Session ID is required for continuing a session")
            return {"error": "Session ID is required for continuing a session"}

        logger.info(f"Building command for continue_session action, session_id: {session_id}")

        # If output_file is provided, use stream-json forma
        use_stream_format = output_file is not None

        if use_stream_format:
            logger.info(f"Using stream-json format with output file: {output_file}")
            cmd = ["claude", "-p", "--verbose", "--output-format", "stream-json"]
        else:
            cmd = ["claude", "-p", "--print", "--output-format", self.output_format]

        # Add MCP configuration
        logger.info(f"Using MCP config from: {self.mcp_config_path}")
        cmd.extend(["--mcp-config", self.mcp_config_path])

        # Add allowed tools (with optional additional tools)
        allowed_tools = self.allowed_tools
        additional_tools = params.get("additional_allowed_tools")
        if additional_tools:
            allowed_tools = f"{allowed_tools},{additional_tools}"
        logger.debug(f"Setting allowed tools: {allowed_tools}")
        cmd.extend(["--allowedTools", allowed_tools])

        # Add max turns
        logger.info(f"Setting max turns: {self.max_turns}")
        cmd.extend(["--max-turns", str(self.max_turns)])

        # Add session ID
        cmd.extend(["--resume", session_id])

        # Add the prompt if provided
        if prompt:
            logger.info(f"Adding prompt for session (length: {len(prompt)})")
            cmd.append(prompt)
        else:
            logger.info(f"No prompt provided for session continuation")

        logger.info(f"Final command: {' '.join(cmd[:5])}... (truncated)")

        try:
            # Execute the command with appropriate environmen
            logger.info(f"Executing Claude command")
            result = self._run_async_safely(
                self._execute_claude_command(cmd, output_file, working_directory=working_directory, agent_name=params.get("agent_name"))
            )

            # If output was written directly to file, parse the final result from file
            if output_file:
                logger.info(f"Output written directly to file: {output_file}")
                if result.returncode == 0:
                    # Parse the final result from the stream-json file
                    try:
                        parsed_result = self._parse_claude_output_from_file(output_file)
                        logger.info(f"Successfully parsed result from output file")
                        return parsed_result
                    except Exception as e:
                        logger.error(f"Error parsing result from output file: {e}")
                        return {
                            "error": "Failed to parse result from output file",
                            "message": str(e),
                            "output_file": output_file
                        }
                else:
                    return {
                        "error": "Claude Code execution failed",
                        "message": result.stderr,
                        "output_file": output_file
                    }

            # Otherwise process the result as before
            if result.returncode != 0:
                logger.error(f"Execution failed with return code {result.returncode}: {result.stderr}")
                return {
                    "error": "Claude Code execution failed",
                    "message": result.stderr
                }

            logger.info(f"Command executed successfully, stdout length: {len(result.stdout)}")

            # Parse the output based on the forma
            return self._parse_claude_output(result.stdout)

        except Exception as e:
            logger.exception(f"Error executing Claude Code: {e}")
            return {
                "error": "Claude Code execution error",
                "message": str(e)
            }

    def _build_otel_env(self, task_id: Optional[str] = None, agent_name: Optional[str] = None) -> Dict[str, str]:
        """Build OTEL telemetry env vars for the Claude Code subprocess.

        Reads ``[telemetry.otel]`` from config and returns a dict of env vars
        that enable Claude Code's native OTEL telemetry, pointing metrics and
        logs at the OTEL Collector running in the swe-agent namespace.

        Returns an empty dict when OTEL is disabled or config is unavailable.
        """
        try:
            otel_config = get_config().get("telemetry", {}).get("otel", {})
        except Exception:
            return {}

        if not otel_config.get("enabled"):
            return {}

        metrics_enabled = otel_config.get("metrics_enabled", True)
        logs_enabled = otel_config.get("logs_enabled", True)

        if not metrics_enabled and not logs_enabled:
            return {}

        endpoint = otel_config.get("endpoint")
        if not endpoint:
            logger.warning("telemetry.otel.endpoint not set, skipping OTEL for Claude Code subprocess")
            return {}
        env_name = os.getenv("APP_ENV", "dev")

        otel_env: Dict[str, str] = {
            "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
            "OTEL_EXPORTER_OTLP_ENDPOINT": endpoint,
            "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "cumulative",
            "OTEL_METRIC_EXPORT_INTERVAL": "60000",
            "OTEL_LOGS_EXPORT_INTERVAL": "10000"
        }

        # Claude Code crashes on OTEL_*_EXPORTER=none (not OTEL-spec compliant).
        # Omit the var entirely to disable that signal; Claude treats unset as "no exporter".
        # See: https://github.com/anthropics/claude-code/issues/18259
        if metrics_enabled:
            otel_env["OTEL_METRICS_EXPORTER"] = "otlp"
        if logs_enabled:
            otel_env["OTEL_LOGS_EXPORTER"] = "otlp"

        if logs_enabled and otel_config.get("log_user_prompts", True):
            otel_env["OTEL_LOG_USER_PROMPTS"] = "1"
        if logs_enabled and otel_config.get("log_tool_details", True):
            otel_env["OTEL_LOG_TOOL_DETAILS"] = "1"

        resource_attrs = [
            f"deployment.environment={env_name}",
            "service.namespace=swe-agent",
        ]
        if task_id:
            resource_attrs.append(f"task.id={task_id}")
        if agent_name and agent_name != "unknown":
            resource_attrs.append(f"agent.name={agent_name}")

        otel_env["OTEL_RESOURCE_ATTRIBUTES"] = ",".join(resource_attrs)

        logger.info("OTEL telemetry enabled for Claude Code subprocess", extra={
            "endpoint": endpoint, "task_id": task_id, "agent_name": agent_name,
        })
        return otel_env

    async def _execute_claude_command(self, cmd: List[str], output_file: Optional[str] = None, task_id: Optional[str] = None, working_directory: Optional[str] = None, stdin_input: Optional[str] = None, extra_env: Optional[Dict[str, str]] = None, agent_name: Optional[str] = None) -> subprocess.CompletedProcess:
        """
        Execute a Claude command with the appropriate environment variables based on provider.

        Args:
            cmd: The command to execute
            output_file: Optional file path to write output directly to
            task_id: Optional task ID for process tracking
            working_directory: Optional working directory for subprocess execution
            extra_env: Optional additional environment variables to inject into the subprocess
            agent_name: Optional agent name for OTEL resource attributes

        Returns:
            subprocess.CompletedProcess: The result of the command execution
        """
        otel_env = self._build_otel_env(task_id=task_id, agent_name=agent_name)
        if otel_env:
            extra_env = {**(extra_env or {}), **otel_env}

        # Route to appropriate provider
        if self.provider == "vertex_ai":
            return await self._execute_vertex_ai_command(cmd, output_file, task_id, working_directory, stdin_input, extra_env=extra_env)
        elif self.provider == "bedrock":
            return await self._execute_bedrock_command(cmd, output_file, task_id, working_directory, stdin_input, extra_env=extra_env)
        else:
            logger.error(f"Unsupported provider: {self.provider}")
            # Return a failed result
            return subprocess.CompletedProcess(
                cmd, 1, "", f"Unsupported provider: {self.provider}"
            )

    async def _execute_bedrock_command(self, cmd: List[str], output_file: Optional[str] = None, task_id: Optional[str] = None, working_directory: Optional[str] = None, stdin_input: Optional[str] = None, extra_env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        """Execute Claude command using AWS Bedrock."""
        logger.info(f"Using Bedrock provider with model: {self.anthropic_model}")

        # Set up base environment variables
        env = os.environ.copy()

        # Set up AWS/Bedrock specific environment
        bedrock_env = {
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "ANTHROPIC_MODEL": self.anthropic_model
        }

        # Merge any extra environment variables (e.g. agent teams flag)
        if extra_env:
            bedrock_env.update(extra_env)

        if self.disable_prompt_caching:
            logger.info(f"Prompt caching disabled")
            bedrock_env["DISABLE_PROMPT_CACHING"] = "1"

        # Get AWS credentials from configuration
        aws_config = self.claude_config.get("aws", {})

        # Exclude setting AWS credentials for stage and prod environments
        app_env = os.getenv("APP_ENV", "dev")

        if app_env not in ["stage", "prod"]:
            if aws_config.get("access_key_id"):
                bedrock_env["AWS_ACCESS_KEY_ID"] = aws_config["access_key_id"]
            if aws_config.get("secret_access_key"):
                bedrock_env["AWS_SECRET_ACCESS_KEY"] = aws_config["secret_access_key"]
            if aws_config.get("session_token"):
                bedrock_env["AWS_SESSION_TOKEN"] = aws_config["session_token"]
        else:
            logger.info(f"Skipping AWS credential configuration for environment: {app_env}")
            
        if aws_config.get("region"):
            bedrock_env["AWS_DEFAULT_REGION"] = aws_config["region"]
            bedrock_env["AWS_REGION"] = aws_config["region"]

        # Use passed task_id or fallback to context lookup for process tracking
        if task_id is None:
            task_id = ProcessManager.get_current_task_id()
            
        # Prepare debug flags if MCP debug is enabled
        debug_flags = ["--mcp-debug"] if self.mcp_debug else None

        # Execute using ProcessManager (async version for parallel execution)
        result = await ProcessManager.run_managed_subprocess_async(
            cmd=cmd,
            env=env,
            output_file=output_file,
            task_id=task_id,
            tool_name="claude_code_bedrock",
            additional_env=bedrock_env,
            debug_flags=debug_flags,
            input_text=stdin_input,
            cwd=working_directory
        )

        return result.process

    async def _execute_vertex_ai_command(self, cmd: List[str], output_file: Optional[str] = None, task_id: Optional[str] = None, working_directory: Optional[str] = None, stdin_input: Optional[str] = None, extra_env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        """Execute Claude command using GCP Vertex AI."""
        # Use current task_id or fallback to context lookup for logging
        if task_id is None:
            task_id = ProcessManager.get_current_task_id()

        # Set up base environment variables
        env = os.environ.copy()

        # Inject Slack MCP env vars from config
        from src.providers.config_loader import get_config as _get_full_config
        _slack_cfg = _get_full_config().get("slack", {})
        for _k, _cfg_key in [
            ("SLACK_TEAM_ID", "slack_team_id"),
            ("SLACK_MCP_XOXP_TOKEN", "slack_mcp_xoxp_token"),
            ("SLACK_MCP_ADD_MESSAGE_TOOL", "slack_mcp_add_message_tool"),
        ]:
            _v = _slack_cfg.get(_cfg_key, "")
            if _v and not env.get(_k):
                env[_k] = _v

        # Get GCP config
        gcp_config = self.claude_config.get("gcp", {})
        project_id = gcp_config.get("project_id")
        region = self.claude_config.get("region", gcp_config.get("region", "us-east5"))
        credentials_json = gcp_config.get("credentials_json")

        if not project_id:
            logger.error(
                "GCP project_id not configured for Vertex AI",
                extra={"task_id": task_id}
            )
            return subprocess.CompletedProcess(cmd, 1, "", "GCP project_id not configured")

        # Set required Vertex AI environment variables
        vertex_env = {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "CLOUD_ML_REGION": region,
            "ANTHROPIC_VERTEX_PROJECT_ID": project_id,
            "ANTHROPIC_MODEL": self.anthropic_model
        }

        # Merge any extra environment variables (e.g. agent teams flag)
        if extra_env:
            vertex_env.update(extra_env)

        # Log Vertex AI configuration (consolidated)
        logger.info(
            f"Using Vertex AI provider: project={project_id}, region={region}",
            extra={"task_id": task_id, "project_id": project_id, "region": region}
        )

        # Use credentials file that was written during initialization
        # Credentials are now set up in _setup_vertex_ai_credentials() during __init__
        default_creds_path = "/root/.config/gcloud/application_default_credentials.json"
        if os.path.exists(default_creds_path):
            vertex_env["GOOGLE_APPLICATION_CREDENTIALS"] = default_creds_path
            logger.debug(
                f"Using Vertex AI credentials from: {default_creds_path}",
                extra={"task_id": task_id, "creds_path": default_creds_path}
            )
        else:
            logger.warning(
                "Vertex AI credentials file not found. It should have been created during initialization.",
                extra={"task_id": task_id, "expected_path": default_creds_path}
            )

        # Use passed task_id or fallback to context lookup for process tracking
        if task_id is None:
            task_id = ProcessManager.get_current_task_id()
            
        # Prepare debug flags if MCP debug is enabled
        debug_flags = ["--mcp-debug"] if self.mcp_debug else None

        # Execute using ProcessManager (async version for parallel execution)
        result = await ProcessManager.run_managed_subprocess_async(
            cmd=cmd,
            env=env,
            output_file=output_file,
            task_id=task_id,
            tool_name="claude_code_vertex",
            additional_env=vertex_env,
            debug_flags=debug_flags,
            input_text=stdin_input,
            cwd=working_directory
        )

        return result.process







    def _parse_claude_output_from_file(self, output_file: str) -> Dict[str, Any]:
        """Parse Claude's output from a stream-json file by extracting the last JSON line."""
        logger.info(f"Parsing Claude output from file: {output_file}")

        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if not lines:
                logger.warning(f"Output file is empty: {output_file}")
                return {
                    "error": "Empty output file",
                    "message": "The Claude output file is empty"
                }

            # Collect tool usage from stream output
            mcp_calls = []
            skills_used = []

            for line in lines:
                try:
                    event = json.loads(line.strip())

                    # In stream-json format, tool_use items are nested inside
                    # assistant messages: {"type": "assistant", "message":
                    #   {"content": [{"type": "tool_use", "name": "Read", ...}]}}
                    content_items = []
                    if event.get("type") == "assistant":
                        message = event.get("message", {})
                        for item in message.get("content", []):
                            if isinstance(item, dict) and item.get("type") == "tool_use":
                                content_items.append(item)

                    for tool_item in content_items:
                        tool_name = tool_item.get("name", "")

                        # Track MCP tool calls (names start with mcp__)
                        if tool_name.startswith("mcp__"):
                            # Parse mcp__server-name__tool_name format
                            parts = tool_name.split("__")
                            if len(parts) >= 3:
                                mcp_server = parts[1]
                                mcp_tool = "__".join(parts[2:])
                            else:
                                mcp_server = "unknown"
                                mcp_tool = tool_name

                            mcp_calls.append({
                                "server": mcp_server,
                                "tool": mcp_tool,
                                "full_name": tool_name
                            })

                        # Track Skill invocations
                        elif tool_name == "Skill":
                            skill_name = tool_item.get("input", {}).get("skill", "unknown")
                            skills_used.append(skill_name)

                except json.JSONDecodeError:
                    continue

            # Log summary of tool usage
            if mcp_calls or skills_used:
                logger.info(
                    f"Tool usage summary: {len(mcp_calls)} MCP calls, {len(skills_used)} Skills"
                )

            # Find the last non-empty JSON line
            last_json_line = None
            for line in reversed(lines):
                line = line.strip()
                if line and line.startswith('{'):
                    try:
                        # Test if it's valid JSON
                        json.loads(line)
                        last_json_line = line
                        break
                    except json.JSONDecodeError:
                        continue

            if not last_json_line:
                logger.error(f"No valid JSON found in output file: {output_file}")
                return {
                    "error": "No valid JSON found",
                    "message": "Could not find valid JSON in the output file"
                }

            logger.info(f"Found final JSON result in output file")
            result = self._parse_claude_output(last_json_line)

            # Add tool usage to result
            result["mcp_calls"] = mcp_calls
            result["skills_used"] = skills_used

            return result

        except Exception as e:
            logger.error(f"Error reading output file {output_file}: {e}")
            return {
                "error": "File read error",
                "message": f"Failed to read output file: {str(e)}"
            }

    def _parse_claude_output(self, stdout: str) -> Dict[str, Any]:
        """Parse Claude's output based on the configured format."""
        logger.info(f"Parsing Claude output (length: {len(stdout)})")

        if self.output_format == "json":
            try:
                data = json.loads(stdout)
                logger.info(f"Successfully parsed JSON response with keys: {', '.join(data.keys())}")
                return {
                    "type": "claude_code_response",
                    "result": data.get("result", ""),
                    "session_id": data.get("session_id", ""),
                    "cost_usd": data.get("cost_usd", data.get("total_cost_usd", 0)),
                    "duration_ms": data.get("duration_ms", 0),
                    "num_turns": data.get("num_turns", 0),
                    "raw_response": data
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response preview: {stdout[:200]}...")
                return {
                    "error": "JSON parse error",
                    "message": "Failed to parse JSON response from Claude Code"
                }
        else:
            logger.info(f"Using raw text format, returning as is")
            return {
                "type": "claude_code_response",
                "result": stdout,
                "raw_output": stdout
            }

    def get_info(self) -> Dict[str, Any]:
        """Get information about this tool."""
        return {
            "name": self.name,
            "description": "Claude Code integration for code generation and analysis",
            "actions": {
                "run_prompt": {
                    "description": "Run a prompt with Claude Code",
                    "params": {
                        "prompt": "The prompt to send to Claude Code",
                        "system_prompt": "Optional system prompt to override the default",
                        "append_system_prompt": "Optional instructions to append to the system prompt"
                    }
                },
                "continue_session": {
                    "description": "Continue a session with Claude Code",
                    "params": {
                        "prompt": "The prompt to send to Claude Code",
                        "session_id": "Session ID to continue"
                    }
                }
            }
        }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validate the parameters for the tool.

        Args:
            params: Parameters to validate

        Returns:
            bool: True if parameters are valid, False otherwise
        """
        action = params.get("action", "run_prompt")

        if action == "run_prompt":
            # Prompt is required for run_prompt action
            if "prompt" not in params:
                logger.error("Prompt is required for run_prompt action")
                return False

        elif action == "continue_session":
            # Session ID is required for continue_session action
            if "session_id" not in params:
                logger.error("Session ID is required for continue_session action")
                return False

        else:
            # Unsupported action
            logger.error(f"Unsupported action: {action}")
            return False

        return True

    def _get_parameter_schema(self) -> Dict[str, Any]:
        """Get the parameter schema for this tool."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["run_prompt", "continue_session"],
                    "description": "Action to perform"
                },
                "prompt": {
                    "type": "string",
                    "description": "The prompt to send to Claude Code"
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID to continue a conversation"
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system prompt to override the default"
                },
                "append_system_prompt": {
                    "type": "string",
                    "description": "Optional instructions to append to the system prompt"
                }
            }
        }

    def _get_output_schema(self) -> Dict[str, Any]:
        """Get the output schema for this tool."""
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Type of the response"
                },
                "result": {
                    "type": "string",
                    "description": "The result text from Claude Code"
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID for continuing the conversation"
                },
                "error": {
                    "type": "string",
                    "description": "Error message if something went wrong"
                }
            }
        }

    def is_mcp_registered(self, mcp_name: str) -> bool:
        """
        Check if an MCP is already registered.

        Args:
            mcp_name: Name of the MCP to check

        Returns:
            bool: True if the MCP is registered, False otherwise
        """
        global _registered_mcps
        return mcp_name in _registered_mcps

    def mark_mcp_registered(self, mcp_name: str) -> None:
        """
        Mark an MCP as registered.

        Args:
            mcp_name: Name of the MCP to mark as registered
        """
        global _registered_mcps
        _registered_mcps.add(mcp_name)
        logger.debug(f"Marked MCP as registered: {mcp_name}")