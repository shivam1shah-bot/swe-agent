"""
Input Sanitizer for MCP tool protection.

Provides protection against prompt injection attacks and malicious input.
"""

import re
from typing import Dict, Any, List, Optional, Union
from urllib.parse import unquote

from src.providers.logger import Logger


class InputSanitizer:
    """
    Input sanitizer for MCP tool protection.
    
    Provides protection against prompt injection attacks, XSS, and other
    malicious input patterns.
    """
    
    def __init__(self):
        """Initialize input sanitizer."""
        self.logger = Logger("InputSanitizer")
        
        # Prompt injection patterns
        self.injection_patterns = self._get_injection_patterns()
        
        # Safe character patterns
        self.safe_patterns = self._get_safe_patterns()
    
    def _get_injection_patterns(self) -> List[re.Pattern]:
        """
        Get patterns that indicate potential prompt injection.
        
        Returns:
            List of compiled regex patterns
        """
        patterns = [
            # Common prompt injection starters
            re.compile(r'\b(ignore|forget|disregard)\s+(previous|above|all)\s+(instructions?|prompts?)', re.IGNORECASE),
            re.compile(r'\b(now|instead)\s+(do|execute|run|perform)', re.IGNORECASE),
            re.compile(r'\b(system|assistant|ai)\s*(message|prompt|instruction)', re.IGNORECASE),
            
            # Role manipulation attempts
            re.compile(r'\b(you\s+are|act\s+as|pretend\s+to\s+be|role\s*play)', re.IGNORECASE),
            re.compile(r'\b(admin|administrator|root|superuser|god\s+mode)', re.IGNORECASE),
            
            # Command injection patterns
            re.compile(r'[;&|`$()<>]'),  # Shell metacharacters
            re.compile(r'\b(exec|eval|system|shell|cmd|command)', re.IGNORECASE),
            
            # Script injection patterns
            re.compile(r'<script[^>]*>', re.IGNORECASE),
            re.compile(r'javascript:', re.IGNORECASE),
            re.compile(r'on\w+\s*=', re.IGNORECASE),  # Event handlers
            
            # Path traversal
            re.compile(r'\.\./|\.\.\\'),
            
            # SQL injection patterns
            re.compile(r'\b(union|select|insert|update|delete|drop|create|alter)\s+', re.IGNORECASE),
            re.compile(r'[\'";]'),  # SQL quote characters
            
            # Tool manipulation attempts
            re.compile(r'\b(override|bypass|skip|disable)\s+(validation|security|check)', re.IGNORECASE),
            re.compile(r'\b(reveal|show|expose|leak)\s+(system|internal|private)', re.IGNORECASE),
        ]
        
        return patterns
    
    def _get_safe_patterns(self) -> Dict[str, re.Pattern]:
        """
        Get patterns for safe input validation.
        
        Returns:
            Dictionary of safe patterns by type
        """
        return {
            'alphanumeric': re.compile(r'^[a-zA-Z0-9_-]+$'),
            'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            'uuid': re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'),
            'safe_string': re.compile(r'^[a-zA-Z0-9\s._-]+$'),
            'url_safe': re.compile(r'^[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=]+$'),
        }
    
    def sanitize_input(self, input_data: Any, field_name: str = "") -> Any:
        """
        Sanitize input data to prevent injection attacks.
        
        Args:
            input_data: Input data to sanitize
            field_name: Optional field name for logging
            
        Returns:
            Sanitized input data
            
        Raises:
            ValueError: If input contains malicious patterns
        """
        if input_data is None:
            return None
        
        if isinstance(input_data, str):
            return self._sanitize_string(input_data, field_name)
        elif isinstance(input_data, dict):
            return self._sanitize_dict(input_data, field_name)
        elif isinstance(input_data, list):
            return self._sanitize_list(input_data, field_name)
        elif isinstance(input_data, (int, float, bool)):
            return input_data
        else:
            # Convert to string and sanitize
            return self._sanitize_string(str(input_data), field_name)
    
    def _sanitize_string(self, text: str, field_name: str = "") -> str:
        """
        Sanitize a string input.
        
        Args:
            text: String to sanitize
            field_name: Optional field name for logging
            
        Returns:
            Sanitized string
            
        Raises:
            ValueError: If string contains malicious patterns
        """
        if not text:
            return text
        
        # Check for injection patterns
        suspicious_patterns = self._detect_injection_patterns(text)
        if suspicious_patterns:
            self.logger.warning(
                "Potential injection attack detected",
                field=field_name,
                patterns=suspicious_patterns,
                text_snippet=text[:100]
            )
            raise ValueError("Potential security threat detected")
        
        # URL decode to catch encoded attacks
        try:
            decoded_text = unquote(text)
            if decoded_text != text:
                # Check decoded version for injection patterns
                decoded_patterns = self._detect_injection_patterns(decoded_text)
                if decoded_patterns:
                    self.logger.warning(
                        "Potential injection attack detected in URL-decoded input",
                        field=field_name,
                        patterns=decoded_patterns
                    )
                    raise ValueError(f"URL-decoded input contains malicious content: {', '.join(decoded_patterns)}")
        except Exception:
            # If URL decoding fails, continue with original text
            pass
        
        # Basic HTML entity encoding for safety
        sanitized = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        sanitized = sanitized.replace('"', '&quot;').replace("'", '&#x27;')
        
        return sanitized
    
    def _sanitize_dict(self, data: Dict[str, Any], parent_field: str = "") -> Dict[str, Any]:
        """
        Sanitize a dictionary recursively.
        
        Args:
            data: Dictionary to sanitize
            parent_field: Parent field name for logging
            
        Returns:
            Sanitized dictionary
        """
        sanitized = {}
        for key, value in data.items():
            field_name = f"{parent_field}.{key}" if parent_field else key
            
            # Sanitize the key itself
            sanitized_key = self._sanitize_string(key, f"{field_name}[key]")
            
            # Sanitize the value
            sanitized_value = self.sanitize_input(value, field_name)
            
            sanitized[sanitized_key] = sanitized_value
        
        return sanitized
    
    def _sanitize_list(self, data: List[Any], field_name: str = "") -> List[Any]:
        """
        Sanitize a list recursively.
        
        Args:
            data: List to sanitize
            field_name: Field name for logging
            
        Returns:
            Sanitized list
        """
        sanitized = []
        for i, item in enumerate(data):
            item_field = f"{field_name}[{i}]"
            sanitized_item = self.sanitize_input(item, item_field)
            sanitized.append(sanitized_item)
        
        return sanitized
    
    def _detect_injection_patterns(self, text: str) -> List[str]:
        """
        Detect potential injection patterns in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of detected pattern names
        """
        detected_patterns = []
        
        for pattern in self.injection_patterns:
            if pattern.search(text):
                detected_patterns.append(pattern.pattern[:50])  # Truncate for logging
        
        return detected_patterns
    
    def validate_safe_input(self, text: str, input_type: str = "safe_string") -> bool:
        """
        Validate that input matches a safe pattern.
        
        Args:
            text: Text to validate
            input_type: Type of validation (alphanumeric, email, etc.)
            
        Returns:
            True if input is safe
        """
        if not text:
            return True
        
        pattern = self.safe_patterns.get(input_type)
        if not pattern:
            self.logger.warning("Unknown input type for validation", input_type=input_type)
            return False
        
        return bool(pattern.match(text))
    
    def sanitize_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize tool arguments with tool-specific rules.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments to sanitize
            
        Returns:
            Sanitized arguments
            
        Raises:
            ValueError: If arguments contain malicious content
        """
        try:
            self.logger.debug("Sanitizing tool arguments", tool_name=tool_name, arg_count=len(arguments))
            
            # Apply general sanitization
            sanitized_args = self.sanitize_input(arguments, f"tool.{tool_name}")
            
            # Apply tool-specific validation rules
            self._apply_tool_specific_validation(tool_name, sanitized_args)
            
            return sanitized_args
            
        except Exception as e:
            self.logger.error("Error sanitizing tool arguments", tool_name=tool_name, error=str(e))
            raise
    
    def _apply_tool_specific_validation(self, tool_name: str, arguments: Dict[str, Any]):
        """
        Apply tool-specific validation rules.
        
        Args:
            tool_name: Name of the tool
            arguments: Arguments to validate
            
        Raises:
            ValueError: If validation fails
        """
        # Task ID validation for task tools
        if 'task_id' in arguments and tool_name.startswith(('get_task', 'update_task')):
            task_id = arguments['task_id']
            if not self.validate_safe_input(task_id, 'uuid'):
                raise ValueError("Invalid task ID format")
        
        # No specific tool argument validation currently needed for removed tools
        
        # Limit validation for list operations
        if 'limit' in arguments:
            limit = arguments['limit']
            if not isinstance(limit, int) or limit < 1 or limit > 1000:
                raise ValueError("Limit must be an integer between 1 and 1000")
        
        # Page validation for pagination
        if 'page' in arguments:
            page = arguments['page']
            if not isinstance(page, int) or page < 1:
                raise ValueError("Page must be a positive integer")
    
    def get_sanitization_stats(self) -> Dict[str, Any]:
        """
        Get sanitization statistics.
        
        Returns:
            Dictionary with sanitization statistics
        """
        return {
            "injection_patterns_count": len(self.injection_patterns),
            "safe_patterns_count": len(self.safe_patterns),
            "pattern_types": list(self.safe_patterns.keys())
        } 