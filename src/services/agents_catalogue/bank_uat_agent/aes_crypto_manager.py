"""
AES Crypto Manager for Bank UAT Agent

This module provides AES encryption/decryption capabilities for backward compatibility
with the original pdf_api_doc_uat agent's crypto functionality.
"""

import os
import base64
import json
import subprocess
import tempfile
import uuid
import random
from pathlib import Path
from typing import Optional, Dict, Any, List

# Optional crypto imports - graceful fallback if pycryptodome not installed  
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    from Crypto.Random import get_random_bytes
    CRYPTO_AVAILABLE = True
except ImportError:
    # Fallback when pycryptodome is not installed
    AES = None
    pad = None
    unpad = None
    get_random_bytes = None
    CRYPTO_AVAILABLE = False

from src.providers.logger import Logger
from .config.encryption_config import PaddingScheme


class AESCryptoManager:
    """
    AES Encryption manager maintaining compatibility with UAT_LangGraph
    
    Features:
    - AES/CBC/PKCS5 encryption matching UAT_LangGraph specification
    - Dynamic IV generation (16 ASCII characters from range 47-126)
    - Base64 encoding for output format
    - Custom crypto specification file support
    """
    
    # Default test key matching UAT_LangGraph
    DEFAULT_HEX_KEY = "76616d706c65446868634145536b659129616d706365496488631145536b7567"
    
    def __init__(self, logger: Optional[Logger] = None):
        """Initialize AES crypto manager with optional logger"""
        self.logger = logger or Logger()
        
        # Initialize padding manager for enhanced padding support
        try:
            from .crypto.padding_manager import PaddingManager
            self.padding_manager = PaddingManager(logger)
        except ImportError:
            self.padding_manager = None
            self.logger.debug("Padding manager not available - using basic padding")
        
        if not CRYPTO_AVAILABLE:
            self.logger.warning("AES encryption not available. Please install pycryptodome: pip install pycryptodome>=3.19.0")
    
    def check_availability(self) -> bool:
        """Check if AES encryption is available"""
        return CRYPTO_AVAILABLE
    
    @staticmethod
    def generate_iv() -> bytes:
        """
        Generate 16 random ASCII characters (47-126) as IV
        Matches UAT_LangGraph's IV generation exactly
        """
        if not CRYPTO_AVAILABLE:
            raise Exception("IV generation not available. Please install pycryptodome: pip install pycryptodome>=3.19.0")
        
        # Generate 16 ASCII characters from range 47-126 (matching UAT_LangGraph)
        iv_chars = []
        for _ in range(16):
            ascii_code = random.randint(47, 126)
            iv_chars.append(chr(ascii_code))
        
        return ''.join(iv_chars).encode('utf-8')
    
    @staticmethod
    def encrypt_payload(payload: str, hex_key: str) -> str:
        """
        Encrypt payload using AES/CBC/PKCS5 matching UAT_LangGraph specification
        
        Args:
            payload: Data to encrypt
            hex_key: Encryption key in hexadecimal format
            
        Returns:
            Base64 encoded string containing IV + encrypted payload
            
        Raises:
            Exception: If encryption fails or crypto not available
        """
        if not CRYPTO_AVAILABLE:
            raise Exception("AES encryption not available. Please install pycryptodome: pip install pycryptodome>=3.19.0")
        
        try:
            # Convert hex key to bytes
            key = bytes.fromhex(hex_key)
            
            # Generate IV using UAT_LangGraph method
            iv = AESCryptoManager.generate_iv()
            
            # Create cipher
            cipher = AES.new(key, AES.MODE_CBC, iv)
            
            # Pad payload to multiple of 16 bytes (PKCS5/PKCS7)
            padded_payload = pad(payload.encode('utf-8'), AES.block_size)
            
            # Encrypt
            encrypted = cipher.encrypt(padded_payload)
            
            # Combine IV + encrypted payload and encode as base64
            combined = iv + encrypted
            result = base64.b64encode(combined).decode('utf-8')
            
            return result
            
        except Exception as e:
            raise Exception(f"AES encryption failed: {str(e)}")
    
    @staticmethod
    def decrypt_payload(encrypted_data: str, hex_key: str) -> str:
        """
        Decrypt API response matching UAT_LangGraph decryption logic
        
        Args:
            encrypted_data: Base64 encoded encrypted data with IV prefix
            hex_key: Decryption key in hexadecimal format
            
        Returns:
            Decrypted payload as string
            
        Raises:
            Exception: If decryption fails or crypto not available
        """
        if not CRYPTO_AVAILABLE:
            raise Exception("AES decryption not available. Please install pycryptodome: pip install pycryptodome>=3.19.0")
        
        try:
            # Convert hex key to bytes
            key = bytes.fromhex(hex_key)
            
            # Decode base64
            combined = base64.b64decode(encrypted_data)
            
            # Extract IV (first 16 bytes) and encrypted data
            iv = combined[:16]
            encrypted = combined[16:]
            
            # Create cipher
            cipher = AES.new(key, AES.MODE_CBC, iv)
            
            # Decrypt
            decrypted_padded = cipher.decrypt(encrypted)
            
            # Remove padding
            decrypted = unpad(decrypted_padded, AES.block_size)
            
            return decrypted.decode('utf-8')
            
        except Exception as e:
            raise Exception(f"AES decryption failed: {str(e)}")
    
    def load_encryption_specification(self, crypto_file_path: Optional[str] = None) -> str:
        """
        Load encryption specification from file or return default
        
        Args:
            crypto_file_path: Optional path to custom crypto specification file
            
        Returns:
            Crypto specification content as string
        """
        if crypto_file_path and os.path.exists(crypto_file_path):
            try:
                with open(crypto_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                self.logger.info(f"Loaded custom crypto specification from {crypto_file_path}")
                return content
                
            except Exception as e:
                self.logger.warning(f"Failed to load crypto spec from {crypto_file_path}: {str(e)}")
                # Fall back to default
        
        # Return comprehensive default spec matching UAT_LangGraph's crypto.txt
        return self._get_default_crypto_spec()
    
    def _get_default_crypto_spec(self) -> str:
        """Get default crypto specification matching UAT_LangGraph"""
        return f'''
## AES Encryption Specification - UAT_LangGraph Compatible

### Algorithm Details
- **Cipher**: AES (Advanced Encryption Standard)
- **Mode**: CBC (Cipher Block Chaining) 
- **Padding**: PKCS5/PKCS7
- **Key Size**: 256-bit (32 bytes)
- **Block Size**: 128-bit (16 bytes)
- **IV Size**: 128-bit (16 bytes)

### Key Management
- **Format**: Hexadecimal string representation
- **Default Test Key**: {self.DEFAULT_HEX_KEY}
- **IV Generation**: Dynamic random ASCII characters (range 47-126)

### Encryption Process
1. Generate random 16-byte IV using ASCII characters (47-126)
2. Pad plaintext using PKCS5 padding to multiple of 16 bytes
3. Encrypt padded plaintext using AES-CBC with generated IV
4. Prepend IV to encrypted data
5. Encode result as Base64 string

### Output Format
- **Structure**: Base64(IV + EncryptedData)
- **Encoding**: UTF-8 string
- **IV Position**: First 16 bytes of decoded Base64

### Decryption Process  
1. Decode Base64 input string
2. Extract IV (first 16 bytes) and encrypted data (remaining bytes)
3. Initialize AES-CBC cipher with extracted IV
4. Decrypt encrypted data
5. Remove PKCS5 padding from decrypted result
6. Return UTF-8 decoded plaintext

### Test Vectors
- **Test Key**: {self.DEFAULT_HEX_KEY}
- **Test Plaintext**: "Hello World"
- **Expected Format**: Base64 string starting with dynamic IV

### Security Notes
- IV must be unique for each encryption operation
- Key should be securely generated and stored
- Use secure random number generator for IV generation
- Validate padding during decryption to prevent padding oracle attacks

### UAT_LangGraph Compatibility
- 100% compatible with UAT_LangGraph crypto implementation
- Maintains same IV generation method (ASCII 47-126)
- Uses identical padding and encoding schemes
- Preserves output format for seamless integration
'''
    
    def looks_like_encrypted_response(self, response: str) -> bool:
        """
        Check if response looks like it could be encrypted
        Matches UAT_LangGraph's detection logic
        
        Args:
            response: API response to check
            
        Returns:
            True if response appears to be encrypted
        """
        if not response or len(response.strip()) < 20:
            return False
        
        response = response.strip()
        
        # Check for base64-like patterns
        try:
            # Try to decode as base64
            decoded = base64.b64decode(response)
            
            # Check if decoded length suggests encrypted data with IV
            if len(decoded) >= 32:  # At least IV (16) + some encrypted data (16+)
                return True
                
        except Exception:
            pass
        
        # Check for JSON with encrypted fields
        try:
            json_data = json.loads(response)
            if isinstance(json_data, dict):
                # Look for common encrypted field names
                encrypted_fields = ['encrypted_data', 'cipher', 'payload', 'data']
                for field in encrypted_fields:
                    if field in json_data and len(str(json_data[field])) > 20:
                        return True
        except:
            pass
        
        return False
    
    def cleanup_temporary_files(self):
        """Clean up any temporary encryption/decryption files"""
        try:
            temp_dir = Path(tempfile.gettempdir())
            
            # Clean up AES-related temporary files
            for file_pattern in ["aes_encrypt_*.py", "aes_decrypt_*.py"]:
                for temp_file in temp_dir.glob(file_pattern):
                    try:
                        temp_file.unlink()
                        self.logger.debug(f"Cleaned up temporary file: {temp_file}")
                    except Exception as e:
                        self.logger.warning(f"Could not remove temporary file {temp_file}: {str(e)}")
                        
        except Exception as e:
            self.logger.warning(f"Error during AES temporary file cleanup: {str(e)}")
    
    # Enhanced methods with padding support
    def encrypt_with_padding(self, data: bytes, key: bytes, padding_scheme: str = PaddingScheme.PKCS5.value, iv: bytes = None, mode: str = "CBC") -> bytes:
        """
        Encrypt data with specified padding scheme
        
        Args:
            data: Data to encrypt
            key: AES key as bytes
            padding_scheme: Padding scheme (PKCS5, PKCS7, ZERO, NONE)
            iv: Initialization vector (generated if not provided)
            mode: AES mode (CBC, GCM)
            
        Returns:
            Encrypted data as bytes (includes IV for CBC mode)
        """
        if self.padding_manager:
            return self.padding_manager.encrypt_with_padding(data, key, "AES", padding_scheme, iv=iv, mode=mode)
        else:
            # Fallback to basic PKCS5 encryption
            hex_key = key.hex() if isinstance(key, bytes) else key
            encrypted_b64 = self.encrypt_payload(data.decode('utf-8') if isinstance(data, bytes) else data, hex_key)
            return base64.b64decode(encrypted_b64)
    
    def decrypt_with_padding(self, encrypted_data: bytes, key: bytes, padding_scheme: str = PaddingScheme.PKCS5.value, iv: bytes = None, mode: str = "CBC") -> bytes:
        """
        Decrypt data with specified padding scheme
        
        Args:
            encrypted_data: Encrypted data to decrypt
            key: AES key as bytes
            padding_scheme: Padding scheme (PKCS5, PKCS7, ZERO, NONE)
            iv: Initialization vector (extracted from data if not provided)
            mode: AES mode (CBC, GCM)
            
        Returns:
            Decrypted data as bytes
        """
        if self.padding_manager:
            return self.padding_manager.decrypt_with_padding(encrypted_data, key, "AES", padding_scheme, iv=iv, mode=mode)
        else:
            # Fallback to basic PKCS5 decryption
            encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
            decrypted = self.decrypt_response(encrypted_b64)
            return decrypted.encode('utf-8') if decrypted else b''
    
    
    def generate_iv_with_format(self, format_type: str = "random") -> bytes:
        """
        Generate IV with specific format
        
        Args:
            format_type: "random" for standard random IV, "16_digit_numeric" for numeric IV
            
        Returns:
            Generated IV as bytes
        """
        if self.padding_manager:
            return self.padding_manager.generate_iv("AES", format_type)
        else:
            # Fallback to standard IV generation
            if format_type == "16_digit_numeric":
                import random
                numeric_iv = ''.join([str(random.randint(0, 9)) for _ in range(16)])
                return numeric_iv.encode('utf-8')
            else:
                return self.generate_iv() 