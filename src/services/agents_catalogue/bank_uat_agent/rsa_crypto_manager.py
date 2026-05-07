"""
RSA Crypto Manager for Bank UAT Agent

This module provides comprehensive RSA encryption/decryption capabilities
for bank API UAT testing with public/private key management.
"""

import os
import base64
import json
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

# Optional crypto imports - graceful fallback if cryptography not installed
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    CRYPTO_AVAILABLE = True
except ImportError:
    # Fallback when cryptography is not installed
    CRYPTO_AVAILABLE = False

from src.providers.logger import Logger
from .config.encryption_config import PaddingScheme


class RSACryptoManager:
    """
    RSA Encryption manager for bank API UAT testing
    
    Features:
    - RSA key pair generation and loading
    - RSA encryption with public key
    - RSA decryption with private key  
    - Hybrid encryption (RSA + AES for large payloads)
    - Key validation and format conversion
    """
    
    def __init__(self, logger: Optional[Logger] = None):
        """Initialize RSA crypto manager with optional logger"""
        self.logger = logger or Logger()
        
        # Initialize padding manager for enhanced padding support
        try:
            from .crypto.padding_manager import PaddingManager
            self.padding_manager = PaddingManager(logger)
        except ImportError:
            self.padding_manager = None
            self.logger.debug("Padding manager not available - using basic padding")
        
        if not CRYPTO_AVAILABLE:
            self.logger.warning("RSA encryption not available. Please install cryptography: pip install cryptography")
    
    def check_availability(self) -> bool:
        """Check if RSA encryption is available"""
        return CRYPTO_AVAILABLE
    
    def generate_rsa_keypair(self, key_size: int = 2048) -> Tuple[str, str]:
        """
        Generate RSA key pair
        
        Args:
            key_size: RSA key size in bits (default: 2048)
            
        Returns:
            Tuple of (public_key_pem, private_key_pem)
            
        Raises:
            Exception: If key generation fails or crypto not available
        """
        if not CRYPTO_AVAILABLE:
            raise Exception("RSA key generation not available. Please install cryptography: pip install cryptography")
        
        try:
            self.logger.info(f"Generating RSA key pair with {key_size} bits")
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
            )
            
            # Get public key
            public_key = private_key.public_key()
            
            # Serialize to PEM format
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            
            self.logger.info("RSA key pair generated successfully")
            return public_pem, private_pem
            
        except Exception as e:
            self.logger.error(f"RSA key generation failed: {str(e)}")
            raise Exception(f"RSA key generation failed: {str(e)}")
    
    def load_public_key(self, key_path: str) -> str:
        """
        Load public key from file - supports both X.509 certificates and pure public keys
        
        Args:
            key_path: Path to public key or certificate file
            
        Returns:
            Public key in PEM format as string
            
        Raises:
            Exception: If key loading fails
        """
        try:
            self.logger.info(f"🔑 Loading public key from: {key_path}")
            
            # Check file existence and size
            if not os.path.exists(key_path):
                raise FileNotFoundError(f"Public key file not found: {key_path}")
                
            file_size = os.path.getsize(key_path)
            self.logger.info(f"  File size: {file_size} bytes")
            
            with open(key_path, 'r') as f:
                key_content = f.read()
            
            # Log key content details (first few lines for security)
            key_lines = key_content.strip().split('\n')
            self.logger.info(f"  Key has {len(key_lines)} lines")
            if key_lines:
                self.logger.info(f"  First line: {key_lines[0]}")
                if len(key_lines) > 1:
                    self.logger.info(f"  Last line: {key_lines[-1]}")
            
            # Handle X.509 certificate - extract public key
            if "BEGIN CERTIFICATE" in key_content:
                if not CRYPTO_AVAILABLE:
                    raise Exception("Certificate processing requires cryptography library")
                
                self.logger.info(f"  Detected X.509 certificate format")
                
                try:
                    from cryptography import x509
                    from cryptography.hazmat.primitives import serialization
                    
                    # Load certificate
                    cert = x509.load_pem_x509_certificate(
                        key_content.encode('utf-8'),
                    )
                    
                    # Extract public key from certificate
                    public_key = cert.public_key()
                    
                    # Convert to PEM format
                    public_key_pem = public_key.public_key_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    ).decode('utf-8')
                    
                    self.logger.info(f"  Successfully extracted public key from certificate")
                    self.logger.info(f"  Public key size: {public_key.key_size} bits")
                    
                    # Return the extracted public key in PEM format
                    key_content = public_key_pem
                    
                except Exception as cert_error:
                    raise Exception(f"Failed to extract public key from certificate: {str(cert_error)}")
            
            # Validate final key format
            if not self._is_valid_public_key(key_content):
                raise Exception("Invalid public key format after processing")
            
            self.logger.info(f"✅ Successfully loaded and validated public key from {key_path}")
            return key_content
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load public key from {key_path}: {str(e)}")
            raise Exception(f"Failed to load public key: {str(e)}")
    
    def load_private_key(self, key_path: str, password: Optional[str] = None) -> str:
        """
        Load private key from file
        
        Args:
            key_path: Path to private key file
            password: Optional password for encrypted private key
            
        Returns:
            Private key in PEM format as string
            
        Raises:
            Exception: If key loading fails
        """
        try:
            self.logger.info(f"🔐 Loading private key from: {key_path}")
            
            # Check file existence and size
            if not os.path.exists(key_path):
                raise FileNotFoundError(f"Private key file not found: {key_path}")
                
            file_size = os.path.getsize(key_path)
            self.logger.info(f"  File size: {file_size} bytes")
            
            with open(key_path, 'r') as f:
                key_content = f.read()
            
            # Log key content details (first few lines for security)
            key_lines = key_content.strip().split('\n')
            self.logger.info(f"  Key has {len(key_lines)} lines")
            if key_lines:
                self.logger.info(f"  First line: {key_lines[0]}")
                if len(key_lines) > 1:
                    self.logger.info(f"  Last line: {key_lines[-1]}")
            
            # Validate key format
            if not self._is_valid_private_key(key_content):
                raise Exception("Invalid private key format")
            
            # Test key loading with cryptography
            if CRYPTO_AVAILABLE:
                try:
                    password_bytes = password.encode('utf-8') if password else None
                    serialization.load_pem_private_key(
                        key_content.encode('utf-8'),
                        password=password_bytes,
                    )
                    self.logger.info("  ✅ Private key cryptographic validation passed")
                except Exception as e:
                    raise Exception(f"Private key validation failed: {str(e)}")
            
            self.logger.info(f"✅ Successfully loaded and validated private key from {key_path}")
            return key_content
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load private key from {key_path}: {str(e)}")
            raise Exception(f"Failed to load private key: {str(e)}")
    
    def encrypt_with_public_key(self, data: str, public_key_pem: str) -> str:
        """
        Encrypt data with RSA public key
        
        Args:
            data: Data to encrypt
            public_key_pem: Public key in PEM format
            
        Returns:
            Base64 encoded encrypted data
            
        Raises:
            Exception: If encryption fails
        """
        if not CRYPTO_AVAILABLE:
            raise Exception("RSA encryption not available. Please install cryptography: pip install cryptography")
        
        try:
            self.logger.info(f"🔐 Starting RSA encryption operation")
            self.logger.info(f"  Data length: {len(data)} characters")
            
            # Analyze the public key being used
            key_lines = public_key_pem.strip().split('\n')
            self.logger.info(f"  Using public key with {len(key_lines)} lines")
            if key_lines:
                self.logger.info(f"  Key header: {key_lines[0]}")
                if len(key_lines) > 1:
                    self.logger.info(f"  Key footer: {key_lines[-1]}")
            
            # Load public key
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
            )
            
            # Log key details
            key_size = public_key.key_size
            max_size = (key_size // 8) - 66  # OAEP padding overhead
            self.logger.info(f"  RSA key size: {key_size} bits")
            self.logger.info(f"  Max data size for RSA: {max_size} bytes")
            
            # Check data size for RSA limitations
            data_bytes_len = len(data.encode('utf-8'))
            self.logger.info(f"  Data size: {data_bytes_len} bytes")
            
            if data_bytes_len > max_size:
                # Use hybrid encryption for large data
                self.logger.info("  📦 Data too large for RSA, using hybrid encryption (RSA + AES)")
                return self._hybrid_encrypt(data, public_key_pem)
            else:
                self.logger.info("  🔐 Using pure RSA encryption")
            
            # Encrypt with RSA-OAEP
            encrypted = public_key.encrypt(
                data.encode('utf-8'),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Return base64 encoded
            encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')
            
            self.logger.info(f"✅ RSA encryption successful: {len(data)} chars -> {len(encrypted_b64)} chars (base64)")
            return encrypted_b64
            
        except Exception as e:
            self.logger.error(f"❌ RSA encryption failed: {str(e)}")
            raise Exception(f"RSA encryption failed: {str(e)}")
    
    def decrypt_with_private_key(self, encrypted_data: str, private_key_pem: str, password: Optional[str] = None) -> str:
        """
        Decrypt data with RSA private key
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            private_key_pem: Private key in PEM format
            password: Optional password for encrypted private key
            
        Returns:
            Decrypted data as string
            
        Raises:
            Exception: If decryption fails
        """
        if not CRYPTO_AVAILABLE:
            raise Exception("RSA decryption not available. Please install cryptography: pip install cryptography")
        
        try:
            self.logger.info(f"🔓 Starting RSA decryption operation")
            self.logger.info(f"  Encrypted data length: {len(encrypted_data)} characters (base64)")
            
            # Analyze the private key being used
            key_lines = private_key_pem.strip().split('\n')
            self.logger.info(f"  Using private key with {len(key_lines)} lines")
            if key_lines:
                self.logger.info(f"  Key header: {key_lines[0]}")
                if len(key_lines) > 1:
                    self.logger.info(f"  Key footer: {key_lines[-1]}")
            
            # Load private key
            password_bytes = password.encode('utf-8') if password else None
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=password_bytes,
            )
            
            # Log key details
            key_size = private_key.key_size
            self.logger.info(f"  RSA key size: {key_size} bits")
            
            # Check if this might be hybrid encrypted data
            if self._is_hybrid_encrypted(encrypted_data):
                self.logger.info("  📦 Detected hybrid encryption, using hybrid decryption (RSA + AES)")
                return self._hybrid_decrypt(encrypted_data, private_key_pem, password)
            else:
                self.logger.info("  🔓 Using pure RSA decryption")
            
            # Decode base64
            encrypted_bytes = base64.b64decode(encrypted_data)
            self.logger.info(f"  Decoded base64: {len(encrypted_bytes)} bytes")
            
            # Decrypt with RSA-OAEP
            decrypted = private_key.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            decrypted_str = decrypted.decode('utf-8')
            
            self.logger.info(f"✅ RSA decryption successful: {len(encrypted_data)} chars (base64) -> {len(decrypted_str)} chars")
            return decrypted_str
            
        except Exception as e:
            self.logger.error(f"❌ RSA decryption failed: {str(e)}")
            self.logger.error(f"  This could be due to:")
            self.logger.error(f"    - Wrong private key (doesn't match the public key used for encryption)")
            self.logger.error(f"    - Corrupted encrypted data")
            self.logger.error(f"    - Invalid key format")
            self.logger.error(f"    - Encrypted data was not encrypted with RSA")
            raise Exception(f"RSA decryption failed: {str(e)}")
    
    def _hybrid_encrypt(self, data: str, public_key_pem: str) -> str:
        """
        Hybrid encryption: RSA for AES key + AES for data
        
        Args:
            data: Data to encrypt
            public_key_pem: Public key in PEM format
            
        Returns:
            Base64 encoded hybrid encrypted data (RSA encrypted AES key + AES encrypted data)
        """
        try:
            # Generate random AES key
            aes_key = os.urandom(32)  # 256-bit AES key
            iv = os.urandom(16)  # 128-bit IV
            
            # Encrypt data with AES
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), )
            encryptor = cipher.encryptor()
            
            # Pad data to multiple of 16 bytes
            padded_data = self._pkcs7_pad(data.encode('utf-8'), 16)
            aes_encrypted = encryptor.update(padded_data) + encryptor.finalize()
            
            # Encrypt AES key with RSA
            aes_key_encrypted = self.encrypt_with_public_key(base64.b64encode(aes_key).decode('utf-8'), public_key_pem)
            
            # Combine: encrypted_aes_key:iv:encrypted_data
            hybrid_data = {
                "type": "hybrid_rsa_aes",
                "encrypted_key": aes_key_encrypted,
                "iv": base64.b64encode(iv).decode('utf-8'),
                "encrypted_data": base64.b64encode(aes_encrypted).decode('utf-8')
            }
            
            # Return as base64 encoded JSON
            hybrid_json = json.dumps(hybrid_data)
            return base64.b64encode(hybrid_json.encode('utf-8')).decode('utf-8')
            
        except Exception as e:
            raise Exception(f"Hybrid encryption failed: {str(e)}")
    
    def _hybrid_decrypt(self, encrypted_data: str, private_key_pem: str, password: Optional[str] = None) -> str:
        """
        Hybrid decryption: RSA for AES key + AES for data
        
        Args:
            encrypted_data: Base64 encoded hybrid encrypted data
            private_key_pem: Private key in PEM format
            password: Optional password for encrypted private key
            
        Returns:
            Decrypted data as string
        """
        try:
            # Decode and parse hybrid data
            hybrid_json = base64.b64decode(encrypted_data).decode('utf-8')
            hybrid_data = json.loads(hybrid_json)
            
            if hybrid_data.get("type") != "hybrid_rsa_aes":
                raise Exception("Invalid hybrid encryption format")
            
            # Decrypt AES key with RSA
            encrypted_aes_key = hybrid_data["encrypted_key"]
            aes_key_b64 = self.decrypt_with_private_key(encrypted_aes_key, private_key_pem, password)
            aes_key = base64.b64decode(aes_key_b64)
            
            # Extract IV and encrypted data
            iv = base64.b64decode(hybrid_data["iv"])
            aes_encrypted = base64.b64decode(hybrid_data["encrypted_data"])
            
            # Decrypt data with AES
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), )
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(aes_encrypted) + decryptor.finalize()
            
            # Remove padding
            data = self._pkcs7_unpad(padded_data, 16)
            
            return data.decode('utf-8')
            
        except Exception as e:
            raise Exception(f"Hybrid decryption failed: {str(e)}")
    
    def _is_hybrid_encrypted(self, data: str) -> bool:
        """Check if data is hybrid encrypted"""
        try:
            hybrid_json = base64.b64decode(data).decode('utf-8')
            hybrid_data = json.loads(hybrid_json)
            return hybrid_data.get("type") == "hybrid_rsa_aes"
        except:
            return False
    
    def _pkcs7_pad(self, data: bytes, block_size: int) -> bytes:
        """PKCS7 padding"""
        padding_length = block_size - (len(data) % block_size)
        padding = bytes([padding_length]) * padding_length
        return data + padding
    
    def _pkcs7_unpad(self, data: bytes, block_size: int) -> bytes:
        """PKCS7 unpadding"""
        padding_length = data[-1]
        return data[:-padding_length]
    
    def _is_valid_public_key(self, key_content: str) -> bool:
        """Validate public key format - supports both X.509 certificates and pure public keys"""
        if not CRYPTO_AVAILABLE:
            # Basic format check for various formats
            return (("BEGIN PUBLIC KEY" in key_content and "END PUBLIC KEY" in key_content) or
                   ("BEGIN CERTIFICATE" in key_content and "END CERTIFICATE" in key_content) or
                   ("BEGIN RSA PUBLIC KEY" in key_content and "END RSA PUBLIC KEY" in key_content))
        
        try:
            # First try to load as X.509 certificate
            if "BEGIN CERTIFICATE" in key_content:
                from cryptography import x509
                cert = x509.load_pem_x509_certificate(
                    key_content.encode('utf-8'),
                )
                # Extract public key from certificate to validate it
                public_key = cert.public_key()
                return True
            else:
                # Try to load as pure public key
                serialization.load_pem_public_key(
                    key_content.encode('utf-8'),
                )
                return True
        except Exception as e:
            # Log the specific error for debugging
            self.logger.debug(f"Public key validation failed: {str(e)}")
            return False
    
    def _is_valid_private_key(self, key_content: str) -> bool:
        """Validate private key format"""
        if not CRYPTO_AVAILABLE:
            # Basic format check
            return ("BEGIN PRIVATE KEY" in key_content or "BEGIN RSA PRIVATE KEY" in key_content) and \
                   ("END PRIVATE KEY" in key_content or "END RSA PRIVATE KEY" in key_content)
        
        try:
            serialization.load_pem_private_key(
                key_content.encode('utf-8'),
                password=None,
            )
            return True
        except:
            return False
    
    def validate_rsa_keys(self, public_key_pem: str, private_key_pem: str) -> bool:
        """
        Validate that public and private keys are a matching pair
        
        Args:
            public_key_pem: Public key in PEM format
            private_key_pem: Private key in PEM format
            
        Returns:
            True if keys are a matching pair, False otherwise
        """
        if not CRYPTO_AVAILABLE:
            # Basic format validation only
            return self._is_valid_public_key(public_key_pem) and self._is_valid_private_key(private_key_pem)
        
        try:
            # Test encryption/decryption round trip
            test_data = "RSA key validation test"
            encrypted = self.encrypt_with_public_key(test_data, public_key_pem)
            decrypted = self.decrypt_with_private_key(encrypted, private_key_pem)
            
            return test_data == decrypted
            
        except Exception as e:
            self.logger.warning(f"RSA key validation failed: {str(e)}")
            return False
    
    
    # Enhanced methods with padding support
    def encrypt_with_padding(self, data: bytes, public_key: Any, padding_scheme: str = PaddingScheme.PKCS1.value) -> bytes:
        """
        Encrypt data with specified padding scheme
        
        Args:
            data: Data to encrypt
            public_key: RSA public key object
            padding_scheme: Padding scheme (PKCS1, OAEP, OAEP_SHA256)
            
        Returns:
            Encrypted data as bytes
        """
        if self.padding_manager:
            return self.padding_manager.encrypt_with_padding(data, public_key, "RSA", padding_scheme)
        else:
            # Fallback to basic PKCS1 padding
            return self.encrypt_with_public_key(base64.b64encode(data).decode('utf-8'), public_key)
    
    def decrypt_with_padding(self, encrypted_data: bytes, private_key: Any, padding_scheme: str = PaddingScheme.PKCS1.value) -> bytes:
        """
        Decrypt data with specified padding scheme
        
        Args:
            encrypted_data: Encrypted data to decrypt
            private_key: RSA private key object
            padding_scheme: Padding scheme (PKCS1, OAEP, OAEP_SHA256)
            
        Returns:
            Decrypted data as bytes
        """
        if self.padding_manager:
            return self.padding_manager.decrypt_with_padding(encrypted_data, private_key, "RSA", padding_scheme)
        else:
            # Fallback to basic PKCS1 padding
            decrypted_b64 = self.decrypt_with_private_key(base64.b64encode(encrypted_data).decode('utf-8'), private_key)
            return base64.b64decode(decrypted_b64) if decrypted_b64 else b''
    
    def sign_with_padding(self, data: bytes, private_key: Any, padding_scheme: str = PaddingScheme.PKCS1.value, hash_algorithm: str = "SHA256") -> bytes:
        """
        Sign data with specified padding scheme
        
        Args:
            data: Data to sign
            private_key: RSA private key object
            padding_scheme: Padding scheme (PKCS1, PSS)
            hash_algorithm: Hash algorithm (SHA1, SHA256)
            
        Returns:
            Signature as bytes
        """
        if self.padding_manager:
            return self.padding_manager.sign_with_padding(data, private_key, padding_scheme, hash_algorithm)
        else:
            # Fallback - not implemented in basic manager
            self.logger.warning("Signing not available without padding manager")
            return b''
    
    def verify_with_padding(self, signature: bytes, data: bytes, public_key: Any, padding_scheme: str = PaddingScheme.PKCS1.value, hash_algorithm: str = "SHA256") -> bool:
        """
        Verify signature with specified padding scheme
        
        Args:
            signature: Signature to verify
            data: Original data that was signed
            public_key: RSA public key object
            padding_scheme: Padding scheme (PKCS1, PSS)
            hash_algorithm: Hash algorithm (SHA1, SHA256)
            
        Returns:
            True if signature is valid, False otherwise
        """
        if self.padding_manager:
            return self.padding_manager.verify_with_padding(signature, data, public_key, padding_scheme, hash_algorithm)
        else:
            # Fallback - not implemented in basic manager
            self.logger.warning("Signature verification not available without padding manager")
            return False
