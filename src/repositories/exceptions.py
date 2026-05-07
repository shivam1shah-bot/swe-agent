"""
Repository exceptions for the SWE Agent.

These exceptions represent data access layer errors and database-related issues.
"""


class RepositoryError(Exception):
    """Base exception for all repository-related errors."""
    pass


class EntityNotFoundError(RepositoryError):
    """Raised when an entity cannot be found in the repository."""
    
    def __init__(self, entity_type: str, identifier: str):
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} with identifier '{identifier}' not found")


class DuplicateEntityError(RepositoryError):
    """Raised when attempting to create an entity that already exists."""
    
    def __init__(self, entity_type: str, identifier: str):
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} with identifier '{identifier}' already exists")


class DatabaseConnectionError(RepositoryError):
    """Raised when database connection fails."""
    
    def __init__(self, message: str):
        super().__init__(f"Database connection error: {message}")


class QueryExecutionError(RepositoryError):
    """Raised when a database query fails to execute."""
    
    def __init__(self, query: str, error: str):
        self.query = query
        self.error = error
        super().__init__(f"Query execution failed: {error}")


class TransactionError(RepositoryError):
    """Raised when a database transaction fails."""
    
    def __init__(self, operation: str, error: str):
        self.operation = operation
        self.error = error
        super().__init__(f"Transaction failed during {operation}: {error}") 