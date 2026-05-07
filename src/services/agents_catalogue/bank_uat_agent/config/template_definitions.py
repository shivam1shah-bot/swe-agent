"""
Encryption Template Definitions for Bank UAT Agent

Provides pre-defined encryption patterns for common bank API implementations.
Templates make it easy to support different banks without custom configuration.
"""

from typing import Dict, Any, List, Optional
from .encryption_config import (
    EncryptionConfig, AlgorithmConfig, PaddingConfig, CryptoKeys, 
    HeaderConfig, PlacementStrategy, EncryptionType, PaddingScheme
)


# Template definitions for common bank patterns
ENCRYPTION_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "rsa_aes_headers": {
        "name": "RSA+AES Headers-Based",
        "description": "RSA key encryption, AES payload encryption, all auth data in headers (like your specification)",
        "use_cases": ["Modern banks", "Header-based authentication", "Hybrid encryption"],
        "complexity": "Medium",
        "security_level": "High",
        "config": {
            "encryption_type": EncryptionType.TEMPLATE.value,
            "placement_strategy": PlacementStrategy.HEADERS.value,
            "algorithms": {
                "key_encryption": "RSA/ECB/PKCS1Padding",
                "payload_encryption": "AES/CBC/PKCS5Padding",
                "signature": "SHA1withRSA",
                "padding": {
                    "rsa_padding": PaddingScheme.PKCS1.value,
                    "aes_padding": PaddingScheme.PKCS5.value,
                    "signature_padding": PaddingScheme.PKCS1.value
                }
            },
            "headers": {
                "token": {
                    "name": "token",
                    "source": "signature",
                    "encoding": "base64",
                    "description": "SHA1withRSA signature of plain JSON"
                },
                "key": {
                    "name": "key", 
                    "source": "encrypted_aes_key",
                    "encoding": "base64",
                    "description": "AES key encrypted with bank public key"
                },

                "iv": {
                    "name": "iv",
                    "source": "generated_iv",
                    "encoding": "none",
                    "format": "16_digit_numeric",
                    "description": "16-digit numeric initialization vector"
                },
                "content_type": {
                    "name": "Content-Type",
                    "source": "static_value",
                    "encoding": "none",
                    "static_value": "application/json",
                    "description": "Content type header"
                },

            },
            "payload_encryption": {
                "encrypt_full_body": True,
                "field_name": "encrypted_data"
            },
            "generate_encrypted_curls": True
        }
    },
    
    "rsa_aes_body": {
        "name": "RSA+AES Body-Based",
        "description": "RSA key encryption, AES payload encryption, auth data in request body",
        "use_cases": ["Traditional banks", "Body-based authentication", "Legacy compatibility"],
        "complexity": "Medium",
        "security_level": "High",
        "config": {
            "encryption_type": EncryptionType.TEMPLATE.value,
            "placement_strategy": PlacementStrategy.BODY.value,
            "algorithms": {
                "key_encryption": "RSA/ECB/PKCS1Padding",
                "payload_encryption": "AES/CBC/PKCS5Padding",
                "signature": "SHA256withRSA",
                "padding": {
                    "rsa_padding": PaddingScheme.PKCS1.value,
                    "aes_padding": PaddingScheme.PKCS5.value,
                    "signature_padding": PaddingScheme.PKCS1.value
                }
            },
            "body_structure": {
                "auth": {
                    "signature": "signature_value",
                    "key": "encrypted_aes_key",
                    "partner_id": "encrypted_partner_id",
                    "iv": "initialization_vector",
                    "timestamp": "request_timestamp"
                },
                "data": "encrypted_payload"
            },
            "generate_encrypted_curls": True
        }
    },
    
    "rsa_aes_mixed": {
        "name": "RSA+AES Mixed Placement", 
        "description": "RSA key encryption, AES payload encryption, auth split between headers and body",
        "use_cases": ["Modern APIs", "Hybrid placement", "Enhanced security"],
        "complexity": "High",
        "security_level": "Very High",
        "config": {
            "encryption_type": EncryptionType.TEMPLATE.value,
            "placement_strategy": PlacementStrategy.MIXED.value,
            "algorithms": {
                "key_encryption": "RSA/ECB/OAEP",
                "payload_encryption": "AES/CBC/PKCS7Padding",
                "signature": "SHA256withRSA",
                "padding": {
                    "rsa_padding": PaddingScheme.OAEP.value,
                    "aes_padding": PaddingScheme.PKCS7.value,
                    "signature_padding": PaddingScheme.PSS.value
                }
            },
            "headers": {
                "Authorization": {
                    "name": "Authorization",
                    "source": "bearer_signature",
                    "encoding": "base64",
                    "format": "bearer_token"
                },
                "X-Partner-ID": {
                    "name": "X-Partner-ID",
                    "source": "partner_id",
                    "encoding": "none"
                },
                "X-Timestamp": {
                    "name": "X-Timestamp",
                    "source": "timestamp",
                    "encoding": "none"
                }
            },
            "body_structure": {
                "encrypted_data": "aes_encrypted_payload",
                "encryption_metadata": {
                    "iv": "base64_encoded_iv",
                    "key_id": "encrypted_key_reference"
                }
            },
            "generate_encrypted_curls": True
        }
    },
    
    "signature_only": {
        "name": "Signature-Only Authentication",
        "description": "Request signing without payload encryption",
        "use_cases": ["Non-sensitive APIs", "Performance critical", "Legacy systems"],
        "complexity": "Low",
        "security_level": "Medium",
        "config": {
            "encryption_type": EncryptionType.TEMPLATE.value,
            "placement_strategy": PlacementStrategy.HEADERS.value,
            "algorithms": {
                "signature": "SHA256withRSA",
                "padding": {
                    "signature_padding": PaddingScheme.PKCS1.value
                }
            },
            "headers": {
                "signature": {
                    "name": "X-Signature",
                    "source": "signature",
                    "encoding": "base64",
                    "description": "Digital signature of the request payload"
                },

                "timestamp": {
                    "name": "X-Timestamp",
                    "source": "timestamp",
                    "encoding": "none",
                    "description": "Request timestamp"
                },
                "content_type": {
                    "name": "Content-Type",
                    "source": "static_value",
                    "encoding": "none",
                    "static_value": "application/json",
                    "description": "Content type header"
                },
                "api_key": {
                    "name": "X-API-Key",
                    "source": "static_value", 
                    "encoding": "none",
                    "static_value": "your_api_key_here",
                    "description": "Static API key header - replace with actual key"
                }
            },
            "payload_encryption": False,
            "generate_encrypted_curls": False
        }
    },
    
    "aes_legacy": {
        "name": "Legacy AES-Only",
        "description": "AES-only encryption for backward compatibility with UAT_LangGraph",
        "use_cases": ["Legacy systems", "Simple encryption", "Backward compatibility"],
        "complexity": "Low", 
        "security_level": "Medium",
        "config": {
            "encryption_type": EncryptionType.TEMPLATE.value,
            "placement_strategy": PlacementStrategy.BODY.value,
            "algorithms": {
                "payload_encryption": "AES/CBC/PKCS5Padding",
                "padding": {
                    "aes_padding": PaddingScheme.PKCS5.value
                }
            },
            "body_structure": {
                "encrypted_data": "aes_encrypted_payload",
                "iv": "base64_encoded_iv"
            },
            "key_management": {
                "shared_key": "pre_shared_hex_key",
                "key_source": "configuration"
            },
            "generate_encrypted_curls": True
        }
    },
    
    "rsa_pure": {
        "name": "Pure RSA Encryption",
        "description": "RSA-only encryption for small payloads",
        "use_cases": ["Small data", "High security", "No AES requirement"],
        "complexity": "Low",
        "security_level": "High",
        "limitations": ["Max payload size limited by RSA key size"],
        "config": {
            "encryption_type": EncryptionType.TEMPLATE.value,
            "placement_strategy": PlacementStrategy.HEADERS.value,
            "algorithms": {
                "key_encryption": "RSA/ECB/OAEP",
                "signature": "SHA256withRSA",
                "padding": {
                    "rsa_padding": PaddingScheme.OAEP.value,
                    "signature_padding": PaddingScheme.PSS.value
                }
            },
            "headers": {
                "X-Encrypted-Data": {
                    "name": "X-Encrypted-Data",
                    "source": "rsa_encrypted_payload",
                    "encoding": "base64"
                },
                "X-Signature": {
                    "name": "X-Signature",
                    "source": "signature",
                    "encoding": "base64"
                }
            },
            "payload_encryption": False,  # Data goes in headers
            "generate_encrypted_curls": True
        }
    }
}


def get_template_by_name(template_name: str) -> Optional[Dict[str, Any]]:
    """Get encryption template by name"""
    return ENCRYPTION_TEMPLATES.get(template_name)


def get_available_templates() -> List[Dict[str, Any]]:
    """Get list of available templates with metadata"""
    templates = []
    for name, template in ENCRYPTION_TEMPLATES.items():
        templates.append({
            "name": name,
            "display_name": template["name"],
            "description": template["description"],
            "use_cases": template.get("use_cases", []),
            "complexity": template.get("complexity", "Medium"),
            "security_level": template.get("security_level", "Medium"),
            "limitations": template.get("limitations", [])
        })
    return templates


def validate_template_name(template_name: str) -> bool:
    """Validate if template name exists"""
    return template_name in ENCRYPTION_TEMPLATES


def create_config_from_template(template_name: str, overrides: Optional[Dict[str, Any]] = None) -> EncryptionConfig:
    """Create EncryptionConfig from template with optional overrides"""
    template = get_template_by_name(template_name)
    if not template:
        raise ValueError(f"Template '{template_name}' not found")
    
    # Start with template config
    config_data = template["config"].copy()
    config_data["template_name"] = template_name
    
    # Apply overrides if provided
    if overrides:
        config_data.update(overrides)
    
    # Create EncryptionConfig from the data
    return EncryptionConfig.from_dict(config_data)


def get_template_recommendations(bank_name: str, use_case: str = "") -> List[str]:
    """Get template recommendations based on bank name and use case"""
    recommendations = []
    
    bank_lower = bank_name.lower()
    use_case_lower = use_case.lower()
    
    # Bank-specific recommendations (could be enhanced with ML/AI)
    if any(bank in bank_lower for bank in ["hdfc", "icici", "axis", "sbi"]):
        recommendations.append("rsa_aes_headers")  # Most Indian banks use header-based
    
    # Use case recommendations
    if "legacy" in use_case_lower or "backward" in use_case_lower:
        recommendations.append("aes_legacy")
    elif "simple" in use_case_lower or "basic" in use_case_lower:
        recommendations.append("signature_only")
    elif "high security" in use_case_lower or "secure" in use_case_lower:
        recommendations.append("rsa_aes_mixed")
    
    # Default recommendations
    if not recommendations:
        recommendations = ["rsa_aes_headers", "rsa_aes_body", "signature_only"]
    
    return recommendations[:3]  # Return top 3 recommendations


def get_template_compatibility_info(template_name: str) -> Dict[str, Any]:
    """Get compatibility information for a template"""
    template = get_template_by_name(template_name)
    if not template:
        return {}
    
    config = template["config"]
    algorithms = config.get("algorithms", {})
    
    compatibility = {
        "template_name": template_name,
        "requires_rsa_keys": "rsa" in algorithms.get("key_encryption", "").lower(),
        "requires_aes_key": "aes" in algorithms.get("payload_encryption", "").lower(),
        "requires_partner_id": True,  # Most templates require partner ID
        "payload_size_limit": None,
        "supported_algorithms": [],
        "padding_schemes": [],
        "placement_strategy": config.get("placement_strategy", "headers")
    }
    
    # RSA-specific info
    if compatibility["requires_rsa_keys"]:
        compatibility["supported_algorithms"].append("RSA")
        if template_name == "rsa_pure":
            compatibility["payload_size_limit"] = "RSA key size dependent (e.g., 245 bytes for 2048-bit)"
    
    # AES-specific info
    if compatibility["requires_aes_key"]:
        compatibility["supported_algorithms"].append("AES")
        compatibility["payload_size_limit"] = "No limit (AES can encrypt any size)"
    
    # Padding schemes
    padding = algorithms.get("padding", {})
    if padding.get("rsa_padding"):
        compatibility["padding_schemes"].append(f"RSA: {padding['rsa_padding']}")
    if padding.get("aes_padding"):
        compatibility["padding_schemes"].append(f"AES: {padding['aes_padding']}")
    
    return compatibility


# Template validation utilities
def validate_template_config(template_name: str) -> List[str]:
    """Validate template configuration and return any issues"""
    template = get_template_by_name(template_name)
    if not template:
        return [f"Template '{template_name}' not found"]
    
    issues = []
    config = template["config"]
    
    # Check required fields
    if not config.get("placement_strategy"):
        issues.append("Missing placement_strategy")
    
    algorithms = config.get("algorithms", {})
    if not algorithms:
        issues.append("Missing algorithms configuration")
    
    # Check algorithm/padding compatibility
    if algorithms.get("key_encryption", "").startswith("RSA"):
        padding = algorithms.get("padding", {})
        rsa_padding = padding.get("rsa_padding")
        if not rsa_padding or rsa_padding not in [e.value for e in PaddingScheme]:
            issues.append(f"Invalid or missing RSA padding: {rsa_padding}")
    
    return issues


# Export template information for API responses
def get_template_summary() -> Dict[str, Any]:
    """Get summary of all available templates"""
    return {
        "total_templates": len(ENCRYPTION_TEMPLATES),
        "templates": get_available_templates(),
        "categories": {
            "hybrid_rsa_aes": ["rsa_aes_headers", "rsa_aes_body", "rsa_aes_mixed"],
            "rsa_only": ["rsa_pure"],
            "aes_only": ["aes_legacy"],
            "signature_only": ["signature_only"]
        },
        "complexity_levels": {
            "low": ["signature_only", "aes_legacy", "rsa_pure"],
            "medium": ["rsa_aes_headers", "rsa_aes_body"],
            "high": ["rsa_aes_mixed"]
        },
        "security_levels": {
            "medium": ["signature_only", "aes_legacy"],
            "high": ["rsa_aes_headers", "rsa_aes_body", "rsa_pure"],
            "very_high": ["rsa_aes_mixed"]
        }
    }


# Config creation utilities
def create_no_encryption_config(bank_name: str) -> EncryptionConfig:
    """Create a no-encryption configuration as fallback"""
    
    no_encryption_template = {
        "encryption_type": EncryptionType.NONE.value,
        "template_name": "no_encryption",
        "placement_strategy": PlacementStrategy.NONE.value,
        "algorithms": {
            "key_encryption": None,
            "payload_encryption": None,
            "signature": None
        },
        "padding": {},
        "keys": {},
        "headers": {},
        "bank_name": bank_name,
        "description": "No encryption configuration - API calls will be sent in plain text",
        "recommendations": [
            "This configuration disables all encryption",
            "Use only for APIs that do not require encryption",
            "Consider security implications for production use"
        ]
    }
    
    return EncryptionConfig.from_dict(no_encryption_template)


def create_default_config(bank_name: str = "default_bank") -> EncryptionConfig:
    """Create a default encryption configuration"""
    return create_config_from_template("rsa_aes_headers") 