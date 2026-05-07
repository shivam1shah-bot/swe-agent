"""
Unit tests for TaskProcessor bot_name propagation.

Tests the critical bot_name parameter propagation through the token refresh cycle.
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from src.constants.github_bots import GitHubBot, DEFAULT_BOT


@pytest.mark.unit
class TestBotNamePropagation:
    """Test bot_name parameter propagation through token refresh."""

    @pytest.fixture
    def task_processor(self):
        """Create TaskProcessor instance with mocked dependencies."""
        # Mock task_manager before importing TaskProcessor to avoid DB initialization
        with patch('src.tasks.service.task_manager', Mock()), \
             patch('src.worker.tasks.task_manager', Mock()), \
             patch('src.worker.tasks.get_config') as mock_config:

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

            # Import here after mocking dependencies
            from src.worker.tasks import TaskProcessor
            processor = TaskProcessor()
            yield processor

    @pytest.mark.asyncio
    async def test_setup_cli_tools_propagates_bot_name(self, task_processor):
        """Test _setup_cli_tools_with_new_token() passes bot_name to auth_service."""
        with patch('src.providers.github.auth_service.GitHubAuthService') as mock_auth_class:
            mock_auth = Mock()
            mock_auth.setup_git_config = AsyncMock(return_value={"success": True})
            mock_auth.ensure_gh_auth = AsyncMock(return_value={"success": True})
            mock_auth_class.return_value = mock_auth

            # Test with CODE_REVIEW bot
            result = await task_processor._setup_cli_tools_with_new_token(
                bot_name=GitHubBot.CODE_REVIEW
            )

            # Assert bot_name propagated correctly
            assert result == True
            mock_auth.setup_git_config.assert_called_once_with(bot_name=GitHubBot.CODE_REVIEW)
            mock_auth.ensure_gh_auth.assert_called_once_with(bot_name=GitHubBot.CODE_REVIEW)

    @pytest.mark.asyncio
    async def test_schedule_refresh_includes_bot_name(self, task_processor):
        """Test _schedule_next_refresh_check() includes bot_name in task parameters."""
        with patch('src.worker.queue_manager.QueueManager') as mock_queue_class:
            mock_queue = Mock()
            mock_queue.send_task = Mock(return_value=True)
            mock_queue_class.return_value = mock_queue

            # Schedule refresh for CODE_REVIEW bot
            result = await task_processor._schedule_next_refresh_check(
                delay_seconds=600,
                bot_name=GitHubBot.CODE_REVIEW
            )

            # Assert task data includes bot_name
            assert result == True
            call_args = mock_queue.send_task.call_args[0][0]
            assert call_args['parameters']['bot_name'] == GitHubBot.CODE_REVIEW
            assert 'rzp_code_review' in call_args['task_id']

    @pytest.mark.asyncio
    async def test_token_refresh_maintains_bot_name_through_cycle(self, task_processor):
        """Test full token refresh cycle maintains bot_name."""
        # Mock all dependencies
        with patch('src.providers.cache.redis_client.get_redis_client') as mock_redis, \
             patch.object(task_processor, '_generate_github_app_token') as mock_gen_token, \
             patch.object(task_processor, '_setup_cli_tools_with_new_token') as mock_cli_setup, \
             patch.object(task_processor, '_schedule_next_refresh_check') as mock_schedule:

            # Setup mocks
            mock_cache = Mock()
            mock_cache.get.return_value = None  # No cached token
            mock_cache.set = Mock()
            mock_cache.get_ttl = Mock(return_value=0)
            mock_redis.return_value = mock_cache

            mock_gen_token.return_value = {
                "success": True,
                "token": "ghs_new_token",
                "metadata": {"token_type": "github_app", "bot_name": "rzp_code_review"}
            }
            mock_cli_setup.return_value = True
            mock_schedule.return_value = True

            # Set up worker_instance with matching github_bot so CLI setup is called
            # The code checks: if bot_name == worker_bot: call _setup_cli_tools_with_new_token
            mock_worker = Mock()
            mock_worker.github_bot = GitHubBot.CODE_REVIEW
            task_processor.worker_instance = mock_worker

            # Execute token refresh for CODE_REVIEW bot
            task_data = {
                'task_id': 'test-refresh',
                'parameters': {'bot_name': GitHubBot.CODE_REVIEW, 'queue_only': True}
            }

            result = await task_processor._handle_github_token_refresh(task_data)

            # Verify bot_name maintained through entire cycle
            assert result['success'] == True

            # Check cache keys are bot-specific
            cache_calls = [call[0][0] for call in mock_cache.set.call_args_list]
            assert any('github:token:rzp_code_review' in key for key in cache_calls)

            # Check CLI setup called with bot_name
            mock_cli_setup.assert_called_once_with(bot_name=GitHubBot.CODE_REVIEW)

            # Check next refresh scheduled with bot_name
            mock_schedule.assert_called_once()
            schedule_call_kwargs = mock_schedule.call_args[1]
            assert schedule_call_kwargs['bot_name'] == GitHubBot.CODE_REVIEW
