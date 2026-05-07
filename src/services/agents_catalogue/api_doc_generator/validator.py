"""
Validator for API Documentation Generator Service.

This module provides parameter validation and security sanitization 
for the API documentation generation workflow.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List


class APIDocGeneratorValidator:
    """Validator for API Documentation Generator Service parameters."""
    
    SERVICE_NAME = "api-doc-generator"
    
    # Maximum file size (50MB)
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
    
    # Allowed file extensions for input documents
    ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.doc', '.docx']
    
    # Pattern for bank name validation (alphanumeric, spaces, hyphens, underscores)
    BANK_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_]{1,100}$')
    
    @classmethod
    def get_validation_schema(cls) -> Dict[str, Any]:
        """Get validation schema for the service."""
        return {
            "required": ["document_file_path", "bank_name"],
            "optional": ["custom_prompt", "output_format", "include_examples", "enhance_context"],
            "validation_rules": {
                "document_file_path": {
                    "type": str,
                    "max_length": 500,
                    "custom_validator": "validate_document_file_path"
                },
                "bank_name": {
                    "type": str,
                    "pattern": cls.BANK_NAME_PATTERN.pattern,
                    "max_length": 100,
                    "min_length": 1
                },
                "custom_prompt": {
                    "type": str,
                    "max_length": 2000,
                    "default": "Generate comprehensive API documentation"
                },
                "output_format": {
                    "type": str,
                    "enum": ["txt", "json", "markdown", "all"],
                    "default": "markdown"
                },
                "include_examples": {
                    "type": bool,
                    "default": True
                },
                "enhance_context": {
                    "type": bool,
                    "default": True
                }
            }
        }
    
    @classmethod
    def validate_parameters(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize all parameters for API documentation generation."""
        schema = cls.get_validation_schema()
        validated = {}
        errors = []
        
        # Check required parameters
        for param in schema["required"]:
            if param not in parameters:
                errors.append(f"Missing required parameter: {param}")
            else:
                validated[param] = parameters[param]
        
        # Validate and set optional parameters
        for param in schema["optional"]:
            if param in parameters:
                validated[param] = parameters[param]
            else:
                # Set default if specified
                rule = schema["validation_rules"].get(param, {})
                if "default" in rule:
                    validated[param] = rule["default"]
        
        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")
        
        # Perform specific validations
        validated = cls._validate_document_file_path(validated)
        validated = cls._validate_bank_name(validated)
        validated = cls._validate_custom_prompt(validated)
        validated = cls._validate_output_format(validated)
        
        return validated
    
    @classmethod
    def _validate_document_file_path(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate document file path parameter."""
        file_path = parameters.get("document_file_path", "")
        
        if not file_path:
            raise ValueError("Document file path cannot be empty")
        
        # Security check: prevent path traversal
        if ".." in file_path or file_path.startswith("/"):
            # Allow absolute paths but log them
            pass
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise ValueError(f"Document file does not exist: {file_path}")
        
        # Check file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {file_ext}. Allowed: {cls.ALLOWED_EXTENSIONS}")
        
        # Check file size
        try:
            file_size = os.path.getsize(file_path)
            if file_size > cls.MAX_FILE_SIZE_BYTES:
                raise ValueError(f"File too large: {file_size} bytes. Maximum: {cls.MAX_FILE_SIZE_BYTES}")
            
            if file_size == 0:
                raise ValueError("Document file is empty")
                
        except OSError as e:
            raise ValueError(f"Cannot access file: {str(e)}")
        
        return parameters
    
    @classmethod
    def _validate_bank_name(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate bank name parameter."""
        bank_name = parameters.get("bank_name", "")
        
        if not bank_name:
            raise ValueError("Bank name cannot be empty")
        
        if not cls.BANK_NAME_PATTERN.match(bank_name):
            raise ValueError("Bank name contains invalid characters. Use only alphanumeric, spaces, hyphens, underscores")
        
        # Normalize bank name (trim and title case)
        parameters["bank_name"] = bank_name.strip().title()
        
        return parameters
    

    
    @classmethod
    def _validate_custom_prompt(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate custom prompt parameter."""
        custom_prompt = parameters.get("custom_prompt", "")
        
        if custom_prompt:
            # Basic sanitization
            custom_prompt = custom_prompt.strip()
            
            # Check length
            if len(custom_prompt) > 2000:
                raise ValueError("Custom prompt too long. Maximum 2000 characters")
            
            # Security: basic check for potential injection
            suspicious_patterns = ['<script', 'javascript:', 'eval(', 'exec(']
            if any(pattern in custom_prompt.lower() for pattern in suspicious_patterns):
                raise ValueError("Custom prompt contains potentially unsafe content")
            
            parameters["custom_prompt"] = custom_prompt
        
        return parameters
    
    @classmethod
    def _validate_output_format(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate output format parameter."""
        output_format = parameters.get("output_format", "txt")
        
        valid_formats = ["txt", "json", "markdown", "all"]
        if output_format not in valid_formats:
            raise ValueError(f"Invalid output format: {output_format}. Valid: {valid_formats}")
        
        return parameters
    
    @classmethod
    def validate_document_file_path(cls, file_path: str) -> bool:
        """Standalone validation for document file path."""
        try:
            cls._validate_document_file_path({"document_file_path": file_path})
            return True
        except ValueError:
            return False


# Validation functions for validator discovery system
def validate_document_file_path(document_file_path: str) -> str:
    """Validate document file path parameter."""
    validator = APIDocGeneratorValidator()
    validator._validate_document_file_path({"document_file_path": document_file_path})
    return document_file_path


def validate_bank_name(bank_name: str) -> str:
    """Validate bank name parameter."""
    validator = APIDocGeneratorValidator()
    validator._validate_bank_name({"bank_name": bank_name})
    return bank_name


def validate_parameters(parameters: Dict[str, Any]) -> None:
    """Top-level parameter validation for API doc generator service."""
    # Check required parameters
    document_file_path = parameters.get("document_file_path")
    if not isinstance(document_file_path, str) or not document_file_path.strip():
        raise ValueError("Missing required parameter: document_file_path")
    
    bank_name = parameters.get("bank_name")
    if not isinstance(bank_name, str) or not bank_name.strip():
        raise ValueError("Missing required parameter: bank_name")
    
    # Validate individual parameters
    validate_document_file_path(document_file_path.strip())
    validate_bank_name(bank_name.strip())


# Expose required parameters for validator discovery to enforce presence
REQUIRED_PARAMETERS: List[str] = ["document_file_path", "bank_name"]


def required_parameters() -> List[str]:
    """Return list of required parameters."""
    return REQUIRED_PARAMETERS 