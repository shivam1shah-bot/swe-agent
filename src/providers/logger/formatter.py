"""
Custom log formatters for enhanced security and readability.

This module provides log formatters that work with the Logger provider
to ensure consistent and secure log formatting.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any

from .sanitizer import sanitize_log_input


class SecureFormatter(logging.Formatter):
    """
    Secure log formatter that ensures all log record fields are safe.
    
    This formatter provides an additional layer of security by sanitizing
    log record attributes before formatting.
    """
    
    def __init__(self, fmt=None, datefmt=None, style='%', validate=True):
        """
        Initialize the secure formatter.
        
        Args:
            fmt: Format string
            datefmt: Date format string
            style: Style of format string ('%', '{', or '$')
            validate: Whether to validate the format string
        """
        if fmt is None:
            fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate)
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with additional security measures.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log string
        """
        # Create a copy of the record to avoid modifying the original
        record_copy = logging.LogRecord(
            name=record.name,
            level=record.levelno,
            pathname=record.pathname,
            lineno=record.lineno,
            msg=record.msg,
            args=record.args,
            exc_info=record.exc_info,
            func=record.funcName,
            stime=record.created
        )
        
        # Sanitize sensitive fields that could be manipulated
        if hasattr(record, 'funcName') and record.funcName:
            record_copy.funcName = sanitize_log_input(record.funcName, max_length=50)
        
        if hasattr(record, 'filename') and record.filename:
            record_copy.filename = sanitize_log_input(record.filename, max_length=100)
        
        # Copy other attributes
        for key, value in record.__dict__.items():
            if key not in ['funcName', 'filename'] and not hasattr(record_copy, key):
                setattr(record_copy, key, value)
        
        # Use parent formatter
        return super().format(record_copy)


class StructuredFormatter(logging.Formatter):
    """
    Structured log formatter that outputs JSON with sanitized fields.
    
    This formatter creates structured JSON logs while ensuring all
    user-provided data is properly sanitized.
    """
    
    def __init__(self, include_extra=True, exclude_fields=None):
        """
        Initialize the structured formatter.
        
        Args:
            include_extra: Whether to include extra fields in output
            exclude_fields: List of field names to exclude from output
        """
        super().__init__()
        self.include_extra = include_extra
        self.exclude_fields = set(exclude_fields or [])
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as structured JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON formatted log string
        """
        # Base log data
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if requested
        if self.include_extra:
            for key, value in record.__dict__.items():
                if (key not in log_data and 
                    key not in self.exclude_fields and
                    not key.startswith('_') and
                    key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                               'pathname', 'filename', 'module', 'lineno', 
                               'funcName', 'created', 'msecs', 'relativeCreated',
                               'thread', 'threadName', 'processName', 'process',
                               'exc_info', 'exc_text', 'stack_info']):
                    # Sanitize extra fields
                    safe_value = sanitize_log_input(value)
                    log_data[key] = safe_value
        
        try:
            return json.dumps(log_data, separators=(',', ':'), ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # Fallback to basic format if JSON serialization fails
            return f"{log_data['timestamp']} - {log_data['logger']} - {log_data['level']} - {log_data['message']}"


class ContextFormatter(logging.Formatter):
    """
    Context-aware formatter that includes additional context information.
    
    This formatter adds contextual information like request IDs, user IDs,
    etc., while ensuring all context data is properly sanitized.
    """
    
    def __init__(self, fmt=None, datefmt=None, include_context=True):
        """
        Initialize the context formatter.
        
        Args:
            fmt: Format string
            datefmt: Date format string
            include_context: Whether to include context information
        """
        if fmt is None:
            fmt = '%(asctime)s - %(name)s - %(levelname)s - [%(context)s] - %(message)s'
        
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.include_context = include_context
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with context information.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log string with context
        """
        # Build context string
        context_parts = []
        
        if self.include_context:
            # Add common context fields if present
            context_fields = ['request_id', 'user_id', 'task_id', 'workflow_id', 'session_id']
            
            for field in context_fields:
                if hasattr(record, field) and getattr(record, field):
                    value = getattr(record, field)
                    safe_value = sanitize_log_input(value, max_length=20)
                    context_parts.append(f"{field}={safe_value}")
        
        # Set context on record
        record.context = ', '.join(context_parts) if context_parts else 'no-context'
        
        return super().format(record) 