#!/usr/bin/env python3
"""
Unit tests for task cancellation functionality.

Tests the core cancellation logic including:
- Task pickup validation for cancelled tasks
- Background cancellation monitoring  
- Worker task registry operations
- TaskProcessor cancellation detection
"""

import asyncio
import threading
import time
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock


class TestTaskCancellationLogic:
    """Test core cancellation logic without external dependencies."""
    
    def test_worker_task_registry_operations(self):
        """Test basic task registry operations."""
        # Create minimal worker-like object with task registry
        class MockWorker:
            def __init__(self):
                self.running_tasks = {}
                self.task_lock = threading.Lock()
            
            def register_running_task(self, task_id, task_data):
                with self.task_lock:
                    self.running_tasks[task_id] = {
                        'start_time': time.time(),
                        'task_data': task_data,
                        'cancel_requested': False
                    }
            
            def unregister_running_task(self, task_id):
                with self.task_lock:
                    if task_id in self.running_tasks:
                        del self.running_tasks[task_id]
            
            def is_task_cancellation_requested(self, task_id):
                with self.task_lock:
                    task_info = self.running_tasks.get(task_id, {})
                    return task_info.get('cancel_requested', False)
            
            def signal_task_cancellation(self, task_id):
                with self.task_lock:
                    if task_id in self.running_tasks:
                        self.running_tasks[task_id]['cancel_requested'] = True
        
        worker = MockWorker()
        task_id = "test-task-123"
        task_data = {'task_id': task_id, 'task_type': 'test'}
        
        # Test registration
        assert task_id not in worker.running_tasks
        worker.register_running_task(task_id, task_data)
        assert task_id in worker.running_tasks
        assert worker.running_tasks[task_id]['task_data'] == task_data
        assert worker.running_tasks[task_id]['cancel_requested'] == False
        
        # Test cancellation detection
        assert worker.is_task_cancellation_requested(task_id) == False
        worker.signal_task_cancellation(task_id)
        assert worker.is_task_cancellation_requested(task_id) == True
        
        # Test unregistration
        worker.unregister_running_task(task_id)
        assert task_id not in worker.running_tasks
        assert worker.is_task_cancellation_requested(task_id) == False
    
    @pytest.mark.asyncio
    async def test_task_status_validation_logic(self):
        """Test task status validation logic without database."""
        # Mock task manager
        mock_task_manager = Mock()
        
        # Simulate our task validation logic
        def validate_task_before_processing(task_id, task_manager):
            current_status = task_manager.get_task_status(task_id)
            if current_status:
                terminal_states = ['cancelled', 'failed', 'completed']
                if current_status.lower() in terminal_states:
                    return {
                        'success': True,
                        'skipped': True,
                        'reason': f'task_already_{current_status.lower()}',
                        'task_id': task_id
                    }
            return None  # Continue processing
        
        # Test cancelled task
        mock_task_manager.get_task_status.return_value = 'cancelled'
        result = validate_task_before_processing('cancelled-task', mock_task_manager)
        assert result['success'] == True
        assert result['skipped'] == True
        assert result['reason'] == 'task_already_cancelled'
        
        # Test failed task
        mock_task_manager.get_task_status.return_value = 'failed'
        result = validate_task_before_processing('failed-task', mock_task_manager)
        assert result['success'] == True
        assert result['skipped'] == True
        assert result['reason'] == 'task_already_failed'
        
        # Test completed task
        mock_task_manager.get_task_status.return_value = 'completed'
        result = validate_task_before_processing('completed-task', mock_task_manager)
        assert result['success'] == True
        assert result['skipped'] == True
        assert result['reason'] == 'task_already_completed'
        
        # Test valid task (should continue processing)
        mock_task_manager.get_task_status.return_value = 'pending'
        result = validate_task_before_processing('valid-task', mock_task_manager)
        assert result is None  # Continue processing
    
    @pytest.mark.asyncio
    async def test_cancellation_detection_priority(self):
        """Test that worker registry is checked before database."""
        # Mock worker and task manager
        mock_worker = Mock()
        mock_task_manager = Mock()
        
        # Simulate our cancellation detection logic
        async def check_task_cancelled(task_id, worker_instance, task_manager):
            # Check worker registry first (faster)
            if worker_instance and worker_instance.is_task_cancellation_requested(task_id):
                return True
            
            # Fall back to database check
            task_status = task_manager.get_task_status(task_id)
            if task_status and task_status.lower() == 'cancelled':
                return True
            
            return False
        
        task_id = 'test-task'
        
        # Test: Worker registry detects cancellation
        mock_worker.is_task_cancellation_requested.return_value = True
        is_cancelled = await check_task_cancelled(task_id, mock_worker, mock_task_manager)
        assert is_cancelled == True
        mock_worker.is_task_cancellation_requested.assert_called_with(task_id)
        # Database should NOT be called
        mock_task_manager.get_task_status.assert_not_called()
        
        # Reset mocks
        mock_worker.reset_mock()
        mock_task_manager.reset_mock()
        
        # Test: Worker registry doesn't detect, database does
        mock_worker.is_task_cancellation_requested.return_value = False
        mock_task_manager.get_task_status.return_value = 'cancelled'
        is_cancelled = await check_task_cancelled(task_id, mock_worker, mock_task_manager)
        assert is_cancelled == True
        mock_worker.is_task_cancellation_requested.assert_called_with(task_id)
        mock_task_manager.get_task_status.assert_called_with(task_id)
        
        # Reset mocks
        mock_worker.reset_mock()
        mock_task_manager.reset_mock()
        
        # Test: Neither detects cancellation
        mock_worker.is_task_cancellation_requested.return_value = False
        mock_task_manager.get_task_status.return_value = 'running'
        is_cancelled = await check_task_cancelled(task_id, mock_worker, mock_task_manager)
        assert is_cancelled == False
    
    def test_background_monitoring_logic(self):
        """Test background monitoring detection logic."""
        # Mock worker with registry
        class MockWorker:
            def __init__(self):
                self.running_tasks = {'task1': {}, 'task2': {}}
                self.task_lock = threading.Lock()
            
            def get_running_task_ids(self):
                with self.task_lock:
                    return list(self.running_tasks.keys())
            
            def signal_task_cancellation(self, task_id):
                # In real implementation, this would set cancel_requested=True
                pass
        
        # Mock task manager
        mock_task_manager = Mock()
        
        # Simulate background monitoring logic
        def check_running_tasks_for_cancellation(worker, task_manager):
            detected_cancellations = []
            
            running_task_ids = worker.get_running_task_ids()
            for task_id in running_task_ids:
                try:
                    current_status = task_manager.get_task_status(task_id)
                    if current_status and current_status.lower() == 'cancelled':
                        worker.signal_task_cancellation(task_id)
                        detected_cancellations.append(task_id)
                except Exception:
                    continue  # Skip on error
            
            return detected_cancellations
        
        worker = MockWorker()
        
        # Test: One task cancelled, one running
        def mock_get_status(task_id):
            return 'cancelled' if task_id == 'task1' else 'running'
        
        mock_task_manager.get_task_status.side_effect = mock_get_status
        
        detected = check_running_tasks_for_cancellation(worker, mock_task_manager)
        assert 'task1' in detected
        assert 'task2' not in detected
        assert len(detected) == 1
        
        # Verify task manager was called for both tasks
        assert mock_task_manager.get_task_status.call_count == 2


@pytest.mark.asyncio
class TestIntegrationLogic:
    """Test integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_task_processing_workflow(self):
        """Test complete task processing workflow with cancellation."""
        # Mock components
        mock_worker = Mock()
        mock_task_manager = Mock()
        
        # Simulate task processing function
        async def process_task_with_cancellation(task_data, worker, task_manager):
            task_id = task_data.get('task_id')
            
            # Validate task status before processing
            current_status = task_manager.get_task_status(task_id)
            if current_status and current_status.lower() in ['cancelled', 'failed', 'completed']:
                return {
                    'success': True,
                    'skipped': True,
                    'reason': f'task_already_{current_status.lower()}',
                    'task_id': task_id
                }
            
            # Register task as running
            worker.register_running_task(task_id, task_data)
            
            try:
                # Update status to running
                task_manager.update_task_status(task_id, 'running', 0)
                
                # Check cancellation before processing
                if worker.is_task_cancellation_requested(task_id):
                    return {
                        'success': True,
                        'skipped': True,
                        'reason': 'task_cancelled_before_processing',
                        'task_id': task_id
                    }
                
                # Simulate task processing
                await asyncio.sleep(0.01)  # Simulate work
                
                # Check cancellation during processing
                if worker.is_task_cancellation_requested(task_id):
                    return {
                        'success': True,
                        'skipped': True,
                        'reason': 'task_cancelled_during_processing',
                        'task_id': task_id
                    }
                
                # Complete successfully
                task_manager.update_task_status(task_id, 'completed', 100)
                return {'success': True, 'task_id': task_id, 'result': 'completed'}
                
            finally:
                # Always unregister task
                worker.unregister_running_task(task_id)
        
        # Test 1: Task already cancelled
        task_data = {'task_id': 'cancelled-task', 'task_type': 'test'}
        mock_task_manager.get_task_status.return_value = 'cancelled'
        
        result = await process_task_with_cancellation(task_data, mock_worker, mock_task_manager)
        assert result['success'] == True
        assert result['skipped'] == True
        assert result['reason'] == 'task_already_cancelled'
        mock_worker.register_running_task.assert_not_called()
        
        # Reset mocks
        mock_worker.reset_mock()
        mock_task_manager.reset_mock()
        
        # Test 2: Task cancelled during processing
        task_data = {'task_id': 'cancel-during-task', 'task_type': 'test'}
        mock_task_manager.get_task_status.return_value = 'pending'
        mock_worker.is_task_cancellation_requested.side_effect = [False, True]  # False first, True second
        
        result = await process_task_with_cancellation(task_data, mock_worker, mock_task_manager)
        assert result['success'] == True
        assert result['skipped'] == True
        assert result['reason'] == 'task_cancelled_during_processing'
        mock_worker.register_running_task.assert_called_once()
        mock_worker.unregister_running_task.assert_called_once()
        
        # Reset mocks
        mock_worker.reset_mock()
        mock_task_manager.reset_mock()
        
        # Test 3: Task completes successfully
        task_data = {'task_id': 'success-task', 'task_type': 'test'}
        mock_task_manager.get_task_status.return_value = 'pending'
        mock_worker.is_task_cancellation_requested.return_value = False
        mock_worker.is_task_cancellation_requested.side_effect = None  # Clear side_effect
        
        result = await process_task_with_cancellation(task_data, mock_worker, mock_task_manager)
        assert result['success'] == True
        assert 'skipped' not in result
        assert result['result'] == 'completed'
        mock_worker.register_running_task.assert_called_once()
        mock_worker.unregister_running_task.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])