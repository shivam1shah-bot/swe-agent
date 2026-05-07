"""
Unit tests for TaskService pagination and ordering functionality.

Tests the new pagination, ordering, and multi-status methods
added to improve performance and user experience.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.task_service import TaskService
from src.repositories.task_repository import SQLAlchemyTaskRepository
from src.models.base import TaskStatus
from src.models.task import Task
from src.services.exceptions import BusinessLogicError
from src.providers.logger import Logger


class TestTaskServicePagination:
    """Test cases for TaskService pagination functionality."""

    @pytest.fixture
    def mock_task_repo(self):
        """Create mock task repository."""
        repo = Mock(spec=SQLAlchemyTaskRepository)
        repo.get_all.return_value = []
        repo.get_by_status.return_value = []
        repo.get_by_statuses.return_value = []
        return repo

    @pytest.fixture  
    def mock_config(self):
        """Create mock configuration."""
        return {
            'database': {'url': 'sqlite:///:memory:'},
            'app': {'secret_key': 'test-secret'},
            'environment': {'name': 'test'}
        }

    @pytest.fixture
    def mock_database_provider(self):
        """Create mock database provider."""
        provider = Mock()
        provider.is_initialized.return_value = True
        return provider

    @pytest.fixture
    def task_service(self, mock_config, mock_database_provider):
        """Create TaskService instance with mocked dependencies."""
        with patch('src.services.task_service.get_session') as mock_get_session, \
             patch('src.services.task_service.get_readonly_session') as mock_get_readonly_session, \
             patch('src.providers.database.session.session_factory') as mock_session_factory, \
             patch.object(TaskService, 'initialize') as mock_initialize:
            
            # Mock the session context manager for both regular and readonly sessions
            mock_session = Mock()
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None
            
            mock_readonly_session = Mock()
            mock_get_readonly_session.return_value.__enter__.return_value = mock_readonly_session
            mock_get_readonly_session.return_value.__exit__.return_value = None
            
            # Mock session factory as initialized
            mock_session_factory.is_initialized.return_value = True
            
            service = TaskService(mock_config, mock_database_provider)
            service._initialized = True  # Bypass initialization checks
            return service

    def test_list_tasks_with_pagination(self, task_service, mock_task_repo):
        """Test list_tasks method with pagination parameters."""
        # Create realistic mock tasks with proper attributes for _task_to_dict
        from datetime import datetime
        
        mock_task1 = Mock(spec=Task)
        mock_task1.id = '1'
        mock_task1.name = 'Task 1'
        mock_task1.description = 'Test description 1'
        mock_task1.status = 'running'
        mock_task1.progress = 50
        mock_task1.parameters = '{"test": "value1"}'  # JSON string
        mock_task1.result = None
        mock_task1.created_at = datetime(2025, 1, 31, 12, 0, 0)
        mock_task1.updated_at = datetime(2025, 1, 31, 12, 1, 0)
        
        mock_task2 = Mock(spec=Task)
        mock_task2.id = '2'
        mock_task2.name = 'Task 2'
        mock_task2.description = 'Test description 2'
        mock_task2.status = 'pending'
        mock_task2.progress = 0
        mock_task2.parameters = '{"test": "value2"}'  # JSON string
        mock_task2.result = None
        mock_task2.created_at = datetime(2025, 1, 31, 11, 0, 0)
        mock_task2.updated_at = datetime(2025, 1, 31, 11, 1, 0)
        
        sample_tasks = [mock_task1, mock_task2]
        mock_task_repo.get_all.return_value = sample_tasks
        
        with patch('src.services.task_service.get_readonly_session') as mock_get_readonly_session:
            mock_session = Mock()
            mock_get_readonly_session.return_value.__enter__.return_value = mock_session
            mock_get_readonly_session.return_value.__exit__.return_value = None
            
            with patch.object(task_service, '_get_task_repo', return_value=mock_task_repo):
                result = task_service.list_tasks(status=None, limit=10, offset=5)
                
                # Verify repository was called with correct parameters
                mock_task_repo.get_all.assert_called_once_with(limit=10, offset=5)
                
                # Verify result structure
                assert 'tasks' in result
                assert 'count' in result
                assert result['count'] == 2
                
                # Verify task serialization worked
                tasks = result['tasks']
                assert len(tasks) == 2
                assert tasks[0]['id'] == '1'
                assert tasks[0]['name'] == 'Task 1'
                assert tasks[0]['status'] == 'running'
                assert tasks[0]['parameters'] == {"test": "value1"}  # Should be deserialized

    def test_list_tasks_with_status_filter(self, task_service, mock_task_repo):
        """Test list_tasks method with status filtering."""
        from datetime import datetime
        
        mock_task = Mock(spec=Task)
        mock_task.id = '1'
        mock_task.name = 'Running Task'
        mock_task.description = 'Running task description'
        mock_task.status = 'running'
        mock_task.progress = 75
        mock_task.parameters = '{"priority": "high"}'  # JSON string
        mock_task.result = None
        mock_task.created_at = datetime(2025, 1, 31, 12, 0, 0)
        mock_task.updated_at = datetime(2025, 1, 31, 12, 15, 0)
        
        sample_tasks = [mock_task]
        mock_task_repo.get_by_status.return_value = sample_tasks
        
        with patch('src.services.task_service.get_readonly_session') as mock_get_readonly_session:
            mock_session = Mock()
            mock_get_readonly_session.return_value.__enter__.return_value = mock_session
            mock_get_readonly_session.return_value.__exit__.return_value = None
            
            with patch.object(task_service, '_get_task_repo', return_value=mock_task_repo):
                result = task_service.list_tasks(status=TaskStatus.RUNNING, limit=20, offset=0)
                
                # Verify repository was called with correct parameters
                mock_task_repo.get_by_status.assert_called_once_with(TaskStatus.RUNNING, 20, 0)
                
                assert result['count'] == 1
                assert result['tasks'][0]['status'] == 'running'

    def test_list_tasks_by_statuses_new_method(self, task_service, mock_task_repo):
        """Test the new list_tasks_by_statuses method for multi-status filtering."""
        from datetime import datetime
        
        mock_task1 = Mock(spec=Task)
        mock_task1.id = '1'
        mock_task1.name = 'Running Task'
        mock_task1.description = 'Running task description'
        mock_task1.status = 'running'
        mock_task1.progress = 60
        mock_task1.parameters = '{}'  # Empty JSON
        mock_task1.result = None
        mock_task1.created_at = datetime(2025, 1, 31, 12, 0, 0)
        mock_task1.updated_at = datetime(2025, 1, 31, 12, 10, 0)
        
        mock_task2 = Mock(spec=Task)
        mock_task2.id = '2'
        mock_task2.name = 'Pending Task'
        mock_task2.description = 'Pending task description'
        mock_task2.status = 'pending'
        mock_task2.progress = 0
        mock_task2.parameters = '{"queue": "default"}'  # JSON string
        mock_task2.result = None
        mock_task2.created_at = datetime(2025, 1, 31, 11, 30, 0)
        mock_task2.updated_at = datetime(2025, 1, 31, 11, 30, 0)
        
        sample_tasks = [mock_task1, mock_task2]
        mock_task_repo.get_by_statuses.return_value = sample_tasks
        
        with patch('src.services.task_service.get_readonly_session') as mock_get_readonly_session:
            mock_session = Mock()
            mock_get_readonly_session.return_value.__enter__.return_value = mock_session
            mock_get_readonly_session.return_value.__exit__.return_value = None
            
            with patch.object(task_service, '_get_task_repo', return_value=mock_task_repo):
                statuses = [TaskStatus.RUNNING, TaskStatus.PENDING]
                result = task_service.list_tasks_by_statuses(statuses, limit=15, offset=10)
                
                # Verify repository was called with correct parameters
                mock_task_repo.get_by_statuses.assert_called_once_with(statuses, 15, 10)
                
                assert result['count'] == 2
                assert result['tasks'][0]['status'] == 'running'
                assert result['tasks'][1]['status'] == 'pending'

    def test_pagination_offset_calculation_edge_cases(self, task_service, mock_task_repo):
        """Test edge cases for pagination calculations."""
        mock_task_repo.get_all.return_value = []
        
        with patch('src.services.task_service.get_readonly_session') as mock_get_readonly_session:
            mock_session = Mock()
            mock_get_readonly_session.return_value.__enter__.return_value = mock_session
            mock_get_readonly_session.return_value.__exit__.return_value = None
            
            with patch.object(task_service, '_get_task_repo', return_value=mock_task_repo):
                # Test zero offset
                task_service.list_tasks(status=None, limit=5, offset=0)
                mock_task_repo.get_all.assert_called_with(limit=5, offset=0)
                
                mock_task_repo.reset_mock()
                
                # Test large offset
                task_service.list_tasks(status=None, limit=1, offset=1000)
                mock_task_repo.get_all.assert_called_with(limit=1, offset=1000)

    def test_service_error_handling(self, task_service, mock_task_repo):
        """Test error handling in service methods."""
        from src.repositories.exceptions import RepositoryError
        mock_task_repo.get_all.side_effect = RepositoryError("Database connection failed")
        
        with patch('src.services.task_service.get_readonly_session') as mock_get_readonly_session:
            mock_session = Mock()
            mock_get_readonly_session.return_value.__enter__.return_value = mock_session
            mock_get_readonly_session.return_value.__exit__.return_value = None
            
            with patch.object(task_service, '_get_task_repo', return_value=mock_task_repo):
                with pytest.raises(BusinessLogicError):
                    task_service.list_tasks(status=None, limit=10, offset=0)

    def test_task_serialization_in_response(self, task_service, mock_task_repo):
        """Test that tasks are properly serialized in the response."""
        from datetime import datetime
        
        # Create a mock task with a to_dict method (for this specific test)
        mock_task = Mock(spec=Task)
        mock_task.id = 'task_123'
        mock_task.name = 'Test Task'
        mock_task.description = 'Test description'
        mock_task.status = 'running'
        mock_task.progress = 80
        mock_task.parameters = '{"test": "serialization"}'
        mock_task.result = '{"output": "success"}'  # JSON string
        mock_task.created_at = datetime(2025, 1, 31, 12, 0, 0)
        mock_task.updated_at = datetime(2025, 1, 31, 12, 5, 0)
        
        mock_task_repo.get_all.return_value = [mock_task]
        
        with patch('src.services.task_service.get_readonly_session') as mock_get_readonly_session:
            mock_session = Mock()
            mock_get_readonly_session.return_value.__enter__.return_value = mock_session
            mock_get_readonly_session.return_value.__exit__.return_value = None
            
            with patch.object(task_service, '_get_task_repo', return_value=mock_task_repo):
                result = task_service.list_tasks(status=None, limit=10, offset=0)
                
                # Verify task serialization worked
                assert len(result['tasks']) == 1
                task_dict = result['tasks'][0]
                assert task_dict['id'] == 'task_123'
                assert task_dict['name'] == 'Test Task'
                assert task_dict['status'] == 'running'
                assert task_dict['parameters'] == {"test": "serialization"}  # Deserialized JSON
                assert task_dict['result'] == {"output": "success"}  # Deserialized JSON

    def test_multi_status_efficiency(self, task_service, mock_task_repo):
        """Test that multi-status filtering uses the efficient repository method."""
        from datetime import datetime
        
        mock_task = Mock(spec=Task)
        mock_task.id = '1'
        mock_task.name = 'Test Task'
        mock_task.description = 'Test description'
        mock_task.status = 'running'
        mock_task.progress = 45
        mock_task.parameters = None  # None parameters (should default to empty dict)
        mock_task.result = None
        mock_task.created_at = datetime(2025, 1, 31, 12, 0, 0)
        mock_task.updated_at = datetime(2025, 1, 31, 12, 3, 0)
        
        sample_tasks = [mock_task]
        mock_task_repo.get_by_statuses.return_value = sample_tasks
        
        with patch('src.services.task_service.get_readonly_session') as mock_get_readonly_session:
            mock_session = Mock()
            mock_get_readonly_session.return_value.__enter__.return_value = mock_session
            mock_get_readonly_session.return_value.__exit__.return_value = None
            
            with patch.object(task_service, '_get_task_repo', return_value=mock_task_repo):
                # Call with multiple statuses
                statuses = [TaskStatus.RUNNING, TaskStatus.PENDING, TaskStatus.FAILED]
                task_service.list_tasks_by_statuses(statuses, limit=50, offset=25)
                
                # Should call get_by_statuses, not individual get_by_status calls
                mock_task_repo.get_by_statuses.assert_called_once_with(statuses, 50, 25)
                # Should NOT call get_by_status multiple times
                mock_task_repo.get_by_status.assert_not_called()

    def test_service_initialization_requirement(self, mock_config, mock_database_provider):
        """Test that service methods require proper initialization."""
        with patch('src.services.task_service.get_session'), \
             patch.object(TaskService, 'initialize'):
            
            service = TaskService(mock_config, mock_database_provider)
            service._initialized = False  # Simulate uninitialized state
            
            with pytest.raises(RuntimeError, match="not initialized"):
                service.list_tasks(status=None, limit=10, offset=0) 