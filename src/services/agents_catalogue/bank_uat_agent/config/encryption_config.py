"""
Encryption Configuration Models for Bank UAT Agent

Provides comprehensive data models for configuring various encryption schemes,
padding options, and crypto parameters for different bank API patterns.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class EncryptionType(str, Enum):
    """Supported encryption types"""
    AUTO_DETECT = "auto_detect"
    TEMPLATE = "template" 
    CUSTOM = "custom"
    NONE = "none"


class PlacementStrategy(str, Enum):
    """Where to place encryption/auth data"""
    HEADERS = "headers"
    BODY = "body"
    MIXED = "mixed"
    QUERY_PARAMS = "query_params"
    NONE = "none"


class PaddingScheme(str, Enum):
    """Supported padding schemes"""
    # RSA Padding
    PKCS1 = "PKCS1"
    OAEP = "OAEP"
    OAEP_SHA256 = "OAEP_SHA256"
    PSS = "PSS"
    
    # AES Padding
    PKCS5 = "PKCS5"
    PKCS7 = "PKCS7"
    ZERO = "ZERO"
    NONE = "NONE"


@dataclass
class PaddingConfig:
    """Padding configuration for different algorithms"""
    rsa_padding: str = PaddingScheme.PKCS1.value
    aes_padding: str = PaddingScheme.PKCS5.value
    signature_padding: str = PaddingScheme.PKCS1.value
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary"""
        return {
            "rsa_padding": self.rsa_padding,
            "aes_padding": self.aes_padding,
            "signature_padding": self.signature_padding
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'PaddingConfig':
        """Create from dictionary"""
        return cls(
            rsa_padding=data.get("rsa_padding", PaddingScheme.PKCS1.value),
            aes_padding=data.get("aes_padding", PaddingScheme.PKCS5.value),
            signature_padding=data.get("signature_padding", PaddingScheme.PKCS1.value)
        )


@dataclass
class AlgorithmConfig:
    """Algorithm configuration with padding support"""
    key_encryption: str = "RSA/ECB/PKCS1Padding"
    payload_encryption: str = "AES/CBC/PKCS5Padding"
    signature: str = "SHA1withRSA"
    padding: PaddingConfig = field(default_factory=PaddingConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "key_encryption": self.key_encryption,
            "payload_encryption": self.payload_encryption,
            "signature": self.signature,
            "padding": self.padding.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlgorithmConfig':
        """Create from dictionary"""
        padding_data = data.get("padding", {})
        padding = PaddingConfig.from_dict(padding_data) if isinstance(padding_data, dict) else PaddingConfig()
        
        return cls(
            key_encryption=data.get("key_encryption", "RSA/ECB/PKCS1Padding"),
            payload_encryption=data.get("payload_encryption", "AES/CBC/PKCS5Padding"),
            signature=data.get("signature", "SHA1withRSA"),
            padding=padding
        )


@dataclass
class CryptoKeys:
    """Cryptographic keys configuration"""
    bank_public_cert_path: Optional[str] = None
    partner_private_key_path: Optional[str] = None
    partner_id: Optional[str] = None
    aes_key_hex: Optional[str] = None
    
    # Key metadata
    bank_cert_format: Optional[str] = None  # "PEM", "DER", "CER"
    partner_key_format: Optional[str] = None  # "PKCS8", "PKCS1"
    key_size: Optional[int] = None  # RSA key size in bits
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "bank_public_cert_path": self.bank_public_cert_path,
            "partner_private_key_path": self.partner_private_key_path,
            "partner_id": self.partner_id,
            "aes_key_hex": self.aes_key_hex,
            "bank_cert_format": self.bank_cert_format,
            "partner_key_format": self.partner_key_format,
            "key_size": self.key_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CryptoKeys':
        """Create from dictionary"""
        return cls(
            bank_public_cert_path=data.get("bank_public_cert_path"),
            partner_private_key_path=data.get("partner_private_key_path"),
            partner_id=data.get("partner_id"),
            aes_key_hex=data.get("aes_key_hex"),
            bank_cert_format=data.get("bank_cert_format"),
            partner_key_format=data.get("partner_key_format"),
            key_size=data.get("key_size")
        )
    
    def has_rsa_keys(self) -> bool:
        """Check if RSA keys are configured"""
        return bool(self.bank_public_cert_path and self.partner_private_key_path and self.partner_id)
    
    def has_aes_key(self) -> bool:
        """Check if AES key is configured"""
        return bool(self.aes_key_hex)


@dataclass
class HeaderConfig:
    """Configuration for encryption headers"""
    name: str
    source: str  # "signature", "encrypted_aes_key", "encrypted_partner_id", "generated_iv", "static_value"
    encoding: str = "base64"  # "base64", "hex", "none"
    format: Optional[str] = None  # "16_digit_numeric" for IV
    static_value: Optional[str] = None  # Static value for "static_value" source type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "source": self.source,
            "encoding": self.encoding,
            "format": self.format,
            "static_value": self.static_value
        }


@dataclass
class EncryptionConfig:
    """Complete encryption configuration"""
    encryption_type: str = EncryptionType.AUTO_DETECT.value
    template_name: Optional[str] = None
    placement_strategy: str = PlacementStrategy.HEADERS.value
    algorithms: AlgorithmConfig = field(default_factory=AlgorithmConfig)
    crypto_keys: CryptoKeys = field(default_factory=CryptoKeys)
    generate_encrypted_curls: bool = False
    
    # Template and custom configuration
    headers: Dict[str, HeaderConfig] = field(default_factory=dict)
    body_structure: Dict[str, Any] = field(default_factory=dict)
    crypto_overrides: Dict[str, Any] = field(default_factory=dict)
    
    # Validation and metadata
    validation_notes: List[str] = field(default_factory=list)
    confidence_score: Optional[float] = None
    ai_detected: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "encryption_type": self.encryption_type,
            "template_name": self.template_name,
            "placement_strategy": self.placement_strategy,
            "algorithms": self.algorithms.to_dict(),
            "crypto_keys": self.crypto_keys.to_dict(),
            "generate_encrypted_curls": self.generate_encrypted_curls,
            "headers": {name: config.to_dict() for name, config in self.headers.items()},
            "body_structure": self.body_structure,
            "crypto_overrides": self.crypto_overrides,
            "validation_notes": self.validation_notes,
            "confidence_score": self.confidence_score,
            "ai_detected": self.ai_detected
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptionConfig':
        """Create from dictionary"""
        # Parse algorithms
        algorithms_data = data.get("algorithms", {})
        algorithms = AlgorithmConfig.from_dict(algorithms_data) if algorithms_data else AlgorithmConfig()
        
        # Parse crypto keys
        keys_data = data.get("crypto_keys", {})
        crypto_keys = CryptoKeys.from_dict(keys_data) if keys_data else CryptoKeys()
        
        # Parse headers
        headers_data = data.get("headers", {})
        headers = {}
        for name, config_data in headers_data.items():
            headers[name] = HeaderConfig(
                name=config_data.get("name", name),
                source=config_data.get("source", ""),
                encoding=config_data.get("encoding", "base64"),
                format=config_data.get("format"),
                static_value=config_data.get("static_value")
            )
        
        return cls(
            encryption_type=data.get("encryption_type", EncryptionType.AUTO_DETECT.value),
            template_name=data.get("template_name"),
            placement_strategy=data.get("placement_strategy", PlacementStrategy.HEADERS.value),
            algorithms=algorithms,
            crypto_keys=crypto_keys,
            generate_encrypted_curls=data.get("generate_encrypted_curls", False),
            headers=headers,
            body_structure=data.get("body_structure", {}),
            crypto_overrides=data.get("crypto_overrides", {}),
            validation_notes=data.get("validation_notes", []),
            confidence_score=data.get("confidence_score"),
            ai_detected=data.get("ai_detected", False)
        )
    
    def is_encryption_enabled(self) -> bool:
        """Check if encryption is enabled"""
        return self.encryption_type != EncryptionType.NONE.value
    
    def requires_rsa_keys(self) -> bool:
        """Check if configuration requires RSA keys"""
        return (
            self.is_encryption_enabled() and 
            "rsa" in self.algorithms.key_encryption.lower()
        )
    
    def requires_aes_key(self) -> bool:
        """Check if configuration requires AES key"""
        return (
            self.is_encryption_enabled() and
            "aes" in self.algorithms.payload_encryption.lower()
        )


@dataclass
class AIExtractedConfig:
    """Configuration extracted by AI from documentation"""
    extracted_config: EncryptionConfig
    confidence_score: float
    detected_patterns: List[str]
    recommendations: List[str] 
    validation_notes: List[str]
    extraction_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "extracted_config": self.extracted_config.to_dict(),
            "confidence_score": self.confidence_score,
            "detected_patterns": self.detected_patterns,
            "recommendations": self.recommendations,
            "validation_notes": self.validation_notes,
            "extraction_metadata": self.extraction_metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIExtractedConfig':
        """Create from dictionary"""
        config_data = data.get("extracted_config", {})
        extracted_config = EncryptionConfig.from_dict(config_data)
        extracted_config.ai_detected = True
        extracted_config.confidence_score = data.get("confidence_score", 0.0)
        
        return cls(
            extracted_config=extracted_config,
            confidence_score=data.get("confidence_score", 0.0),
            detected_patterns=data.get("detected_patterns", []),
            recommendations=data.get("recommendations", []),
            validation_notes=data.get("validation_notes", []),
            extraction_metadata=data.get("extraction_metadata", {})
        )


# Utility functions for configuration validation
def validate_encryption_config(config: EncryptionConfig) -> List[str]:
    """Validate encryption configuration and return list of errors"""
    errors = []
    
    if config.is_encryption_enabled():
        # Check for required keys
        if config.requires_rsa_keys() and not config.crypto_keys.has_rsa_keys():
            errors.append("RSA encryption requires bank certificate, partner private key, and partner ID")
        
        if config.requires_aes_key() and not config.crypto_keys.has_aes_key():
            # AES key will be generated if not provided, so this is just a warning
            pass
        
        # Validate padding compatibility
        if config.algorithms.key_encryption.startswith("RSA"):
            if config.algorithms.padding.rsa_padding not in [e.value for e in PaddingScheme if e.name.startswith(("PKCS1", "OAEP", "PSS"))]:
                errors.append(f"Invalid RSA padding scheme: {config.algorithms.padding.rsa_padding}")
        
        if config.algorithms.payload_encryption.startswith("AES"):
            if config.algorithms.padding.aes_padding not in [e.value for e in PaddingScheme if e.name.startswith(("PKCS", "ZERO", "NONE"))]:
                errors.append(f"Invalid AES padding scheme: {config.algorithms.padding.aes_padding}")
    
    return errors


def create_default_config() -> EncryptionConfig:
    """Create a default encryption configuration"""
    return EncryptionConfig(
        encryption_type=EncryptionType.AUTO_DETECT.value,
        placement_strategy=PlacementStrategy.HEADERS.value,
        algorithms=AlgorithmConfig(),
        crypto_keys=CryptoKeys(),
        generate_encrypted_curls=False
    ) 