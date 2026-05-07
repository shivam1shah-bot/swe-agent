"""
Unit tests for GitHub Provider (Auth Service, Bootstrap, and Exceptions).
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.providers.github.auth_service import GitHubAuthService
from src.providers.github.bootstrap import GitHubAuthBootstrap, initialize_github_auth
from src.providers.github.cli_sync_service import (
    GitHubCliSyncService, get_cli_sync_service, start_cli_sync_service, stop_cli_sync_service
)
from src.providers.github.exceptions import (
    GitHubError, GitHubAuthenticationError, GitHubCLIError
)


@pytest.mark.unit
class TestGitHubAuthService:
    """Test GitHub Authentication Service core functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "github": {
                "token": "ghp_personal_token_123",
                "rzp_swe_agent_app": {
                    "app_id": "123456",
                    "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
                    "installation_id": "789012"
                }
            },
            "environment": {"name": "dev"}
        }
        self.cache = Mock()

    @patch('src.providers.github.auth_service.get_config')
    @patch('src.providers.github.auth_service.get_redis_client')
    def test_initialization_and_environment_detection(self, mock_redis, mock_config):
        """Test service initialization and production environment detection."""
        # Test development environment
        dev_config = {"environment": {"name": "dev"}, "github": {}}
        mock_config.return_value = dev_config
        mock_redis.return_value = self.cache
        
        service = GitHubAuthService()
        assert service._is_production_env == False
        
        # Test production with GitHub app config
        mock_config.return_value = self.config
        service = GitHubAuthService()
        assert service._is_production_env == True  # Has GitHub app config

    @patch('src.providers.github.auth_service.get_config')
    @patch('src.providers.github.auth_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_token_retrieval_scenarios(self, mock_redis, mock_config):
        """Test main token retrieval scenarios."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubAuthService()
        
        # Scenario 1: Get token from cache
        self.cache.get.return_value = "ghs_cached_token_123"
        token = await service.get_token()
        assert token == "ghs_cached_token_123"
        
        # Scenario 2: Fallback to personal token in dev
        dev_config = {"environment": {"name": "dev"}, "github": {"token": "ghp_personal"}}
        mock_config.return_value = dev_config
        service = GitHubAuthService()
        self.cache.get.return_value = None  # No cached token
        
        token = await service.get_token()
        assert token == "ghp_personal"
        
        # Scenario 3: No token in production should raise error
        mock_config.return_value = self.config  # Production config
        service = GitHubAuthService()
        self.cache.get.return_value = None
        
        with pytest.raises(GitHubAuthenticationError) as exc_info:
            await service.get_token()
        assert "No GitHub token available" in str(exc_info.value)

    @patch('src.providers.github.auth_service.get_config')
    @patch('src.providers.github.auth_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_token_info_and_metadata(self, mock_redis, mock_config):
        """Test token info retrieval with metadata."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubAuthService()
        
        # Test with cached token and metadata (bot-specific keys)
        self.cache.get.side_effect = lambda key: {
            "github:token:rzp_swe_agent_app": "ghs_test_token",
            "github:token:metadata:rzp_swe_agent_app": json.dumps({"token_type": "github_app", "user_login": "test-user"})
        }.get(key)
        self.cache.get_ttl.return_value = 1800
        
        token_info = await service.get_token_info()
        
        assert token_info["authenticated"] == True
        assert token_info["source"] == "cache"
        assert token_info["token_type"] == "github_app"
        assert token_info["ttl_seconds"] == 1800

    def test_token_type_detection(self):
        """Test token type detection."""
        with patch('src.providers.github.auth_service.get_config') as mock_config, \
             patch('src.providers.github.auth_service.get_redis_client') as mock_redis:
            mock_config.return_value = self.config
            mock_redis.return_value = self.cache
            
            service = GitHubAuthService()
            
            assert service._detect_token_type("ghs_1234567890") == "github_app"
            assert service._detect_token_type("ghp_1234567890") == "personal_classic"
            assert service._detect_token_type("github_pat_1234567890") == "personal_fine_grained"
            assert service._detect_token_type("unknown_format") == "unknown"


@pytest.mark.unit
class TestGitHubAuthBootstrap:
    """Test GitHub Authentication Bootstrap functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            "github": {
                "rzp_swe_agent_app": {
                    "app_id": "123456",
                    "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
                    "installation_id": "789012"
                }
            },
            "environment": {"name": "dev"}
        }

    @patch('src.providers.github.bootstrap.get_config')
    @patch('src.providers.github.bootstrap.get_redis_client')
    @patch('src.providers.github.bootstrap.GitHubAuthService')
    def test_bootstrap_initialization(self, mock_auth_service, mock_redis, mock_config):
        """Test bootstrap initialization."""
        mock_config.return_value = self.config
        mock_redis.return_value = Mock()
        mock_auth_service.return_value = Mock()
        
        bootstrap = GitHubAuthBootstrap()
        assert bootstrap.config is not None
        assert bootstrap.cache is not None
        assert bootstrap.auth_service is not None

    @patch('src.providers.github.bootstrap.get_config')
    @patch('src.providers.github.bootstrap.get_redis_client')
    @patch('src.providers.github.bootstrap.GitHubAuthService')
    @pytest.mark.asyncio
    async def test_github_auth_initialization_flow(self, mock_auth_service, mock_redis, mock_config):
        """Test GitHub authentication initialization flow basics."""
        mock_config.return_value = self.config
        mock_redis.return_value = Mock()
        
        # Mock auth service with basic behavior
        mock_auth = Mock()
        mock_auth._is_production_env = False  # Simplified for unit test
        mock_auth.get_token_info = AsyncMock(return_value={
            "authenticated": False,
            "ttl_seconds": 0
        })
        mock_auth.setup_git_config = AsyncMock(return_value={"success": True})
        mock_auth.setup_gh_auth = AsyncMock(return_value={"success": True})
        mock_auth_service.return_value = mock_auth
        
        bootstrap = GitHubAuthBootstrap()
        
        # Test that bootstrap can be initialized
        assert bootstrap.config is not None
        assert bootstrap.cache is not None
        assert bootstrap.auth_service is not None

    @patch('src.providers.github.bootstrap.get_config')
    @patch('src.providers.github.bootstrap.get_redis_client')
    @patch('src.providers.github.bootstrap.GitHubAuthService')
    @pytest.mark.asyncio
    async def test_initialization_with_existing_token(self, mock_auth_service, mock_redis, mock_config):
        """Test initialization skipped when valid token exists."""
        mock_config.return_value = self.config
        mock_redis.return_value = Mock()
        
        # Mock auth service with existing valid token
        mock_auth = Mock()
        mock_auth.get_token_info = AsyncMock(return_value={
            "authenticated": True,
            "ttl_seconds": 1800,  # 30 minutes - more than 10 minute threshold
            "source": "cache"
        })
        mock_auth.setup_git_config = AsyncMock(return_value={"success": True})
        mock_auth.setup_gh_auth = AsyncMock(return_value={"success": True})
        mock_auth_service.return_value = mock_auth
        
        bootstrap = GitHubAuthBootstrap()
        result = await bootstrap.initialize_github_auth()

        assert result["success"] == True
        # Multi-bot response has "bots" key with per-bot results
        assert "bots" in result
        # Check rzp_swe_agent_app bot was initialized
        from src.constants.github_bots import GitHubBot
        assert GitHubBot.SWE_AGENT in result["bots"]
        assert result["bots"][GitHubBot.SWE_AGENT]["bootstrap_performed"] == False
        assert "already initialized" in result["bots"][GitHubBot.SWE_AGENT]["message"]

    @patch('src.providers.github.bootstrap.GitHubAuthBootstrap')
    @pytest.mark.asyncio
    async def test_module_initialize_function(self, mock_bootstrap_class):
        """Test module-level initialize_github_auth function."""
        mock_bootstrap = Mock()
        mock_bootstrap.initialize_github_auth = AsyncMock(return_value={
            "success": True,
            "message": "GitHub authentication system initialized"
        })
        mock_bootstrap_class.return_value = mock_bootstrap
        
        result = await initialize_github_auth()
        
        assert result["success"] == True
        assert "initialized" in result["message"]


@pytest.mark.unit
class TestGitHubCliSyncService:
    """Test GitHub CLI Synchronization Service functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {"github": {"token": "test_token"}}
        self.cache = Mock()
        
    def teardown_method(self):
        """Clean up after each test."""
        # Reset global sync service state (uses _sync_services dict, not _sync_service)
        import src.providers.github.cli_sync_service as sync_module
        sync_module._sync_services.clear()

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    def test_service_initialization(self, mock_redis, mock_config):
        """Test CLI sync service initialization."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService(sync_interval=600)
        
        assert service.sync_interval == 600
        assert service._running == False
        assert service._sync_task is None
        assert service.config == self.config
        assert service.cache == self.cache

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_service_lifecycle_start_stop(self, mock_redis, mock_config):
        """Test service start and stop functionality."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        # Test start
        with patch.object(service, '_background_sync_loop', new_callable=AsyncMock) as mock_loop:
            await service.start()
            assert service._running == True
            assert service._sync_task is not None
            
            # Test start when already running
            await service.start()  # Should not create new task
            
        # Test stop
        await service.stop()
        assert service._running == False

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_manual_sync_success(self, mock_redis, mock_config):
        """Test manual sync operation success."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        with patch.object(service, '_sync_cli_configs', new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = True  # Sync performed
            result = await service.sync_now()
            assert result == True
            mock_sync.assert_called_once()

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_manual_sync_failure(self, mock_redis, mock_config):
        """Test manual sync operation failure handling."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        with patch.object(service, '_sync_cli_configs', new_callable=AsyncMock) as mock_sync:
            mock_sync.side_effect = Exception("Sync failed")
            result = await service.sync_now()
            assert result == False

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_token_retrieval_from_local_file(self, mock_redis, mock_config):
        """Test local token extraction from git credentials."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        # Test successful token extraction
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'read_text', return_value="https://ghs_test_token@github.com"):
            
            token = await service._get_local_token()
            assert token == "ghs_test_token"
        
        # Test file not exists
        with patch.object(Path, 'exists', return_value=False):
            token = await service._get_local_token()
            assert token is None
        
        # Test invalid format
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'read_text', return_value="invalid format"):
            
            token = await service._get_local_token()
            assert token is None

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_redis_token_retrieval(self, mock_redis, mock_config):
        """Test token retrieval from Redis cache."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        # Test successful retrieval
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_executor = Mock()
            mock_executor.run_in_executor.return_value = asyncio.Future()
            mock_executor.run_in_executor.return_value.set_result("ghs_redis_token")
            mock_loop.return_value = mock_executor
            
            token = await service._get_redis_token()
            assert token == "ghs_redis_token"
        
        # Test retrieval failure
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_executor = Mock()
            mock_executor.run_in_executor.side_effect = Exception("Redis error")
            mock_loop.return_value = mock_executor
            
            token = await service._get_redis_token()
            assert token is None

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_redis_metadata_retrieval(self, mock_redis, mock_config):
        """Test metadata retrieval from Redis cache."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        # Test successful metadata retrieval
        test_metadata = {"token_type": "github_app", "user_login": "test-user"}
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_executor = Mock()
            mock_executor.run_in_executor.return_value = asyncio.Future()
            mock_executor.run_in_executor.return_value.set_result(json.dumps(test_metadata))
            mock_loop.return_value = mock_executor
            
            metadata = await service._get_redis_metadata()
            assert metadata == test_metadata

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_sync_cli_configs_scenarios(self, mock_redis, mock_config):
        """Test CLI config sync scenarios."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        # Scenario 1: Tokens match - no sync needed
        with patch.object(service, '_get_local_token', return_value="same_token"), \
             patch.object(service, '_get_redis_token', return_value="same_token"):
            
            result = await service._sync_cli_configs()
            assert result == False
        
        # Scenario 2: No Redis token
        with patch.object(service, '_get_local_token', return_value="local_token"), \
             patch.object(service, '_get_redis_token', return_value=None):
            
            result = await service._sync_cli_configs()
            assert result == False
        
        # Scenario 3: Tokens differ - sync performed
        with patch.object(service, '_get_local_token', return_value="old_token"), \
             patch.object(service, '_get_redis_token', return_value="new_token"), \
             patch.object(service, '_update_cli_configs', new_callable=AsyncMock) as mock_update:
            
            result = await service._sync_cli_configs()
            assert result == True
            mock_update.assert_called_once_with("new_token")

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    def test_file_path_initialization(self, mock_redis, mock_config):
        """Test file path initialization and directory creation."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        with patch.object(Path, 'mkdir') as mock_mkdir:
            service = GitHubCliSyncService()
            
            # Verify paths are set correctly
            assert service.git_credentials_path.name == ".git-credentials"
            assert service.gh_hosts_path.name == "hosts.yml"
            assert "gh" in str(service.gh_hosts_path)
            
            # Verify directory creation was attempted
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_cli_config_updates(self, mock_redis, mock_config):
        """Test CLI configuration file updates."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        with patch.object(service, '_get_redis_metadata', return_value={"user_login": "test-user"}), \
             patch.object(service, '_write_file_atomic', new_callable=AsyncMock) as mock_write:
            
            await service._update_cli_configs("ghs_new_token")
            
            # Should call write twice - git credentials and gh config
            assert mock_write.call_count == 2
            
            # Check git credentials call
            git_call = mock_write.call_args_list[0]
            assert "https://ghs_new_token@github.com" in str(git_call)
            
            # Check gh config call
            gh_call = mock_write.call_args_list[1]
            assert "oauth_token: ghs_new_token" in str(gh_call)
            assert "user: test-user" in str(gh_call)

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    def test_service_status(self, mock_redis, mock_config):
        """Test service status reporting."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        with patch.object(Path, 'exists', return_value=True):
            status = service.get_status()
            
            assert "running" in status
            assert "sync_interval" in status
            assert "git_credentials_exists" in status
            assert "gh_config_exists" in status
            assert "task_active" in status
            assert status["sync_interval"] == 300  # Default interval

    @patch('src.providers.github.cli_sync_service.get_config')
    @patch('src.providers.github.cli_sync_service.get_redis_client')
    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_redis, mock_config):
        """Test timeout handling in sync operations."""
        mock_config.return_value = self.config
        mock_redis.return_value = self.cache
        
        service = GitHubCliSyncService()
        
        with patch.object(service, '_get_local_token', return_value="local_token"), \
             patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            
            result = await service._sync_cli_configs()
            assert result == False

    def test_global_service_management(self):
        """Test global service instance management."""
        # Reset global state (uses _sync_services dict, not _sync_service)
        import src.providers.github.cli_sync_service as sync_module
        sync_module._sync_services.clear()

        with patch('src.providers.github.cli_sync_service.get_config'), \
             patch('src.providers.github.cli_sync_service.get_redis_client'):

            # Test get_cli_sync_service creates instance
            service1 = get_cli_sync_service()
            assert isinstance(service1, GitHubCliSyncService)

            # Test singleton behavior
            service2 = get_cli_sync_service()
            assert service1 is service2

    @patch('src.providers.github.cli_sync_service.get_cli_sync_service')
    @pytest.mark.asyncio
    async def test_global_start_stop_functions(self, mock_get_service):
        """Test global start/stop functions."""
        mock_service = Mock()
        mock_service.start = AsyncMock()
        mock_service.stop = AsyncMock()
        mock_get_service.return_value = mock_service

        # Test start_cli_sync_service
        await start_cli_sync_service(600)
        assert mock_service.sync_interval == 600
        mock_service.start.assert_called_once()

        # Test stop_cli_sync_service - need to set global variable
        # Note: The implementation uses _sync_services (plural, dict) not _sync_service
        import src.providers.github.cli_sync_service as sync_module
        from src.constants.github_bots import DEFAULT_BOT
        bot_key = DEFAULT_BOT.value if hasattr(DEFAULT_BOT, 'value') else DEFAULT_BOT
        sync_module._sync_services[bot_key] = mock_service  # Set in dict with bot key

        await stop_cli_sync_service()
        mock_service.stop.assert_called_once()


@pytest.mark.unit
class TestGitHubExceptions:
    """Test GitHub exception hierarchy."""

    def test_exception_inheritance(self):
        """Test exception inheritance and basic functionality."""
        # Test base exception
        base_error = GitHubError("Base error")
        assert isinstance(base_error, Exception)
        assert str(base_error) == "Base error"
        
        # Test authentication error
        auth_error = GitHubAuthenticationError("Auth failed")
        assert isinstance(auth_error, GitHubError)
        assert str(auth_error) == "Auth failed"
        
        # Test CLI error with details
        cli_error = GitHubCLIError(
            message="Command failed",
            command="gh auth login",
            returncode=1,
            stderr="authentication required"
        )
        assert isinstance(cli_error, GitHubError)
        assert str(cli_error) == "Command failed"
        assert cli_error.command == "gh auth login"
        assert cli_error.returncode == 1
        assert cli_error.stderr == "authentication required"

    def test_exception_catching(self):
        """Test that all GitHub exceptions can be caught as GitHubError."""
        exceptions = [
            GitHubAuthenticationError("auth error"),
            GitHubCLIError("cli error")
        ]

        for exc in exceptions:
            try:
                raise exc
            except GitHubError as caught:
                assert isinstance(caught, GitHubError)
                assert caught == exc


@pytest.mark.unit
class TestMultiBotSupport:
    """Test multi-bot authentication support."""

    @pytest.mark.asyncio
    async def test_auth_service_uses_bot_specific_cache_keys(self):
        """Test GitHubAuthService uses bot-specific cache keys."""
        from src.constants.github_bots import GitHubBot

        with patch('src.providers.github.auth_service.get_config') as mock_config, \
             patch('src.providers.github.auth_service.get_redis_client') as mock_redis:

            # Setup config for both bots
            mock_config.return_value = {
                "github": {
                    "rzp_swe_agent_app": {"app_id": "123"},
                    "rzp_code_review": {"app_id": "456"}
                },
                "environment": {"name": "dev"}
            }

            # Setup cache mock with bot-specific tokens
            mock_cache = Mock()
            mock_cache.get.side_effect = lambda key: {
                "github:token:rzp_swe_agent_app": "ghs_swe_token",
                "github:token:rzp_code_review": "ghs_review_token"
            }.get(key)
            mock_redis.return_value = mock_cache

            service = GitHubAuthService()

            # Get tokens for both bots
            swe_token = await service.get_token(bot_name=GitHubBot.SWE_AGENT)
            review_token = await service.get_token(bot_name=GitHubBot.CODE_REVIEW)

            # Assert different tokens returned
            assert swe_token == "ghs_swe_token"
            assert review_token == "ghs_review_token"

            # Assert correct cache keys used
            cache_calls = [call[0][0] for call in mock_cache.get.call_args_list]
            assert "github:token:rzp_swe_agent_app" in cache_calls
            assert "github:token:rzp_code_review" in cache_calls

    @pytest.mark.asyncio
    async def test_bootstrap_initializes_both_bots(self):
        """Test GitHubAuthBootstrap initializes both configured bots."""
        from src.constants.github_bots import GitHubBot

        with patch('src.providers.github.bootstrap.get_config') as mock_config, \
             patch('src.providers.github.bootstrap.get_redis_client') as mock_redis, \
             patch('src.providers.github.bootstrap.GitHubAuthService') as mock_auth_class:

            # Setup config with both bots
            mock_config.return_value = {
                "github": {
                    "rzp_swe_agent_app": {
                        "app_id": "123",
                        "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
                        "installation_id": "789"
                    },
                    "rzp_code_review": {
                        "app_id": "456",
                        "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
                        "installation_id": "012"
                    }
                },
                "environment": {"name": "dev"}
            }

            mock_redis.return_value = Mock()
            mock_auth = Mock()
            mock_auth.get_token_info = AsyncMock(return_value={"authenticated": False})
            mock_auth._detect_production_environment = Mock(return_value=True)
            mock_auth_class.return_value = mock_auth

            # Mock _initialize_bot to return success
            bootstrap = GitHubAuthBootstrap()

            with patch.object(bootstrap, '_initialize_bot') as mock_init_bot:
                mock_init_bot.return_value = {"success": True, "bot_name": "test", "configured": True}

                result = await bootstrap.initialize_github_auth()

                # Assert both bots initialized
                assert result['success'] == True
                assert GitHubBot.SWE_AGENT in result['bots']
                assert GitHubBot.CODE_REVIEW in result['bots']

                # Assert _initialize_bot called for both
                assert mock_init_bot.call_count == 2
                bot_names_called = [call[0][0] for call in mock_init_bot.call_args_list]
                assert GitHubBot.SWE_AGENT in bot_names_called
                assert GitHubBot.CODE_REVIEW in bot_names_called
