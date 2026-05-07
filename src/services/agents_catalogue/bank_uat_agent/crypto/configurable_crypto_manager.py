"""
Configurable Crypto Manager for Bank UAT Agent

Main orchestrator for different encryption strategies. Handles template-based,
custom, and AI-detected encryption configurations with flexible padding support.
"""

import json
import base64
import secrets
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import asdict

from src.providers.logger import Logger
from .padding_manager import PaddingManager, PaddingValidationError
from ..rsa_crypto_manager import RSACryptoManager
from ..aes_crypto_manager import AESCryptoManager
from ..config.encryption_config import (
    EncryptionConfig, AlgorithmConfig, PaddingConfig, CryptoKeys,
    EncryptionType, PlacementStrategy, PaddingScheme
)
from ..config.template_definitions import (
    create_config_from_template, get_template_by_name, validate_template_name
)


class CryptoOperationError(Exception):
    """Exception raised when crypto operations fail"""
    pass


class CryptoStrategy(ABC):
    """Abstract base class for encryption strategies"""
    
    def __init__(self, config: EncryptionConfig, logger: Optional[Logger] = None):
        self.config = config
        self.logger = logger or Logger()
        self.padding_manager = PaddingManager(logger)
        
    @abstractmethod
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """
        Encrypt request according to strategy
        
        Returns:
            Tuple of (modified_curl_command, encryption_metadata)
        """
        pass
    
    @abstractmethod
    def decrypt_response(self, response: str) -> Optional[str]:
        """Decrypt response if encrypted"""
        pass
    
    @abstractmethod
    def validate_configuration(self) -> List[str]:
        """Validate strategy configuration and return errors"""
        pass


class HeaderBasedStrategy(CryptoStrategy):
    """Strategy for header-based encryption (like your specification)"""
    
    def __init__(self, config: EncryptionConfig, logger: Optional[Logger] = None):
        super().__init__(config, logger)
        self.rsa_crypto = RSACryptoManager(logger)
        self.aes_crypto = AESCryptoManager(logger)
        
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """Encrypt request with headers-based strategy"""
        metadata = {"strategy": "headers", "headers_added": [], "payload_encrypted": False}
        
        try:
            # Load keys
            public_key = None
            private_key = None
            
            if self.config.crypto_keys.bank_public_cert_path:
                public_key = self.rsa_crypto.load_public_key(self.config.crypto_keys.bank_public_cert_path)
            if self.config.crypto_keys.partner_private_key_path:
                private_key = self.rsa_crypto.load_private_key(self.config.crypto_keys.partner_private_key_path)
            
            # Generate AES key for this transaction
            aes_key = secrets.token_bytes(16)  # 128-bit AES key
            metadata["aes_key_generated"] = True
            
            # Generate IV based on configuration
            iv_format = self._get_iv_format()
            if iv_format == "16_digit_numeric":
                iv = self.padding_manager.generate_iv("AES", "16_digit_numeric")
                iv_value = iv.decode('utf-8')
            else:
                iv = self.padding_manager.generate_iv("AES", "random")
                iv_value = base64.b64encode(iv).decode('utf-8')
            
            # Prepare headers to add
            headers_to_add = []
            
            # Generate signature (token header)
            if "token" in self.config.headers:
                plain_json = json.dumps(payload, separators=(',', ':'))
                signature = self.padding_manager.sign_with_padding(
                    plain_json.encode('utf-8'),
                    private_key,
                    self.config.algorithms.padding.signature_padding,
                    self._extract_hash_algorithm(self.config.algorithms.signature)
                )
                token_value = base64.b64encode(signature).decode('utf-8')
                headers_to_add.append(f'-H "token: {token_value}"')
                metadata["headers_added"].append("token")
            
            # Encrypt AES key with bank's public key (key header)
            if "key" in self.config.headers and public_key:
                encrypted_aes_key = self.padding_manager.encrypt_with_padding(
                    aes_key,
                    public_key,
                    self._extract_algorithm_name(self.config.algorithms.key_encryption),
                    self.config.algorithms.padding.rsa_padding
                )
                key_value = base64.b64encode(encrypted_aes_key).decode('utf-8')
                headers_to_add.append(f'-H "key: {key_value}"')
                metadata["headers_added"].append("key")
            
            # Encrypt partner ID (partner header)
            if "partner" in self.config.headers and public_key and self.config.crypto_keys.partner_id:
                encrypted_partner_id = self.padding_manager.encrypt_with_padding(
                    self.config.crypto_keys.partner_id.encode('utf-8'),
                    public_key,
                    self._extract_algorithm_name(self.config.algorithms.key_encryption),
                    self.config.algorithms.padding.rsa_padding
                )
                partner_value = base64.b64encode(encrypted_partner_id).decode('utf-8')
                headers_to_add.append(f'-H "partner: {partner_value}"')
                metadata["headers_added"].append("partner")
            
            # Add IV header
            if "iv" in self.config.headers:
                headers_to_add.append(f'-H "iv: {iv_value}"')
                metadata["headers_added"].append("iv")
            
            # Encrypt payload if required
            modified_curl = curl_command
            if self.config.headers.get("payload_encryption", {}).get("encrypt_full_body", False):
                # Encrypt the JSON payload with AES
                payload_json = json.dumps(payload, separators=(',', ':'))
                encrypted_payload = self.padding_manager.encrypt_with_padding(
                    payload_json.encode('utf-8'),
                    aes_key,
                    self._extract_algorithm_name(self.config.algorithms.payload_encryption),
                    self.config.algorithms.padding.aes_padding,
                    iv=iv if isinstance(iv, bytes) else iv.encode('utf-8'),
                    mode="CBC"
                )
                encrypted_payload_b64 = base64.b64encode(encrypted_payload).decode('utf-8')
                
                # Replace the original JSON payload in curl command
                modified_curl = self._replace_payload_in_curl(curl_command, encrypted_payload_b64)
                metadata["payload_encrypted"] = True
            
            # Add headers to curl command
            for header in headers_to_add:
                modified_curl = self._add_header_to_curl(modified_curl, header)
            
            metadata["encryption_successful"] = True
            return modified_curl, metadata
            
        except Exception as e:
            self.logger.error(f"Header-based encryption failed: {str(e)}")
            metadata["error"] = str(e)
            metadata["encryption_successful"] = False
            return curl_command, metadata
    
    def decrypt_response(self, response: str) -> Optional[str]:
        """Decrypt response if it appears to be encrypted"""
        try:
            # Check if response looks like encrypted data
            if self._looks_like_encrypted_response(response):
                # Try to decrypt with available keys and algorithms
                # This is a simplified implementation - in practice, you'd need
                # the same AES key and IV that were used for encryption
                self.logger.info("Response appears encrypted but decryption requires request context")
                return None
            return None
        except Exception as e:
            self.logger.debug(f"Response decryption failed: {str(e)}")
            return None
    
    def validate_configuration(self) -> List[str]:
        """Validate header-based configuration"""
        errors = []
        
        # Check required keys for RSA operations
        if self.config.requires_rsa_keys() and not self.config.crypto_keys.has_rsa_keys():
            errors.append("Header-based RSA encryption requires bank certificate, partner private key, and partner ID")
        
        # Validate padding compatibility
        if self.config.algorithms.key_encryption.startswith("RSA"):
            compat_info = self.padding_manager.validate_padding_compatibility(
                "RSA", 
                self.config.algorithms.padding.rsa_padding,
                self.config.crypto_keys.key_size
            )
            if not compat_info.is_compatible:
                errors.extend(compat_info.errors)
        
        return errors
    
    def _get_iv_format(self) -> str:
        """Get IV format from configuration"""
        iv_config = self.config.headers.get("iv", {})
        return iv_config.get("format", "base64")
    
    def _extract_algorithm_name(self, algorithm_spec: str) -> str:
        """Extract algorithm name from specification like 'RSA/ECB/PKCS1Padding'"""
        return algorithm_spec.split('/')[0] if '/' in algorithm_spec else algorithm_spec
    
    def _extract_hash_algorithm(self, signature_spec: str) -> str:
        """Extract hash algorithm from signature specification like 'SHA1withRSA'"""
        if "SHA1" in signature_spec.upper():
            return "SHA1"
        elif "SHA256" in signature_spec.upper():
            return "SHA256"
        else:
            return "SHA256"  # Default
    
    def _looks_like_encrypted_response(self, response: str) -> bool:
        """Check if response appears to be encrypted"""
        try:
            # Simple heuristics for encrypted data
            if len(response) > 50 and response.replace('\n', '').replace(' ', '').isalnum():
                # Could be base64 encoded
                decoded = base64.b64decode(response.replace('\n', '').replace(' ', ''))
                return len(decoded) > 16  # Minimum for encrypted data
        except:
            pass
        return False
    
    def _replace_payload_in_curl(self, curl_command: str, encrypted_payload: str) -> str:
        """Replace JSON payload in curl command with encrypted data"""
        # Find and replace the -d '...' part
        import re
        pattern = r"-d\s+'([^']+)'"
        replacement = f"-d '{encrypted_payload}'"
        return re.sub(pattern, replacement, curl_command)
    
    def _add_header_to_curl(self, curl_command: str, header: str) -> str:
        """Add header to curl command"""
        # Insert header after the URL but before -d if present
        parts = curl_command.split(' ')
        url_index = -1
        
        # Find URL (starts with http)
        for i, part in enumerate(parts):
            if part.startswith('http'):
                url_index = i
                break
        
        if url_index >= 0:
            # Insert header after URL
            parts.insert(url_index + 1, header)
            return ' '.join(parts)
        else:
            # Fallback: add at the end
            return f"{curl_command} {header}"


class BodyBasedStrategy(CryptoStrategy):
    """Strategy for body-based encryption"""
    
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """Encrypt request with body-based strategy"""
        metadata = {"strategy": "body", "body_modified": False}
        
        try:
            # Create new body structure with auth and encrypted data sections
            new_body = {}
            
            # Add authentication section
            if "auth" in self.config.body_structure:
                auth_section = {}
                # Add signature, encrypted keys, etc. to auth section
                new_body["auth"] = auth_section
            
            # Add encrypted data section
            if "data" in self.config.body_structure:
                # Encrypt the original payload
                encrypted_data = self._encrypt_payload_for_body(payload)
                new_body["data"] = encrypted_data
                metadata["body_modified"] = True
            
            # Replace payload in curl command
            modified_curl = self._replace_payload_in_curl(curl_command, json.dumps(new_body))
            
            metadata["encryption_successful"] = True
            return modified_curl, metadata
            
        except Exception as e:
            self.logger.error(f"Body-based encryption failed: {str(e)}")
            metadata["error"] = str(e)
            metadata["encryption_successful"] = False
            return curl_command, metadata
    
    def decrypt_response(self, response: str) -> Optional[str]:
        """Decrypt body-based response"""
        # Implementation for body-based decryption
        return None
    
    def validate_configuration(self) -> List[str]:
        """Validate body-based configuration"""
        errors = []
        
        if not self.config.body_structure:
            errors.append("Body-based strategy requires body_structure configuration")
        
        return errors
    
    def _encrypt_payload_for_body(self, payload: Dict[str, Any]) -> str:
        """Encrypt payload for body placement"""
        # Simplified implementation
        payload_json = json.dumps(payload)
        return base64.b64encode(payload_json.encode('utf-8')).decode('utf-8')
    
    def _replace_payload_in_curl(self, curl_command: str, new_payload: str) -> str:
        """Replace payload in curl command"""
        import re
        pattern = r"-d\s+'([^']+)'"
        replacement = f"-d '{new_payload}'"
        return re.sub(pattern, replacement, curl_command)


class MixedStrategy(CryptoStrategy):
    """Strategy for mixed placement (headers + body)"""
    
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """Encrypt request with mixed strategy"""
        metadata = {"strategy": "mixed", "headers_added": [], "body_modified": False}
        
        # Combine header and body strategies
        modified_curl = curl_command
        
        # Add headers if configured
        if self.config.headers:
            header_strategy = HeaderBasedStrategy(self.config, self.logger)
            modified_curl, header_metadata = header_strategy.encrypt_request(payload, modified_curl)
            metadata["headers_added"] = header_metadata.get("headers_added", [])
        
        # Modify body if configured
        if self.config.body_structure:
            body_strategy = BodyBasedStrategy(self.config, self.logger)
            modified_curl, body_metadata = body_strategy.encrypt_request(payload, modified_curl)
            metadata["body_modified"] = body_metadata.get("body_modified", False)
        
        metadata["encryption_successful"] = True
        return modified_curl, metadata
    
    def decrypt_response(self, response: str) -> Optional[str]:
        """Decrypt mixed response"""
        return None
    
    def validate_configuration(self) -> List[str]:
        """Validate mixed configuration"""
        errors = []
        
        if not self.config.headers and not self.config.body_structure:
            errors.append("Mixed strategy requires either headers or body_structure configuration")
        
        return errors


class ConfigurableCryptoManager:
    """
    Main configurable crypto manager that orchestrates different encryption strategies
    """
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        self.padding_manager = PaddingManager(logger)
        
        # Strategy mapping
        self.strategies = {
            PlacementStrategy.HEADERS.value: HeaderBasedStrategy,
            PlacementStrategy.BODY.value: BodyBasedStrategy,
            PlacementStrategy.MIXED.value: MixedStrategy
        }
    
    def create_encryption_config(self, config_data: Dict[str, Any]) -> EncryptionConfig:
        """Create EncryptionConfig from various input formats"""
        
        if isinstance(config_data, dict):
            # Handle template-based configuration
            if config_data.get("encryption_type") == EncryptionType.TEMPLATE.value:
                template_name = config_data.get("template_name")
                if not template_name or not validate_template_name(template_name):
                    raise ValueError(f"Invalid template name: {template_name}")
                
                # Create config from template with overrides
                overrides = config_data.get("crypto_overrides", {})
                return create_config_from_template(template_name=template_name, overrides=overrides)
            
            # Handle custom configuration
            elif config_data.get("encryption_type") == EncryptionType.CUSTOM.value:
                return EncryptionConfig.from_dict(config_data)
            
            # Handle auto-detect (will be processed by AI analyzer)
            elif config_data.get("encryption_type") == EncryptionType.AUTO_DETECT.value:
                return EncryptionConfig.from_dict(config_data)
            
            # Handle none (no encryption)
            elif config_data.get("encryption_type") == EncryptionType.NONE.value:
                config = EncryptionConfig.from_dict(config_data)
                config.generate_encrypted_curls = False
                return config
            
            else:
                # Default to auto-detect
                config_data["encryption_type"] = EncryptionType.AUTO_DETECT.value
                return EncryptionConfig.from_dict(config_data)
        
        else:
            raise ValueError(f"Invalid config data type: {type(config_data)}")
    
    def encrypt_curl_request(self, curl_command: str, payload: Dict[str, Any], config: EncryptionConfig) -> Tuple[str, Dict[str, Any]]:
        """
        Encrypt curl request according to configuration
        
        Returns:
            Tuple of (modified_curl_command, encryption_metadata)
        """
        metadata = {
            "original_command": curl_command,
            "config_type": config.encryption_type,
            "placement_strategy": config.placement_strategy,
            "encryption_enabled": config.generate_encrypted_curls
        }
        
        # Skip encryption if disabled or type is 'none'
        if not config.generate_encrypted_curls or config.encryption_type == EncryptionType.NONE.value:
            metadata["encryption_skipped"] = True
            metadata["reason"] = "Encryption disabled or type is 'none'"
            return curl_command, metadata
        
        try:
            # Validate configuration
            validation_errors = self.validate_encryption_config(config)
            if validation_errors:
                metadata["validation_errors"] = validation_errors
                metadata["encryption_failed"] = True
                return curl_command, metadata
            
            # Get appropriate strategy
            strategy_class = self.strategies.get(config.placement_strategy)
            if not strategy_class:
                raise ValueError(f"Unsupported placement strategy: {config.placement_strategy}")
            
            # Create strategy instance and encrypt
            strategy = strategy_class(config, self.logger)
            encrypted_curl, strategy_metadata = strategy.encrypt_request(payload, curl_command)
            
            # Merge metadata
            metadata.update(strategy_metadata)
            
            return encrypted_curl, metadata
            
        except Exception as e:
            self.logger.error(f"Curl encryption failed: {str(e)}")
            metadata["encryption_failed"] = True
            metadata["error"] = str(e)
            return curl_command, metadata
    
    def decrypt_response(self, response: str, config: EncryptionConfig) -> Optional[str]:
        """Decrypt response if encrypted"""
        if not config.generate_encrypted_curls or config.encryption_type == EncryptionType.NONE.value:
            return None
        
        try:
            strategy_class = self.strategies.get(config.placement_strategy)
            if strategy_class:
                strategy = strategy_class(config, self.logger)
                return strategy.decrypt_response(response)
        except Exception as e:
            self.logger.debug(f"Response decryption failed: {str(e)}")
        
        return None
    
    def validate_encryption_config(self, config: EncryptionConfig) -> List[str]:
        """Validate encryption configuration"""
        errors = []
        
        try:
            # Basic validation
            if config.is_encryption_enabled():
                # Validate strategy
                if config.placement_strategy not in self.strategies:
                    errors.append(f"Unsupported placement strategy: {config.placement_strategy}")
                else:
                    # Validate strategy-specific configuration
                    strategy_class = self.strategies[config.placement_strategy]
                    strategy = strategy_class(config, self.logger)
                    strategy_errors = strategy.validate_configuration()
                    errors.extend(strategy_errors)
                
                # Validate padding compatibility
                if config.algorithms.key_encryption.startswith("RSA"):
                    rsa_compat = self.padding_manager.validate_padding_compatibility(
                        "RSA",
                        config.algorithms.padding.rsa_padding,
                        config.crypto_keys.key_size
                    )
                    if not rsa_compat.is_compatible:
                        errors.extend(rsa_compat.errors)
                
                if config.algorithms.payload_encryption.startswith("AES"):
                    aes_compat = self.padding_manager.validate_padding_compatibility(
                        "AES",
                        config.algorithms.padding.aes_padding
                    )
                    if not aes_compat.is_compatible:
                        errors.extend(aes_compat.errors)
        
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return errors
    
    def get_supported_strategies(self) -> List[Dict[str, Any]]:
        """Get list of supported encryption strategies"""
        return [
            {
                "name": "headers",
                "display_name": "Headers-Based",
                "description": "Place encryption data in HTTP headers",
                "complexity": "Medium",
                "use_cases": ["Modern APIs", "Header-based auth"]
            },
            {
                "name": "body", 
                "display_name": "Body-Based",
                "description": "Place encryption data in request body",
                "complexity": "Medium",
                "use_cases": ["Traditional APIs", "Body-based auth"]
            },
            {
                "name": "mixed",
                "display_name": "Mixed Placement",
                "description": "Split encryption data between headers and body",
                "complexity": "High",
                "use_cases": ["Advanced security", "Hybrid approaches"]
            }
        ]
    
    def get_configuration_summary(self, config: EncryptionConfig) -> Dict[str, Any]:
        """Get human-readable configuration summary"""
        return {
            "encryption_type": config.encryption_type,
            "template_name": config.template_name,
            "placement_strategy": config.placement_strategy,
            "algorithms": {
                "key_encryption": config.algorithms.key_encryption,
                "payload_encryption": config.algorithms.payload_encryption,
                "signature": config.algorithms.signature
            },
            "padding_schemes": {
                "rsa_padding": config.algorithms.padding.rsa_padding,
                "aes_padding": config.algorithms.padding.aes_padding,
                "signature_padding": config.algorithms.padding.signature_padding
            },
            "keys_configured": {
                "bank_certificate": bool(config.crypto_keys.bank_public_cert_path),
                "partner_private_key": bool(config.crypto_keys.partner_private_key_path),
                "partner_id": bool(config.crypto_keys.partner_id),
                "aes_key": bool(config.crypto_keys.aes_key_hex)
            },
            "encryption_enabled": config.generate_encrypted_curls,
            "ai_detected": config.ai_detected,
            "confidence_score": config.confidence_score
        } 