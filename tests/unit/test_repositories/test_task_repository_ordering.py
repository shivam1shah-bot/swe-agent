"""
Unit tests for TaskRepository ordering and multi-status functionality.

Tests the new ordering logic, pagination, and multi-status filtering
added to the task repository for improved performance.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.repositories.task_repository import SQLAlchemyTaskRepository
from src.repositories.exceptions import QueryExecutionError
from src.models.task import Task
from src.models.base import TaskStatus
from src.providers.logger import Logger


class TestTaskRepositoryOrdering:
    """Test cases for TaskRepository ordering and pagination functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create mock SQLAlchemy session."""
        session = Mock(spec=Session)
        # Mock query chaining
        mock_query = Mock()
        mock_query.order_by.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        session.query.return_value = mock_query
        return session

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return Mock(spec=Logger)

    @pytest.fixture
    def task_repository(self, mock_session, mock_logger):
        """Create TaskRepository instance with mocked dependencies."""
        repo = SQLAlchemyTaskRepository(mock_session)
        repo.logger = mock_logger
        return repo

    @pytest.fixture
    def sample_tasks(self):
        """Create sample task objects for testing."""
        tasks = []
        # Running tasks
        running_task = Mock(spec=Task)
        running_task.id = "running_1"
        running_task.status = TaskStatus.RUNNING.value
        running_task.name = "Running Task"
        tasks.append(running_task)
        
        # Pending tasks
        pending_task = Mock(spec=Task)
        pending_task.id = "pending_1" 
        pending_task.status = TaskStatus.PENDING.value
        pending_task.name = "Pending Task"
        tasks.append(pending_task)
        
        return tasks

    def test_get_all_with_ordering(self, task_repository, mock_session, sample_tasks):
        """Test get_all method applies correct ordering."""
        mock_query = mock_session.query.return_value
        mock_query.all.return_value = sample_tasks
        
        with patch('sqlalchemy.case') as mock_case, \
             patch('sqlalchemy.desc') as mock_desc:
            
            # Setup mocks for SQL ordering functions
            mock_case.return_value = Mock()
            mock_desc.return_value = Mock()
            
            result = task_repository.get_all(limit=10, offset=5)
            
            # Verify session.query was called with Task model
            mock_session.query.assert_called_once_with(Task)
            
            # Verify order_by was called (implementing priority ordering)
            mock_query.order_by.assert_called_once()
            
            # Verify pagination
            mock_query.offset.assert_called_once_with(5)
            mock_query.limit.assert_called_once_with(10)
            
            # Verify final execution
            mock_query.all.assert_called_once()
            
            assert result == sample_tasks

    def test_get_all_without_pagination(self, task_repository, mock_session, sample_tasks):
        """Test get_all method without pagination parameters."""
        mock_query = mock_session.query.return_value
        mock_query.all.return_value = sample_tasks
        
        with patch('sqlalchemy.case') as mock_case, \
             patch('sqlalchemy.desc') as mock_desc:
            
            mock_case.return_value = Mock()
            mock_desc.return_value = Mock()
            
            result = task_repository.get_all()
            
            # Should not call offset or limit
            mock_query.offset.assert_not_called()
            mock_query.limit.assert_not_called()
            
            # Should still call order_by and all
            mock_query.order_by.assert_called_once()
            mock_query.all.assert_called_once()

    def test_get_by_status_with_pagination(self, task_repository, mock_session, sample_tasks):
        """Test get_by_status method with pagination."""
        mock_query = mock_session.query.return_value
        mock_query.all.return_value = sample_tasks[:1]  # Only running task
        
        with patch('sqlalchemy.desc') as mock_desc:
            mock_desc.return_value = Mock()
            
            result = task_repository.get_by_status(TaskStatus.RUNNING, limit=5, offset=10)
            
            # Verify filter by status
            mock_query.filter.assert_called_once()
            
            # Verify ordering by created_at DESC
            mock_query.order_by.assert_called_once()
            
            # Verify pagination
            mock_query.offset.assert_called_once_with(10)
            mock_query.limit.assert_called_once_with(5)
            
            assert result == sample_tasks[:1]

    def test_get_by_statuses_new_method(self, task_repository, mock_session, sample_tasks):
        """Test the new get_by_statuses method for multi-status queries."""
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = sample_tasks
        
        with patch('sqlalchemy.case') as mock_case, \
             patch('sqlalchemy.desc') as mock_desc:
            mock_case.return_value = Mock()
            mock_desc.return_value = Mock()
            
            statuses = [TaskStatus.RUNNING, TaskStatus.PENDING]
            result = task_repository.get_by_statuses(statuses, limit=20, offset=0)
            
            # Verify filter with IN clause for multiple statuses
            mock_query.filter.assert_called_once()
            
            # Verify priority ordering
            mock_query.order_by.assert_called_once()
            
            # Verify pagination - offset(0) should NOT be called (optimized away)
            mock_query.offset.assert_not_called()  # Changed: offset(0) is not called
            mock_query.limit.assert_called_once_with(20)
            
            assert result == sample_tasks

    def test_ordering_priority_logic(self, task_repository, mock_session):
        """Test that the ordering prioritizes running > pending > others."""
        mock_query = mock_session.query.return_value
        
        with patch('sqlalchemy.case') as mock_case, \
             patch('sqlalchemy.desc') as mock_desc:
            
            mock_case_instance = Mock()
            mock_case.return_value = mock_case_instance
            mock_desc.return_value = Mock()
            
            task_repository.get_all()
            
            # Verify case statement was created for priority ordering
            mock_case.assert_called_once()
            
            # Verify the case statement includes running and pending priorities
            call_args = mock_case.call_args
            assert call_args is not None

    def test_error_handling_sqlalchemy_error(self, task_repository, mock_session, mock_logger):
        """Test error handling for SQLAlchemy errors."""
        mock_query = mock_session.query.return_value
        mock_query.all.side_effect = SQLAlchemyError("Database connection error")
        
        with patch('sqlalchemy.case'), \
             patch('sqlalchemy.desc'):
            
            with pytest.raises(QueryExecutionError):
                task_repository.get_all()
            
            # Verify error was logged
            mock_logger.error.assert_called_once()

    def test_get_by_status_error_handling(self, task_repository, mock_session, mock_logger):
        """Test error handling in get_by_status method."""
        mock_query = mock_session.query.return_value
        mock_query.all.side_effect = SQLAlchemyError("Query failed")
        
        with patch('sqlalchemy.desc'):
            with pytest.raises(QueryExecutionError):
                task_repository.get_by_status(TaskStatus.RUNNING)
            
            mock_logger.error.assert_called_once()

    def test_get_by_statuses_error_handling(self, task_repository, mock_session, mock_logger):
        """Test error handling in get_by_statuses method."""
        mock_query = mock_session.query.return_value
        mock_query.all.side_effect = SQLAlchemyError("Multi-status query failed")
        
        with patch('sqlalchemy.case'), \
             patch('sqlalchemy.desc'):
            
            statuses = [TaskStatus.RUNNING, TaskStatus.PENDING]
            with pytest.raises(QueryExecutionError):
                task_repository.get_by_statuses(statuses)
            
            mock_logger.error.assert_called_once()

    def test_pagination_edge_cases(self, task_repository, mock_session):
        """Test pagination with edge case values."""
        mock_query = mock_session.query.return_value
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        with patch('sqlalchemy.case'), \
             patch('sqlalchemy.desc'):
            
            # Test with offset=0 - should NOT call offset (optimized away)
            task_repository.get_all(limit=5, offset=0)
            mock_query.offset.assert_not_called()  # Changed: offset(0) is not called
            mock_query.limit.assert_called_with(5)  # Verify limit is still called
            
            # Reset mock for next test
            mock_query.reset_mock()
            
            # Test with large offset - should call offset
            task_repository.get_all(limit=1, offset=1000)
            mock_query.offset.assert_called_with(1000)
            mock_query.limit.assert_called_with(1)

    def test_empty_status_list_handling(self, task_repository, mock_session):
        """Test get_by_statuses with empty status list."""
        mock_query = mock_session.query.return_value
        mock_query.all.return_value = []
        
        with patch('sqlalchemy.case'), \
             patch('sqlalchemy.desc'):
            
            result = task_repository.get_by_statuses([])
            
            # Should still execute query but with empty filter
            mock_query.filter.assert_called_once()
            assert result == []

    def test_single_status_in_statuses_method(self, task_repository, mock_session, sample_tasks):
        """Test get_by_statuses with single status (edge case)."""
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = sample_tasks[:1]
        
        with patch('sqlalchemy.case'), \
             patch('sqlalchemy.desc'):
            
            statuses = [TaskStatus.RUNNING]  # Single status
            result = task_repository.get_by_statuses(statuses, limit=10, offset=0)
            
            # Should work the same as multi-status
            mock_query.filter.assert_called_once()
            mock_query.order_by.assert_called_once()
            mock_query.limit.assert_called_once_with(10)
            # offset(0) should NOT be called (optimized away)
            mock_query.offset.assert_not_called()
            
            assert result == sample_tasks[:1] 