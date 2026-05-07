"""
GitHub Authentication Service for Multi-Pod Environment.

This service provides GitHub authentication for API pods by reading tokens from cache
and handling git/gh CLI setup. Token refresh is handled by dedicated worker processes.
"""

import asyncio
import logging
import os
import subprocess
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone

from ..cache.redis_client import get_redis_client
from ..config_loader import get_config
from .exceptions import GitHubAuthenticationError
from src.constants.github_bots import GitHubBot, DEFAULT_BOT

logger = logging.getLogger(__name__)


class GitHubAuthService:
    """
    Main GitHub authentication service for multi-pod deployments.
    
    Provides:
    - Token retrieval from cache with fallback
    - Git and gh CLI configuration
    - Token validation and testing
    - Comprehensive status reporting
    """
    
    def __init__(self):
        """Initialize the GitHub auth service."""
        self.config = get_config()
        self.cache = get_redis_client()
        self._is_production_env = self._detect_production_environment()

    def _detect_production_environment(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> bool:
        """
        Detect if we should use GitHub app authentication for specified bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum (or string)

        Returns True if:
        1. GitHub app configuration is available (app_id, private_key, installation_id), OR
        2. Running in production/stage environment
        """
        # Check if GitHub app configuration is available for this bot
        github_app_config = self.config.get("github", {}).get(bot_name.value, {})
        has_github_app = all([
            github_app_config.get("app_id"),
            github_app_config.get("private_key"),
            github_app_config.get("installation_id")
        ])

        if has_github_app:
            return True

        # Fallback to environment name check
        env_name = self.config.get("environment", {}).get("name", "dev")
        return env_name in ["prod", "stage", "production"]
        
    async def get_token(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> str:
        """
        Get valid GitHub token for specified bot from cache with fallback.

        Args:
            bot_name: Bot identifier from GitHubBot enum (or string)

        Returns:
            GitHub token string

        Raises:
            GitHubAuthenticationError: If no valid token available
        """
        try:
            # Try to get cached token first (bot-specific key)
            cache_key = f"github:token:{bot_name.value if hasattr(bot_name, 'value') else bot_name}"
            cached_token = self.cache.get(cache_key)

            if cached_token:
                # Handle potential bytes from Redis (tokens are plain strings, not JSON)
                if isinstance(cached_token, bytes):
                    cached_token = cached_token.decode('utf-8')

                logger.debug(f"Using cached GitHub token for {bot_name}")
                return cached_token

            # If no cached token, check fallback options
            is_production = self._detect_production_environment(bot_name=bot_name)
            if not is_production:
                # Development environment - try personal token fallback
                personal_token = self._get_personal_token_fallback()
                if personal_token:
                    logger.info(f"Using personal token fallback for {bot_name} in development")
                    return personal_token

            # No token available
            if is_production:
                raise GitHubAuthenticationError(
                    f"No GitHub token available for {bot_name}. Ensure worker is running to refresh tokens."
                )
            else:
                raise GitHubAuthenticationError(
                    f"No GitHub token available for {bot_name}. Set github.token in configuration or ensure worker is running."
                )

        except Exception as e:
            if isinstance(e, GitHubAuthenticationError):
                raise
            logger.error(f"Failed to get GitHub token for {bot_name}: {e}")
            raise GitHubAuthenticationError(f"Token retrieval failed for {bot_name}: {str(e)}")
            
    def _get_personal_token_fallback(self) -> Optional[str]:
        """Get personal access token from configuration only."""
        try:
            # Get token from configuration only
            token = self.config.get("github", {}).get("token")
            if token:
                logger.debug("Found personal token in configuration")
                return token
                    
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get personal token fallback: {e}")
            return None
            
    async def get_token_info(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> Dict[str, Any]:
        """
        Get comprehensive information about token for specified bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum (or string)

        Returns:
            Dictionary with token status, metadata, and environment info
        """
        try:
            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "environment": self.config.get("environment", {}).get("name", "stage"),
                "bot_name": bot_name
            }

            # Check for cached token and metadata (bot-specific keys)
            bot_name_str = bot_name.value if hasattr(bot_name, 'value') else bot_name
            cache_key = f"github:token:{bot_name_str}"
            metadata_key = f"github:token:metadata:{bot_name_str}"

            cached_token = self.cache.get(cache_key)
            token_metadata = self.cache.get(metadata_key)

            if cached_token:
                token_ttl = self.cache.get_ttl(cache_key)
                
                result.update({
                    "authenticated": True,
                    "source": "cache",
                    "token_prefix": cached_token[:10] + "..." if len(cached_token) > 10 else cached_token,
                    "token_type": self._detect_token_type(cached_token),
                    "ttl_seconds": token_ttl,
                    "expires_in_minutes": round(token_ttl / 60) if token_ttl > 0 else 0
                })
                
                # Add metadata if available
                if token_metadata:
                    try:
                        import json
                        metadata = json.loads(token_metadata) if isinstance(token_metadata, str) else token_metadata
                        result["metadata"] = metadata
                    except (json.JSONDecodeError, TypeError):
                        logger.warning("Failed to parse token metadata")
                        
            elif not self._is_production_env:
                # Check for fallback token in development
                fallback_token = self._get_personal_token_fallback()
                if fallback_token:
                    result.update({
                        "authenticated": True,
                        "source": "fallback",
                        "token_prefix": fallback_token[:10] + "..." if len(fallback_token) > 10 else fallback_token,
                        "token_type": self._detect_token_type(fallback_token),
                        "ttl_seconds": -1,  # No TTL for fallback tokens
                        "expires_in_minutes": -1
                    })
                else:
                    result.update({
                        "authenticated": False,
                        "source": "none",
                        "message": "No token available in development environment"
                    })
            else:
                result.update({
                    "authenticated": False,
                    "source": "none", 
                    "message": "No cached token available in production environment"
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return {
                "authenticated": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    def _detect_token_type(self, token: str) -> str:
        """Detect the type of GitHub token based on its prefix."""
        if token.startswith('ghs_'):
            return "github_app"
        elif token.startswith('ghp_'):
            return "personal_classic"
        elif token.startswith('github_pat_'):
            return "personal_fine_grained"
        else:
            return "unknown"
            
    async def setup_git_config(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> Dict[str, Any]:
        """
        Setup git configuration with user identity from token metadata for specified bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum (or string)

        Returns:
            Dictionary with setup status and configured values
        """
        try:
            # Get token metadata for user information (bot-specific key)
            metadata_key = f"github:token:metadata:{bot_name.value if hasattr(bot_name, 'value') else bot_name}"
            token_metadata = self.cache.get(metadata_key)
            user_name = None
            user_email = None

            if token_metadata:
                try:
                    import json
                    metadata = json.loads(token_metadata) if isinstance(token_metadata, str) else token_metadata
                    user_name = metadata.get("user_login")
                    user_email = metadata.get("user_email")
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to parse token metadata for git config")
            
            if not user_name:
                user_name = "razorpay-swe-agent"
                user_email = "swe-agent@razorpay.com"
            
            # Set git configuration
            git_commands = [
                ["git", "config", "--global", "user.name", user_name],
                ["git", "config", "--global", "user.email", user_email or f"{user_name}@razorpay.com"],
                ["git", "config", "--global", "credential.helper", "store"]
            ]
            
            configured = {}
            for cmd in git_commands:
                try:
                    result = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await result.communicate()
                    
                    if result.returncode == 0:
                        config_key = cmd[3]  # Extract the config key (user.name, user.email, etc.)
                        configured[config_key] = cmd[4] if len(cmd) > 4 else "configured"
                    else:
                        logger.warning(f"Failed to set git config: {' '.join(cmd)}")
                        
                except Exception as e:
                    logger.warning(f"Error setting git config {' '.join(cmd)}: {e}")
            
            logger.info(f"Git configuration setup completed: {configured}")
            return {
                "success": True,
                "configured": configured,
                "user_name": user_name,
                "user_email": user_email or f"{user_name}@razorpay.com"
            }
            
        except Exception as e:
            logger.error(f"Failed to setup git config: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def ensure_gh_auth(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> Dict[str, Any]:
        """
        Ensure gh CLI is authenticated with current token for specified bot.

        Args:
            bot_name: Bot identifier from GitHubBot enum

        Returns:
            Dictionary with authentication status
        """
        try:
            # Get current token for specified bot
            token = await self.get_token(bot_name=bot_name)
            
            # Authenticate gh CLI with token input
            process = await asyncio.create_subprocess_exec(
                "gh", "auth", "login", "--with-token",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=token.encode()),
                timeout=30.0
            )
            
            if process.returncode == 0:
                logger.info("Successfully authenticated gh CLI")
                
                # Setup git integration
                setup_git_process = await asyncio.create_subprocess_exec(
                    "gh", "auth", "setup-git",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await setup_git_process.communicate()
                
                return {
                    "success": True,
                    "message": "gh CLI authenticated successfully",
                    "git_integration": setup_git_process.returncode == 0
                }
            else:
                error_msg = stderr.decode().strip()
                logger.error(f"gh auth login failed: {error_msg}")
                return {
                    "success": False,
                    "error": f"gh auth login failed: {error_msg}"
                }
                
        except asyncio.TimeoutError:
            logger.error("gh auth login timed out")
            return {
                "success": False,
                "error": "gh auth login timed out"
            }
        except Exception as e:
            logger.error(f"Failed to ensure gh auth: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def test_git_access(self) -> Dict[str, Any]:
        """
        Test git access by attempting a lightweight operation.
        
        Returns:
            Dictionary with test results
        """
        try:
            # Test git ls-remote on a public repository
            process = await asyncio.create_subprocess_exec(
                "git", "ls-remote", "https://github.com/razorpay/swe-agent.git", "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=15.0
            )
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "message": "Git access test successful"
                }
            else:
                error_msg = stderr.decode().strip()
                return {
                    "success": False,
                    "error": f"Git access test failed: {error_msg}"
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Git access test timed out"
            }
        except Exception as e:
            logger.error(f"Git access test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def test_gh_access(self) -> Dict[str, Any]:
        """
        Test gh CLI access by checking authentication status.
        
        Returns:
            Dictionary with test results
        """
        try:
            # Test gh auth status
            process = await asyncio.create_subprocess_exec(
                "gh", "auth", "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=10.0
            )
            
            if process.returncode == 0:
                # Parse the output to get user info
                output = stderr.decode().strip()  # gh auth status outputs to stderr
                return {
                    "success": True,
                    "message": "gh CLI access test successful",
                    "status_output": output
                }
            else:
                error_msg = stderr.decode().strip()
                return {
                    "success": False,
                    "error": f"gh CLI access test failed: {error_msg}"
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "gh CLI access test timed out"
            }
        except Exception as e:
            logger.error(f"gh CLI access test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def test_github_api_access(self) -> Dict[str, Any]:
        """
        Test GitHub API access with current token.
        
        Returns:
            Dictionary with test results including rate limit info
        """
        try:
            import aiohttp
            
            token = await self.get_token()
            
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'swe-agent'
            }
            
            async with aiohttp.ClientSession() as session:
                # Test with rate limit endpoint (lightweight)
                async with session.get('https://api.github.com/rate_limit', headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        return {
                            "success": True,
                            "message": "GitHub API access test successful",
                            "rate_limit": {
                                "limit": data.get("rate", {}).get("limit"),
                                "remaining": data.get("rate", {}).get("remaining"),
                                "reset": data.get("rate", {}).get("reset")
                            }
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"GitHub API access test failed: HTTP {response.status} - {error_text}"
                        }
                        
        except Exception as e:
            logger.error(f"GitHub API access test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def get_comprehensive_status(self, bot_name: Union[GitHubBot, str] = DEFAULT_BOT) -> Dict[str, Any]:
        """
        Get comprehensive GitHub authentication status including all tests.

        Args:
            bot_name: Bot identifier from GitHubBot enum (or string)

        Returns:
            Dictionary with complete status information
        """
        try:
            # Get basic token info
            token_info = await self.get_token_info(bot_name=bot_name)

            # If not authenticated, return early
            if not token_info.get("authenticated", False):
                return {
                    "overall_status": "not_authenticated",
                    "token_info": token_info,
                    "git_config": None,
                    "tests": None
                }

            # Run all tests in parallel
            git_config_task = asyncio.create_task(self.setup_git_config(bot_name=bot_name))
            git_test_task = asyncio.create_task(self.test_git_access(bot_name=bot_name))
            gh_test_task = asyncio.create_task(self.test_gh_access(bot_name=bot_name))
            api_test_task = asyncio.create_task(self.test_github_api_access(bot_name=bot_name))
            
            git_config_result = await git_config_task
            git_test_result = await git_test_task
            gh_test_result = await gh_test_task
            api_test_result = await api_test_task
            
            # Determine overall status
            all_tests_passed = all([
                git_test_result.get("success", False),
                gh_test_result.get("success", False),
                api_test_result.get("success", False)
            ])
            
            overall_status = "healthy" if all_tests_passed else "degraded"
            
            return {
                "overall_status": overall_status,
                "token_info": token_info,
                "git_config": git_config_result,
                "tests": {
                    "git_access": git_test_result,
                    "gh_access": gh_test_result,
                    "api_access": api_test_result
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get comprehensive status: {e}")
            return {
                "overall_status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    async def check_repository_visibility(self, repo_url: str) -> Dict[str, Any]:
        """
        Check if a repository is private or public.
        
        Args:
            repo_url: GitHub repository URL (https://github.com/owner/repo or git@github.com:owner/repo.git)
            
        Returns:
            Dictionary with visibility information:
            - success: bool
            - is_private: bool (only if success=True)
            - accessible: bool (only if success=True) 
            - error: str (only if success=False)
        """
        try:
            # Parse owner and repo from URL
            owner, repo = self._parse_github_url(repo_url)
            if not owner or not repo:
                return {
                    "success": False,
                    "error": f"Invalid GitHub repository URL format: {repo_url}"
                }
            
            import aiohttp
            
            token = await self.get_token()
            
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'swe-agent'
            }
            
            async with aiohttp.ClientSession() as session:
                # Call GitHub API to get repository information
                api_url = f'https://api.github.com/repos/{owner}/{repo}'
                async with session.get(api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        is_private = data.get("private", False)
                        
                        logger.info(f"Repository visibility check successful for {owner}/{repo}",
                                  extra={"owner": owner, "repo": repo, "is_private": is_private})
                        
                        return {
                            "success": True,
                            "is_private": is_private,
                            "accessible": True,
                            "owner": owner,
                            "repo": repo
                        }
                    elif response.status == 404:
                        # Repository not found or no access
                        return {
                            "success": False,
                            "error": f"Repository {owner}/{repo} not found or not accessible with current token"
                        }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "error": "Invalid or expired GitHub token"
                        }
                    elif response.status == 403:
                        return {
                            "success": False,
                            "error": f"Access forbidden to repository {owner}/{repo}. Token may lack required permissions."
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"GitHub API error: HTTP {response.status} - {error_text}"
                        }
                        
        except Exception as e:
            logger.error(f"Repository visibility check failed for {repo_url}: {e}")
            return {
                "success": False,
                "error": f"Failed to check repository visibility: {str(e)}"
            }
    
    def _parse_github_url(self, repo_url: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse GitHub repository URL to extract owner and repository name.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo) or (None, None) if parsing fails
        """
        try:
            import re
            
            # Handle https://github.com/owner/repo format
            https_pattern = r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$'
            https_match = re.match(https_pattern, repo_url.strip())
            
            if https_match:
                return https_match.group(1), https_match.group(2)
            
            # Handle git@github.com:owner/repo.git format
            ssh_pattern = r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$'
            ssh_match = re.match(ssh_pattern, repo_url.strip())
            
            if ssh_match:
                return ssh_match.group(1), ssh_match.group(2)
            
            return None, None
            
        except Exception as e:
            logger.warning(f"Failed to parse GitHub URL {repo_url}: {e}")
            return None, None 