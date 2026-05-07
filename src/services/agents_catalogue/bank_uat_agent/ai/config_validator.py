"""
AI Configuration Validator and Suggestion Engine

Validates AI-extracted configurations, provides suggestions for improvements,
and generates comprehensive validation reports for user review.
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.providers.context import Context
from src.providers.logger import Logger
from src.agents.autonomous_agent import AutonomousAgentTool
from ..config.encryption_config import (
    EncryptionConfig, AlgorithmConfig, PaddingConfig, CryptoKeys,
    EncryptionType, PlacementStrategy, PaddingScheme, AIExtractedConfig,
    validate_encryption_config
)
from ..config.template_definitions import (
    get_template_by_name, get_template_compatibility_info,
    get_template_recommendations, validate_template_config
)


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues"""
    CRITICAL = "critical"   # Must be fixed
    WARNING = "warning"     # Should be reviewed
    INFO = "info"          # Good to know
    SUGGESTION = "suggestion"  # Optional improvement


@dataclass
class ValidationIssue:
    """Individual validation issue"""
    severity: str
    category: str  # "algorithms", "padding", "keys", "compatibility"
    message: str
    suggestion: Optional[str] = None
    auto_fixable: bool = False
    fix_data: Optional[Dict[str, Any]] = None


@dataclass
class ValidationReport:
    """Comprehensive validation report"""
    is_valid: bool
    confidence_assessment: str
    issues: List[ValidationIssue]
    suggestions: List[str]
    recommended_actions: List[str]
    template_alternatives: List[str] = field(default_factory=list)
    compatibility_score: float = 0.0


@dataclass
class ConfigurationSuggestion:
    """Configuration improvement suggestion"""
    type: str  # "algorithm", "padding", "template", "structure"
    current_value: Any
    suggested_value: Any
    reason: str
    impact: str  # "security", "compatibility", "performance"
    confidence: float


class AIConfigValidator:
    """AI-powered configuration validator"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        
        # Initialize autonomous agent for advanced validation
        try:
            self.autonomous_agent = AutonomousAgentTool()
        except Exception as e:
            self.logger.warning(f"Autonomous agent not available: {str(e)}")
            self.autonomous_agent = None
    
    async def validate_extracted_config(
        self,
        extracted_config: AIExtractedConfig,
        original_documentation: str,
        ctx: Optional[Context] = None
    ) -> ValidationReport:
        """
        Comprehensive validation of AI-extracted configuration
        
        Args:
            extracted_config: AI-extracted configuration to validate
            original_documentation: Original API documentation
            ctx: Optional context for AI operations
            
        Returns:
            ValidationReport with detailed analysis
        """
        self.logger.info("Starting AI configuration validation")
        
        config = extracted_config.extracted_config
        issues = []
        suggestions = []
        recommended_actions = []
        
        try:
            # Phase 1: Basic Configuration Validation
            basic_issues = self._validate_basic_configuration(config)
            issues.extend(basic_issues)
            
            # Phase 2: Algorithm Compatibility Validation
            algo_issues = self._validate_algorithm_compatibility(config)
            issues.extend(algo_issues)
            
            # Phase 3: Template Matching Validation
            template_issues, alternatives = self._validate_template_matching(config)
            issues.extend(template_issues)
            
            # Phase 4: AI Cross-Validation
            if self.autonomous_agent:
                ai_issues = self._ai_cross_validate(config, original_documentation, ctx)
                issues.extend(ai_issues)
            
            # Phase 5: Security Assessment
            security_issues = self._validate_security_requirements(config)
            issues.extend(security_issues)
            
            # Phase 6: Generate Suggestions
            suggestions = self._generate_improvement_suggestions(config, issues)
            
            # Phase 7: Generate Recommended Actions
            recommended_actions = self._generate_recommended_actions(issues, extracted_config.confidence_score)
            
            # Phase 8: Calculate Overall Assessment
            is_valid = not any(issue.severity == ValidationSeverity.CRITICAL.value for issue in issues)
            confidence_assessment = self._assess_confidence(extracted_config.confidence_score, issues)
            compatibility_score = self._calculate_compatibility_score(config, issues)
            
            report = ValidationReport(
                is_valid=is_valid,
                confidence_assessment=confidence_assessment,
                issues=issues,
                suggestions=suggestions,
                recommended_actions=recommended_actions,
                template_alternatives=alternatives,
                compatibility_score=compatibility_score
            )
            
            self.logger.info(f"Validation completed: {len(issues)} issues found, valid={is_valid}")
            return report
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {str(e)}")
            return self._create_error_report(str(e))
    
    def _validate_basic_configuration(self, config: EncryptionConfig) -> List[ValidationIssue]:
        """Validate basic configuration structure and requirements"""
        issues = []
        
        # Check encryption type validity
        if config.encryption_type not in [e.value for e in EncryptionType]:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL.value,
                category="configuration",
                message=f"Invalid encryption type: {config.encryption_type}",
                suggestion="Use one of: auto_detect, template, custom, none"
            ))
        
        # Check placement strategy validity
        if config.placement_strategy not in [s.value for s in PlacementStrategy]:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL.value,
                category="configuration",
                message=f"Invalid placement strategy: {config.placement_strategy}",
                suggestion="Use one of: headers, body, mixed, query_params"
            ))
        
        # Validate using built-in function
        config_errors = validate_encryption_config(config)
        for error in config_errors:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL.value,
                category="configuration",
                message=error,
                suggestion="Review and correct the configuration"
            ))
        
        return issues
    
    def _validate_algorithm_compatibility(self, config: EncryptionConfig) -> List[ValidationIssue]:
        """Validate algorithm and padding compatibility"""
        issues = []
        
        # RSA algorithm validation
        if config.algorithms.key_encryption and "RSA" in config.algorithms.key_encryption:
            # Check RSA padding compatibility
            rsa_padding = config.algorithms.padding.rsa_padding
            if rsa_padding not in [scheme.value for scheme in PaddingScheme if scheme.name.startswith(("PKCS1", "OAEP", "PSS"))]:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING.value,
                    category="padding",
                    message=f"Unusual RSA padding scheme: {rsa_padding}",
                    suggestion="Consider using PKCS1 or OAEP for better compatibility"
                ))
            
            # Security recommendations
            if rsa_padding == PaddingScheme.PKCS1.value:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO.value,
                    category="security",
                    message="PKCS1 padding is legacy - consider OAEP for new implementations",
                    suggestion="Upgrade to OAEP padding for enhanced security"
                ))
        
        # AES algorithm validation
        if config.algorithms.payload_encryption and "AES" in config.algorithms.payload_encryption:
            aes_padding = config.algorithms.padding.aes_padding
            if aes_padding == PaddingScheme.ZERO.value:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING.value,
                    category="padding",
                    message="Zero padding can be ambiguous - consider PKCS5/PKCS7",
                    suggestion="Use PKCS5 or PKCS7 padding for better reliability"
                ))
        
        # Signature algorithm validation
        if config.algorithms.signature:
            if "SHA1" in config.algorithms.signature:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING.value,
                    category="security",
                    message="SHA1 is deprecated for signatures - consider SHA256",
                    suggestion="Upgrade to SHA256withRSA for better security",
                    auto_fixable=True,
                    fix_data={"signature": "SHA256withRSA"}
                ))
        
        return issues
    
    def _validate_template_matching(self, config: EncryptionConfig) -> Tuple[List[ValidationIssue], List[str]]:
        """Validate template matching and suggest alternatives"""
        issues = []
        alternatives = []
        
        if config.template_name:
            # Validate template exists
            template = get_template_by_name(config.template_name)
            if not template:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.CRITICAL.value,
                    category="template",
                    message=f"Template not found: {config.template_name}",
                    suggestion="Choose from available templates or use custom configuration"
                ))
                return issues, alternatives
            
            # Validate template configuration
            template_issues = validate_template_config(config.template_name)
            for issue in template_issues:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING.value,
                    category="template",
                    message=f"Template issue: {issue}",
                    suggestion="Review template configuration"
                ))
            
            # Get template compatibility info
            compat_info = get_template_compatibility_info(config.template_name)
            
            # Check key requirements
            if compat_info.get("requires_rsa_keys") and not config.crypto_keys.has_rsa_keys():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.CRITICAL.value,
                    category="keys",
                    message="Template requires RSA keys but none provided",
                    suggestion="Provide bank certificate, partner private key, and partner ID"
                ))
            
            # Suggest alternatives if current template has issues
            if len([i for i in issues if i.severity in [ValidationSeverity.CRITICAL.value, ValidationSeverity.WARNING.value]]) > 0:
                alternatives = self._get_template_alternatives(config.template_name)
        
        return issues, alternatives
    
    def _ai_cross_validate(
        self,
        config: EncryptionConfig,
        documentation: str,
        ctx: Optional[Context]
    ) -> List[ValidationIssue]:
        """Use AI to cross-validate configuration against documentation"""
        if not self.autonomous_agent:
            return []
        
        issues = []
        
        try:
            prompt = f"""
            Cross-validate this encryption configuration against the API documentation:
            
            Configuration:
            - Encryption Type: {config.encryption_type}
            - Placement Strategy: {config.placement_strategy}
            - Key Encryption: {config.algorithms.key_encryption}
            - Payload Encryption: {config.algorithms.payload_encryption}
            - Signature: {config.algorithms.signature}
            - RSA Padding: {config.algorithms.padding.rsa_padding}
            - AES Padding: {config.algorithms.padding.aes_padding}
            
            Documentation:
            {documentation[:2000]}...
            
            Check for:
            1. Algorithm mismatches
            2. Placement strategy conflicts
            3. Missing requirements
            4. Incompatible specifications
            
            Report any discrepancies or concerns.
            """
            
            # Use autonomous agent to validate configuration
            parameters = {
                "prompt": prompt,
                "task": "validate_encryption_configuration",
                "agent_name": "bank-uat-agent",
            }
            response = self.autonomous_agent.execute(parameters)
            
            # Extract content from response
            if response.get("error"):
                self.logger.debug(f"Autonomous agent error: {response['error']}")
                return []
            
            content = response.get("content", "")
            if not content:
                self.logger.debug("No content returned from autonomous agent")
                return []
            
            # Parse AI validation response
            ai_issues = self._parse_ai_validation_response(content)
            issues.extend(ai_issues)
            
        except Exception as e:
            self.logger.debug(f"AI cross-validation failed: {str(e)}")
        
        return issues
    
    def _parse_ai_validation_response(self, response: str) -> List[ValidationIssue]:
        """Parse AI validation response into issues"""
        issues = []
        
        if not response:
            return issues
        
        response_lower = response.lower()
        
        # Look for conflict indicators
        if "mismatch" in response_lower or "conflict" in response_lower:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING.value,
                category="ai_validation",
                message="AI detected potential configuration conflicts",
                suggestion="Review configuration against documentation"
            ))
        
        if "missing" in response_lower:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO.value,
                category="ai_validation",
                message="AI detected potentially missing requirements",
                suggestion="Verify all required fields are configured"
            ))
        
        if "incompatible" in response_lower:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING.value,
                category="ai_validation",
                message="AI detected potential incompatibilities",
                suggestion="Double-check algorithm and padding combinations"
            ))
        
        return issues
    
    def _validate_security_requirements(self, config: EncryptionConfig) -> List[ValidationIssue]:
        """Validate security requirements and best practices"""
        issues = []
        
        # Key size recommendations
        if config.crypto_keys.key_size and config.crypto_keys.key_size < 2048:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING.value,
                category="security",
                message=f"RSA key size {config.crypto_keys.key_size} bits is below recommended 2048 bits",
                suggestion="Use 2048-bit or larger RSA keys for adequate security"
            ))
        
        # Encryption strength assessment
        if config.algorithms.payload_encryption and "128" in config.algorithms.payload_encryption:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO.value,
                category="security",
                message="Using AES-128 - consider AES-256 for higher security",
                suggestion="Upgrade to AES-256 if supported by the bank"
            ))
        
        # Authentication requirements
        if not config.algorithms.signature and config.encryption_type != EncryptionType.NONE.value:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING.value,
                category="security",
                message="No signature algorithm specified - requests may not be authenticated",
                suggestion="Add request signing for authentication"
            ))
        
        return issues
    
    def _generate_improvement_suggestions(
        self,
        config: EncryptionConfig,
        issues: List[ValidationIssue]
    ) -> List[str]:
        """Generate general improvement suggestions"""
        suggestions = []
        
        # Template suggestions
        if not config.template_name:
            suggestions.append("Consider using a predefined template for easier configuration")
        
        # Security suggestions
        critical_issues = [i for i in issues if i.severity == ValidationSeverity.CRITICAL.value]
        if critical_issues:
            suggestions.append("Fix critical issues before proceeding with UAT testing")
        
        warning_issues = [i for i in issues if i.severity == ValidationSeverity.WARNING.value]
        if warning_issues:
            suggestions.append("Review warning issues for potential improvements")
        
        # Performance suggestions
        if config.placement_strategy == PlacementStrategy.MIXED.value:
            suggestions.append("Mixed placement strategy may increase complexity - ensure it's required")
        
        return suggestions
    
    def _generate_recommended_actions(
        self,
        issues: List[ValidationIssue],
        confidence_score: float
    ) -> List[str]:
        """Generate specific recommended actions"""
        actions = []
        
        # Actions based on confidence
        if confidence_score < 0.5:
            actions.append("Manual review recommended due to low confidence score")
        elif confidence_score < 0.7:
            actions.append("Verify configuration with bank documentation")
        
        # Actions based on issues
        critical_count = len([i for i in issues if i.severity == ValidationSeverity.CRITICAL.value])
        if critical_count > 0:
            actions.append(f"Fix {critical_count} critical issue(s) before proceeding")
        
        auto_fixable = [i for i in issues if i.auto_fixable]
        if auto_fixable:
            actions.append(f"Apply {len(auto_fixable)} automatic fix(es)")
        
        # General actions
        actions.append("Test configuration with sample requests")
        actions.append("Validate key files and permissions")
        
        return actions
    
    def _assess_confidence(self, confidence_score: float, issues: List[ValidationIssue]) -> str:
        """Assess overall confidence in the configuration"""
        critical_issues = len([i for i in issues if i.severity == ValidationSeverity.CRITICAL.value])
        
        if critical_issues > 0:
            return "LOW - Critical issues detected"
        elif confidence_score >= 0.8:
            return "HIGH - Configuration appears accurate"
        elif confidence_score >= 0.6:
            return "MEDIUM - Configuration likely correct with minor uncertainties"
        elif confidence_score >= 0.4:
            return "MEDIUM-LOW - Configuration has some uncertainties"
        else:
            return "LOW - Configuration detection was uncertain"
    
    def _calculate_compatibility_score(self, config: EncryptionConfig, issues: List[ValidationIssue]) -> float:
        """Calculate compatibility score based on configuration and issues"""
        base_score = 1.0
        
        # Deduct for issues
        for issue in issues:
            if issue.severity == ValidationSeverity.CRITICAL.value:
                base_score -= 0.3
            elif issue.severity == ValidationSeverity.WARNING.value:
                base_score -= 0.1
            elif issue.severity == ValidationSeverity.INFO.value:
                base_score -= 0.05
        
        # Bonus for template usage
        if config.template_name:
            base_score += 0.1
        
        # Bonus for modern algorithms
        if config.algorithms.padding.rsa_padding == PaddingScheme.OAEP.value:
            base_score += 0.05
        if "SHA256" in str(config.algorithms.signature):
            base_score += 0.05
        
        return max(0.0, min(1.0, base_score))
    
    def _get_template_alternatives(self, current_template: str) -> List[str]:
        """Get alternative template suggestions"""
        alternatives = []
        available_templates = get_available_templates()
        
        for template in available_templates:
            if template["name"] != current_template:
                alternatives.append(template["name"])
        
        return alternatives[:3]  # Top 3 alternatives
    
    def _create_error_report(self, error_msg: str) -> ValidationReport:
        """Create error report when validation fails"""
        return ValidationReport(
            is_valid=False,
            confidence_assessment="ERROR - Validation failed",
            issues=[ValidationIssue(
                severity=ValidationSeverity.CRITICAL.value,
                category="validation",
                message=f"Validation error: {error_msg}",
                suggestion="Check configuration and try again"
            )],
            suggestions=["Review configuration format", "Check for syntax errors"],
            recommended_actions=["Fix validation errors", "Contact support if issue persists"]
        )


class ConfigurationSuggestionEngine:
    """Engine for generating configuration improvement suggestions"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
    
    def generate_suggestions(self, config: EncryptionConfig, context: Dict[str, Any]) -> List[ConfigurationSuggestion]:
        """Generate specific configuration improvement suggestions"""
        suggestions = []
        
        # Algorithm suggestions
        if config.algorithms.signature and "SHA1" in config.algorithms.signature:
            suggestions.append(ConfigurationSuggestion(
                type="algorithm",
                current_value=config.algorithms.signature,
                suggested_value="SHA256withRSA",
                reason="SHA1 is deprecated and less secure than SHA256",
                impact="security",
                confidence=0.9
            ))
        
        # Padding suggestions
        if config.algorithms.padding.rsa_padding == PaddingScheme.PKCS1.value:
            suggestions.append(ConfigurationSuggestion(
                type="padding",
                current_value=PaddingScheme.PKCS1.value,
                suggested_value=PaddingScheme.OAEP.value,
                reason="OAEP provides better security than PKCS1 v1.5",
                impact="security",
                confidence=0.7
            ))
        
        return suggestions


class ValidationReportGenerator:
    """Generates human-readable validation reports"""
    
    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
    
    def generate_markdown_report(self, report: ValidationReport, config: EncryptionConfig) -> str:
        """Generate markdown validation report"""
        md = []
        
        md.append("# Configuration Validation Report")
        md.append("")
        
        # Summary
        md.append("## Summary")
        md.append(f"- **Status**: {'✅ Valid' if report.is_valid else '❌ Invalid'}")
        md.append(f"- **Confidence**: {report.confidence_assessment}")
        md.append(f"- **Compatibility Score**: {report.compatibility_score:.2f}/1.0")
        md.append(f"- **Issues Found**: {len(report.issues)}")
        md.append("")
        
        # Configuration overview
        md.append("## Configuration Overview")
        md.append(f"- **Encryption Type**: {config.encryption_type}")
        md.append(f"- **Template**: {config.template_name or 'Custom'}")
        md.append(f"- **Placement Strategy**: {config.placement_strategy}")
        md.append(f"- **Key Encryption**: {config.algorithms.key_encryption}")
        md.append(f"- **Payload Encryption**: {config.algorithms.payload_encryption}")
        md.append("")
        
        # Issues
        if report.issues:
            md.append("## Issues")
            for issue in report.issues:
                severity_icon = {
                    "critical": "🔴",
                    "warning": "🟡", 
                    "info": "🔵",
                    "suggestion": "💡"
                }.get(issue.severity, "⚪")
                
                md.append(f"### {severity_icon} {issue.severity.title()}: {issue.category.title()}")
                md.append(f"**Issue**: {issue.message}")
                if issue.suggestion:
                    md.append(f"**Suggestion**: {issue.suggestion}")
                md.append("")
        
        # Recommendations
        if report.recommended_actions:
            md.append("## Recommended Actions")
            for action in report.recommended_actions:
                md.append(f"- {action}")
            md.append("")
        
        # Template alternatives
        if report.template_alternatives:
            md.append("## Alternative Templates")
            for template in report.template_alternatives:
                md.append(f"- {template}")
            md.append("")
        
        return "\n".join(md) 