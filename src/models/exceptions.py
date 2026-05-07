"""
Domain exceptions for the SWE Agent models.

These exceptions represent business rule violations and domain-specific errors.
"""


class DomainError(Exception):
    """Base exception for all domain-related errors."""
    pass


class TaskError(DomainError):
    """Base exception for task-related errors."""
    pass


class TaskNotFoundError(TaskError):
    """Raised when a task cannot be found."""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task with ID '{task_id}' not found")


class InvalidTaskStatusError(TaskError):
    """Raised when an invalid status transition is attempted."""
    
    def __init__(self, current_status: str, new_status: str):
        self.current_status = current_status
        self.new_status = new_status
        super().__init__(f"Invalid status transition from '{current_status}' to '{new_status}'")


class WorkflowError(DomainError):
    """Base exception for workflow-related errors."""
    pass


class InvalidWorkflowError(WorkflowError):
    """Raised when an invalid workflow name is used."""
    
    def __init__(self, workflow_name: str):
        self.workflow_name = workflow_name
        super().__init__(f"Invalid workflow name: '{workflow_name}'")


class WorkflowConfigurationError(WorkflowError):
    """Raised when workflow configuration is invalid."""
    
    def __init__(self, workflow_name: str, error_details: str):
        self.workflow_name = workflow_name
        self.error_details = error_details
        super().__init__(f"Invalid configuration for workflow '{workflow_name}': {error_details}") 