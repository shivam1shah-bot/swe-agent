"""
Bank Pattern Matcher and Template Recommendation Engine

Matches detected patterns to specific bank implementations and provides
intelligent template recommendations based on bank characteristics.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from src.providers.logger import Logger
from ..config.encryption_config import EncryptionConfig, PlacementStrategy
from ..config.template_definitions import (
    get_available_templates, get_template_by_name,
    get_template_recommendations, get_template_compatibility_info
)


class BankCategory(str, Enum):
    """Categories of banks based on their characteristics"""
    MAJOR_INDIAN = "major_indian"
    REGIONAL_INDIAN = "regional_indian"
    INTERNATIONAL = "international"
    FINTECH = "fintech"
    COOPERATIVE = "cooperative"
    UNKNOWN = "unknown"


@dataclass
class BankCharacteristics:
    """Characteristics of a specific bank"""
    name: str
    category: BankCategory
    known_patterns: List[str]
    preferred_algorithms: Dict[str, str]
    security_level: str  # "basic", "standard", "high", "enterprise"
    documentation_quality: str  # "poor", "fair", "good", "excellent"
    api_maturity: str  # "legacy", "standard", "modern", "advanced"


@dataclass
class PatternMatch:
    """Result of pattern matching for a bank"""
    bank_name: str
    template_recommendations: List[str]
    confidence_scores: Dict[str, float]
    reasoning: List[str]
    alternative_approaches: List[str]


class BankPatternMatcher:
    """Matches encryption patterns based purely on documentation analysis"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        
        # Generic bank categories for recommendation logic (no hardcoded patterns)
        self.category_defaults = {
            BankCategory.MAJOR_INDIAN: {
                "security_level": "high",
                "api_maturity": "modern",
                "fallback_templates": ["rsa_aes_headers", "signature_only"]
            },
            BankCategory.FINTECH: {
                "security_level": "high", 
                "api_maturity": "advanced",
                "fallback_templates": ["rsa_aes_headers", "rsa_aes_mixed"]
            },
            BankCategory.REGIONAL_INDIAN: {
                "security_level": "standard",
                "api_maturity": "standard", 
                "fallback_templates": ["rsa_aes_body", "signature_only"]
            },
            BankCategory.UNKNOWN: {
                "security_level": "standard",
                "api_maturity": "standard",
                "fallback_templates": ["rsa_aes_headers", "signature_only"]
            }
        }
    
    def match_bank_pattern(
        self,
        bank_name: str,
        detected_patterns: List[str],
        extracted_config: EncryptionConfig
    ) -> PatternMatch:
        """Match detected patterns based purely on documentation analysis"""
        
        # Determine bank category (basic categorization only)
        bank_category = self._categorize_bank(bank_name)
        
        # Calculate template recommendations based on detected patterns only
        recommendations = self._calculate_template_recommendations(
            detected_patterns, extracted_config, bank_category
        )
        
        # Calculate confidence scores based on pattern detection
        confidence_scores = self._calculate_confidence_scores(
            detected_patterns, extracted_config
        )
        
        # Generate reasoning based on analysis, not hardcoded patterns
        reasoning = self._generate_reasoning(bank_category, detected_patterns, recommendations)
        
        # Generate alternatives based on detected patterns
        alternatives = self._generate_alternatives(detected_patterns, recommendations)
        
        return PatternMatch(
            bank_name=bank_name,
            template_recommendations=recommendations,
            confidence_scores=confidence_scores,
            reasoning=reasoning,
            alternative_approaches=alternatives
        )
    
    def _categorize_bank(self, bank_name: str) -> BankCategory:
        """Categorize bank based on name patterns (basic categorization only)"""
        name_lower = bank_name.lower()
        
        # Very basic categorization - no hardcoded patterns
        if any(keyword in name_lower for keyword in ["fintech", "digital", "neo", "neobank"]):
            return BankCategory.FINTECH
        elif any(keyword in name_lower for keyword in ["hdfc", "icici", "axis", "sbi", "kotak", "yes"]):
            return BankCategory.MAJOR_INDIAN
        elif "bank" in name_lower and any(keyword in name_lower for keyword in ["regional", "district", "local"]):
            return BankCategory.REGIONAL_INDIAN
        else:
            return BankCategory.UNKNOWN
    
    def _calculate_template_recommendations(
        self,
        detected_patterns: List[str],
        config: EncryptionConfig,
        bank_category: BankCategory
    ) -> List[str]:
        """Calculate template recommendations based purely on detected patterns"""
        recommendations = []
        
        # Primary recommendation: Use detected patterns directly
        if detected_patterns:
            # Use the highest confidence detected pattern first
            recommendations.extend(detected_patterns[:2])  # Top 2 detected patterns
        
        # Add category-based fallbacks only if no patterns detected
        if not recommendations:
            category_defaults = self.category_defaults.get(bank_category, self.category_defaults[BankCategory.UNKNOWN])
            recommendations.extend(category_defaults["fallback_templates"])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)
        
        return unique_recommendations[:3]  # Top 3 recommendations
    
    def _calculate_confidence_scores(
        self,
        detected_patterns: List[str],
        config: EncryptionConfig
    ) -> Dict[str, float]:
        """Calculate confidence scores based purely on pattern detection"""
        scores = {}
        
        # Score based on detection confidence only
        for i, pattern in enumerate(detected_patterns):
            # Higher score for patterns detected with higher rank
            base_confidence = 0.9 - (i * 0.1)  # First pattern gets 0.9, second gets 0.8, etc.
            scores[pattern] = max(base_confidence, 0.5)  # Minimum 0.5 confidence
        
        # Boost scores based on algorithm specificity
        if config.algorithms.signature and "signature" in str(config.algorithms.signature).lower():
            for pattern in scores:
                if "signature" in pattern:
                    scores[pattern] = min(scores[pattern] + 0.1, 1.0)
        
        if config.algorithms.key_encryption and config.algorithms.payload_encryption:
            for pattern in scores:
                if "rsa_aes" in pattern:
                    scores[pattern] = min(scores[pattern] + 0.1, 1.0)
        
        return scores
    
    def _generate_reasoning(
        self,
        bank_category: BankCategory,
        detected_patterns: List[str],
        recommendations: List[str]
    ) -> List[str]:
        """Generate reasoning based on documentation analysis"""
        reasoning = []
        
        # Pattern detection reasoning
        if detected_patterns:
            reasoning.append(f"Detected {len(detected_patterns)} encryption pattern(s) from documentation")
            reasoning.append(f"Primary pattern: {detected_patterns[0]}")
        else:
            reasoning.append("No specific patterns detected - using category-based fallbacks")
        
        # Bank category reasoning (general)
        if bank_category == BankCategory.MAJOR_INDIAN:
            reasoning.append("Major Indian bank - likely uses standard encryption approaches")
        elif bank_category == BankCategory.FINTECH:
            reasoning.append("Fintech bank - may use modern/advanced encryption patterns")
        elif bank_category == BankCategory.REGIONAL_INDIAN:
            reasoning.append("Regional bank - may prefer simpler encryption implementations")
        else:
            reasoning.append("Bank category unknown - using general recommendations")
        
        # Recommendation reasoning
        if recommendations:
            reasoning.append(f"Top recommendation: {recommendations[0]} based on analysis")
        
        return reasoning
    
    def _generate_alternatives(
        self,
        detected_patterns: List[str],
        recommendations: List[str]
    ) -> List[str]:
        """Generate alternative approaches based on detected patterns"""
        alternatives = []
        
        # Always include signature-only as a fallback
        if "signature_only" not in recommendations:
            alternatives.append("signature_only")
        
        # Include AES legacy if no AES patterns detected
        if not any("aes" in pattern for pattern in detected_patterns) and "aes_legacy" not in recommendations:
            alternatives.append("aes_legacy")
        
        # Include RSA pure for small payload scenarios
        if not any("rsa_pure" in pattern for pattern in detected_patterns) and "rsa_pure" not in recommendations:
            alternatives.append("rsa_pure")
        
        return alternatives[:2]  # Top 2 alternatives


class TemplateRecommendationEngine:
    """Advanced template recommendation engine"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        self.pattern_matcher = BankPatternMatcher(logger)
    
    def recommend_templates(
        self,
        bank_name: str,
        detected_patterns: List[str],
        config: EncryptionConfig,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Comprehensive template recommendation"""
        
        # Get bank-specific recommendations
        pattern_match = self.pattern_matcher.match_bank_pattern(
            bank_name, detected_patterns, config
        )
        
        # Get general template recommendations
        general_recommendations = get_template_recommendations(bank_name, context.get("use_case", "") if context else "")
        
        # Combine and rank recommendations
        all_recommendations = self._combine_recommendations(
            pattern_match.template_recommendations,
            general_recommendations,
            pattern_match.confidence_scores
        )
        
        # Generate detailed analysis
        analysis = self._generate_recommendation_analysis(
            pattern_match, all_recommendations, config
        )
        
        return {
            "primary_recommendations": all_recommendations[:3],
            "bank_specific_match": pattern_match,
            "analysis": analysis,
            "fallback_options": pattern_match.alternative_approaches
        }
    
    def _combine_recommendations(
        self,
        bank_specific: List[str],
        general: List[str],
        confidence_scores: Dict[str, float]
    ) -> List[str]:
        """Combine and rank recommendations from different sources"""
        
        # Create weighted list
        weighted_recommendations = []
        
        # Bank-specific recommendations get higher weight
        for i, template in enumerate(bank_specific):
            weight = confidence_scores.get(template, 0.5) * (1.0 - i * 0.1)
            weighted_recommendations.append((template, weight))
        
        # General recommendations get lower weight
        for i, template in enumerate(general):
            if template not in bank_specific:
                weight = 0.6 * (1.0 - i * 0.1)
                weighted_recommendations.append((template, weight))
        
        # Sort by weight and return template names
        weighted_recommendations.sort(key=lambda x: x[1], reverse=True)
        return [template for template, _ in weighted_recommendations]
    
    def _generate_recommendation_analysis(
        self,
        pattern_match: PatternMatch,
        recommendations: List[str],
        config: EncryptionConfig
    ) -> Dict[str, Any]:
        """Generate detailed analysis of recommendations"""
        
        analysis = {
            "bank_analysis": {
                "name": pattern_match.bank_name,
                "reasoning": pattern_match.reasoning,
                "confidence_scores": pattern_match.confidence_scores
            },
            "template_analysis": {},
            "compatibility_assessment": {},
            "security_assessment": {}
        }
        
        # Analyze each recommendation
        for template in recommendations[:3]:
            template_info = get_template_by_name(template)
            if template_info:
                compat_info = get_template_compatibility_info(template)
                
                analysis["template_analysis"][template] = {
                    "description": template_info.get("description", ""),
                    "complexity": template_info.get("complexity", "Medium"),
                    "security_level": template_info.get("security_level", "Medium"),
                    "use_cases": template_info.get("use_cases", [])
                }
                
                analysis["compatibility_assessment"][template] = compat_info
        
        # Security assessment
        analysis["security_assessment"] = {
            "encryption_enabled": config.is_encryption_enabled(),
            "signature_present": bool(config.algorithms.signature),
            "modern_algorithms": self._assess_algorithm_modernity(config),
            "recommendations": self._generate_security_recommendations(config)
        }
        
        return analysis
    
    def _assess_algorithm_modernity(self, config: EncryptionConfig) -> Dict[str, bool]:
        """Assess if algorithms are modern/secure"""
        return {
            "rsa_modern": config.algorithms.padding.rsa_padding in ["OAEP", "OAEP_SHA256"],
            "aes_secure": config.algorithms.padding.aes_padding in ["PKCS5", "PKCS7"],
            "signature_modern": "SHA256" in str(config.algorithms.signature),
            "overall_modern": all([
                "OAEP" in config.algorithms.padding.rsa_padding if config.algorithms.key_encryption else True,
                "PKCS" in config.algorithms.padding.aes_padding if config.algorithms.payload_encryption else True,
                "SHA256" in str(config.algorithms.signature) if config.algorithms.signature else True
            ])
        }
    
    def _generate_security_recommendations(self, config: EncryptionConfig) -> List[str]:
        """Generate security-focused recommendations"""
        recommendations = []
        
        if config.algorithms.padding.rsa_padding == "PKCS1":
            recommendations.append("Consider upgrading from PKCS1 to OAEP padding for RSA")
        
        if "SHA1" in str(config.algorithms.signature):
            recommendations.append("Upgrade from SHA1 to SHA256 for signatures")
        
        if not config.algorithms.signature and config.is_encryption_enabled():
            recommendations.append("Add request signing for authentication")
        
        return recommendations


class CompatibilityAnalyzer:
    """Analyzes compatibility between detected patterns and bank requirements"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
    
    def analyze_compatibility(
        self,
        config: EncryptionConfig,
        bank_name: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Analyze compatibility between configuration and bank requirements"""
        
        compatibility = {
            "overall_score": 0.0,
            "algorithm_compatibility": {},
            "implementation_compatibility": {},
            "security_compatibility": {},
            "issues": [],
            "recommendations": []
        }
        
        # Algorithm compatibility
        algo_compat = self._analyze_algorithm_compatibility(config)
        compatibility["algorithm_compatibility"] = algo_compat
        
        # Implementation compatibility
        impl_compat = self._analyze_implementation_compatibility(config, context or {})
        compatibility["implementation_compatibility"] = impl_compat
        
        # Security compatibility
        sec_compat = self._analyze_security_compatibility(config)
        compatibility["security_compatibility"] = sec_compat
        
        # Calculate overall score
        compatibility["overall_score"] = (
            algo_compat.get("score", 0.0) * 0.4 +
            impl_compat.get("score", 0.0) * 0.3 +
            sec_compat.get("score", 0.0) * 0.3
        )
        
        return compatibility
    
    def _analyze_algorithm_compatibility(self, config: EncryptionConfig) -> Dict[str, Any]:
        """Analyze algorithm compatibility"""
        score = 1.0
        issues = []
        
        # Check for deprecated algorithms
        if config.algorithms.signature and "SHA1" in config.algorithms.signature:
            score -= 0.2
            issues.append("SHA1 signature algorithm is deprecated")
        
        # Check padding schemes
        if config.algorithms.padding.rsa_padding == "PKCS1":
            score -= 0.1
            issues.append("PKCS1 RSA padding is legacy")
        
        return {
            "score": max(0.0, score),
            "issues": issues,
            "modern_algorithms": score > 0.8
        }
    
    def _analyze_implementation_compatibility(self, config: EncryptionConfig, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze implementation compatibility"""
        score = 1.0
        issues = []
        
        # Check placement strategy appropriateness
        if config.placement_strategy == "mixed" and context.get("complexity_preference") == "simple":
            score -= 0.2
            issues.append("Mixed placement strategy may be too complex for requirements")
        
        return {
            "score": max(0.0, score),
            "issues": issues,
            "implementation_ready": score > 0.7
        }
    
    def _analyze_security_compatibility(self, config: EncryptionConfig) -> Dict[str, Any]:
        """Analyze security compatibility"""
        score = 1.0
        issues = []
        
        # Check if encryption is appropriate
        if not config.is_encryption_enabled():
            score -= 0.3
            issues.append("No encryption configured")
        
        # Check authentication
        if not config.algorithms.signature:
            score -= 0.2
            issues.append("No request authentication configured")
        
        return {
            "score": max(0.0, score),
            "issues": issues,
            "security_adequate": score > 0.7
        } 