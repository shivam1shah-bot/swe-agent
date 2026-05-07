"""
Examples of using the enhanced Logger with context integration and structured logging.

This file demonstrates the new features added to the logger provider:
1. Context Integration - Automatic inclusion of context fields
2. Structured Logging by Default - Enhanced structured logging interface
"""

from src.providers.logger import Logger, LoggerContext, get_logger


def example_basic_structured_logging():
    """Example of basic structured logging."""
    print("\n=== Basic Structured Logging ===")
    
    logger = get_logger("example.basic")
    
    # New structured logging approach (recommended)
    logger.info("User login successful", 
                user_id="user_123", 
                ip_address="192.168.1.1", 
                login_method="oauth", 
                duration=1.2)
    
    logger.error("Database operation failed", 
                 operation="user_update", 
                 table="users", 
                 error_code="TIMEOUT", 
                 retry_count=3)
    
    # Legacy string formatting still works (backward compatibility)
    user_id = "user_456"
    logger.info("Legacy format: User %s logged out", user_id)


def example_global_context():
    """Example of global context management."""
    print("\n=== Global Context Management ===")
    
    logger = get_logger("example.context")
    
    # Set global context for this thread/request
    LoggerContext.set_context(
        request_id="req_789",
        user_id="user_123",
        session_id="sess_456"
    )
    
    # All subsequent logs will include the context automatically
    logger.info("Starting file upload")
    logger.warning("File size exceeds recommended limit", 
                   file_size="10MB", 
                   recommended_limit="5MB")
    logger.info("File upload completed", 
                file_name="document.pdf", 
                upload_duration=2.5)
    
    # Clear context when done
    LoggerContext.clear_context()
    
    # This log won't have the context
    logger.info("Context cleared - no automatic context fields")


def example_persistent_context():
    """Example of persistent context with with_context()."""
    print("\n=== Persistent Context (Logger-specific) ===")
    
    base_logger = get_logger("example.persistent")
    
    # Create a logger with persistent context
    request_logger = base_logger.with_context(
        request_id="req_999",
        user_id="user_789",
        api_version="v2"
    )
    
    # All logs from this logger will include the persistent context
    request_logger.info("API request started", 
                       endpoint="/api/users", 
                       method="POST")
    
    request_logger.error("Validation failed", 
                        field="email", 
                        error="invalid_format")
    
    # You can add more context to the persistent logger
    operation_logger = request_logger.with_context(
        operation="user_creation",
        transaction_id="txn_123"
    )
    
    operation_logger.info("Creating user record", 
                         username="john_doe", 
                         email_domain="example.com")
    
    # Original base logger doesn't have the persistent context
    base_logger.info("This log has no persistent context")


def example_mixed_context():
    """Example of mixing global and persistent context."""
    print("\n=== Mixed Context (Global + Persistent) ===")
    
    # Set some global context
    LoggerContext.set_context(
        server_id="srv_001",
        environment="production"
    )
    
    logger = get_logger("example.mixed")
    
    # Create logger with persistent context
    service_logger = logger.with_context(
        service="payment_processor",
        version="1.2.3"
    )
    
    # This log will have both global context (server_id, environment) 
    # and persistent context (service, version)
    service_logger.info("Processing payment", 
                       payment_id="pay_456", 
                       amount=99.99, 
                       currency="USD")
    
    # Update global context
    LoggerContext.set_context(
        request_id="req_555",  # Add request_id to global context
        server_id="srv_001",   # Keep existing
        environment="production"  # Keep existing
    )
    
    # Now logs will include the new request_id too
    service_logger.error("Payment processing failed", 
                        payment_id="pay_456", 
                        error_code="INSUFFICIENT_FUNDS")
    
    LoggerContext.clear_context()


def example_fastapi_integration():
    """Example of how this would work in FastAPI endpoints."""
    print("\n=== FastAPI Integration Example ===")
    
    # This simulates what would happen in a FastAPI endpoint
    from src.api.dependencies import get_logger
    
    # Simulate FastAPI request context
    LoggerContext.set_context(
        request_id="req_fastapi_001",
        user_agent="Mozilla/5.0...",
        client_ip="203.0.113.1"
    )
    
    # Get logger through dependency injection
    logger = get_logger("api.tasks")
    
    # Create task-specific logger with additional context
    task_logger = logger.with_context(
        endpoint="/api/tasks",
        method="POST"
    )
    
    # Simulate endpoint logic with structured logging
    task_logger.info("Task creation request received", 
                    task_type="code_analysis",
                    priority="high")
    
    try:
        # Simulate some operation
        task_id = "task_789"
        task_logger.info("Task created successfully", 
                        task_id=task_id,
                        estimated_duration="5m")
        
    except Exception as e:
        task_logger.exception("Task creation failed", 
                            error_type=type(e).__name__)
    
    LoggerContext.clear_context()


def example_backward_compatibility():
    """Example showing backward compatibility with existing code."""
    print("\n=== Backward Compatibility ===")
    
    logger = get_logger("example.compat")
    
    # Old style logging still works exactly the same
    logger.info("This is the old style message")
    logger.error("Error occurred: %s", "Something went wrong")
    
    # Mixed old and new style
    logger.warning("Mixed style: %s", "warning message", 
                   error_code="WARN_001", 
                   severity="medium")
    
    # Raw logging for trusted data (no changes)
    logger.raw_info("Raw log with trusted data: %s", "internal_data")


if __name__ == "__main__":
    """Run all examples to demonstrate the new logger features."""
    print("Enhanced Logger Examples")
    print("=" * 50)
    
    example_basic_structured_logging()
    example_global_context()
    example_persistent_context()
    example_mixed_context()
    example_fastapi_integration()
    example_backward_compatibility()
    
    print("\n" + "=" * 50)
    print("All examples completed!") 