"""
AI-Powered Analysis Module for Bank UAT Agent

Provides intelligent analysis of bank API documentation to automatically
detect and configure encryption patterns, algorithms, and placement strategies.
"""

from .crypto_analyzer import (
    CryptoAnalyzer,
    EncryptionPatternDetector,
    AlgorithmExtractor,
    PlacementStrategyDetector
)

from .config_validator import (
    AIConfigValidator,
    ConfigurationSuggestionEngine,
    ValidationReportGenerator
)

from .pattern_matcher import (
    BankPatternMatcher,
    TemplateRecommendationEngine,
    CompatibilityAnalyzer
)

__all__ = [
    # Core Analysis
    'CryptoAnalyzer',
    'EncryptionPatternDetector',
    'AlgorithmExtractor',
    'PlacementStrategyDetector',
    
    # Configuration Validation
    'AIConfigValidator',
    'ConfigurationSuggestionEngine',
    'ValidationReportGenerator',
    
    # Pattern Matching
    'BankPatternMatcher',
    'TemplateRecommendationEngine',
    'CompatibilityAnalyzer'
] 