"""
Enhanced sanitization utilities for logging security.

This module provides robust sanitization functions to prevent log injection attacks
and other security vulnerabilities in log messages.
"""

import re
import json
from enum import Enum
from typing import Any, Dict, List, Union, Optional


class SanitizationLevel(Enum):
    """Sanitization levels for different security requirements."""
    STRICT = "strict"      # Maximum security, minimal allowed characters
    MODERATE = "moderate"  # Balanced security and readability
    LENIENT = "lenient"    # Basic security, preserve most formatting


def sanitize_log_input(
    value: Any, 
    max_length: int = 200, 
    level: SanitizationLevel = SanitizationLevel.MODERATE
) -> str:
    """
    Enhanced sanitization of user input for logging to prevent log injection attacks.
    
    Args:
        value: The value to sanitize (will be converted to string)
        max_length: Maximum length of the sanitized string
        level: Sanitization level (STRICT, MODERATE, LENIENT)
        
    Returns:
        Sanitized string safe for logging
    """
    if value is None:
        return "None"
    
    # Convert to string, handling binary data safely
    if not isinstance(value, str):
        # Handle binary data (bytes, bytearray) without UTF-8 decoding
        if isinstance(value, (bytes, bytearray)):
            # For binary data, show a safe representation
            try:
                # Try to decode as UTF-8 first
                value = value.decode('utf-8')
            except UnicodeDecodeError:
                # If UTF-8 decoding fails, represent as hex or safe binary info
                if len(value) <= 50:
                    value = f"<binary data: {value.hex()[:100]}>"
                else:
                    value = f"<binary data: {len(value)} bytes, starts with {value[:20].hex()}>"
        # Handle complex objects
        elif isinstance(value, (dict, list)):
            try:
                value = json.dumps(value, separators=(',', ':'))
            except (TypeError, ValueError):
                value = str(value)
        else:
            # For other types, use str() but catch any encoding issues
            try:
                value = str(value)
            except UnicodeDecodeError:
                value = f"<object: {type(value).__name__} - encoding error>"
    
    # Apply sanitization based on level
    if level == SanitizationLevel.STRICT:
        sanitized = _strict_sanitize(value)
    elif level == SanitizationLevel.MODERATE:
        sanitized = _moderate_sanitize(value)
    else:  # LENIENT
        sanitized = _lenient_sanitize(value)
    
    # Limit length to prevent log flooding
    if len(sanitized) > max_length:
        if max_length > 3:
            sanitized = sanitized[:max_length-3] + '...'
        else:
            sanitized = sanitized[:max_length]
    
    return sanitized


def _strict_sanitize(value: str) -> str:
    """
    Strict sanitization - only allows alphanumeric, spaces, and basic punctuation.
    
    Args:
        value: String to sanitize
        
    Returns:
        Strictly sanitized string
    """
    # Remove all control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '_', value)
    
    # Replace dangerous characters
    sanitized = sanitized.replace('\n', '_').replace('\r', '_')
    sanitized = sanitized.replace('\t', ' ').replace('\b', '_')
    
    # Only allow safe characters: letters, numbers, spaces, basic punctuation
    sanitized = re.sub(r'[^\w\s\-\.\@\#\$\%\(\)\+\=\[\]\{\}\:\;\"\'<>,\.\?\/]', '_', sanitized)
    
    # Collapse multiple spaces/underscores
    sanitized = re.sub(r'[\s_]+', ' ', sanitized)
    
    return sanitized.strip()


def _moderate_sanitize(value: str) -> str:
    """
    Moderate sanitization - removes dangerous control characters but preserves readability.
    
    Args:
        value: String to sanitize
        
    Returns:
        Moderately sanitized string
    """
    # Remove dangerous control characters but preserve some formatting
    sanitized = re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]', '_', value)
    
    # Replace line breaks with space to prevent log forging
    sanitized = sanitized.replace('\n', ' ').replace('\r', ' ')
    sanitized = sanitized.replace('\t', ' ')
    
    # Remove NULL bytes and other dangerous sequences
    sanitized = sanitized.replace('\x00', '')
    
    # Prevent log injection patterns
    sanitized = re.sub(r'(INFO|DEBUG|WARN|ERROR|FATAL)\s*[\[\]:,-]', r'\1_', sanitized, flags=re.IGNORECASE)
    
    # Collapse multiple spaces
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    return sanitized.strip()


def _lenient_sanitize(value: str) -> str:
    """
    Lenient sanitization - basic security while preserving most content.
    
    Args:
        value: String to sanitize
        
    Returns:
        Leniently sanitized string
    """
    # Remove only the most dangerous characters
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '_', value)
    
    # Replace line breaks to prevent log forging
    sanitized = sanitized.replace('\n', ' | ').replace('\r', '')
    
    # Remove NULL bytes
    sanitized = sanitized.replace('\x00', '')
    
    return sanitized.strip()


def sanitize_structured_data(data: Dict[str, Any], level: SanitizationLevel = SanitizationLevel.MODERATE) -> Dict[str, str]:
    """
    Sanitize structured logging data.
    
    Args:
        data: Dictionary of logging data
        level: Sanitization level
        
    Returns:
        Dictionary with sanitized values
    """
    sanitized = {}
    
    for key, value in data.items():
        # Sanitize the key as well
        safe_key = sanitize_log_input(key, max_length=50, level=level)
        
        # Sanitize the value
        safe_value = sanitize_log_input(value, level=level)
        
        sanitized[safe_key] = safe_value
    
    return sanitized


def is_safe_for_logging(value: str, level: SanitizationLevel = SanitizationLevel.MODERATE) -> bool:
    """
    Check if a value is safe for logging without sanitization.
    
    Args:
        value: String to check
        level: Safety level to check against
        
    Returns:
        True if safe for logging, False otherwise
    """
    if not isinstance(value, str):
        return False
    
    # Check for dangerous patterns
    dangerous_patterns = [
        r'[\x00-\x08\x0b-\x1f\x7f-\x9f]',  # Control characters
        r'\n|\r',  # Line breaks that could forge logs
        r'(INFO|DEBUG|WARN|ERROR|FATAL)\s*[\[\]:,-]',  # Log injection patterns
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return False
    
    return True 