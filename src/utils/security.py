"""
Security utilities for the SWE Agent.

This module provides security-related functions for input validation,
sanitization, and protection against common vulnerabilities.
"""

import re
import html
import logging
from typing import Any, Optional, Union
from urllib.parse import quote

logger = logging.getLogger(__name__)

def sanitize_log_input(value: Any, max_length: int = 100) -> str:
    """
    DEPRECATED: This function has been replaced by the Logger Provider.
    
    Use the new Logger Provider from src.providers.logger instead:
    
    OLD WAY:
        logger.info(f"Processing user: {sanitize_log_input(user_input)}")
    
    NEW WAY:
        logger.info("Processing user", user_input=user_input)
        
    The Logger Provider automatically sanitizes all inputs.
    """
    import warnings
    warnings.warn(
        "sanitize_log_input is deprecated. Use Logger Provider from src.providers.logger instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    if value is None:
        return "None"
    
    # Convert to string
    if not isinstance(value, str):
        value = str(value)
    
    # Remove or replace potentially dangerous characters for log injection
    # Remove control characters, newlines, carriage returns
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '_', value)
    
    # Replace characters that could be used for log forging
    sanitized = sanitized.replace('\n', '_').replace('\r', '_')
    sanitized = sanitized.replace('\t', '_').replace('\b', '_')
    
    # Keep only safe characters: alphanumeric, space, common punctuation
    sanitized = re.sub(r'[^\w\s\-\.\@\#\$\%\^\&\*\(\)\+\=\[\]\{\}\|\\\:\;\"\'\<\>\,\.\?\/\~\`]', '_', sanitized)
    
    # Limit length to prevent log flooding - leave room for ellipsis
    if len(sanitized) > max_length:
        if max_length > 3:
            sanitized = sanitized[:max_length-3] + '...'
        else:
            sanitized = sanitized[:max_length]
    
    return sanitized

def sanitize_html_input(value: str) -> str:
    """
    Sanitize HTML input to prevent XSS attacks.
    
    Args:
        value: The HTML string to sanitize
        
    Returns:
        HTML-escaped string
    """
    if not isinstance(value, str):
        value = str(value)
    
    return html.escape(value, quote=True)

def sanitize_sql_identifier(identifier: str) -> str:
    """
    Sanitize SQL identifiers (table names, column names, etc.).
    
    Args:
        identifier: The SQL identifier to sanitize
        
    Returns:
        Sanitized identifier containing only safe characters
        
    Raises:
        ValueError: If identifier is empty or contains only unsafe characters
    """
    if not isinstance(identifier, str):
        identifier = str(identifier)
    
    # Remove all non-alphanumeric characters except underscores
    sanitized = re.sub(r'[^\w]', '', identifier)
    
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = 'col_' + sanitized
    
    if not sanitized:
        raise ValueError("Invalid SQL identifier: contains no valid characters")
    
    # Limit length
    if len(sanitized) > 64:
        sanitized = sanitized[:64]
    
    return sanitized

def validate_uuid(uuid_string: str) -> bool:
    """
    Validate that a string is a valid UUID format.
    
    Args:
        uuid_string: String to validate
        
    Returns:
        True if valid UUID format, False otherwise
    """
    if not isinstance(uuid_string, str):
        return False
    
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    return bool(uuid_pattern.match(uuid_string))

def sanitize_file_path(file_path: str, allow_relative: bool = False) -> str:
    """
    Sanitize file paths to prevent directory traversal attacks.
    
    Args:
        file_path: The file path to sanitize
        allow_relative: Whether to allow relative paths
        
    Returns:
        Sanitized file path
        
    Raises:
        ValueError: If path contains directory traversal attempts
    """
    if not isinstance(file_path, str):
        file_path = str(file_path)
    
    # Remove null bytes
    file_path = file_path.replace('\x00', '')
    
    # Check for directory traversal patterns
    if '..' in file_path:
        raise ValueError("Directory traversal detected in file path")
    
    # Remove leading/trailing whitespace
    file_path = file_path.strip()
    
    if not allow_relative and not file_path.startswith('/'):
        # If absolute paths are required, ensure it starts with /
        file_path = '/' + file_path.lstrip('/')
    
    # Remove duplicate slashes
    file_path = re.sub(r'/+', '/', file_path)
    
    return file_path

def sanitize_url_parameter(param: str) -> str:
    """
    Sanitize URL parameters to prevent injection attacks.
    
    Args:
        param: URL parameter to sanitize
        
    Returns:
        URL-encoded sanitized parameter
    """
    if not isinstance(param, str):
        param = str(param)
    
    # URL encode the parameter to handle special characters safely
    return quote(param, safe='')

def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid email format, False otherwise
    """
    if not isinstance(email, str):
        return False
    
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    return bool(email_pattern.match(email)) and len(email) <= 254

def sanitize_json_field(value: Any) -> Any:
    """
    Sanitize values that will be stored in JSON fields.
    
    Args:
        value: Value to sanitize
        
    Returns:
        Sanitized value safe for JSON storage
    """
    if isinstance(value, str):
        # Remove control characters that could break JSON
        return re.sub(r'[\x00-\x1f\x7f]', '', value)
    
    return value

def rate_limit_key(identifier: str) -> str:
    """
    Create a safe key for rate limiting based on user identifier.
    
    Args:
        identifier: User identifier (IP, user ID, etc.)
        
    Returns:
        Safe key for rate limiting
    """
    if not isinstance(identifier, str):
        identifier = str(identifier)
    
    # Remove any characters that could cause issues in cache keys
    safe_key = re.sub(r'[^\w\.\-]', '_', identifier)
    
    # Limit length
    if len(safe_key) > 50:
        safe_key = safe_key[:50]
    
    return safe_key 