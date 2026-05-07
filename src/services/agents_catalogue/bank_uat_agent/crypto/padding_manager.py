"""
Universal Padding Manager for Bank UAT Agent

Handles all padding schemes across different cryptographic algorithms and libraries.
Provides consistent interface for PKCS1, OAEP, PKCS5/7, and custom padding schemes.
"""

import os
import secrets
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, Union
from enum import Enum

# Cryptography library imports with graceful fallback
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding as rsa_padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_padding
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from src.providers.logger import Logger
from ..config.encryption_config import PaddingScheme


class PaddingValidationError(Exception):
    """Exception raised when padding validation fails"""
    pass


class PaddingCompatibilityInfo:
    """Information about padding scheme compatibility and limitations"""
    
    def __init__(self, scheme: str, algorithm: str, key_size: Optional[int] = None):
        self.scheme = scheme
        self.algorithm = algorithm
        self.key_size = key_size
        self.errors = []
        self.warnings = []
        self.max_data_size = None
        self.is_compatible = True
        
    def add_error(self, message: str):
        """Add compatibility error"""
        self.errors.append(message)
        self.is_compatible = False
        
    def add_warning(self, message: str):
        """Add compatibility warning"""
        self.warnings.append(message)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "scheme": self.scheme,
            "algorithm": self.algorithm,
            "key_size": self.key_size,
            "is_compatible": self.is_compatible,
            "max_data_size": self.max_data_size,
            "errors": self.errors,
            "warnings": self.warnings
        }


class PaddingHandler(ABC):
    """Abstract base class for padding handlers"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
    
    @abstractmethod
    def encrypt(self, data: bytes, key: Any, **kwargs) -> bytes:
        """Encrypt data with specific padding"""
        pass
    
    @abstractmethod
    def decrypt(self, data: bytes, key: Any, **kwargs) -> bytes:
        """Decrypt data with specific padding"""
        pass
    
    @abstractmethod
    def validate_compatibility(self, key_size: Optional[int] = None) -> PaddingCompatibilityInfo:
        """Validate padding compatibility"""
        pass


class RSAPaddingHandler(PaddingHandler):
    """Handler for RSA padding schemes"""
    
    def __init__(self, padding_scheme: str, logger: Optional[Logger] = None):
        super().__init__(logger)
        self.padding_scheme = padding_scheme
        self._validate_scheme()
    
    def _validate_scheme(self):
        """Validate RSA padding scheme"""
        valid_schemes = [PaddingScheme.PKCS1.value, PaddingScheme.OAEP.value, PaddingScheme.OAEP_SHA256.value, PaddingScheme.PSS.value]
        if self.padding_scheme not in valid_schemes:
            raise ValueError(f"Invalid RSA padding scheme: {self.padding_scheme}. Valid schemes: {valid_schemes}")
    
    def _get_padding_object(self) -> Any:
        """Get cryptography padding object"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available")
        
        if self.padding_scheme == PaddingScheme.PKCS1.value:
            return rsa_padding.PKCS1v15()
        elif self.padding_scheme == PaddingScheme.OAEP.value:
            return rsa_padding.OAEP(
                mgf=rsa_padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None
            )
        elif self.padding_scheme == PaddingScheme.OAEP_SHA256.value:
            return rsa_padding.OAEP(
                mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        elif self.padding_scheme == PaddingScheme.PSS.value:
            return rsa_padding.PSS(
                mgf=rsa_padding.MGF1(hashes.SHA256()),
                salt_length=rsa_padding.PSS.MAX_LENGTH
            )
        else:
            raise ValueError(f"Unsupported RSA padding scheme: {self.padding_scheme}")
    
    def encrypt(self, data: bytes, key: Any, **kwargs) -> bytes:
        """Encrypt data with RSA padding"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available for RSA encryption")
        
        try:
            padding_obj = self._get_padding_object()
            
            # For PSS, we need to sign instead of encrypt
            if self.padding_scheme == PaddingScheme.PSS.value:
                # PSS is for signatures, not encryption
                raise ValueError("PSS padding is for signatures, not encryption. Use PKCS1 or OAEP for encryption.")
            
            return key.encrypt(data, padding_obj)
            
        except Exception as e:
            self.logger.error(f"RSA encryption failed with {self.padding_scheme} padding: {str(e)}")
            raise PaddingValidationError(f"RSA encryption failed: {str(e)}")
    
    def decrypt(self, data: bytes, key: Any, **kwargs) -> bytes:
        """Decrypt data with RSA padding"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available for RSA decryption")
        
        try:
            padding_obj = self._get_padding_object()
            
            # For PSS, we need to verify instead of decrypt
            if self.padding_scheme == PaddingScheme.PSS.value:
                raise ValueError("PSS padding is for signatures, not decryption. Use PKCS1 or OAEP for decryption.")
            
            return key.decrypt(data, padding_obj)
            
        except Exception as e:
            self.logger.error(f"RSA decryption failed with {self.padding_scheme} padding: {str(e)}")
            raise PaddingValidationError(f"RSA decryption failed: {str(e)}")
    
    def sign(self, data: bytes, private_key: Any, hash_algorithm: str = "SHA256") -> bytes:
        """Sign data with RSA padding (for PSS and PKCS1 signatures)"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available for RSA signing")
        
        try:
            # Select hash algorithm
            if hash_algorithm.upper() == "SHA1":
                hash_alg = hashes.SHA1()
            elif hash_algorithm.upper() == "SHA256":
                hash_alg = hashes.SHA256()
            else:
                hash_alg = hashes.SHA256()  # Default
            
            if self.padding_scheme == PaddingScheme.PSS.value:
                padding_obj = rsa_padding.PSS(
                    mgf=rsa_padding.MGF1(hash_alg),
                    salt_length=rsa_padding.PSS.MAX_LENGTH
                )
            else:  # PKCS1 for signatures
                padding_obj = rsa_padding.PKCS1v15()
            
            return private_key.sign(data, padding_obj, hash_alg)
            
        except Exception as e:
            self.logger.error(f"RSA signing failed with {self.padding_scheme} padding: {str(e)}")
            raise PaddingValidationError(f"RSA signing failed: {str(e)}")
    
    def verify(self, signature: bytes, data: bytes, public_key: Any, hash_algorithm: str = "SHA256") -> bool:
        """Verify RSA signature"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available for RSA verification")
        
        try:
            # Select hash algorithm
            if hash_algorithm.upper() == "SHA1":
                hash_alg = hashes.SHA1()
            elif hash_algorithm.upper() == "SHA256":
                hash_alg = hashes.SHA256()
            else:
                hash_alg = hashes.SHA256()  # Default
            
            if self.padding_scheme == PaddingScheme.PSS.value:
                padding_obj = rsa_padding.PSS(
                    mgf=rsa_padding.MGF1(hash_alg),
                    salt_length=rsa_padding.PSS.MAX_LENGTH
                )
            else:  # PKCS1 for signatures
                padding_obj = rsa_padding.PKCS1v15()
            
            public_key.verify(signature, data, padding_obj, hash_alg)
            return True
            
        except Exception as e:
            self.logger.debug(f"RSA signature verification failed: {str(e)}")
            return False
    
    def get_rsa_padding(self, padding_scheme: str) -> Any:
        """Get RSA padding object for encryption/decryption operations"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available")
        
        padding_scheme = padding_scheme.upper()
        
        if padding_scheme == "PKCS1":
            return rsa_padding.PKCS1v15()
        elif padding_scheme == "OAEP":
            return rsa_padding.OAEP(
                mgf=rsa_padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None
            )
        elif padding_scheme == "OAEP_SHA256":
            return rsa_padding.OAEP(
                mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        else:
            # Default to PKCS1 for compatibility
            self.logger.warning(f"Unknown RSA padding scheme: {padding_scheme}, defaulting to PKCS1")
            return rsa_padding.PKCS1v15()
    
    def get_signature_padding(self, padding_scheme: str) -> Any:
        """Get RSA padding object for signature operations"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available")
        
        padding_scheme = padding_scheme.upper()
        
        if padding_scheme == "PSS":
            return rsa_padding.PSS(
                mgf=rsa_padding.MGF1(hashes.SHA256()),
                salt_length=rsa_padding.PSS.MAX_LENGTH
            )
        elif padding_scheme in ["PKCS1", "PKCS1V15"]:
            return rsa_padding.PKCS1v15()
        else:
            # Default to PKCS1 for compatibility
            self.logger.warning(f"Unknown signature padding scheme: {padding_scheme}, defaulting to PKCS1")
            return rsa_padding.PKCS1v15()
    
    def get_hash_algorithm(self, algorithm_name: str) -> Any:
        """Get hash algorithm object for signature operations"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available")
        
        algorithm_name = algorithm_name.upper()
        
        if algorithm_name == "SHA1":
            return hashes.SHA1()
        elif algorithm_name == "SHA256":
            return hashes.SHA256()
        elif algorithm_name == "SHA384":
            return hashes.SHA384()
        elif algorithm_name == "SHA512":
            return hashes.SHA512()
        else:
            # Default to SHA256 for compatibility
            self.logger.warning(f"Unknown hash algorithm: {algorithm_name}, defaulting to SHA256")
            return hashes.SHA256()
    
    def validate_compatibility(self, key_size: Optional[int] = None) -> PaddingCompatibilityInfo:
        """Validate RSA padding compatibility"""
        info = PaddingCompatibilityInfo(self.padding_scheme, "RSA", key_size)
        
        if key_size:
            # Calculate max data size based on padding scheme
            if self.padding_scheme == PaddingScheme.PKCS1.value:
                info.max_data_size = (key_size // 8) - 11
                if key_size < 2048:
                    info.add_warning("RSA key size < 2048 bits is deprecated for security")
            elif self.padding_scheme in [PaddingScheme.OAEP.value, PaddingScheme.OAEP_SHA256.value]:
                if self.padding_scheme == PaddingScheme.OAEP.value:
                    info.max_data_size = (key_size // 8) - 42  # SHA-1 + overhead
                else:
                    info.max_data_size = (key_size // 8) - 66  # SHA-256 + overhead
                
                if key_size < 2048:
                    info.add_error("OAEP padding requires minimum 2048-bit RSA keys")
            elif self.padding_scheme == PaddingScheme.PSS.value:
                info.max_data_size = None  # PSS is for signatures, not encryption
                if key_size < 2048:
                    info.add_warning("PSS with key size < 2048 bits is not recommended")
        
        return info


class AESPaddingHandler(PaddingHandler):
    """Handler for AES padding schemes"""
    
    def __init__(self, padding_scheme: str, logger: Optional[Logger] = None):
        super().__init__(logger)
        self.padding_scheme = padding_scheme
        self._validate_scheme()
    
    def _validate_scheme(self):
        """Validate AES padding scheme"""
        valid_schemes = [PaddingScheme.PKCS5.value, PaddingScheme.PKCS7.value, PaddingScheme.ZERO.value, PaddingScheme.NONE.value]
        if self.padding_scheme not in valid_schemes:
            raise ValueError(f"Invalid AES padding scheme: {self.padding_scheme}. Valid schemes: {valid_schemes}")
    
    def _get_padding_object(self) -> Any:
        """Get cryptography padding object"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available")
        
        if self.padding_scheme in [PaddingScheme.PKCS5.value, PaddingScheme.PKCS7.value]:
            # PKCS5 and PKCS7 are the same for AES (128-bit blocks)
            return sym_padding.PKCS7(128)
        elif self.padding_scheme == PaddingScheme.NONE.value:
            # No padding - used with GCM mode
            return None
        elif self.padding_scheme == PaddingScheme.ZERO.value:
            # Custom zero padding - not provided by cryptography library
            return "custom_zero"
        else:
            raise ValueError(f"Unsupported AES padding scheme: {self.padding_scheme}")
    
    def _apply_zero_padding(self, data: bytes, block_size: int = 16) -> bytes:
        """Apply custom zero padding"""
        padding_length = block_size - (len(data) % block_size)
        if padding_length == block_size:
            padding_length = 0
        return data + b'\x00' * padding_length
    
    def _remove_zero_padding(self, data: bytes) -> bytes:
        """Remove custom zero padding"""
        return data.rstrip(b'\x00')
    
    def encrypt(self, data: bytes, key: bytes, iv: bytes = None, mode: str = "CBC", **kwargs) -> bytes:
        """Encrypt data with AES padding"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available for AES encryption")
        
        try:
            # Generate IV if not provided
            if iv is None:
                iv = os.urandom(16)
            
            # Handle different modes
            if mode.upper() == "GCM":
                if self.padding_scheme != PaddingScheme.NONE.value:
                    self.logger.warning("GCM mode doesn't use padding, ignoring padding scheme")
                
                cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
                encryptor = cipher.encryptor()
                ciphertext = encryptor.update(data) + encryptor.finalize()
                # For GCM, we need to return IV + ciphertext + tag
                return iv + ciphertext + encryptor.tag
            
            elif mode.upper() == "CBC":
                # Apply padding based on scheme
                if self.padding_scheme == PaddingScheme.ZERO.value:
                    padded_data = self._apply_zero_padding(data)
                elif self.padding_scheme in [PaddingScheme.PKCS5.value, PaddingScheme.PKCS7.value]:
                    padding_obj = self._get_padding_object()
                    padder = padding_obj.padder()
                    padded_data = padder.update(data) + padder.finalize()
                elif self.padding_scheme == PaddingScheme.NONE.value:
                    # No padding - data must be block-aligned
                    if len(data) % 16 != 0:
                        raise ValueError("Data must be block-aligned when using no padding")
                    padded_data = data
                else:
                    raise ValueError(f"Unsupported padding scheme: {self.padding_scheme}")

                # nosemgrep: python.cryptography.security.mode-without-authentication.crypto-mode-without-authentication
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                encryptor = cipher.encryptor()
                return encryptor.update(padded_data) + encryptor.finalize()
            
            else:
                raise ValueError(f"Unsupported AES mode: {mode}")
            
        except Exception as e:
            self.logger.error(f"AES encryption failed with {self.padding_scheme} padding: {str(e)}")
            raise PaddingValidationError(f"AES encryption failed: {str(e)}")
    
    def decrypt(self, data: bytes, key: bytes, iv: bytes = None, mode: str = "CBC", **kwargs) -> bytes:
        """Decrypt data with AES padding"""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library not available for AES decryption")
        
        try:
            if mode.upper() == "GCM":
                if self.padding_scheme != PaddingScheme.NONE.value:
                    self.logger.warning("GCM mode doesn't use padding, ignoring padding scheme")
                
                # For GCM: data = IV (12 bytes) + ciphertext + tag (16 bytes)
                if iv is None:
                    iv = data[:12]
                    ciphertext_and_tag = data[12:]
                else:
                    ciphertext_and_tag = data
                
                tag = ciphertext_and_tag[-16:]
                ciphertext = ciphertext_and_tag[:-16]
                
                cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
                decryptor = cipher.decryptor()
                return decryptor.update(ciphertext) + decryptor.finalize()
            
            elif mode.upper() == "CBC":
                if iv is None:
                    # Extract IV from beginning of data
                    iv = data[:16]
                    ciphertext = data[16:]
                else:
                    ciphertext = data

                # nosemgrep: python.cryptography.security.mode-without-authentication.crypto-mode-without-authentication
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                decryptor = cipher.decryptor()
                decrypted_padded = decryptor.update(ciphertext) + decryptor.finalize()
                
                # Remove padding based on scheme
                if self.padding_scheme == PaddingScheme.ZERO.value:
                    return self._remove_zero_padding(decrypted_padded)
                elif self.padding_scheme in [PaddingScheme.PKCS5.value, PaddingScheme.PKCS7.value]:
                    padding_obj = self._get_padding_object()
                    unpadder = padding_obj.unpadder()
                    return unpadder.update(decrypted_padded) + unpadder.finalize()
                elif self.padding_scheme == PaddingScheme.NONE.value:
                    return decrypted_padded
                else:
                    raise ValueError(f"Unsupported padding scheme: {self.padding_scheme}")
            
            else:
                raise ValueError(f"Unsupported AES mode: {mode}")
            
        except Exception as e:
            self.logger.error(f"AES decryption failed with {self.padding_scheme} padding: {str(e)}")
            raise PaddingValidationError(f"AES decryption failed: {str(e)}")
    
    def validate_compatibility(self, key_size: Optional[int] = None) -> PaddingCompatibilityInfo:
        """Validate AES padding compatibility"""
        info = PaddingCompatibilityInfo(self.padding_scheme, "AES", key_size)
        
        # AES doesn't have data size limitations like RSA
        info.max_data_size = "No limit (stream cipher)"
        
        # Validate key size
        if key_size and key_size not in [128, 192, 256]:
            info.add_error(f"Invalid AES key size: {key_size}. Valid sizes: 128, 192, 256 bits")
        
        # Mode-specific warnings
        if self.padding_scheme == PaddingScheme.NONE.value:
            info.add_warning("No padding requires data to be block-aligned or used with stream modes like GCM")
        elif self.padding_scheme == PaddingScheme.ZERO.value:
            info.add_warning("Zero padding can be ambiguous if data naturally ends with zero bytes")
        
        return info


class PaddingManager:
    """Universal padding manager for all cryptographic algorithms"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        self._rsa_handlers = {}
        self._aes_handlers = {}
    
    def get_rsa_handler(self, padding_scheme: str) -> RSAPaddingHandler:
        """Get or create RSA padding handler"""
        if padding_scheme not in self._rsa_handlers:
            self._rsa_handlers[padding_scheme] = RSAPaddingHandler(padding_scheme, self.logger)
        return self._rsa_handlers[padding_scheme]
    
    def get_aes_handler(self, padding_scheme: str) -> AESPaddingHandler:
        """Get or create AES padding handler"""
        if padding_scheme not in self._aes_handlers:
            self._aes_handlers[padding_scheme] = AESPaddingHandler(padding_scheme, self.logger)
        return self._aes_handlers[padding_scheme]
    
    def encrypt_with_padding(self, data: bytes, key: Any, algorithm: str, padding_scheme: str, **kwargs) -> bytes:
        """Universal encryption with specified padding"""
        if algorithm.upper().startswith("RSA"):
            handler = self.get_rsa_handler(padding_scheme)
            return handler.encrypt(data, key, **kwargs)
        elif algorithm.upper().startswith("AES"):
            handler = self.get_aes_handler(padding_scheme)
            return handler.encrypt(data, key, **kwargs)
        else:
            raise ValueError(f"Unsupported algorithm for padding: {algorithm}")
    
    def decrypt_with_padding(self, data: bytes, key: Any, algorithm: str, padding_scheme: str, **kwargs) -> bytes:
        """Universal decryption with specified padding"""
        if algorithm.upper().startswith("RSA"):
            handler = self.get_rsa_handler(padding_scheme)
            return handler.decrypt(data, key, **kwargs)
        elif algorithm.upper().startswith("AES"):
            handler = self.get_aes_handler(padding_scheme)
            return handler.decrypt(data, key, **kwargs)
        else:
            raise ValueError(f"Unsupported algorithm for padding: {algorithm}")
    
    def sign_with_padding(self, data: bytes, private_key: Any, padding_scheme: str, hash_algorithm: str = "SHA256") -> bytes:
        """Sign data with RSA padding"""
        handler = self.get_rsa_handler(padding_scheme)
        return handler.sign(data, private_key, hash_algorithm)
    
    def verify_with_padding(self, signature: bytes, data: bytes, public_key: Any, padding_scheme: str, hash_algorithm: str = "SHA256") -> bool:
        """Verify RSA signature with padding"""
        handler = self.get_rsa_handler(padding_scheme)
        return handler.verify(signature, data, public_key, hash_algorithm)
    
    def validate_padding_compatibility(self, algorithm: str, padding_scheme: str, key_size: Optional[int] = None) -> PaddingCompatibilityInfo:
        """Validate padding compatibility for algorithm and key size"""
        if algorithm.upper().startswith("RSA"):
            handler = self.get_rsa_handler(padding_scheme)
            return handler.validate_compatibility(key_size)
        elif algorithm.upper().startswith("AES"):
            handler = self.get_aes_handler(padding_scheme)
            return handler.validate_compatibility(key_size)
        else:
            info = PaddingCompatibilityInfo(padding_scheme, algorithm, key_size)
            info.add_error(f"Unsupported algorithm: {algorithm}")
            return info
    
    def get_padding_recommendations(self, algorithm: str, use_case: str = "general") -> Dict[str, Any]:
        """Get padding scheme recommendations for algorithm and use case"""
        recommendations = {
            "algorithm": algorithm,
            "use_case": use_case,
            "recommended": [],
            "acceptable": [],
            "avoid": []
        }
        
        if algorithm.upper().startswith("RSA"):
            if use_case.lower() in ["modern", "high_security"]:
                recommendations["recommended"] = [PaddingScheme.OAEP.value, PaddingScheme.OAEP_SHA256.value]
                recommendations["acceptable"] = [PaddingScheme.PKCS1.value]
            elif use_case.lower() in ["legacy", "compatibility"]:
                recommendations["recommended"] = [PaddingScheme.PKCS1.value]
                recommendations["acceptable"] = [PaddingScheme.OAEP.value]
            elif use_case.lower() == "signature":
                recommendations["recommended"] = [PaddingScheme.PSS.value]
                recommendations["acceptable"] = [PaddingScheme.PKCS1.value]
            else:  # general
                recommendations["recommended"] = [PaddingScheme.OAEP.value, PaddingScheme.PKCS1.value]
        
        elif algorithm.upper().startswith("AES"):
            if use_case.lower() in ["modern", "high_security"]:
                recommendations["recommended"] = [PaddingScheme.NONE.value]  # Use with GCM
                recommendations["acceptable"] = [PaddingScheme.PKCS7.value]
            elif use_case.lower() in ["legacy", "compatibility"]:
                recommendations["recommended"] = [PaddingScheme.PKCS5.value, PaddingScheme.PKCS7.value]
                recommendations["avoid"] = [PaddingScheme.ZERO.value]
            else:  # general
                recommendations["recommended"] = [PaddingScheme.PKCS5.value, PaddingScheme.PKCS7.value]
                recommendations["acceptable"] = [PaddingScheme.NONE.value]
        
        return recommendations
    
    def generate_iv(self, algorithm: str, format_type: str = "random") -> bytes:
        """Generate initialization vector for symmetric encryption"""
        if algorithm.upper().startswith("AES"):
            if format_type == "16_digit_numeric":
                # Generate 16-digit numeric IV (for specific bank requirements)
                numeric_iv = ''.join([str(secrets.randbelow(10)) for _ in range(16)])
                return numeric_iv.encode('utf-8')
            else:
                # Standard random IV
                return os.urandom(16)
        else:
            raise ValueError(f"IV generation not supported for algorithm: {algorithm}")
    
    def check_availability(self) -> Dict[str, bool]:
        """Check availability of cryptographic capabilities"""
        return {
            "cryptography_library": CRYPTO_AVAILABLE,
            "rsa_encryption": CRYPTO_AVAILABLE,
            "aes_encryption": CRYPTO_AVAILABLE,
            "padding_support": CRYPTO_AVAILABLE
        } 