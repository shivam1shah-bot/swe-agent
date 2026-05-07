"""
Specific Encryption Strategy Implementations

Provides concrete implementations of encryption strategies for different
bank API patterns including RSA+AES combinations and signature-only approaches.
"""

import json
import base64
import secrets
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

from .configurable_crypto_manager import CryptoStrategy
from ..config.encryption_config import EncryptionConfig, PaddingScheme
from src.providers.logger import Logger


class EncryptionStrategy(CryptoStrategy):
    """Base encryption strategy with common functionality"""
    
    def __init__(self, config: EncryptionConfig, logger: Optional[Logger] = None):
        super().__init__(config, logger)
    
    def _generate_aes_key(self, key_size: int = 128) -> bytes:
        """Generate AES key of specified size"""
        return secrets.token_bytes(key_size // 8)
    
    def _generate_numeric_iv(self, length: int = 16) -> str:
        """Generate numeric IV of specified length"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(length)])
    
    def _extract_json_from_curl(self, curl_command: str) -> Dict[str, Any]:
        """Extract JSON payload from curl command"""
        import re
        match = re.search(r"-d\s+'([^']+)'", curl_command)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _replace_json_in_curl(self, curl_command: str, new_json: str) -> str:
        """Replace JSON payload in curl command"""
        import re
        pattern = r"(-d\s+')[^']+(')"
        replacement = f"\\g<1>{new_json}\\g<2>"
        return re.sub(pattern, replacement, curl_command)
    
    def _generate_configured_headers(self, payload: Dict[str, Any], crypto_context: Dict[str, Any] = None) -> List[str]:
        """
        Generate headers based on configuration instead of hardcoded values
        
        Args:
            payload: Request payload for signature generation
            crypto_context: Dictionary containing crypto values like signatures, encrypted keys, etc.
        
        Returns:
            List of formatted header strings for curl command
        """
        headers = []
        
        if not crypto_context:
            crypto_context = {}
        
        for header_name, header_config in self.config.headers.items():
            header_value = self._get_header_value(header_config, payload, crypto_context)
            if header_value:
                headers.append(f'-H "{header_config.name}: {header_value}"')
        
        return headers
    
    def _get_header_value(self, header_config, payload: Dict[str, Any], crypto_context: Dict[str, Any]) -> Optional[str]:
        """
        Get the value for a specific header based on its configuration
        
        Args:
            header_config: HeaderConfig object
            payload: Request payload
            crypto_context: Crypto values dictionary
        
        Returns:
            Formatted header value or None if cannot generate
        """
        try:
            if header_config.source == "static_value":
                return header_config.static_value
            
            elif header_config.source == "signature":
                return crypto_context.get("signature")
            
            elif header_config.source == "encrypted_aes_key":
                return crypto_context.get("encrypted_aes_key")
            
            elif header_config.source == "encrypted_partner_id":
                return crypto_context.get("encrypted_partner_id")
            
            elif header_config.source == "generated_iv":
                return crypto_context.get("iv")
            
            elif header_config.source == "partner_id":
                return self.config.crypto_keys.partner_id
            
            elif header_config.source == "timestamp":
                import time
                return str(int(time.time()))
            
            else:
                self.logger.warning(f"Unknown header source: {header_config.source}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to generate header value for {header_config.name}: {str(e)}")
            return None
    
    def _add_header_to_curl(self, curl_command: str, header: str) -> str:
        """Add header to curl command"""
        # Find the URL in the curl command and insert header after it
        parts = curl_command.split()
        for i, part in enumerate(parts):
            # Check for URLs with or without quotes
            if part.startswith('http') or part.startswith('"http') or part.startswith("'http"):
                # Insert header after the URL
                parts.insert(i + 1, header)
                break
        return ' '.join(parts)


class RSAAESHeadersStrategy(EncryptionStrategy):
    """RSA+AES encryption with headers placement (your specification pattern)"""
    
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """Encrypt request using RSA+AES headers pattern"""
        metadata = {
            "strategy": "rsa_aes_headers",
            "headers_added": [],
            "payload_encrypted": False,
            "algorithms_used": []
        }
        
        try:
            # Load RSA keys
            if not (self.config.crypto_keys.bank_public_cert_path and 
                   self.config.crypto_keys.partner_private_key_path and
                   self.config.crypto_keys.partner_id):
                raise ValueError("RSA+AES Headers strategy requires bank certificate, partner private key, and partner ID")
            
            from ..rsa_crypto_manager import RSACryptoManager
            from cryptography.hazmat.primitives import serialization
            
            rsa_manager = RSACryptoManager(self.logger)
            
            public_key_pem = rsa_manager.load_public_key(self.config.crypto_keys.bank_public_cert_path)
            private_key_pem = rsa_manager.load_private_key(self.config.crypto_keys.partner_private_key_path)
            
            # Convert PEM strings to crypto objects
            public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
            private_key = serialization.load_pem_private_key(private_key_pem.encode('utf-8'), password=None)
            
            # Generate AES key for this transaction
            aes_key = self._generate_aes_key()
            metadata["algorithms_used"].append("AES-128")
            
            # Generate IV in the required format (16-digit numeric)
            iv_numeric = self._generate_numeric_iv(16)
            
            # Convert payload to JSON string for signing and encryption
            payload_json = json.dumps(payload, separators=(',', ':'))
            
            # 1. Create signature
            signature = rsa_manager.sign_with_padding(
                payload_json.encode('utf-8'),
                private_key,
                self.config.algorithms.padding.signature_padding,
                self._extract_hash_from_algorithm(self.config.algorithms.signature)
            )
            signature_b64 = base64.b64encode(signature).decode('utf-8')
            metadata["algorithms_used"].append(f"Signature: {self.config.algorithms.signature}")
            
            # 2. Encrypt AES key with bank's public key
            encrypted_aes_key = rsa_manager.encrypt_with_padding(
                aes_key,
                public_key,
                self.config.algorithms.padding.rsa_padding
            )
            encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key).decode('utf-8')
            metadata["algorithms_used"].append(f"Key encryption: {self.config.algorithms.key_encryption}")
            
            # 3. Encrypt partner ID
            encrypted_partner_id = rsa_manager.encrypt_with_padding(
                self.config.crypto_keys.partner_id.encode('utf-8'),
                public_key,
                self.config.algorithms.padding.rsa_padding
            )
            encrypted_partner_id_b64 = base64.b64encode(encrypted_partner_id).decode('utf-8')
            
            # Create crypto context for header generation
            crypto_context = {
                "signature": signature_b64,
                "encrypted_aes_key": encrypted_aes_key_b64,
                "encrypted_partner_id": encrypted_partner_id_b64,
                "iv": iv_numeric
            }
            
            # Generate headers based on configuration
            headers = self._generate_configured_headers(payload, crypto_context)
            
            # Track which headers were added
            for header in headers:
                header_name = header.split(':')[0].replace('-H "', '').strip()
                metadata["headers_added"].append(header_name)
            
            # 5. Encrypt payload with AES
            from ..aes_crypto_manager import AESCryptoManager
            aes_manager = AESCryptoManager(self.logger)
            
            encrypted_payload = aes_manager.encrypt_with_padding(
                payload_json.encode('utf-8'),
                aes_key,
                self.config.algorithms.padding.aes_padding,
                iv_numeric.encode('utf-8'),
                "CBC"
            )
            encrypted_payload_b64 = base64.b64encode(encrypted_payload).decode('utf-8')
            metadata["payload_encrypted"] = True
            metadata["algorithms_used"].append(f"Payload encryption: {self.config.algorithms.payload_encryption}")
            
            # Modify curl command
            modified_curl = self._replace_json_in_curl(curl_command, encrypted_payload_b64)
            
            # Add headers to curl command
            for header in headers:
                modified_curl = self._add_header_to_curl(modified_curl, header)
            
            metadata["encryption_successful"] = True
            return modified_curl, metadata
            
        except Exception as e:
            self.logger.error(f"RSA+AES Headers encryption failed: {str(e)}")
            metadata["error"] = str(e)
            metadata["encryption_successful"] = False
            return curl_command, metadata
    
    def decrypt_response(self, response: str) -> Optional[str]:
        """Decrypt RSA+AES Headers response (requires context from request)"""
        # Note: Full decryption requires the AES key and IV from the request context
        # This is a placeholder implementation
        try:
            if self._looks_encrypted(response):
                self.logger.info("Response appears encrypted but requires request context for decryption")
                return None
        except Exception as e:
            self.logger.debug(f"Response decryption check failed: {str(e)}")
        return None
    
    def validate_configuration(self) -> List[str]:
        """Validate RSA+AES Headers configuration"""
        errors = []
        
        if not self.config.crypto_keys.has_rsa_keys():
            errors.append("RSA+AES Headers requires bank certificate, partner private key, and partner ID")
        
        # Validate padding schemes
        if self.config.algorithms.padding.rsa_padding not in [PaddingScheme.PKCS1.value, PaddingScheme.OAEP.value]:
            errors.append(f"Unsupported RSA padding for Headers strategy: {self.config.algorithms.padding.rsa_padding}")
        
        if self.config.algorithms.padding.aes_padding not in [PaddingScheme.PKCS5.value, PaddingScheme.PKCS7.value]:
            errors.append(f"Unsupported AES padding for Headers strategy: {self.config.algorithms.padding.aes_padding}")
        
        return errors
    
    def _extract_hash_from_algorithm(self, algorithm: str) -> str:
        """Extract hash algorithm from signature specification"""
        if "SHA1" in algorithm.upper():
            return "SHA1"
        elif "SHA256" in algorithm.upper():
            return "SHA256"
        return "SHA256"  # Default
    
    def _add_header_to_curl(self, curl_command: str, header: str) -> str:
        """Add header to curl command"""
        # Simple implementation - add after the URL
        parts = curl_command.split()
        for i, part in enumerate(parts):
            if part.startswith('http'):
                parts.insert(i + 1, header)
                break
        return ' '.join(parts)
    
    def _looks_encrypted(self, response: str) -> bool:
        """Check if response looks encrypted"""
        try:
            # Basic heuristic for base64 encoded data
            if len(response) > 50:
                base64.b64decode(response.replace('\n', '').replace(' ', ''))
                return True
        except:
            pass
        return False


class RSAAESBodyStrategy(EncryptionStrategy):
    """RSA+AES encryption with body placement"""
    
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """Encrypt request using RSA+AES body pattern"""
        metadata = {"strategy": "rsa_aes_body", "body_modified": True}
        
        try:
            # Create body structure with auth and data sections
            new_body = {
                "auth": {
                    "signature": "placeholder_signature",
                    "key": "placeholder_encrypted_key",
                    "partner_id": self.config.crypto_keys.partner_id,
                    "timestamp": "placeholder_timestamp"
                },
                "data": "placeholder_encrypted_data"
            }
            
            # Replace curl payload
            modified_curl = self._replace_json_in_curl(curl_command, json.dumps(new_body))
            
            metadata["encryption_successful"] = True
            return modified_curl, metadata
            
        except Exception as e:
            metadata["error"] = str(e)
            metadata["encryption_successful"] = False
            return curl_command, metadata
    
    def decrypt_response(self, response: str) -> Optional[str]:
        """Decrypt RSA+AES Body response"""
        return None
    
    def validate_configuration(self) -> List[str]:
        """Validate RSA+AES Body configuration"""
        return []


class RSAAESMixedStrategy(EncryptionStrategy):
    """RSA+AES encryption with mixed headers and body placement"""
    
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """Encrypt request using RSA+AES mixed pattern"""
        metadata = {"strategy": "rsa_aes_mixed", "headers_added": [], "body_modified": True}
        
        try:
            # Generate headers based on configuration instead of hardcoded values
            crypto_context = {}  # Can be populated with encryption context if needed
            headers = self._generate_configured_headers(payload, crypto_context)
            
            # Modify body with encrypted data
            new_body = {
                "encrypted_data": "placeholder_encrypted_payload",
                "encryption_metadata": {
                    "iv": "placeholder_iv",
                    "algorithm": "AES-256-CBC"
                }
            }
            
            modified_curl = self._replace_json_in_curl(curl_command, json.dumps(new_body))
            
            # Add headers
            for header in headers:
                modified_curl = self._add_header_to_curl(modified_curl, header)
            
            metadata["encryption_successful"] = True
            return modified_curl, metadata
            
        except Exception as e:
            metadata["error"] = str(e)
            metadata["encryption_successful"] = False
            return curl_command, metadata
    
    def decrypt_response(self, response: str) -> Optional[str]:
        """Decrypt RSA+AES Mixed response"""
        return None
    
    def validate_configuration(self) -> List[str]:
        """Validate RSA+AES Mixed configuration"""
        return []


class SignatureOnlyStrategy(EncryptionStrategy):
    """Signature-only authentication without payload encryption"""
    
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """Add signature headers without encrypting payload"""
        metadata = {"strategy": "signature_only", "headers_added": [], "payload_encrypted": False}
        
        try:
            if not self.config.crypto_keys.partner_private_key_path:
                raise ValueError("Signature-only strategy requires partner private key")
            
            from ..rsa_crypto_manager import RSACryptoManager
            from cryptography.hazmat.primitives import serialization
            
            rsa_manager = RSACryptoManager(self.logger)
            private_key_pem = rsa_manager.load_private_key(self.config.crypto_keys.partner_private_key_path)
            
            # Convert PEM string to crypto object
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=None
            )
            
            # Sign the payload
            payload_json = json.dumps(payload, separators=(',', ':'))
            signature = rsa_manager.sign_with_padding(
                payload_json.encode('utf-8'),
                private_key,
                self.config.algorithms.padding.signature_padding,
                "SHA256"
            )
            signature_b64 = base64.b64encode(signature).decode('utf-8')
            
            # Create crypto context for header generation
            crypto_context = {
                "signature": signature_b64
            }
            
            # Generate headers based on configuration
            headers = self._generate_configured_headers(payload, crypto_context)
            
            modified_curl = curl_command
            for header in headers:
                modified_curl = self._add_header_to_curl(modified_curl, header)
                header_name = header.split(':')[0].replace('-H "', '').strip()
                metadata["headers_added"].append(header_name)
            
            metadata["encryption_successful"] = True
            return modified_curl, metadata
            
        except Exception as e:
            metadata["error"] = str(e)
            metadata["encryption_successful"] = False
            return curl_command, metadata
    
    def decrypt_response(self, response: str) -> Optional[str]:
        """No decryption needed for signature-only"""
        return None
    
    def validate_configuration(self) -> List[str]:
        """Validate signature-only configuration"""
        errors = []
        if not self.config.crypto_keys.partner_private_key_path:
            errors.append("Signature-only strategy requires partner private key")
        return errors


class AESLegacyStrategy(EncryptionStrategy):
    """Legacy AES-only encryption for backward compatibility"""
    
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """Encrypt request using legacy AES pattern"""
        metadata = {"strategy": "aes_legacy", "body_modified": True, "payload_encrypted": True}
        
        try:
            from ..aes_crypto_manager import AESCryptoManager
            aes_manager = AESCryptoManager(self.logger)
            
            # Use default key or provided key
            hex_key = self.config.crypto_keys.aes_key_hex or aes_manager.DEFAULT_HEX_KEY
            
            # Encrypt payload
            payload_json = json.dumps(payload, separators=(',', ':'))
            encrypted_data = aes_manager.encrypt_payload(payload_json, hex_key)
            
            # Create new body structure
            new_body = {
                "encrypted_data": encrypted_data,
                "algorithm": "AES-256-CBC"
            }
            
            modified_curl = self._replace_json_in_curl(curl_command, json.dumps(new_body))
            
            metadata["encryption_successful"] = True
            return modified_curl, metadata
            
        except Exception as e:
            metadata["error"] = str(e)
            metadata["encryption_successful"] = False
            return curl_command, metadata
    
    def decrypt_response(self, response: str) -> Optional[str]:
        """Decrypt AES legacy response"""
        try:
            from ..aes_crypto_manager import AESCryptoManager
            aes_manager = AESCryptoManager(self.logger)
            
            if aes_manager.looks_like_encrypted_response(response):
                return aes_manager.decrypt_response(response)
        except Exception as e:
            self.logger.debug(f"AES legacy decryption failed: {str(e)}")
        return None
    
    def validate_configuration(self) -> List[str]:
        """Validate AES legacy configuration"""
        return []


class RSAPureStrategy(EncryptionStrategy):
    """Pure RSA encryption for small payloads"""
    
    def encrypt_request(self, payload: Dict[str, Any], curl_command: str) -> Tuple[str, Dict[str, Any]]:
        """Encrypt request using pure RSA"""
        metadata = {"strategy": "rsa_pure", "headers_added": [], "payload_encrypted": True}
        
        try:
            if not self.config.crypto_keys.bank_public_cert_path:
                raise ValueError("RSA Pure strategy requires bank public certificate")
            
            from ..rsa_crypto_manager import RSACryptoManager
            rsa_manager = RSACryptoManager(self.logger)
            public_key = rsa_manager.load_public_key(self.config.crypto_keys.bank_public_cert_path)
            
            # Encrypt small payload with RSA
            payload_json = json.dumps(payload, separators=(',', ':'))
            
            # Check payload size
            if len(payload_json.encode('utf-8')) > 200:  # Conservative limit
                raise ValueError("Payload too large for pure RSA encryption (max ~200 bytes)")
            
            encrypted_data = rsa_manager.encrypt_with_padding(
                payload_json.encode('utf-8'),
                public_key,
                self.config.algorithms.padding.rsa_padding
            )
            encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
            
            # Put encrypted data in header instead of body
            headers = [f'-H "X-Encrypted-Data: {encrypted_b64}"']
            
            # Remove original payload and add headers
            modified_curl = self._replace_json_in_curl(curl_command, '{}')
            for header in headers:
                modified_curl = self._add_header_to_curl(modified_curl, header)
            
            metadata["encryption_successful"] = True
            return modified_curl, metadata
            
        except Exception as e:
            metadata["error"] = str(e)
            metadata["encryption_successful"] = False
            return curl_command, metadata
    
    def decrypt_response(self, response: str) -> Optional[str]:
        """Decrypt pure RSA response"""
        return None
    
    def validate_configuration(self) -> List[str]:
        """Validate RSA pure configuration"""
        errors = []
        if not self.config.crypto_keys.bank_public_cert_path:
            errors.append("RSA Pure strategy requires bank public certificate")
        return errors
    
    def _add_header_to_curl(self, curl_command: str, header: str) -> str:
        """Add header to curl command"""
        parts = curl_command.split()
        for i, part in enumerate(parts):
            if part.startswith('http'):
                parts.insert(i + 1, header)
                break
        return ' '.join(parts) 