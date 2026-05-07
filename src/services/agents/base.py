"""Base service for autonomous agents."""

from typing import Any, Dict, Optional

from src.providers.context import Context, EXECUTION_MODE, LOG_CORRELATION_ID, METADATA, TASK_ID


class BaseAgentService:
    """Shared helpers for all autonomous agent services."""

    def get_task_id(self, ctx: Context) -> Optional[str]:
        return ctx.get(TASK_ID)

    def get_metadata(self, ctx: Context) -> Dict[str, Any]:
        return ctx.get(METADATA, {})

    def get_execution_mode(self, ctx: Context) -> str:
        return ctx.get(EXECUTION_MODE, "unknown")

    def get_logging_context(self, ctx: Context) -> Dict[str, Any]:
        return ctx.get_logging_context()

    def check_context_done(self, ctx: Context) -> bool:
        return ctx.done()

    def get_context_status(self, ctx: Context) -> Dict[str, Any]:
        return {
            "cancelled": ctx.is_cancelled(),
            "expired": ctx.is_expired(),
            "done": ctx.done(),
            "time_remaining": ctx.time_remaining(),
            "correlation_id": ctx.get(LOG_CORRELATION_ID),
        }

    def _get_current_timestamp(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def cleanup_flows_yaml(workspace_dir: str, logger, log_ctx: Dict[str, Any]) -> None:
        """Clean up flows.yaml from devstackctl by resetting services to empty array.

        Args:
            workspace_dir: Directory containing flows.yaml
            logger: Logger instance for logging cleanup status
            log_ctx: Logging context dictionary
        """
        import os
        flows_yaml_path = os.path.join(workspace_dir, "flows.yaml")
        if os.path.exists(flows_yaml_path):
            try:
                import yaml
                with open(flows_yaml_path, 'r') as f:
                    flows_data = yaml.safe_load(f) or {}

                if 'services' in flows_data:
                    flows_data['services'] = []
                    with open(flows_yaml_path, 'w') as f:
                        yaml.dump(flows_data, f, default_flow_style=False)
                    logger.info("Reset flows.yaml services to empty array", extra={**log_ctx, "flows_yaml": flows_yaml_path})
            except Exception as e:
                logger.warning(f"Failed to clean flows.yaml: {e}", extra={**log_ctx, "flows_yaml": flows_yaml_path})
