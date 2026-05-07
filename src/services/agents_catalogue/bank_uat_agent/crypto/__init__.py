"""
Crypto Module for Bank UAT Agent

Provides comprehensive cryptographic capabilities including:
- Configurable encryption strategies
- Universal padding management  
- Template-based encryption patterns
- AI-powered configuration detection
"""

from .padding_manager import (
    PaddingManager,
    RSAPaddingHandler,
    AESPaddingHandler,
    PaddingValidationError
)

from .configurable_crypto_manager import (
    ConfigurableCryptoManager,
    CryptoStrategy,
    HeaderBasedStrategy,
    BodyBasedStrategy,
    MixedStrategy
)

from .crypto_strategies import (
    EncryptionStrategy,
    RSAAESHeadersStrategy,
    RSAAESBodyStrategy,
    RSAAESMixedStrategy,
    SignatureOnlyStrategy,
    AESLegacyStrategy,
    RSAPureStrategy
)

__all__ = [
    # Padding Management
    'PaddingManager',
    'RSAPaddingHandler', 
    'AESPaddingHandler',
    'PaddingValidationError',
    
    # Configurable Crypto Manager
    'ConfigurableCryptoManager',
    'CryptoStrategy',
    'HeaderBasedStrategy',
    'BodyBasedStrategy', 
    'MixedStrategy',
    
    # Encryption Strategies
    'EncryptionStrategy',
    'RSAAESHeadersStrategy',
    'RSAAESBodyStrategy',
    'RSAAESMixedStrategy', 
    'SignatureOnlyStrategy',
    'AESLegacyStrategy',
    'RSAPureStrategy'
] 