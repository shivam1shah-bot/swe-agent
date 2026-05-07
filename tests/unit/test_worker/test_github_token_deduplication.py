"""
Unit tests for GitHub token refresh deduplication.

Tests the Redis-based deduplication mechanism that prevents duplicate
token refresh task scheduling across multiple pods.
"""
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.constants.github_bots import GitHubBot, DEFAULT_BOT


@pytest.mark.asyncio
class TestGitHubTokenDeduplication:
    """Test GitHub token refresh deduplication logic."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_mock = MagicMock()
        # Storage for test data
        redis_mock._data = {}

        def mock_get(key):
            return redis_mock._data.get(key)

        def mock_set(key, value, ttl=None, **kwargs):
            redis_mock._data[key] = value
            return True

        def mock_delete(key):
            if key in redis_mock._data:
                del redis_mock._data[key]
                return True
            return False

        def mock_get_ttl(key):
            if key in redis_mock._data:
                return 600  # Mock TTL value
            return -2

        redis_mock.get = Mock(side_effect=mock_get)
        redis_mock.set = Mock(side_effect=mock_set)
        redis_mock.delete = Mock(side_effect=mock_delete)
        redis_mock.get_ttl = Mock(side_effect=mock_get_ttl)

        return redis_mock

    @pytest.fixture
    def task_processor(self, mock_redis):
        """Create TaskProcessor instance with mocked dependencies."""
        with patch('src.tasks.service.task_manager', Mock()), \
             patch('src.worker.tasks.task_manager', Mock()), \
             patch('src.worker.tasks.get_config') as mock_config, \
             patch('src.providers.cache.redis_client.get_redis_client', return_value=mock_redis):

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

            from src.worker.tasks import TaskProcessor
            processor = TaskProcessor()
            yield processor

    async def test_schedule_refresh_prevents_duplicate(self, task_processor, mock_redis):
        """Test that concurrent scheduling is prevented via Redis flag."""
        bot_name = "rzp_swe_agent_app"
        dedup_key = f"github:refresh:scheduled:{bot_name}"

        # Clean slate
        mock_redis._data.clear()

        # Mock QueueManager.send_task to avoid actual queue operations
        with patch('src.worker.queue_manager.QueueManager') as mock_qm_class:
            mock_qm = Mock()
            mock_qm.send_task = Mock(return_value=True)
            mock_qm_class.return_value = mock_qm

            # First call - should set flag and send
            result1 = await task_processor._schedule_next_refresh_check(
                delay_seconds=600,
                bot_name=bot_name
            )

            assert result1 is True
            assert mock_redis.get(dedup_key) is not None  # Flag set
            assert mock_qm.send_task.call_count == 1  # Sent to queue

            # Second call (concurrent) - should skip
            result2 = await task_processor._schedule_next_refresh_check(
                delay_seconds=600,
                bot_name=bot_name
            )

            assert result2 is True  # Still success
            assert mock_redis.get(dedup_key) is not None  # Flag still set
            assert mock_qm.send_task.call_count == 1  # NOT sent again

    async def test_dedup_flag_cleared_on_send_failure(self, task_processor, mock_redis):
        """Test that dedup flag is cleared if queue send fails."""
        bot_name = "rzp_swe_agent_app"
        dedup_key = f"github:refresh:scheduled:{bot_name}"
        mock_redis._data.clear()

        # Mock send_task to fail
        with patch('src.worker.queue_manager.QueueManager') as mock_qm_class:
            mock_qm = Mock()
            mock_qm.send_task = Mock(return_value=False)  # Simulate failure
            mock_qm_class.return_value = mock_qm

            result = await task_processor._schedule_next_refresh_check(
                delay_seconds=600,
                bot_name=bot_name
            )

            assert result is False  # Failed
            assert mock_redis.get(dedup_key) is None  # Flag cleared for retry

    async def test_dedup_flag_cleared_after_task_completion(self, task_processor, mock_redis):
        """Test that dedup flag is cleared after token refresh completes."""
        bot_name = GitHubBot.SWE_AGENT
        dedup_key = f"github:refresh:scheduled:{bot_name.value}"

        # Set flag (simulating it was set during scheduling)
        mock_redis._data[dedup_key] = "scheduled"

        task_data = {
            'task_id': 'test-refresh',
            'task_type': 'github_token_refresh',
            'parameters': {
                'queue_only': True,
                'bot_name': bot_name.value
            }
        }

        # Mock token generation to succeed
        with patch.object(task_processor, '_generate_github_app_token',
                         new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                'success': True,
                'token': 'ghs_test_token_1234567890',
                'metadata': {
                    'token_type': 'github_app',
                    'expires_at': '2026-02-10T00:00:00Z'
                }
            }

            with patch.object(task_processor, '_setup_cli_tools_with_new_token',
                             new_callable=AsyncMock) as mock_cli:
                mock_cli.return_value = True

                with patch.object(task_processor, '_schedule_next_refresh_check',
                                 new_callable=AsyncMock) as mock_schedule:
                    mock_schedule.return_value = True

                    # Process task
                    result = await task_processor._handle_github_token_refresh(task_data)

                    assert result['success'] is True
                    # Flag should be cleared by finally block
                    assert mock_redis.get(dedup_key) is None

    async def test_dedup_flag_cleared_after_task_failure(self, task_processor, mock_redis):
        """Test that dedup flag is cleared even when task fails."""
        bot_name = GitHubBot.SWE_AGENT
        dedup_key = f"github:refresh:scheduled:{bot_name.value}"

        # Set flag (simulating it was set during scheduling)
        mock_redis._data[dedup_key] = "scheduled"

        task_data = {
            'task_id': 'test-refresh',
            'task_type': 'github_token_refresh',
            'parameters': {
                'queue_only': True,
                'bot_name': bot_name.value
            }
        }

        # Mock token generation to fail
        with patch.object(task_processor, '_generate_github_app_token',
                         new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                'success': False,
                'error': 'Test failure'
            }

            with patch.object(task_processor, '_schedule_next_refresh_check',
                             new_callable=AsyncMock) as mock_schedule:
                mock_schedule.return_value = True

                # Process task
                result = await task_processor._handle_github_token_refresh(task_data)

                assert result['success'] is False
                # Flag should be cleared by finally block even on failure
                assert mock_redis.get(dedup_key) is None

    async def test_dedup_per_bot_independent(self, task_processor, mock_redis):
        """Test that deduplication is per-bot (independent flags)."""
        bot1 = "rzp_swe_agent_app"
        bot2 = "rzp_code_review"
        dedup_key1 = f"github:refresh:scheduled:{bot1}"
        dedup_key2 = f"github:refresh:scheduled:{bot2}"

        mock_redis._data.clear()

        with patch('src.worker.queue_manager.QueueManager') as mock_qm_class:
            mock_qm = Mock()
            mock_qm.send_task = Mock(return_value=True)
            mock_qm_class.return_value = mock_qm

            # Schedule for bot1
            await task_processor._schedule_next_refresh_check(600, bot1)
            assert mock_redis.get(dedup_key1) is not None
            assert mock_redis.get(dedup_key2) is None

            # Schedule for bot2 - should NOT be blocked by bot1's flag
            await task_processor._schedule_next_refresh_check(600, bot2)
            assert mock_redis.get(dedup_key1) is not None  # Still set
            assert mock_redis.get(dedup_key2) is not None  # Also set

            # Both bots sent tasks
            assert mock_qm.send_task.call_count == 2

    async def test_dedup_flag_cleared_on_exception(self, task_processor, mock_redis):
        """Test that dedup flag is cleared when exception occurs during scheduling."""
        bot_name = "rzp_swe_agent_app"
        dedup_key = f"github:refresh:scheduled:{bot_name}"
        mock_redis._data.clear()

        # Mock QueueManager to raise exception
        with patch('src.worker.queue_manager.QueueManager') as mock_qm_class:
            mock_qm_class.side_effect = Exception("Test exception")

            result = await task_processor._schedule_next_refresh_check(
                delay_seconds=600,
                bot_name=bot_name
            )

            assert result is False  # Failed
            # Flag should be cleared by exception handler
            assert mock_redis.get(dedup_key) is None

    async def test_schedule_with_enum_bot_name(self, task_processor, mock_redis):
        """Test scheduling works with GitHubBot enum."""
        bot_name_enum = GitHubBot.SWE_AGENT
        dedup_key = f"github:refresh:scheduled:{bot_name_enum.value}"
        mock_redis._data.clear()

        with patch('src.worker.queue_manager.QueueManager') as mock_qm_class:
            mock_qm = Mock()
            mock_qm.send_task = Mock(return_value=True)
            mock_qm_class.return_value = mock_qm

            # Schedule with enum
            result = await task_processor._schedule_next_refresh_check(
                delay_seconds=600,
                bot_name=bot_name_enum
            )

            assert result is True
            assert mock_redis.get(dedup_key) is not None

    async def test_schedule_with_string_bot_name(self, task_processor, mock_redis):
        """Test scheduling works with string bot name."""
        bot_name_str = "rzp_swe_agent_app"
        dedup_key = f"github:refresh:scheduled:{bot_name_str}"
        mock_redis._data.clear()

        with patch('src.worker.queue_manager.QueueManager') as mock_qm_class:
            mock_qm = Mock()
            mock_qm.send_task = Mock(return_value=True)
            mock_qm_class.return_value = mock_qm

            # Schedule with string
            result = await task_processor._schedule_next_refresh_check(
                delay_seconds=600,
                bot_name=bot_name_str
            )

            assert result is True
            assert mock_redis.get(dedup_key) is not None
