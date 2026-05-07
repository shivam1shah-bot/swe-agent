"""
Service exceptions for the SWE Agent.

These exceptions represent business logic errors and service-level issues.
"""


class ServiceError(Exception):
    """Base exception for all service-related errors."""
    pass


class BusinessLogicError(ServiceError):
    """Raised when business logic rules are violated."""
    
    def __init__(self, message: str, details: str = None):
        self.details = details
        super().__init__(message)


class ValidationError(ServiceError):
    """Raised when input validation fails."""
    
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation error for '{field}': {message}")


class WorkflowValidationError(ValidationError):
    """Raised when workflow validation fails."""
    
    def __init__(self, workflow_name: str, message: str):
        self.workflow_name = workflow_name
        super().__init__("workflow_name", f"Invalid workflow '{workflow_name}': {message}")


class TaskNotFoundError(ServiceError):
    """Raised when a task cannot be found."""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' not found")


class InvalidStatusTransitionError(BusinessLogicError):
    """Raised when an invalid status transition is attempted."""
    
    def __init__(self, current_status: str, new_status: str):
        self.current_status = current_status
        self.new_status = new_status
        super().__init__(
            f"Invalid status transition from '{current_status}' to '{new_status}'",
            f"Status transitions must follow business rules"
        )


class ConfigurationError(ServiceError):
    """Raised when service configuration is invalid."""
    
    def __init__(self, service_name: str, message: str):
        self.service_name = service_name
        super().__init__(f"Configuration error in {service_name}: {message}")


class ExternalServiceError(ServiceError):
    """Raised when external service calls fail."""
    
    def __init__(self, service_name: str, operation: str, error: str):
        self.service_name = service_name
        self.operation = operation
        self.error = error
        super().__init__(f"External service '{service_name}' failed during '{operation}': {error}") 