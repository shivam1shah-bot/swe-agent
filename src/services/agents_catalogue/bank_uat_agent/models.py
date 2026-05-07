"""
Bank UAT Agent Service Models

Contains request and response models for the bank UAT agent service.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BankUATAgentRequest(BaseModel):
    """Request model for Bank UAT Agent."""
    
    api_doc_path: str = Field(..., description="Path to API documentation file")
    bank_name: str = Field(..., description="Name of the bank for context")
    uat_host: Optional[str] = Field(None, description="UAT host URL override")
    
    # Encryption Configuration - Updated for three-certificate structure
    generate_encrypted_curls: Optional[bool] = Field(False, description="Whether to generate encrypted cURL commands")
    bank_public_cert_path: Optional[str] = Field(None, description="Path to bank's public certificate for encrypting requests TO bank")
    private_key_path: Optional[str] = Field(None, description="Path to partner's private key for decrypting responses FROM bank")
    partner_public_key_path: Optional[str] = Field(None, description="Path to partner's public key for bank to encrypt responses TO partner")
    public_key_path: Optional[str] = Field(None, description="Legacy: Path to RSA public key file (use bank_public_cert_path instead)")
    encryption_type: Optional[str] = Field("auto_detect", description="Encryption type: rsa, aes, hybrid, none, auto_detect, template, custom")
    encryption_template: Optional[str] = Field(None, description="Pre-defined encryption template: rsa_aes_headers, rsa_aes_body, rsa_aes_mixed, signature_only, aes_legacy, rsa_pure")
    
    # AI Configuration  
    enable_ai_analysis: Optional[bool] = Field(True, description="Whether to enable AI-powered encryption analysis")
    ai_confidence_threshold: Optional[float] = Field(0.6, description="Minimum confidence threshold for AI analysis (0.0-1.0)")
    manual_config_override: Optional[Dict[str, Any]] = Field(None, description="Manual configuration overrides for AI-detected settings")
    
    # Legacy Parameters
    test_scenarios: Optional[List[str]] = Field(["success", "error"], description="Test scenarios")
    timeout_seconds: Optional[int] = Field(60, description="Request timeout (10-300 seconds)")
    include_response_analysis: Optional[bool] = Field(True, description="Enable detailed response analysis")
    custom_headers: Optional[Dict[str, str]] = Field({}, description="Additional HTTP headers")
    custom_prompt: Optional[str] = Field(None, description="Custom requirements for UAT testing") 