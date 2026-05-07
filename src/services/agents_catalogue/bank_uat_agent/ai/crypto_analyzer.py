"""
AI-Powered Crypto Configuration Analyzer

Analyzes bank API documentation to automatically detect encryption requirements,
algorithms, placement strategies, and configuration parameters using AI.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.providers.context import Context
from src.providers.logger import Logger
from src.agents.autonomous_agent import AutonomousAgentTool
from ..config.encryption_config import (
    EncryptionConfig, AlgorithmConfig, PaddingConfig, CryptoKeys,
    EncryptionType, PlacementStrategy, PaddingScheme, AIExtractedConfig
)
from ..config.template_definitions import (
    get_template_by_name, get_available_templates, get_template_recommendations
)


class AnalysisConfidence(str, Enum):
    """Confidence levels for AI analysis"""
    HIGH = "high"       # >0.8 - Very confident in detection
    MEDIUM = "medium"   # 0.5-0.8 - Moderately confident  
    LOW = "low"         # 0.2-0.5 - Low confidence
    UNCERTAIN = "uncertain"  # <0.2 - Very uncertain


@dataclass
class EncryptionPattern:
    """Detected encryption pattern with confidence"""
    pattern_type: str  # "rsa_aes_headers", "signature_only", etc.
    confidence: float
    detected_elements: List[str]
    supporting_evidence: List[str]
    template_match: Optional[str] = None


@dataclass
class AlgorithmDetection:
    """Detected algorithm specifications"""
    key_encryption: Optional[str] = None
    payload_encryption: Optional[str] = None
    signature_algorithm: Optional[str] = None
    padding_schemes: Dict[str, str] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class PlacementAnalysis:
    """Analysis of where encryption data should be placed"""
    strategy: str  # "headers", "body", "mixed"
    confidence: float
    detected_locations: Dict[str, str]  # {"token": "header", "encrypted_data": "body"}
    reasoning: List[str]


class EncryptionPatternDetector:
    """Detects encryption patterns from documentation text"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        
        # Pattern signatures for different encryption types
        self.pattern_signatures = {
            "rsa_aes_headers": {
                "keywords": ["token", "key", "partner", "iv", "header", "rsa", "aes"],
                "algorithms": ["RSA/ECB/PKCS1Padding", "AES/CBC/PKCS5Padding"],
                "indicators": ["base64", "encrypted", "signature"],
                "weight": 1.0
            },
            "rsa_aes_body": {
                "keywords": ["auth", "data", "encrypted_data", "rsa", "aes", "body"],
                "algorithms": ["RSA", "AES"],
                "indicators": ["request body", "payload", "json structure"],
                "weight": 0.9
            },
            "signature_only": {
                "keywords": ["signature", "sign", "verify", "authentication"],
                "algorithms": ["SHA1withRSA", "SHA256withRSA"],
                "indicators": ["no encryption", "signing only"],
                "weight": 0.8
            },
            "aes_legacy": {
                "keywords": ["aes", "legacy", "simple", "symmetric"],
                "algorithms": ["AES/CBC", "AES-256"],
                "indicators": ["shared key", "pre-shared"],
                "weight": 0.7
            }
        }
    
    def detect_patterns(self, documentation: str) -> List[EncryptionPattern]:
        """Detect encryption patterns from documentation"""
        patterns = []
        doc_lower = documentation.lower()
        
        for pattern_type, signature in self.pattern_signatures.items():
            confidence, evidence = self._calculate_pattern_confidence(
                doc_lower, signature
            )
            
            if confidence > 0.2:  # Only include patterns with some confidence
                pattern = EncryptionPattern(
                    pattern_type=pattern_type,
                    confidence=confidence,
                    detected_elements=self._extract_detected_elements(doc_lower, signature),
                    supporting_evidence=evidence
                )
                patterns.append(pattern)
        
        # Sort by confidence
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns
    
    def _calculate_pattern_confidence(self, doc_lower: str, signature: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Calculate confidence score for a pattern"""
        evidence = []
        total_score = 0.0
        max_score = 0.0
        
        # Check keywords
        keyword_score = 0.0
        for keyword in signature["keywords"]:
            if keyword in doc_lower:
                keyword_score += 1.0
                evidence.append(f"Found keyword: {keyword}")
        
        keyword_confidence = min(keyword_score / len(signature["keywords"]), 1.0)
        total_score += keyword_confidence * 0.4
        max_score += 0.4
        
        # Check algorithms
        algorithm_score = 0.0
        for algorithm in signature["algorithms"]:
            if algorithm.lower() in doc_lower:
                algorithm_score += 1.0
                evidence.append(f"Found algorithm: {algorithm}")
        
        if signature["algorithms"]:
            algorithm_confidence = min(algorithm_score / len(signature["algorithms"]), 1.0)
            total_score += algorithm_confidence * 0.4
            max_score += 0.4
        
        # Check indicators
        indicator_score = 0.0
        for indicator in signature["indicators"]:
            if indicator.lower() in doc_lower:
                indicator_score += 1.0
                evidence.append(f"Found indicator: {indicator}")
        
        if signature["indicators"]:
            indicator_confidence = min(indicator_score / len(signature["indicators"]), 1.0)
            total_score += indicator_confidence * 0.2
            max_score += 0.2
        
        # Apply pattern weight
        final_confidence = (total_score / max_score) * signature["weight"] if max_score > 0 else 0.0
        
        return final_confidence, evidence
    
    def _extract_detected_elements(self, doc_lower: str, signature: Dict[str, Any]) -> List[str]:
        """Extract specific elements detected in the documentation"""
        elements = []
        
        for keyword in signature["keywords"]:
            if keyword in doc_lower:
                elements.append(keyword)
        
        for algorithm in signature["algorithms"]:
            if algorithm.lower() in doc_lower:
                elements.append(algorithm)
        
        return list(set(elements))  # Remove duplicates


class AlgorithmExtractor:
    """Extracts specific algorithm information from documentation"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        
        # Algorithm patterns
        self.algorithm_patterns = {
            "rsa_algorithms": [
                r"RSA/ECB/PKCS1Padding",
                r"RSA/ECB/OAEPPadding", 
                r"RSA-PKCS1",
                r"RSA-OAEP"
            ],
            "aes_algorithms": [
                r"AES/CBC/PKCS5Padding",
                r"AES/CBC/PKCS7Padding",
                r"AES-256-CBC",
                r"AES-128-CBC"
            ],
            "signature_algorithms": [
                r"SHA1withRSA",
                r"SHA256withRSA",
                r"SHA-1",
                r"SHA-256"
            ]
        }
        
        # Padding scheme patterns
        self.padding_patterns = {
            "rsa_padding": {
                "PKCS1": [r"PKCS1", r"PKCS#1", r"PKCS1Padding"],
                "OAEP": [r"OAEP", r"OAEPPadding"],
                "PSS": [r"PSS", r"PSS.*padding"]
            },
            "aes_padding": {
                "PKCS5": [r"PKCS5", r"PKCS#5", r"PKCS5Padding"],
                "PKCS7": [r"PKCS7", r"PKCS#7", r"PKCS7Padding"],
                "ZERO": [r"zero.*padding", r"null.*padding"]
            }
        }
    
    def extract_algorithms(self, documentation: str) -> AlgorithmDetection:
        """Extract algorithm specifications from documentation"""
        detection = AlgorithmDetection()
        
        # Extract RSA algorithms
        rsa_alg, rsa_conf = self._extract_algorithm_type(documentation, "rsa_algorithms")
        if rsa_alg:
            detection.key_encryption = rsa_alg
            detection.confidence_scores["key_encryption"] = rsa_conf
        
        # Extract AES algorithms
        aes_alg, aes_conf = self._extract_algorithm_type(documentation, "aes_algorithms")
        if aes_alg:
            detection.payload_encryption = aes_alg
            detection.confidence_scores["payload_encryption"] = aes_conf
        
        # Extract signature algorithms
        sig_alg, sig_conf = self._extract_algorithm_type(documentation, "signature_algorithms")
        if sig_alg:
            detection.signature_algorithm = sig_alg
            detection.confidence_scores["signature_algorithm"] = sig_conf
        
        # Extract padding schemes
        detection.padding_schemes = self._extract_padding_schemes(documentation)
        
        return detection
    
    def _extract_algorithm_type(self, documentation: str, algorithm_type: str) -> Tuple[Optional[str], float]:
        """Extract specific algorithm type with confidence"""
        patterns = self.algorithm_patterns.get(algorithm_type, [])
        
        for pattern in patterns:
            matches = re.findall(pattern, documentation, re.IGNORECASE)
            if matches:
                # Return first match with high confidence
                return matches[0], 0.9
        
        return None, 0.0
    
    def _extract_padding_schemes(self, documentation: str) -> Dict[str, str]:
        """Extract padding schemes from documentation"""
        schemes = {}
        
        for padding_type, padding_schemes in self.padding_patterns.items():
            for scheme_name, patterns in padding_schemes.items():
                for pattern in patterns:
                    if re.search(pattern, documentation, re.IGNORECASE):
                        schemes[padding_type] = scheme_name
                        break
                if padding_type in schemes:
                    break
        
        return schemes


class PlacementStrategyDetector:
    """Detects where encryption data should be placed (headers vs body)"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        
        # Placement indicators
        self.placement_indicators = {
            "headers": {
                "keywords": ["header", "token", "authorization", "x-", "bearer"],
                "phrases": ["http header", "request header", "header field"],
                "weight": 1.0
            },
            "body": {
                "keywords": ["body", "payload", "request body", "json", "data"],
                "phrases": ["request body", "json body", "payload structure"],
                "weight": 0.9
            },
            "mixed": {
                "keywords": ["both", "combination", "mixed", "header and body"],
                "phrases": ["some in headers", "some in body"],
                "weight": 0.8
            }
        }
    
    def detect_placement_strategy(self, documentation: str) -> PlacementAnalysis:
        """Detect placement strategy from documentation"""
        doc_lower = documentation.lower()
        strategy_scores = {}
        detected_locations = {}
        reasoning = []
        
        # Calculate scores for each strategy
        for strategy, indicators in self.placement_indicators.items():
            score = self._calculate_placement_score(doc_lower, indicators)
            strategy_scores[strategy] = score
            
            if score > 0.3:
                reasoning.append(f"{strategy.title()} placement detected (score: {score:.2f})")
        
        # Determine best strategy
        best_strategy = max(strategy_scores.items(), key=lambda x: x[1])
        strategy_name, confidence = best_strategy
        
        # Extract specific locations if possible
        detected_locations = self._extract_field_locations(doc_lower)
        
        return PlacementAnalysis(
            strategy=strategy_name,
            confidence=confidence,
            detected_locations=detected_locations,
            reasoning=reasoning
        )
    
    def _calculate_placement_score(self, doc_lower: str, indicators: Dict[str, Any]) -> float:
        """Calculate placement strategy score"""
        score = 0.0
        total_weight = 0.0
        
        # Check keywords
        keyword_hits = sum(1 for keyword in indicators["keywords"] if keyword in doc_lower)
        if indicators["keywords"]:
            keyword_score = min(keyword_hits / len(indicators["keywords"]), 1.0)
            score += keyword_score * 0.6
            total_weight += 0.6
        
        # Check phrases
        phrase_hits = sum(1 for phrase in indicators["phrases"] if phrase in doc_lower)
        if indicators["phrases"]:
            phrase_score = min(phrase_hits / len(indicators["phrases"]), 1.0)
            score += phrase_score * 0.4
            total_weight += 0.4
        
        # Apply weight and normalize
        if total_weight > 0:
            final_score = (score / total_weight) * indicators["weight"]
        else:
            final_score = 0.0
        
        return final_score
    
    def _extract_field_locations(self, doc_lower: str) -> Dict[str, str]:
        """Extract specific field locations from documentation"""
        locations = {}
        
        # Common field patterns
        field_patterns = {
            "token": ["token.*header", "authorization.*header"],
            "key": ["key.*header", "encrypted.*key.*header"],
            "partner": ["partner.*header", "partner.*id.*header"],
            "iv": ["iv.*header", "initialization.*vector"],
            "signature": ["signature.*header", "x-signature"],
            "encrypted_data": ["data.*body", "encrypted.*data.*body", "payload"]
        }
        
        for field, patterns in field_patterns.items():
            for pattern in patterns:
                if re.search(pattern, doc_lower):
                    if "header" in pattern:
                        locations[field] = "header"
                    elif "body" in pattern:
                        locations[field] = "body"
                    break
        
        return locations


class CryptoAnalyzer:
    """Main AI-powered crypto configuration analyzer"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        self.pattern_detector = EncryptionPatternDetector(logger)
        self.algorithm_extractor = AlgorithmExtractor(logger)
        self.placement_detector = PlacementStrategyDetector(logger)
        
        # Initialize autonomous agent for advanced analysis
        try:
            self.autonomous_agent = AutonomousAgentTool()
        except Exception as e:
            self.logger.warning(f"Autonomous agent not available: {str(e)}")
            self.autonomous_agent = None
    
    async def analyze_encryption_requirements(
        self, 
        api_doc_content: str, 
        bank_name: str,
        ctx: Optional[Context] = None
    ) -> AIExtractedConfig:
        """
        Comprehensive AI analysis of encryption requirements
        
        Args:
            api_doc_content: API documentation content
            bank_name: Bank name for context
            ctx: Optional context for AI operations
            
        Returns:
            AIExtractedConfig with detected configuration
        """
        self.logger.info(f"Starting AI crypto analysis for {bank_name}")
        
        try:
            # Phase 1: Pattern Detection
            patterns = self.pattern_detector.detect_patterns(api_doc_content)
            self.logger.info(f"Detected {len(patterns)} encryption patterns")
            
            # Phase 2: Algorithm Extraction
            algorithms = self.algorithm_extractor.extract_algorithms(api_doc_content)
            self.logger.info(f"Extracted algorithms: RSA={algorithms.key_encryption}, AES={algorithms.payload_encryption}")
            
            # Phase 3: Placement Strategy Detection
            placement = self.placement_detector.detect_placement_strategy(api_doc_content)
            self.logger.info(f"Detected placement strategy: {placement.strategy} (confidence: {placement.confidence:.2f})")
            
            # Phase 4: AI Enhancement (if available)
            ai_insights = self._get_ai_insights(api_doc_content, bank_name, ctx)
            
            # Phase 5: Synthesize Results
            extracted_config = self._synthesize_configuration(
                patterns, algorithms, placement, ai_insights, bank_name
            )
            
            # Phase 6: Generate Recommendations
            recommendations = self._generate_recommendations(extracted_config, patterns)
            
            # Phase 7: Validation and Confidence Scoring
            validation_notes = self._generate_validation_notes(extracted_config)
            confidence_score = self._calculate_overall_confidence(patterns, algorithms, placement)
            
            # Create AI extracted configuration
            ai_config = AIExtractedConfig(
                extracted_config=extracted_config,
                confidence_score=confidence_score,
                detected_patterns=[p.pattern_type for p in patterns[:3]],  # Top 3 patterns
                recommendations=recommendations,
                validation_notes=validation_notes,
                extraction_metadata={
                    "bank_name": bank_name,
                    "patterns_analyzed": len(patterns),
                    "ai_enhancement_used": ai_insights is not None,
                    "primary_pattern": patterns[0].pattern_type if patterns else "unknown",
                    "placement_strategy": placement.strategy,
                    "placement_confidence": placement.confidence
                }
            )
            
            self.logger.info(f"AI analysis completed with confidence: {confidence_score:.2f}")
            return ai_config
            
        except Exception as e:
            self.logger.error(f"AI crypto analysis failed: {str(e)}")
            # Return fallback configuration
            return self._create_fallback_config(bank_name, str(e))
    
    def _get_ai_insights(
        self, 
        api_doc_content: str, 
        bank_name: str, 
        ctx: Optional[Context]
    ) -> Optional[Dict[str, Any]]:
        """Get additional insights from autonomous agent"""
        if not self.autonomous_agent:
            return None
        
        try:
            prompt = f"""
            Analyze this bank API documentation for {bank_name} and extract encryption requirements:
            
            {api_doc_content}
            
            Focus on:
            1. Specific encryption algorithms (RSA, AES variants)
            2. Padding schemes (PKCS1, OAEP, PKCS5, etc.)
            3. Where authentication data is placed (headers vs body)
            4. Required headers or body structure
            5. Any bank-specific requirements or patterns
            
            Return analysis as structured information about:
            - Encryption type (rsa+aes, signature-only, etc.)
            - Algorithm specifications
            - Data placement strategy
            - Key requirements
            - Any special formatting or encoding requirements
            """
            
            # Use autonomous agent to analyze documentation
            parameters = {
                "prompt": prompt,
                "task": "analyze_encryption_requirements",
                "agent_name": "bank-uat-agent",
            }
            response = self.autonomous_agent.execute(parameters)
            
            # Extract content from response
            if response.get("error"):
                self.logger.debug(f"Autonomous agent error: {response['error']}")
                return None
            
            content = response.get("content", "")
            if not content:
                self.logger.debug("No content returned from autonomous agent")
                return None
            
            # Parse AI response (expecting structured text)
            insights = self._parse_ai_response(content)
            return insights
            
        except Exception as e:
            self.logger.debug(f"AI insights extraction failed: {str(e)}")
            return None
    
    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response into structured data"""
        insights = {
            "ai_detected_type": None,
            "ai_algorithms": {},
            "ai_placement": None,
            "ai_special_requirements": []
        }
        
        if not response:
            return insights
        
        response_lower = response.lower()
        
        # Extract encryption type
        if "rsa" in response_lower and "aes" in response_lower:
            if "header" in response_lower:
                insights["ai_detected_type"] = "rsa_aes_headers"
            elif "body" in response_lower:
                insights["ai_detected_type"] = "rsa_aes_body"
            else:
                insights["ai_detected_type"] = "rsa_aes_mixed"
        elif "signature" in response_lower and "only" in response_lower:
            insights["ai_detected_type"] = "signature_only"
        elif "aes" in response_lower:
            insights["ai_detected_type"] = "aes_legacy"
        
        # Extract placement strategy
        if "header" in response_lower and "body" in response_lower:
            insights["ai_placement"] = "mixed"
        elif "header" in response_lower:
            insights["ai_placement"] = "headers"
        elif "body" in response_lower:
            insights["ai_placement"] = "body"
        
        return insights
    
    def _synthesize_configuration(
        self,
        patterns: List[EncryptionPattern],
        algorithms: AlgorithmDetection, 
        placement: PlacementAnalysis,
        ai_insights: Optional[Dict[str, Any]],
        bank_name: str
    ) -> EncryptionConfig:
        """Synthesize all analysis into final configuration"""
        
        # Determine encryption type
        if patterns:
            primary_pattern = patterns[0].pattern_type
        elif ai_insights and ai_insights.get("ai_detected_type"):
            primary_pattern = ai_insights["ai_detected_type"]
        else:
            primary_pattern = "rsa_aes_headers"  # Default fallback
        
        # Build algorithm configuration
        algorithm_config = AlgorithmConfig()
        
        if algorithms.key_encryption:
            algorithm_config.key_encryption = algorithms.key_encryption
        if algorithms.payload_encryption:
            algorithm_config.payload_encryption = algorithms.payload_encryption
        if algorithms.signature_algorithm:
            algorithm_config.signature = algorithms.signature_algorithm
        
        # Build padding configuration
        padding_config = PaddingConfig()
        if algorithms.padding_schemes.get("rsa_padding"):
            padding_config.rsa_padding = algorithms.padding_schemes["rsa_padding"]
        if algorithms.padding_schemes.get("aes_padding"):
            padding_config.aes_padding = algorithms.padding_schemes["aes_padding"]
        
        algorithm_config.padding = padding_config
        
        # Determine placement strategy
        placement_strategy = placement.strategy
        if ai_insights and ai_insights.get("ai_placement"):
            # Use AI insight if available and confident
            if placement.confidence < 0.7:
                placement_strategy = ai_insights["ai_placement"]
        
        # Create configuration
        config = EncryptionConfig(
            encryption_type=EncryptionType.AUTO_DETECT.value,
            template_name=primary_pattern if primary_pattern in ["rsa_aes_headers", "rsa_aes_body", "signature_only", "aes_legacy"] else None,
            placement_strategy=placement_strategy,
            algorithms=algorithm_config,
            crypto_keys=CryptoKeys(),  # Will be filled by user
            generate_encrypted_curls=True,
            ai_detected=True
        )
        
        return config
    
    def _generate_recommendations(
        self, 
        config: EncryptionConfig, 
        patterns: List[EncryptionPattern]
    ) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # Template recommendations
        if config.template_name:
            recommendations.append(f"Detected pattern matches '{config.template_name}' template")
        
        # Security recommendations
        if config.algorithms.padding.rsa_padding == PaddingScheme.PKCS1.value:
            recommendations.append("Consider upgrading to OAEP padding for enhanced RSA security")
        
        # Pattern confidence recommendations
        if patterns and patterns[0].confidence < 0.7:
            recommendations.append("Pattern detection confidence is moderate - please verify configuration")
        
        # Key requirements
        if config.requires_rsa_keys():
            recommendations.append("RSA keys required: bank public certificate and partner private key")
        
        return recommendations
    
    def _generate_validation_notes(self, config: EncryptionConfig) -> List[str]:
        """Generate validation notes for the configuration"""
        notes = []
        
        if config.placement_strategy == PlacementStrategy.HEADERS.value:
            notes.append("Headers-based encryption detected - verify header names match API specification")
        
        if config.algorithms.signature:
            notes.append(f"Signature algorithm: {config.algorithms.signature} - ensure partner private key is available")
        
        if config.template_name:
            notes.append(f"Configuration based on template: {config.template_name}")
        
        return notes
    
    def _calculate_overall_confidence(
        self,
        patterns: List[EncryptionPattern],
        algorithms: AlgorithmDetection,
        placement: PlacementAnalysis
    ) -> float:
        """Calculate overall confidence score for the analysis"""
        if not patterns:
            return 0.1
        
        # Weight different factors
        pattern_confidence = patterns[0].confidence * 0.5
        algorithm_confidence = sum(algorithms.confidence_scores.values()) / max(len(algorithms.confidence_scores), 1) * 0.3
        placement_confidence = placement.confidence * 0.2
        
        total_confidence = pattern_confidence + algorithm_confidence + placement_confidence
        return min(total_confidence, 1.0)
    
    def _create_fallback_config(self, bank_name: str, error_msg: str) -> AIExtractedConfig:
        """Create fallback configuration when analysis fails"""
        fallback_config = EncryptionConfig(
            encryption_type=EncryptionType.TEMPLATE.value,
            template_name="rsa_aes_headers",  # Safe default
            placement_strategy=PlacementStrategy.HEADERS.value,
            generate_encrypted_curls=True,
            ai_detected=False
        )
        
        return AIExtractedConfig(
            extracted_config=fallback_config,
            confidence_score=0.1,
            detected_patterns=["fallback"],
            recommendations=[
                "AI analysis failed - using safe default configuration",
                "Please review and adjust configuration manually",
                f"Error: {error_msg}"
            ],
            validation_notes=[
                "This is a fallback configuration",
                "Manual verification required"
            ],
            extraction_metadata={
                "bank_name": bank_name,
                "fallback_used": True,
                "error": error_msg
            }
        ) 