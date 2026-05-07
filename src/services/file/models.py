"""
File service models and data structures.

Contains shared models used across file upload services.
"""

from typing import Optional, Set

from pydantic import BaseModel, Field


class FileUploadRequest(BaseModel):
    """Request model for file upload service."""
    file_type: str = Field(..., description="Type of file being uploaded")


class FileUploadResult(BaseModel):
    """Result model for file upload service."""
    success: bool = Field(..., description="Whether the upload was successful")
    message: str = Field(..., description="Upload status message")
    file_path: str = Field(..., description="Server path to the uploaded file")
    original_filename: str = Field(..., description="Original filename")
    saved_filename: str = Field(..., description="Saved filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="File type category")
    content_type: Optional[str] = Field(None, description="MIME content type")
    upload_timestamp: Optional[int] = Field(None, description="Upload timestamp")

    # Type-specific backward compatibility fields
    pdf_file_path: Optional[str] = Field(None, description="PDF file path (for PDF uploads)")
    crypto_file_path: Optional[str] = Field(None, description="Crypto file path (for crypto uploads)")
    document_file_path: Optional[str] = Field(None, description="Document file path (for document uploads)")


class FileTypeConfig:
    """Configuration for different file types."""

    def __init__(self, allowed_extensions: Set[str], max_size: int,
                 upload_subdir: str, file_prefix: str):
        self.allowed_extensions = allowed_extensions
        self.max_size = max_size
        self.upload_subdir = upload_subdir
        self.file_prefix = file_prefix
