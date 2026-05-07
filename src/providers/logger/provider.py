"""
Logger Provider

Enhanced logging provider with automatic sanitization for security,
context integration, and structured logging by default.
"""

import logging
import threading
from typing import Any, Dict, Optional, Union
from contextvars import ContextVar

from .sanitizer import sanitize_log_input, sanitize_structured_data, SanitizationLevel

# Context storage for automatic field inclusion
_context_storage: ContextVar[Dict[str, Any]] = ContextVar('logger_context', default={})


class LoggerContext:
    """
    Context manager for logger context fields.
    
    Provides thread-safe context storage for automatic inclusion 
    of common fields like request_id, task_id, user_id, etc.
    """
    
    @staticmethod
    def set_context(**context_fields: Any) -> None:
        """
        Set context fields that will be automatically included in all log messages.
        
        Args:
            **context_fields: Key-value pairs to include in logs
            
        Example:
            LoggerContext.set_context(request_id="req_123", user_id="user_456")
        """
        current_context = _context_storage.get({})
        updated_context = {**current_context, **context_fields}
        _context_storage.set(updated_context)
    
    @staticmethod
    def clear_context() -> None:
        """Clear all context fields."""
        _context_storage.set({})
    
    @staticmethod
    def get_context() -> Dict[str, Any]:
        """Get current context fields."""
        return _context_storage.get({}).copy()
    
    @staticmethod
    def remove_context_field(key: str) -> None:
        """Remove a specific context field."""
        current_context = _context_storage.get({})
        if key in current_context:
            updated_context = current_context.copy()
            del updated_context[key]
            _context_storage.set(updated_context)


class Logger:
    """
    Enhanced logger with automatic sanitization, context integration, 
    and structured logging capabilities.
    
    Features:
    - Automatic sanitization for security
    - Automatic context field inclusion (request_id, task_id, etc.)
    - Structured logging by default
    - Backward compatibility with string-only logging
    """
    
    def __init__(
        self, 
        name: Optional[str] = None,
        level: Union[str, int] = logging.INFO,
        sanitization_level: SanitizationLevel = SanitizationLevel.MODERATE,
        include_context: bool = True
    ):
        """
        Initialize the logger provider.
        
        Args:
            name: Logger name (defaults to calling module)
            level: Logging level
            sanitization_level: Default sanitization level for secure methods
            include_context: Whether to automatically include context fields
        """
        if name is None:
            # Try to get the calling module name
            import inspect
            frame = inspect.currentframe()
            try:
                caller_frame = frame.f_back
                if caller_frame and caller_frame.f_globals:
                    name = caller_frame.f_globals.get('__name__', 'swe_agent.logger')
                else:
                    name = 'swe_agent.logger'
            finally:
                del frame
        
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._sanitization_level = sanitization_level
        self._include_context = include_context
        
        # Only add a handler if this logger has no handlers AND root logger has no handlers
        # This prevents duplicate handlers when basicConfig is already set up
        root_logger = logging.getLogger()
        if not self._logger.handlers and not root_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
    
    # ENHANCED STRUCTURED LOGGING METHODS (primary interface)
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """
        Log a debug message with automatic sanitization and context.
        
        Structured logging is encouraged through keyword arguments:
        
        Args:
            msg: Primary message
            *args: Positional arguments for string formatting (legacy)
            **kwargs: Structured fields (recommended)
            
        Examples:
            # Structured logging (recommended)
            logger.debug("User operation completed", 
                        user_id="123", operation="login", duration=1.2)
            
            # Legacy string formatting (supported)
            logger.debug("User %s completed operation", user_id)
        """
        self._log_sanitized(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """
        Log an info message with automatic sanitization and context.
        
        Structured logging is encouraged through keyword arguments:
        
        Args:
            msg: Primary message
            *args: Positional arguments for string formatting (legacy)
            **kwargs: Structured fields (recommended)
            
        Examples:
            # Structured logging (recommended)
            logger.info("Task created successfully", 
                       task_id="task_123", task_type="analysis", priority="high")
            
            # Legacy string formatting (supported)
            logger.info("Task %s created with priority %s", task_id, priority)
        """
        self._log_sanitized(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """
        Log a warning message with automatic sanitization and context.
        
        Structured logging is encouraged through keyword arguments:
        
        Args:
            msg: Primary message
            *args: Positional arguments for string formatting (legacy)
            **kwargs: Structured fields (recommended)
            
        Examples:
            # Structured logging (recommended)
            logger.warning("Operation took longer than expected", 
                          operation="file_read", duration=5.2, threshold=3.0)
            
            # Legacy string formatting (supported)
            logger.warning("Operation %s took %s seconds", operation, duration)
        """
        self._log_sanitized(logging.WARNING, msg, *args, **kwargs)
    
    def warn(self, msg: str, *args, **kwargs) -> None:
        """Alias for warning() for compatibility."""
        self.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """
        Log an error message with automatic sanitization and context.
        
        Structured logging is encouraged through keyword arguments:
        
        Args:
            msg: Primary message
            *args: Positional arguments for string formatting (legacy)
            **kwargs: Structured fields (recommended)
            
        Examples:
            # Structured logging (recommended)
            logger.error("Database connection failed", 
                        database="postgres", host="db.example.com", 
                        error_code="CONNECTION_TIMEOUT", retry_count=3)
            
            # Legacy string formatting (supported)
            logger.error("Database connection to %s failed: %s", host, error_msg)
        """
        self._log_sanitized(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """
        Log a critical message with automatic sanitization and context.
        
        Structured logging is encouraged through keyword arguments:
        
        Args:
            msg: Primary message
            *args: Positional arguments for string formatting (legacy)
            **kwargs: Structured fields (recommended)
        """
        self._log_sanitized(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs) -> None:
        """
        Log an exception message with automatic sanitization and context.
        Includes exc_info=True automatically.
        
        Args:
            msg: Primary message
            *args: Positional arguments for string formatting (legacy)
            **kwargs: Structured fields (recommended)
        """
        kwargs['exc_info'] = True
        self._log_sanitized(logging.ERROR, msg, *args, **kwargs)
    
    # CONTEXT MANAGEMENT METHODS
    
    def with_context(self, **context_fields: Any) -> 'Logger':
        """
        Create a new logger instance with additional persistent context fields.
        
        These fields will be automatically included in all log messages from this logger.
        
        Args:
            **context_fields: Key-value pairs to include in all logs
            
        Returns:
            New logger instance with persistent context
            
        Example:
            request_logger = logger.with_context(request_id="req_123", user_id="user_456")
            request_logger.info("Operation started", operation="file_upload")
            # Output will include request_id and user_id automatically
        """
        # Create a new logger instance with the same configuration
        new_logger = Logger(
            name=self._logger.name,
            level=self._logger.level,
            sanitization_level=self._sanitization_level,
            include_context=self._include_context
        )
        
        # Set persistent context on the new logger
        new_logger._persistent_context = getattr(self, '_persistent_context', {}).copy()
        new_logger._persistent_context.update(context_fields)
        
        return new_logger
    
    def set_context(self, **context_fields: Any) -> None:
        """
        Set global context fields for this thread/request.
        
        Args:
            **context_fields: Key-value pairs to include in logs
            
        Example:
            logger.set_context(request_id="req_123", user_id="user_456")
        """
        LoggerContext.set_context(**context_fields)
    
    def clear_context(self) -> None:
        """Clear global context fields for this thread/request."""
        LoggerContext.clear_context()
    
    # RAW METHODS (no sanitization - for trusted data only)
    
    def raw_debug(self, msg: str, *args, **kwargs) -> None:
        """Log a debug message without sanitization (trusted data only)."""
        self._log_raw(logging.DEBUG, msg, *args, **kwargs)
    
    def raw_info(self, msg: str, *args, **kwargs) -> None:
        """Log an info message without sanitization (trusted data only)."""
        self._log_raw(logging.INFO, msg, *args, **kwargs)
    
    def raw_warning(self, msg: str, *args, **kwargs) -> None:
        """Log a warning message without sanitization (trusted data only)."""
        self._log_raw(logging.WARNING, msg, *args, **kwargs)
    
    def raw_warn(self, msg: str, *args, **kwargs) -> None:
        """Alias for raw_warning() for compatibility."""
        self.raw_warning(msg, *args, **kwargs)
    
    def raw_error(self, msg: str, *args, **kwargs) -> None:
        """Log an error message without sanitization (trusted data only)."""
        self._log_raw(logging.ERROR, msg, *args, **kwargs)
    
    def raw_critical(self, msg: str, *args, **kwargs) -> None:
        """Log a critical message without sanitization (trusted data only)."""
        self._log_raw(logging.CRITICAL, msg, *args, **kwargs)
    
    def raw_exception(self, msg: str, *args, **kwargs) -> None:
        """Log an exception message without sanitization (trusted data only)."""
        kwargs['exc_info'] = True
        self._log_raw(logging.ERROR, msg, *args, **kwargs)
    
    # INTERNAL METHODS
    
    def _get_all_context_fields(self) -> Dict[str, Any]:
        """
        Get all context fields from various sources.
        
        Returns:
            Combined context fields from global context and persistent context
        """
        all_context = {}
        
        # Add global context (thread/request-local)
        if self._include_context:
            all_context.update(LoggerContext.get_context())
        
        # Add persistent context (logger instance-specific)
        if hasattr(self, '_persistent_context'):
            all_context.update(self._persistent_context)
        
        # Try to extract FastAPI request context if available
        try:
            from fastapi import Request
            import contextvars
            # This is a simplified approach - in practice you'd need more sophisticated
            # FastAPI context extraction
        except ImportError:
            pass
        
        return all_context
    
    def _filter_reserved_logrecord_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter out reserved LogRecord field names to prevent conflicts.
        
        Args:
            data: Dictionary of structured logging data
            
        Returns:
            Filtered dictionary with reserved fields renamed or removed
        """
        # Reserved field names in Python's LogRecord
        reserved_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
            'thread', 'threadName', 'processName', 'process', 'exc_info', 'exc_text',
            'stack_info', 'getMessage', 'taskName', 'message'
        }
        
        filtered_data = {}
        
        for key, value in data.items():
            if key in reserved_fields:
                # Rename reserved fields with a prefix to avoid conflicts
                new_key = f"data_{key}"
                filtered_data[new_key] = value
            else:
                filtered_data[key] = value
        
        return filtered_data
    
    def _log_sanitized(self, level: int, msg: str, *args, **kwargs) -> None:
        """
        Internal method to log with sanitization, context, and structured logging.
        
        Args:
            level: Logging level
            msg: Message to log
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments for structured logging
        """
        if not self._logger.isEnabledFor(level):
            return
        
        # Get all context fields
        context_fields = self._get_all_context_fields()
        
        # Sanitize the message
        safe_msg = sanitize_log_input(msg, level=self._sanitization_level)
        
        # Sanitize positional arguments
        safe_args = []
        for arg in args:
            safe_args.append(sanitize_log_input(arg, level=self._sanitization_level))
        
        # Extract logging-specific kwargs
        logging_kwargs = {}
        structured_kwargs = {}
        
        for key, value in kwargs.items():
            if key in ['exc_info', 'stack_info', 'stacklevel', 'extra']:
                logging_kwargs[key] = value
            else:
                structured_kwargs[key] = value
        
        # Merge context fields with structured data (structured data takes precedence)
        all_structured_data = {**context_fields, **structured_kwargs}
        
        # Sanitize all structured logging data
        if all_structured_data:
            safe_structured = sanitize_structured_data(all_structured_data, level=self._sanitization_level)
            
            # Filter out reserved LogRecord field names to prevent conflicts
            filtered_structured = self._filter_reserved_logrecord_fields(safe_structured)
            
            # Add to extra for structured logging
            if 'extra' not in logging_kwargs:
                logging_kwargs['extra'] = {}
            logging_kwargs['extra'].update(filtered_structured)
            
            # Create enhanced message format for structured logging
            if structured_kwargs or context_fields:  # Only if we have structured data
                # Separate context fields from explicit structured fields for better readability
                context_parts = []
                structured_parts = []
                
                for k, v in filtered_structured.items():
                    if k in context_fields or k.startswith('data_') and k[5:] in context_fields:
                        context_parts.append(f"{k}={v}")
                    else:
                        structured_parts.append(f"{k}={v}")
                
                # Build enhanced message with clear separation
                message_parts = [safe_msg]
                
                if context_parts:
                    message_parts.append(f"[context: {', '.join(context_parts)}]")
                
                if structured_parts:
                    message_parts.append(f"[fields: {', '.join(structured_parts)}]")
                
                safe_msg = " ".join(message_parts)
        
        # Log the sanitized message
        try:
            if safe_args:
                self._logger.log(level, safe_msg, *safe_args, **logging_kwargs)
            else:
                self._logger.log(level, safe_msg, **logging_kwargs)
        except (TypeError, ValueError) as e:
            # Fallback if formatting fails
            self._logger.log(level, f"[SANITIZED LOG ERROR] {safe_msg}", **logging_kwargs)
    
    def _log_raw(self, level: int, msg: str, *args, **kwargs) -> None:
        """
        Internal method to log without sanitization (trusted data only).
        
        Args:
            level: Logging level
            msg: Message to log
            *args: Positional arguments for message formatting
            **kwargs: Keyword arguments for logging
        """
        if not self._logger.isEnabledFor(level):
            return
        
        # Log directly without sanitization
        try:
            if args:
                self._logger.log(level, msg, *args, **kwargs)
            else:
                self._logger.log(level, msg, **kwargs)
        except (TypeError, ValueError) as e:
            # Fallback if formatting fails
            self._logger.log(level, f"[RAW LOG ERROR] {msg}", **kwargs)
    
    # UTILITY METHODS
    
    def set_level(self, level: Union[str, int]) -> None:
        """Set the logging level."""
        self._logger.setLevel(level)
    
    def set_sanitization_level(self, level: SanitizationLevel) -> None:
        """Set the sanitization level for secure methods."""
        self._sanitization_level = level
    
    def get_effective_level(self) -> int:
        """Get the effective logging level."""
        return self._logger.getEffectiveLevel()
    
    def is_enabled_for(self, level: int) -> bool:
        """Check if logging is enabled for the specified level."""
        return self._logger.isEnabledFor(level)
    
    @property 
    def name(self) -> str:
        """Get the logger name."""
        return self._logger.name


# Convenience function to create a logger
def get_logger(
    name: Optional[str] = None,
    level: Union[str, int] = logging.INFO,
    sanitization_level: SanitizationLevel = SanitizationLevel.MODERATE,
    include_context: bool = True
) -> Logger:
    """
    Create a logger instance.
    
    Args:
        name: Logger name (defaults to calling module)
        level: Logging level
        sanitization_level: Default sanitization level
        include_context: Whether to automatically include context fields
        
    Returns:
        Logger instance
    """
    return Logger(
        name=name, 
        level=level, 
        sanitization_level=sanitization_level,
        include_context=include_context
    )


# Export context management for direct use
__all__ = ['Logger', 'get_logger', 'LoggerContext'] 