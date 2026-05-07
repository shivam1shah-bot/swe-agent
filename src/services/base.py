"""
Base service class for the SWE Agent.

Provides common service functionality and patterns.
"""

from abc import ABC
from typing import Dict, Any, Optional
from src.providers.logger import Logger


class BaseService(ABC):
    """
    Abstract base service class.
    
    Provides common functionality for all service classes.
    """
    
    def __init__(self, logger_name: Optional[str] = None):
        """
        Initialize the base service.
        
        Args:
            logger_name: Optional logger name, defaults to class name
        """
        self.logger = Logger(logger_name or self.__class__.__name__)
        self._initialized = False
    
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the service with configuration.
        
        Args:
            config: Service configuration
        """
        if self._initialized:
            self.logger.warning("Service already initialized")
            return
        
        self.logger.info("Initializing service")
        self._configure(config)
        self._initialized = True
        self.logger.info("Service initialized successfully")
    
    def _configure(self, config: Dict[str, Any]) -> None:
        """
        Configure the service (override in subclasses).
        
        Args:
            config: Service configuration
        """
        pass
    
    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the service.
        
        Returns:
            Dictionary containing health check results
        """
        if not self._initialized:
            return {
                "status": "error",
                "message": "Service not initialized"
            }
        
        return {
            "status": "healthy",
            "message": "Service is operational"
        }
    
    def _validate_initialized(self) -> None:
        """
        Validate that the service is initialized.
        
        Raises:
            RuntimeError: If service is not initialized
        """
        if not self._initialized:
            raise RuntimeError(f"{self.__class__.__name__} not initialized. Call initialize() first.")
    
    def _log_operation(self, operation: str, **kwargs) -> None:
        """
        Log a service operation.
        
        Args:
            operation: Operation name
            **kwargs: Additional context
        """
        context = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.debug(f"Operation: {operation} ({context})")
    
    def _log_error(self, operation: str, error: Exception, **kwargs) -> None:
        """
        Log a service error.
        
        Args:
            operation: Operation name
            error: Exception that occurred
            **kwargs: Additional context
        """
        self.logger.error("Operation failed", 
                          extra={
                              "operation": operation, 
                              "error": str(error), 
                              **kwargs
                          })
    
    def _log_success(self, operation: str, **kwargs) -> None:
        """
        Log a successful service operation.
        
        Args:
            operation: Operation name
            **kwargs: Additional context
        """
        self.logger.info("Operation successful", 
                          extra={
                              "operation": operation, 
                              **kwargs
                          }) 