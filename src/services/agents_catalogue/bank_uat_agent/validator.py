"""
Validator for Bank UAT Agent Service.

This module provides parameter validation and security sanitization 
for the bank UAT testing workflow with RSA encryption support.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List


class BankUATValidator:
    """Validator for Bank UAT Agent Service parameters."""
    
    SERVICE_NAME = "bank-uat-agent"
    
    # Maximum file size (10MB for keys and docs)
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
    
    # Allowed file extensions for API documentation
    ALLOWED_DOC_EXTENSIONS = ['.txt', '.json', '.md', '.pdf']
    
    # Allowed file extensions for encryption keys
    ALLOWED_KEY_EXTENSIONS = ['.pem', '.key', '.crt', '.txt']
    
    # Pattern for bank name validation
    BANK_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_]{1,100}$')
    
    # Pattern for API names (alphanumeric, spaces, hyphens, underscores, forward slashes)
    API_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_/]{1,200}$')
    
    @classmethod
    def get_validation_schema(cls) -> Dict[str, Any]:
        """Get validation schema for the service."""
        return {
            "required": ["api_doc_path", "bank_name"],
            "optional": [
                "uat_host", "generate_encrypted_curls", "bank_public_cert_path", "private_key_path", 
                "partner_public_key_path", "aes_key", "encryption_type", 
                "apis_to_test", "timeout_seconds", 
                "include_response_analysis", "custom_headers",
                "enable_ai_analysis", "ai_confidence_threshold", "manual_config_override",
                "encryption_template", "public_key_path"  # Legacy support
            ],
            "validation_rules": {
                "api_doc_path": {
                    "type": str,
                    "max_length": 500,
                    "custom_validator": "validate_api_doc_path"
                },
                "bank_name": {
                    "type": str,
                    "pattern": cls.BANK_NAME_PATTERN.pattern,
                    "max_length": 100,
                    "min_length": 1
                },
                "uat_host": {
                    "type": str,
                    "max_length": 500,
                    "min_length": 0,
                    "default": "",
                    "skip_validation": True  # Skip URL format validation as requested
                },
                "generate_encrypted_curls": {
                    "type": bool,
                    "default": False,
                    "description": "Whether to generate encrypted curl commands"
                },
                "bank_public_cert_path": {
                    "type": str,
                    "max_length": 500,
                    "custom_validator": "validate_key_file_path",
                    "description": "Path to bank's public certificate for encrypting requests TO the bank"
                },
                "public_key_path": {
                    "type": str,
                    "max_length": 500,
                    "custom_validator": "validate_key_file_path",
                    "description": "Legacy parameter - use bank_public_cert_path instead"
                },
                "private_key_path": {
                    "type": str,
                    "max_length": 500,
                    "custom_validator": "validate_key_file_path",
                    "description": "Path to partner's private key for decrypting responses FROM the bank"
                },
                "partner_public_key_path": {
                    "type": str,
                    "max_length": 500,
                    "custom_validator": "validate_key_file_path",
                    "description": "Path to partner's public key for bank to encrypt responses TO partner"
                },
                "aes_key": {
                    "type": str,
                    "pattern": r"^[0-9A-Fa-f]{32}$|^[0-9A-Fa-f]{48}$|^[0-9A-Fa-f]{64}$",
                    "description": "AES key in hexadecimal format (32/48/64 characters for 128/192/256-bit)"
                },
                "encryption_type": {
                    "type": str,
                    "enum": ["rsa", "aes", "hybrid", "signature_only", "none", "auto_detect", "template", "custom"],
                    "default": "auto_detect"
                },
                "apis_to_test": {
                    "type": [list, str],
                    "max_length": 50,
                    "item_validator": "validate_api_name",
                    "description": "List of API names or comma-separated string (quotes are automatically stripped)"
                },

                "timeout_seconds": {
                    "type": int,
                    "min_value": 10,
                    "max_value": 300,
                    "default": 60
                },
                "include_response_analysis": {
                    "type": bool,
                    "default": True
                },
                "custom_headers": {
                    "type": dict,
                    "max_size": 20
                },
                "enable_ai_analysis": {
                    "type": bool,
                    "default": True,
                    "description": "Whether to enable AI-powered encryption analysis"
                },
                "ai_confidence_threshold": {
                    "type": float,
                    "default": 0.6,
                    "min_value": 0.0,
                    "max_value": 1.0,
                    "description": "Minimum confidence threshold for AI analysis"
                },
                "manual_config_override": {
                    "type": dict,
                    "description": "Manual configuration overrides for AI-detected settings"
                },
                "encryption_template": {
                    "type": str,
                    "enum": ["rsa_aes_headers", "rsa_aes_body", "rsa_aes_mixed", "signature_only", "aes_legacy", "rsa_pure"],
                    "description": "Pre-defined encryption template to use"
                }
            }
        }
    
    @classmethod
    def validate_parameters(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize all parameters for bank UAT testing."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"DEBUG: Raw parameters received in validator: {parameters}")
        logger.info(f"DEBUG: generate_encrypted_curls type: {type(parameters.get('generate_encrypted_curls'))}")
        logger.info(f"DEBUG: generate_encrypted_curls value: {parameters.get('generate_encrypted_curls')}")
        
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
                logger.info(f"DEBUG: Setting {param} to {parameters[param]} (type: {type(parameters[param])})")
            else:
                # Set default if specified
                rule = schema["validation_rules"].get(param, {})
                if "default" in rule:
                    validated[param] = rule["default"]
                    logger.info(f"DEBUG: Setting {param} to default: {rule['default']}")
        
        logger.info(f"DEBUG: Validated parameters: {validated}")
        
        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")
        
        # Perform specific validations
        validated = cls._validate_api_doc_path(validated)
        validated = cls._validate_bank_name(validated)
        validated = cls._validate_encryption_settings(validated)

        validated = cls._validate_custom_headers(validated)
        
        return validated
    
    @classmethod
    def _validate_api_doc_path(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API documentation file path parameter."""
        api_doc_path = parameters.get("api_doc_path", "")
        
        if not api_doc_path:
            raise ValueError("API documentation path cannot be empty")
        
        # Check if file exists
        if not os.path.exists(api_doc_path):
            raise ValueError(f"API documentation file does not exist: {api_doc_path}")
        
        # Check file extension
        file_ext = Path(api_doc_path).suffix.lower()
        if file_ext not in cls.ALLOWED_DOC_EXTENSIONS:
            raise ValueError(f"Unsupported API doc file type: {file_ext}. Allowed: {cls.ALLOWED_DOC_EXTENSIONS}")
        
        # Check file size
        try:
            file_size = os.path.getsize(api_doc_path)
            if file_size > cls.MAX_FILE_SIZE_BYTES:
                raise ValueError(f"API doc file too large: {file_size} bytes. Maximum: {cls.MAX_FILE_SIZE_BYTES}")
            
            if file_size == 0:
                raise ValueError("API documentation file is empty")
                
        except OSError as e:
            raise ValueError(f"Cannot access API doc file: {str(e)}")
        
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
    def _validate_encryption_settings(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate encryption-related parameters."""
        encryption_type = parameters.get("encryption_type", "auto_detect")
        
        if encryption_type not in ["auto_detect", "hybrid", "none"]:
            raise ValueError("encryption_type must be one of: auto_detect, hybrid, none")
        
        # Validate hybrid encryption parameters using three-certificate structure
        # Skip validation for auto_detect as requirements will be resolved later
        if encryption_type == "hybrid":
            # Check for bank public certificate (required for encrypting requests TO bank)
            bank_public_cert_path = parameters.get("bank_public_cert_path") or parameters.get("public_key_path")  # Legacy support
            private_key_path = parameters.get("private_key_path")
            
            if not bank_public_cert_path:
                raise ValueError("bank_public_cert_path is required for hybrid encryption (bank's public certificate)")
            
            if not private_key_path:
                raise ValueError("private_key_path is required for hybrid encryption (partner's private key)")
            
            # Validate key file paths exist
            if not os.path.exists(bank_public_cert_path):
                raise ValueError(f"Bank public certificate file not found: {bank_public_cert_path}")
            if not os.path.exists(private_key_path):
                raise ValueError(f"Private key file not found: {private_key_path}")
                
            # Optional: Partner's public key (for bank to encrypt responses TO partner)
            partner_public_key_path = parameters.get("partner_public_key_path")
            if partner_public_key_path and not os.path.exists(partner_public_key_path):
                raise ValueError(f"Partner public key file not found: {partner_public_key_path}")
        
        # For auto_detect, key validation will be done later during execution
        elif encryption_type == "auto_detect":
            # This type may require keys depending on what's detected/configured
            # Skip strict validation here as requirements will be determined later
            pass
        
        return parameters
    

    
    @classmethod
    def _validate_custom_headers(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate custom headers parameter."""
        custom_headers = parameters.get("custom_headers", {})
        
        if custom_headers:
            if not isinstance(custom_headers, dict):
                raise ValueError("custom_headers must be a dictionary")
            
            if len(custom_headers) > 20:
                raise ValueError("Too many custom headers. Maximum: 20")
            
            # Validate header names and values
            for header_name, header_value in custom_headers.items():
                if not isinstance(header_name, str) or not isinstance(header_value, str):
                    raise ValueError("Header names and values must be strings")
                
                if len(header_name) > 100 or len(header_value) > 500:
                    raise ValueError("Header name/value too long")
                
                # Basic security check
                if any(char in header_name.lower() for char in ['<', '>', 'script', 'eval']):
                    raise ValueError(f"Invalid header name: {header_name}")
        
        return parameters
    
    @classmethod
    def validate_api_doc_path(cls, file_path: str) -> bool:
        """Standalone validation for API documentation file path."""
        try:
            cls._validate_api_doc_path({"api_doc_path": file_path})
            return True
        except ValueError:
            return False
    
    @classmethod
    def validate_key_file_path(cls, file_path: str) -> bool:
        """Standalone validation for encryption key file path."""
        try:
            if not file_path:
                return True  # Optional parameter
            
            if not os.path.exists(file_path):
                return False
            
            file_ext = Path(file_path).suffix.lower()
            return file_ext in cls.ALLOWED_KEY_EXTENSIONS
            
        except Exception:
            return False
    
    @classmethod
    def validate_api_name(cls, api_name: str) -> bool:
        """Standalone validation for API name."""
        try:
            return cls.API_NAME_PATTERN.match(api_name) is not None
        except Exception:
            return False


# Validation functions for validator discovery system
def validate_api_doc_path(api_doc_path: str) -> str:
    """Validate API documentation path parameter."""
    validator = BankUATValidator()
    validator._validate_api_doc_path({"api_doc_path": api_doc_path})
    return api_doc_path


def validate_bank_name(bank_name: str) -> str:
    """Validate bank name parameter."""
    validator = BankUATValidator()
    validator._validate_bank_name({"bank_name": bank_name})
    return bank_name


def validate_parameters(parameters: Dict[str, Any]) -> None:
    """Top-level parameter validation for bank UAT agent service."""
    # Check required parameters
    api_doc_path = parameters.get("api_doc_path")
    if not isinstance(api_doc_path, str) or not api_doc_path.strip():
        raise ValueError("Missing required parameter: api_doc_path")
    
    bank_name = parameters.get("bank_name")
    if not isinstance(bank_name, str) or not bank_name.strip():
        raise ValueError("Missing required parameter: bank_name")
    
    # Validate individual parameters
    validate_api_doc_path(api_doc_path.strip())
    validate_bank_name(bank_name.strip())


# Expose required parameters for validator discovery to enforce presence
REQUIRED_PARAMETERS: List[str] = ["api_doc_path", "bank_name"]


def required_parameters() -> List[str]:
    """Return list of required parameters."""
    return REQUIRED_PARAMETERS 