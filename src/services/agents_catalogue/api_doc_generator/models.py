"""
API Documentation Generator Service Models

Contains request and response models for the API documentation generator service.
"""

from typing import Optional
from pydantic import BaseModel, Field


class APIDocGeneratorRequest(BaseModel):
    """Request model for API Documentation Generator."""
    
    document_file_path: str = Field(..., description="Path to PDF/document file")
    bank_name: str = Field(..., description="Name of the bank for context enhancement")
    custom_prompt: Optional[str] = Field(None, description="Additional requirements for documentation")
    output_format: Optional[str] = Field("markdown", description="Output format: txt, json, markdown, all")
    include_examples: Optional[bool] = Field(True, description="Include code examples")
    enhance_context: Optional[bool] = Field(True, description="Use bank-specific context") 