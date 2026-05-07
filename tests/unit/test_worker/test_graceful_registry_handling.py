#!/usr/bin/env python3
"""
Unit tests for graceful registry handling when worker_instance is not available.

Tests that claude_code.py works correctly in different execution contexts:
- Worker pods (worker_instance available)
- API pods (worker_instance not available)  
- Standalone execution (worker_instance not available)
"""

import subprocess
import threading
import pytest
from unittest.mock import Mock, patch, MagicMock

# Mock database connections before importing
# Note: Python 3.13+ doesn't allow patching __init__ magic methods directly
# Instead, we patch the entire TaskManager class with a MagicMock
with patch('src.providers.database.provider.DatabaseProvider.initialize'), \
     patch('src.migrations.manager.MigrationManager'), \
     patch('src.tasks.service.TaskManager', MagicMock()):
    from src.agents.terminal_agents.claude_code import ClaudeCodeTool
    from src.utils.process_manager import ProcessManager


class TestGracefulRegistryHandling:
    """Test graceful handling when worker_instance may not exist."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clear any existing thread-local data
        current_thread = threading.current_thread()
        if hasattr(current_thread, 'worker_instance'):
            delattr(current_thread, 'worker_instance')
        if hasattr(current_thread, 'task_id'):
            delattr(current_thread, 'task_id')
    
    def test_worker_instance_detection_with_worker_available(self):
        """Test worker instance detection when running in worker pod."""
        # Create a mock worker instance
        mock_worker = Mock()
        mock_worker.register_task_process = Mock()
        mock_worker.unregister_task_process = Mock()
        
        # Set thread-local worker instance (simulates TaskProcessor setting it)
        current_thread = threading.current_thread()
        current_thread.worker_instance = mock_worker
        current_thread.task_id = "test-task-123"
        
        # Test worker instance detection using ProcessManager
        detected_worker = ProcessManager.get_current_worker_instance()
        assert detected_worker is mock_worker
        
        # Test task ID detection using ProcessManager
        detected_task_id = ProcessManager.get_current_task_id()
        assert detected_task_id == "test-task-123"
    
    def test_worker_instance_detection_api_pod_context(self):
        """Test worker instance detection when running in API pod (no worker)."""
        # Ensure no thread-local worker instance
        current_thread = threading.current_thread()
        if hasattr(current_thread, 'worker_instance'):
            delattr(current_thread, 'worker_instance')
        if hasattr(current_thread, 'task_id'):
            delattr(current_thread, 'task_id')
        
        # Test worker instance detection using ProcessManager (should be None)
        detected_worker = ProcessManager.get_current_worker_instance()
        assert detected_worker is None
        
        # Test task ID detection using ProcessManager (should be None)
        detected_task_id = ProcessManager.get_current_task_id()
        assert detected_task_id is None
    
    @patch('subprocess.Popen')
    def test_subprocess_execution_with_worker_available(self, mock_popen):
        """Test subprocess execution with worker instance available."""
        # Set up mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("output", "")
        mock_popen.return_value = mock_process
        
        # Set up mock worker
        mock_worker = Mock()
        mock_worker.register_task_process = Mock()
        mock_worker.unregister_task_process = Mock()
        
        # Set thread-local context
        current_thread = threading.current_thread()
        current_thread.worker_instance = mock_worker
        current_thread.task_id = "test-task-123"
        
        # Execute subprocess using ProcessManager directly
        result = ProcessManager.run_managed_subprocess(
            cmd=['echo', 'test'],
            env={},
            output_file=None,
            task_id="test-task-123",
            tool_name="test_tool"
        )
        
        # Verify process was registered and unregistered
        mock_worker.register_task_process.assert_called_once_with("test-task-123", 12345)
        mock_worker.unregister_task_process.assert_called_once_with("test-task-123", 12345)
        
        # Verify subprocess executed correctly
        assert result.returncode == 0
    
    @patch('subprocess.Popen')
    def test_subprocess_execution_without_worker(self, mock_popen):
        """Test subprocess execution without worker instance (API pod context)."""
        # Set up mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("output", "")
        mock_popen.return_value = mock_process
        
        # Ensure no worker instance in thread-local storage
        current_thread = threading.current_thread()
        if hasattr(current_thread, 'worker_instance'):
            delattr(current_thread, 'worker_instance')
        if hasattr(current_thread, 'task_id'):
            delattr(current_thread, 'task_id')
        
        # Execute subprocess using ProcessManager (should work without worker)
        result = ProcessManager.run_managed_subprocess(
            cmd=['echo', 'test'],
            env={},
            output_file=None,
            task_id=None,
            tool_name="test_tool"
        )
        
        # Verify subprocess executed correctly without errors
        assert result.returncode == 0
        
        # Verify our specific subprocess call was made
        mock_popen.assert_called_with(
            ['echo', 'test'],
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={}
        )
    
    @patch('subprocess.Popen')
    def test_subprocess_execution_worker_registration_error(self, mock_popen):
        """Test graceful handling when worker registration fails."""
        # Set up mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("output", "")
        mock_popen.return_value = mock_process
        
        # Set up mock worker that raises error on registration
        mock_worker = Mock()
        mock_worker.register_task_process.side_effect = Exception("Registration failed")
        mock_worker.unregister_task_process = Mock()
        
        # Set thread-local context
        current_thread = threading.current_thread()
        current_thread.worker_instance = mock_worker
        current_thread.task_id = "test-task-123"
        
        # Execute subprocess using ProcessManager (should handle registration error gracefully)
        result = ProcessManager.run_managed_subprocess(
            cmd=['echo', 'test'],
            env={},
            output_file=None,
            task_id="test-task-123",
            tool_name="test_tool"
        )
        
        # Verify subprocess still executed successfully despite registration error
        assert result.returncode == 0
        
        # Verify registration was attempted but failed gracefully
        mock_worker.register_task_process.assert_called_once_with("test-task-123", 12345)
        
        # Unregistration should not be called since registration failed
        mock_worker.unregister_task_process.assert_not_called()
    
    @patch('subprocess.Popen')
    def test_subprocess_execution_worker_unregistration_error(self, mock_popen):
        """Test graceful handling when worker unregistration fails."""
        # Set up mock process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("output", "")
        mock_popen.return_value = mock_process
        
        # Set up mock worker that raises error on unregistration
        mock_worker = Mock()
        mock_worker.register_task_process = Mock()
        mock_worker.unregister_task_process.side_effect = Exception("Unregistration failed")
        
        # Set thread-local context
        current_thread = threading.current_thread()
        current_thread.worker_instance = mock_worker
        current_thread.task_id = "test-task-123"
        
        # Execute subprocess using ProcessManager (should handle unregistration error gracefully)
        result = ProcessManager.run_managed_subprocess(
            cmd=['echo', 'test'],
            env={},
            output_file=None,
            task_id="test-task-123",
            tool_name="test_tool"
        )
        
        # Verify subprocess executed successfully despite unregistration error
        assert result.returncode == 0
        
        # Verify both registration and unregistration were attempted
        mock_worker.register_task_process.assert_called_once_with("test-task-123", 12345)
        mock_worker.unregister_task_process.assert_called_once_with("test-task-123", 12345)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])