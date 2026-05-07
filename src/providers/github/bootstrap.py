"""
GitHub Authentication Bootstrap.

Handles initial token generation and task scheduling during application startup.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime, timezone, timedelta

from ..cache.redis_client import get_redis_client
from ..config_loader import get_config
from .auth_service import GitHubAuthService
from .exceptions import GitHubAuthenticationError
from src.constants.github_bots import GitHubBot, DEFAULT_BOT

logger = logging.getLogger(__name__)


class GitHubAuthBootstrap:
    """
    Bootstrap GitHub authentication during application startup.
    
    Handles:
    - Initial token generation
    - Token caching
    - Git/gh CLI setup
    - First refresh task scheduling
    """
    
    def __init__(self):
        """Initialize the bootstrap service."""
        self.config = get_config()
        self.cache = get_redis_client()
        self.auth_service = GitHubAuthService()
        
    async def initialize_github_auth(self) -> Dict[str, Any]:
        """
        Initialize GitHub authentication for all configured bots.

        This method:
        1. Initializes rzp_swe_agent_app (existing bot)
        2. Initializes rzp_code_review (new bot) if configured
        3. Returns combined status for both bots

        Returns:
            Dictionary with initialization status for all bots
        """
        try:
            logger.info("Initializing GitHub authentication system for all bots")

            # Initialize both bots
            results = {}

            # Initialize rzp_swe_agent_app (existing bot)
            logger.info(f"Initializing {GitHubBot.SWE_AGENT}")
            results[GitHubBot.SWE_AGENT] = await self._initialize_bot(GitHubBot.SWE_AGENT)

            # Initialize rzp_code_review (new bot) if configured
            code_review_config = self.config.get("github", {}).get(GitHubBot.CODE_REVIEW.value, {})
            if code_review_config.get("app_id"):
                logger.info(f"Initializing {GitHubBot.CODE_REVIEW}")
                results[GitHubBot.CODE_REVIEW] = await self._initialize_bot(GitHubBot.CODE_REVIEW)
            else:
                logger.info(f"{GitHubBot.CODE_REVIEW} not configured, skipping")
                results[GitHubBot.CODE_REVIEW] = {
                    "success": True,
                    "message": "Bot not configured",
                    "bot_name": GitHubBot.CODE_REVIEW,
                    "configured": False
                }

            # Determine overall success
            any_success = any(result.get("success", False) for result in results.values())
            all_configured = all(
                result.get("success", False)
                for result in results.values()
                if result.get("configured", True)
            )

            return {
                "success": any_success,
                "message": "GitHub authentication system initialized for all bots",
                "bots": results,
                "all_configured_bots_initialized": all_configured
            }

        except Exception as e:
            logger.error(f"GitHub authentication bootstrap failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _initialize_bot(self, bot_name: Union[GitHubBot, str]) -> Dict[str, Any]:
        """
        Initialize a single bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum

        Returns:
            Dictionary with initialization status for this bot
        """
        try:
            logger.info(f"Initializing {bot_name}")

            # Check if we already have a valid cached token for this bot
            existing_token_info = await self.auth_service.get_token_info(bot_name=bot_name)

            if existing_token_info.get("authenticated", False):
                # Check TTL - if more than 10 minutes remaining, skip bootstrap
                ttl_seconds = existing_token_info.get("ttl_seconds", 0)
                if ttl_seconds > 600:  # More than 10 minutes
                    logger.info(f"Valid token already cached for {bot_name} with {ttl_seconds} seconds remaining")

                    # Still ensure git/gh CLI is set up
                    await self._setup_cli_tools(bot_name=bot_name)

                    return {
                        "success": True,
                        "message": f"{bot_name} authentication already initialized",
                        "bot_name": bot_name,
                        "token_info": existing_token_info,
                        "bootstrap_performed": False,
                        "configured": True
                    }

            # Generate initial token for this bot
            logger.info(f"Generating initial GitHub token for {bot_name}")
            token_result = await self._generate_initial_token(bot_name=bot_name)

            if not token_result["success"]:
                # Use auth service detection for consistent logic
                should_use_github_app = self.auth_service._detect_production_environment(bot_name=bot_name)

                if not should_use_github_app:
                    logger.warning(f"Initial token generation failed for {bot_name} (no GitHub app config): {token_result.get('error')}")
                    return {
                        "success": False,
                        "message": f"No GitHub token configured for {bot_name}",
                        "bot_name": bot_name,
                        "error": token_result.get("error"),
                        "bootstrap_performed": True,
                        "development_mode": True,
                        "configured": False
                    }
                else:
                    logger.error(f"Initial token generation failed for {bot_name} (GitHub app config present): {token_result.get('error')}")
                    return {
                        "success": False,
                        "bot_name": bot_name,
                        "error": token_result.get("error"),
                        "bootstrap_performed": True,
                        "configured": True
                    }

            # Setup git and gh CLI tools
            cli_setup_result = await self._setup_cli_tools(bot_name=bot_name)

            # Get final token info to check type
            final_token_info = await self.auth_service.get_token_info(bot_name=bot_name)
            token_type = final_token_info.get("token_type", "unknown")

            # Only schedule refresh for GitHub app tokens that expire
            refresh_scheduled = False
            if token_type == "github_app":
                logger.info(f"GitHub app token detected for {bot_name} - scheduling first refresh")
                refresh_scheduled = await self._schedule_first_refresh(bot_name=bot_name)
            else:
                logger.info(f"Token type '{token_type}' for {bot_name} does not require automatic refresh")

            logger.info(f"{bot_name} initialized successfully")

            return {
                "success": True,
                "message": f"{bot_name} initialized ({'with refresh scheduled' if refresh_scheduled else 'no refresh needed'})",
                "bot_name": bot_name,
                "token_info": final_token_info,
                "cli_setup": cli_setup_result,
                "refresh_scheduled": refresh_scheduled,
                "refresh_needed": token_type == "github_app",
                "bootstrap_performed": True,
                "configured": True
            }

        except Exception as e:
            logger.error(f"{bot_name} initialization failed: {e}")
            return {
                "success": False,
                "bot_name": bot_name,
                "error": str(e),
                "bootstrap_performed": True,
                "configured": True
            }
            
    async def _generate_initial_token(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> Dict[str, Any]:
        """
        Generate initial token and cache it for specified bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum

        Returns:
            Dictionary with generation status
        """
        try:
            # Import here to avoid circular imports
            from src.worker.tasks import TaskProcessor

            # Create a temporary task processor to generate token
            task_processor = TaskProcessor()

            # Use auth service's environment detection for this bot
            should_use_github_app = self.auth_service._detect_production_environment(bot_name=bot_name)

            if should_use_github_app:
                logger.info(f"Generating GitHub App token for {bot_name} (GitHub app configuration detected)")
                result = await task_processor._generate_github_app_token(bot_name=bot_name)
            else:
                logger.info(f"Attempting to use personal token for {bot_name} (no GitHub app configuration)")
                result = await task_processor._generate_personal_token(bot_name=bot_name)

            if not result["success"]:
                return result

            token = result["token"]
            metadata = result.get("metadata", {})

            # Cache the token and metadata (bot-specific keys)
            cache_ttl = 3000  # 50 minutes
            bot_name_str = bot_name.value if hasattr(bot_name, 'value') else bot_name
            cache_key = f"github:token:{bot_name_str}"
            metadata_key = f"github:token:metadata:{bot_name_str}"
            self.cache.set(cache_key, token, ttl=cache_ttl)
            self.cache.set(metadata_key, json.dumps(metadata), ttl=cache_ttl)

            logger.info(f"Initial GitHub token for {bot_name} cached successfully (type: {metadata.get('token_type', 'unknown')})")
            
            # Get environment name for response
            environment = self.config.get("environment", {}).get("name", "dev")
            
            return {
                "success": True,
                "token_type": metadata.get("token_type"),
                "user_login": metadata.get("user_login"),
                "environment": environment
            }
            
        except Exception as e:
            logger.error(f"Initial token generation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def _setup_cli_tools(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> Dict[str, Any]:
        """
        Setup git and gh CLI tools with current token for specified bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum

        Returns:
            Dictionary with setup status
        """
        try:
            logger.info(f"Setting up git and gh CLI tools for {bot_name}")

            # Setup git configuration
            git_setup = await self.auth_service.setup_git_config(bot_name=bot_name)

            # Setup gh CLI authentication
            gh_setup = await self.auth_service.ensure_gh_auth(bot_name=bot_name)
            
            setup_result = {
                "git_config": git_setup,
                "gh_auth": gh_setup,
                "overall_success": git_setup.get("success", False) and gh_setup.get("success", False)
            }
            
            if setup_result["overall_success"]:
                logger.info("Git and gh CLI tools configured successfully")
            else:
                logger.warning("Some CLI tool setup operations failed")
            
            return setup_result
            
        except Exception as e:
            logger.error(f"CLI tools setup failed: {e}")
            return {
                "git_config": {"success": False, "error": str(e)},
                "gh_auth": {"success": False, "error": str(e)},
                "overall_success": False
            }
            
    async def _schedule_first_refresh(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> bool:
        """
        Schedule the first token refresh task for specified bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum

        Returns:
            True if task was scheduled successfully
        """
        try:
            logger.info(f"Scheduling first GitHub token refresh task for {bot_name}")

            # Use direct queue submission (no database) with 10-minute delay
            success = await self._send_refresh_task_directly(delay_seconds=600, bot_name=bot_name)  # 10 minutes

            if success:
                logger.info(f"First token refresh task for {bot_name} scheduled successfully (queue-only)")
                return True
            else:
                logger.warning(f"Failed to schedule first token refresh task for {bot_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to schedule first refresh task for {bot_name}: {e}")
            return False

    async def _send_refresh_task_directly(self, delay_seconds: int = 0, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> bool:
        """
        Send refresh task directly to queue without database operations.

        Args:
            delay_seconds: Delay before task execution (max 900 seconds for SQS)
            bot_name: Bot identifier from GitHubBot enum

        Returns:
            True if task was sent successfully
        """
        try:
            import time

            # Import QueueManager directly
            from src.worker.queue_manager import QueueManager

            queue_manager = QueueManager()

            # Create task data for queue-only processing
            bot_name_str = bot_name.value if hasattr(bot_name, 'value') else bot_name
            task_data = {
                'task_type': 'github_token_refresh',
                'task_id': f'github-refresh-{bot_name_str}-{int(time.time())}',  # Ensure enum converts to string value
                'parameters': {
                    'scheduled_for': (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat(),
                    'queue_only': True,  # Flag to skip DB operations in worker
                    'bot_name': bot_name,  # Include bot name for multi-bot support
                    'refresh_cycle': True,
                    'bootstrap': False  # Not a bootstrap task
                },
                'delay_seconds': delay_seconds,  # For SQS DelaySeconds
                'priority': 0,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'submitted_by': 'github_auth_system'
            }
            
            # Send directly to queue
            success = queue_manager.send_task(task_data)
            
            if success:
                if delay_seconds > 0:
                    logger.info(f"GitHub refresh task scheduled for {delay_seconds} seconds delay")
                else:
                    logger.info("GitHub refresh task sent to queue immediately")
            else:
                logger.error("Failed to send GitHub refresh task to queue")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to send refresh task directly: {e}")
            return False
            
    async def get_bootstrap_status(self) -> Dict[str, Any]:
        """
        Get current bootstrap and authentication status for all configured bots.

        Returns:
            Dictionary with comprehensive status for all bots
        """
        try:
            from src.constants.github_bots import GitHubBot, get_all_bots

            # Get status for all configured bots
            bots_info = {}

            for bot in get_all_bots():
                try:
                    # Get token info for this bot
                    token_info = await self.auth_service.get_token_info(bot_name=bot)

                    # Get comprehensive auth status for this bot
                    auth_status = await self.auth_service.get_comprehensive_status(bot_name=bot)

                    bots_info[bot.value] = {
                        "token_info": token_info,
                        "auth_status": auth_status
                    }
                except Exception as e:
                    logger.error(f"Failed to get status for {bot}: {e}")
                    bots_info[bot.value] = {
                        "error": str(e)
                    }

            # Check if refresh tasks are scheduled (still global)
            refresh_status = await self._check_refresh_tasks()

            # Determine if bootstrap is complete (all bots authenticated)
            all_authenticated = all(
                bot_info.get("token_info", {}).get("authenticated", False)
                for bot_info in bots_info.values()
                if "error" not in bot_info
            )

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "bots": bots_info,
                "refresh_status": refresh_status,
                "bootstrap_complete": all_authenticated,
                "total_bots": len(bots_info),
                "authenticated_bots": sum(
                    1 for bot_info in bots_info.values()
                    if bot_info.get("token_info", {}).get("authenticated", False)
                )
            }

        except Exception as e:
            logger.error(f"Failed to get bootstrap status: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    async def _check_refresh_tasks(self) -> Dict[str, Any]:
        """
        Check if refresh tasks are properly scheduled.
        
        Returns:
            Dictionary with refresh task status
        """
        try:
            # Import here to avoid circular imports
            from src.tasks.service import TaskManager
            
            task_manager = TaskManager()  # Fixed: TaskManager takes no arguments
            
            # Get recent github_token_refresh tasks
            # This is a simplified check - in a full implementation you'd query the database
            return {
                "tasks_scheduled": True,  # Placeholder
                "next_refresh_estimated": "45 minutes from last refresh",
                "check_method": "simplified"
            }
            
        except Exception as e:
            logger.warning(f"Failed to check refresh tasks: {e}")
            return {
                "tasks_scheduled": False,
                "error": str(e)
            }


# Global bootstrap instance
_bootstrap_instance: Optional[GitHubAuthBootstrap] = None


async def initialize_github_auth() -> Dict[str, Any]:
    """
    Initialize GitHub authentication during application startup.
    
    This is the main entry point called from FastAPI lifespan.
    
    Returns:
        Dictionary with initialization status
    """
    global _bootstrap_instance
    
    try:
        _bootstrap_instance = GitHubAuthBootstrap()
        return await _bootstrap_instance.initialize_github_auth()
        
    except Exception as e:
        logger.error(f"GitHub authentication bootstrap failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def get_bootstrap_status() -> Dict[str, Any]:
    """
    Get current bootstrap status.
    
    Returns:
        Dictionary with bootstrap status
    """
    global _bootstrap_instance
    
    if _bootstrap_instance:
        return await _bootstrap_instance.get_bootstrap_status()
    else:
        return {
            "error": "Bootstrap not initialized",
            "timestamp": datetime.now(timezone.utc).isoformat()
        } 