"""
GitHub CLI Synchronization Service.

Handles background synchronization of git and gh CLI configurations
across multiple pods by monitoring Redis for token changes.
"""

import asyncio
import logging
import os
import tempfile
import json
from typing import Optional, Dict, Any
from pathlib import Path

from ..cache.redis_client import get_redis_client
from ..config_loader import get_config
from src.constants.github_bots import GitHubBot, DEFAULT_BOT

logger = logging.getLogger(__name__)


class GitHubCliSyncService:
    """
    Background service that synchronizes GitHub CLI configurations across pods.
    
    Monitors Redis for token changes and updates local CLI configs when needed.
    """
    
    def __init__(self, sync_interval: int = 300, bot_name: GitHubBot = None):
        """
        Initialize the CLI sync service.

        Args:
            sync_interval: Sync check interval in seconds (default: 5 minutes)
            bot_name: GitHub bot to sync credentials for (default: DEFAULT_BOT)
        """
        self.config = get_config()
        self.cache = get_redis_client()
        self.sync_interval = sync_interval
        self.bot_name = bot_name or DEFAULT_BOT
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False
        
        # CLI config paths
        self.git_credentials_path = Path.home() / ".git-credentials"
        self.gh_hosts_path = Path.home() / ".config" / "gh" / "hosts.yml"
        
        # Ensure directories exist
        self.gh_hosts_path.parent.mkdir(parents=True, exist_ok=True)
        
    async def start(self):
        """Start the background sync service."""
        if self._running:
            logger.warning("CLI sync service already running")
            return
            
        self._running = True
        self._sync_task = asyncio.create_task(self._background_sync_loop())
        logger.info(f"GitHub CLI sync service started (interval: {self.sync_interval}s)")
        
    async def stop(self):
        """Stop the background sync service."""
        if not self._running:
            return
            
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
                
        logger.info("GitHub CLI sync service stopped")
        
    async def sync_now(self) -> bool:
        """
        Perform immediate sync check and update if needed.
        
        Returns:
            True if sync was performed, False if no update needed
        """
        try:
            return await self._sync_cli_configs()
        except Exception as e:
            logger.warning(f"Manual sync failed: {e}")
            return False
            
    async def _background_sync_loop(self):
        """Background loop that performs periodic sync checks."""
        while self._running:
            try:
                await self._sync_cli_configs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Background sync failed: {e}")
                
            try:
                await asyncio.sleep(self.sync_interval)
            except asyncio.CancelledError:
                break
                
    async def _sync_cli_configs(self) -> bool:
        """
        Check and sync CLI configurations if needed.
        
        Returns:
            True if sync was performed, False if no update needed
        """
        try:
            # Get current local token
            local_token = await self._get_local_token()
            
            # Get Redis token with timeout
            redis_token = await asyncio.wait_for(
                self._get_redis_token(),
                timeout=2.0
            )
            
            if not redis_token:
                logger.debug("No token in Redis cache")
                return False
                
            if local_token == redis_token:
                logger.debug("Local CLI config is up to date")
                return False
                
            # Tokens differ - update local config
            await self._update_cli_configs(redis_token)
            logger.info("CLI configuration synced from Redis")
            return True
            
        except asyncio.TimeoutError:
            logger.debug("Redis timeout during sync - skipping this cycle")
            return False
        except Exception as e:
            logger.warning(f"CLI sync failed: {e}")
            return False
            
    async def _get_local_token(self) -> Optional[str]:
        """Extract current token from local git credentials."""
        try:
            if not self.git_credentials_path.exists():
                return None
                
            async with asyncio.Lock():
                content = self.git_credentials_path.read_text().strip()
                
            # Extract token from: https://TOKEN@github.com
            if content.startswith("https://") and "@github.com" in content:
                token_part = content.split("://")[1].split("@github.com")[0]
                return token_part
                
            return None
            
        except Exception as e:
            logger.debug(f"Failed to read local token: {e}")
            return None
            
    async def _get_redis_token(self) -> Optional[str]:
        """Get current token from Redis cache using bot-specific key."""
        try:
            # Build bot-specific cache key
            bot_value = self.bot_name.value if hasattr(self.bot_name, 'value') else self.bot_name
            cache_key = f"github:token:{bot_value}"

            # Run in thread pool to avoid blocking
            token = await asyncio.get_event_loop().run_in_executor(
                None,
                self.cache.get,
                cache_key
            )
            return token
        except Exception as e:
            logger.debug(f"Failed to get Redis token for {self.bot_name}: {e}")
            return None
            
    async def _get_redis_metadata(self) -> Dict[str, Any]:
        """Get token metadata from Redis cache using bot-specific key."""
        try:
            # Build bot-specific cache key
            bot_value = self.bot_name.value if hasattr(self.bot_name, 'value') else self.bot_name
            metadata_key = f"github:token:metadata:{bot_value}"

            metadata_json = await asyncio.get_event_loop().run_in_executor(
                None,
                self.cache.get,
                metadata_key
            )

            if metadata_json:
                return json.loads(metadata_json)
            return {}

        except Exception as e:
            logger.debug(f"Failed to get Redis metadata for {self.bot_name}: {e}")
            return {}
            
    async def _update_cli_configs(self, token: str):
        """
        Update local CLI configurations with new token.
        
        Args:
            token: New GitHub token
        """
        metadata = await self._get_redis_metadata()
        user_login = metadata.get("user_login", "rzp-swe-agent[bot]")
        
        # Update git credentials
        await self._update_git_credentials(token)
        
        # Update gh CLI config
        await self._update_gh_config(token, user_login)
        
    async def _update_git_credentials(self, token: str):
        """Update git credentials file atomically."""
        git_credentials_content = f"https://{token}@github.com"
        
        await self._write_file_atomic(
            self.git_credentials_path,
            git_credentials_content,
            mode=0o600  # Secure permissions
        )
        
    async def _update_gh_config(self, token: str, user_login: str):
        """Update gh CLI hosts.yml file atomically."""
        gh_config_content = f"""github.com:
    oauth_token: {token}
    user: {user_login}
    git_protocol: https
"""
        
        await self._write_file_atomic(
            self.gh_hosts_path,
            gh_config_content,
            mode=0o600  # Secure permissions
        )
        
    async def _write_file_atomic(self, target_path: Path, content: str, mode: int = 0o644):
        """
        Write file content atomically using temporary file and rename.
        
        Args:
            target_path: Target file path
            content: File content to write
            mode: File permissions
        """
        # Create temporary file in same directory as target
        temp_dir = target_path.parent
        
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=temp_dir,
            delete=False,
            prefix=f".{target_path.name}.tmp"
        ) as temp_file:
            temp_path = Path(temp_file.name)
            
            # Write content to temporary file
            await asyncio.get_event_loop().run_in_executor(
                None,
                temp_file.write,
                content
            )
            
        try:
            # Set correct permissions
            temp_path.chmod(mode)
            
            # Atomic rename
            await asyncio.get_event_loop().run_in_executor(
                None,
                temp_path.rename,
                target_path
            )
            
        except Exception:
            # Clean up temp file on failure
            temp_path.unlink(missing_ok=True)
            raise
            
    def get_status(self) -> Dict[str, Any]:
        """Get current sync service status."""
        return {
            "running": self._running,
            "sync_interval": self.sync_interval,
            "git_credentials_exists": self.git_credentials_path.exists(),
            "gh_config_exists": self.gh_hosts_path.exists(),
            "task_active": self._sync_task is not None and not self._sync_task.done()
        }


# Global sync service instance (per bot)
_sync_services: Dict[str, GitHubCliSyncService] = {}


def get_cli_sync_service(bot_name: GitHubBot = None) -> GitHubCliSyncService:
    """Get the CLI sync service instance for a specific bot."""
    global _sync_services
    bot = bot_name or DEFAULT_BOT
    bot_key = bot.value if hasattr(bot, 'value') else bot

    if bot_key not in _sync_services:
        _sync_services[bot_key] = GitHubCliSyncService(bot_name=bot)
    return _sync_services[bot_key]


async def start_cli_sync_service(sync_interval: int = 300, bot_name: GitHubBot = None):
    """Start the CLI sync service for a specific bot."""
    service = get_cli_sync_service(bot_name=bot_name)
    service.sync_interval = sync_interval
    await service.start()


async def stop_cli_sync_service(bot_name: GitHubBot = None):
    """Stop the CLI sync service for a specific bot."""
    global _sync_services
    bot = bot_name or DEFAULT_BOT
    bot_key = bot.value if hasattr(bot, 'value') else bot

    if bot_key in _sync_services:
        await _sync_services[bot_key].stop() 