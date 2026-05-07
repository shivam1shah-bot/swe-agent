#!/usr/bin/env python3
"""
Integration tests for the task management functionality.
"""

import pytest
import uuid
import json
import time
from unittest.mock import patch, MagicMock

# Fix imports to use proper database provider and models
from src.providers.database.session import get_session
from src.models import Task, TaskStatus
# from src.models.workflow_registry import WorkflowRegistry  # Removed - agents catalogue is the new workflow system
from src.services.task_service import TaskService
from src.providers.database.provider import DatabaseProvider
from src.providers.config_loader import get_config


@pytest.mark.integration
@pytest.mark.database
class TestTaskManagerIntegration:
    """Integration test cases for the TaskManager class"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and tear down the test environment"""
        # Initialize database provider for tests
        config = get_config()
        self.db_provider = DatabaseProvider()
        self.db_provider.initialize(config)

        # Initialize task service
        self.task_service = TaskService(config, self.db_provider)

        # Workflow registry removed - using legacy workflow name for tests
        self.workflow_name = "test_workflow"

        yield

        # Clean up after tests
        with get_session() as session:
            # Delete tasks associated with test workflow
            session.query(Task).filter(Task.workflow_name == self.workflow_name).delete()
            session.commit()

    def test_create_task(self):
        """Test creating a task"""
        # Create a task using the task service
        task_data = self.task_service.create_task(
            name="Test Task Creation",
            workflow_name=self.workflow_name,
            description="Test task for integration tests",
            parameters={"test_param": "test_value"}
        )

        # Verify task was created in database
        with get_session() as session:
            task = session.query(Task).filter(Task.id == task_data["id"]).first()
            assert task is not None
            assert task.name == "Test Task Creation"
            assert task.status == TaskStatus.PENDING

    def test_get_task(self):
        """Test retrieving a task"""
        # Create a task using the task service
        task_data = self.task_service.create_task(
            name="Test Task Retrieval",
            workflow_name=self.workflow_name,
            description="Test task for retrieval",
            parameters={"test_param": "test_value"}
        )

        # Retrieve the task
        task = self.task_service.get_task(task_data["id"])

        # Verify task properties
        assert task is not None
        assert task["id"] == task_data["id"]
        assert task["name"] == "Test Task Retrieval"
        assert task["status"] == "pending"
        assert task["workflow_name"] == self.workflow_name
        assert task["parameters"]["test_param"] == "test_value"

    def test_update_task_status(self):
        """Test updating task status"""
        # Create a task using the task service
        task_data = self.task_service.create_task(
            name="Test Status Update",
            workflow_name=self.workflow_name,
            description="Test task for status update"
        )

        # Update the task status
        result = self.task_service.update_task_status(
            task_id=task_data["id"],
            status=TaskStatus.RUNNING,
            progress=50,
            message="Task is running"
        )

        # Verify update was successful
        assert result is True

        # Retrieve the task and verify updated fields
        task = self.task_service.get_task(task_data["id"])
        assert task["status"] == "running"
        assert task["progress"] == 50
        assert task["message"] == "Task is running"

    def test_list_tasks(self):
        """Test listing tasks with filters"""
        # Create multiple tasks
        task_ids = []
        for i in range(3):
            task_data = self.task_service.create_task(
                name=f"Test Task {i+1}",
                workflow_name=self.workflow_name,
                description=f"Test task {i+1} for list"
            )
            task_ids.append(task_data["id"])

        # Update one task to a different status
        self.task_service.update_task_status(
            task_id=task_ids[1],
            status=TaskStatus.RUNNING
        )

        # List all tasks (workflow filtering removed since workflow registry is gone)
        all_tasks = self.task_service.list_tasks()
        assert len(all_tasks["tasks"]) >= 3

        # List only pending tasks
        pending_tasks = self.task_service.list_tasks(status=TaskStatus.PENDING)
        assert len(pending_tasks["tasks"]) >= 2

        # List only running tasks  
        running_tasks = self.task_service.list_tasks(status=TaskStatus.RUNNING)
        assert len(running_tasks["tasks"]) >= 1

    def test_workflow_operations(self):
        """Test workflow operations"""
        # Get available workflows (now returns empty since registry removed)
        workflows = self.task_service.get_available_workflows()
        
        # Since workflow registry is removed, this should return empty dict
        assert isinstance(workflows, dict)
        assert len(workflows) == 0

    def test_task_to_dict_parses_json_fields(self):
        """Test task service handles JSON fields correctly"""
        # Create a task with JSON parameters
        params = {"key": "value", "nested": {"inner": 123}}

        task_data = self.task_service.create_task(
            name="Test JSON Fields",
            workflow_name=self.workflow_name,
            description="Test task with JSON parameters",
            parameters=params
        )

        # Retrieve the task and verify JSON fields were parsed
        task = self.task_service.get_task(task_data["id"])
        assert task["parameters"] == params