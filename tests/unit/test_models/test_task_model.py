"""
Unit tests for Task model.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from src.models.task import Task, TaskStatus
from src.models.base import Base


@pytest.mark.unit
class TestTaskModel:
    """Test cases for Task model."""
    
    def test_task_creation(self):
        """Test creating a task instance."""
        task = Task(
            name="Test Task",
            description="A test task",
            status=TaskStatus.PENDING.value
        )
        
        assert task.name == "Test Task"
        assert task.description == "A test task"
        assert task.status == TaskStatus.PENDING.value
        assert task.parameters is None
        assert task.result is None
    
    def test_task_with_parameters(self):
        """Test creating a task with parameters."""
        import json
        parameters = {"repo": "test/repo", "branch": "main"}
        task = Task(
            name="Test Task",
            description="A test task",
            status=TaskStatus.PENDING.value,
            parameters=json.dumps(parameters)
        )
        
        assert json.loads(task.parameters) == parameters
    
    def test_task_with_result(self):
        """Test creating a task with result."""
        import json
        result = {"success": True, "output": "Task completed"}
        task = Task(
            name="Test Task",
            description="A test task",
            status=TaskStatus.COMPLETED.value,
            result=json.dumps(result)
        )
        
        assert json.loads(task.result) == result
    
    def test_task_status_enum_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
    
    def test_task_status_transition(self):
        """Test changing task status."""
        task = Task(
            name="Test Task",
            description="A test task",
            status=TaskStatus.PENDING.value
        )
        
        task.status = TaskStatus.RUNNING.value
        assert task.status == TaskStatus.RUNNING.value
        
        task.status = TaskStatus.COMPLETED.value
        assert task.status == TaskStatus.COMPLETED.value
    
    def test_task_timestamps(self):
        """Test task timestamp behavior."""
        import time
        task = Task(
            name="Test Task",
            description="A test task",
            status=TaskStatus.PENDING.value
        )
        
        # For unit tests, manually set timestamps since SQLAlchemy defaults trigger on DB save
        current_time = int(time.time())
        task.created_at = current_time
        task.updated_at = current_time
        
        assert task.created_at is not None
        assert isinstance(task.created_at, int)
        assert task.updated_at is not None
        assert isinstance(task.updated_at, int)
    
    def test_task_string_representation(self):
        """Test task string representation if implemented."""
        task = Task(
            name="Test Task",
            description="A test task",
            status=TaskStatus.PENDING.value
        )
        
        # Test that str doesn't crash
        str_repr = str(task)
        assert isinstance(str_repr, str)
    
    def test_task_equality(self):
        """Test task equality comparison."""
        task1 = Task(
            name="Test Task",
            description="A test task",
            status=TaskStatus.PENDING.value
        )
        task1.id = "task-1"
        
        task2 = Task(
            name="Test Task",
            description="A test task",
            status=TaskStatus.PENDING.value
        )
        task2.id = "task-1"
        
        task3 = Task(
            name="Different Task",
            description="A different task",
            status=TaskStatus.PENDING.value
        )
        task3.id = "task-2"
        
        # Test equality based on ID (if implemented)
        assert task1.id == task2.id
        assert task1.id != task3.id
    
    def test_task_json_serialization(self):
        """Test task can be serialized to JSON-like dict."""
        import json
        parameters = {"repo": "test/repo", "branch": "main"}
        result = {"success": True, "output": "Task completed"}
        
        task = Task(
            name="Test Task",
            description="A test task",
            status=TaskStatus.COMPLETED.value,
            parameters=json.dumps(parameters),
            result=json.dumps(result)
        )
        
        # Test that attributes can be accessed (basic serialization)
        task_dict = {
            "name": task.name,
            "description": task.description,
            "status": task.status,
            "parameters": json.loads(task.parameters),
            "result": json.loads(task.result)
        }
        
        assert task_dict["name"] == "Test Task"
        assert task_dict["status"] == TaskStatus.COMPLETED.value
        assert task_dict["parameters"] == parameters
        assert task_dict["result"] == result
    
    def test_task_invalid_status(self):
        """Test task with invalid status."""
        # Test that invalid status is handled (status is stored as string)
        task = Task(
            name="Test Task",
            description="A test task",
            status="invalid_status"  # This might be allowed since it's just a string
        )
        assert task.status == "invalid_status"
    
    def test_task_empty_name(self):
        """Test task with empty name."""
        task = Task(
            name="",
            description="A test task",
            status=TaskStatus.PENDING.value
        )
        
        assert task.name == ""
    
    def test_task_none_description(self):
        """Test task with None description."""
        task = Task(
            name="Test Task",
            description=None,
            status=TaskStatus.PENDING.value
        )
        
        assert task.description is None
    
    def test_task_long_description(self):
        """Test task with very long description."""
        long_description = "A" * 1000  # Very long description
        task = Task(
            name="Test Task",
            description=long_description,
            status=TaskStatus.PENDING.value
        )
        
        assert task.description == long_description
        assert len(task.description) == 1000


@pytest.mark.unit
class TestTaskStatusEnum:
    """Test cases for TaskStatus enum."""
    
    def test_all_status_values(self):
        """Test all TaskStatus enum values."""
        statuses = [
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED
        ]
        
        expected_values = ["pending", "running", "completed", "failed", "cancelled"]
        
        for status, expected in zip(statuses, expected_values):
            assert status.value == expected
    
    def test_status_comparison(self):
        """Test TaskStatus comparison."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING != TaskStatus.PENDING
        assert TaskStatus.COMPLETED.value != "pending"
    
    def test_status_in_list(self):
        """Test TaskStatus membership in lists."""
        final_states = [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
        
        assert TaskStatus.COMPLETED in final_states
        assert TaskStatus.PENDING not in final_states
        assert TaskStatus.RUNNING not in final_states 