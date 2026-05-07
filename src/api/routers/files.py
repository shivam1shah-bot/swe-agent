"""
File router for FastAPI.

This module provides REST API endpoints for file upload functionality.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
from pydantic import BaseModel, Field

from src.providers.auth import require_role
from src.providers.logger import Logger
from src.services.file import FileService
from src.services.file.parsing_service import FileParsingService
from ..dependencies import get_logger

# Initialize router
router = APIRouter()


# File upload response model
class FileUploadResponse(BaseModel):
    """Response model for file upload."""
    success: bool = Field(..., description="Whether the upload was successful")
    message: str = Field(..., description="Upload status message")
    file_path: Optional[str] = Field(None, description="Server path to the uploaded file")
    original_filename: Optional[str] = Field(None, description="Original filename")
    saved_filename: Optional[str] = Field(None, description="Saved filename")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    file_type: Optional[str] = Field(None, description="File type category")
    content_type: Optional[str] = Field(None, description="MIME content type")
    upload_timestamp: Optional[int] = Field(None, description="Upload timestamp")

    # Type-specific backward compatibility fields
    pdf_file_path: Optional[str] = Field(None, description="PDF file path (for PDF uploads)")
    crypto_file_path: Optional[str] = Field(None, description="Crypto file path (for crypto uploads)")
    document_file_path: Optional[str] = Field(None, description="Document file path (for document uploads)")


# Enhanced File Upload Endpoint
@router.post("/upload-file", response_model=FileUploadResponse)
@require_role(["dashboard", "admin"])
async def upload_file(
        request: Request,
        file: UploadFile = File(...),
        file_type: str = Form(default="document",
                              description="Type of file: 'gateway', 'pdf', 'crypto', 'bank_crypto', 'bank_document', 'document'"),
        logger: Logger = Depends(get_logger)
):
    """
    Enhanced file upload endpoint supporting multiple file types and use cases.
    
    This endpoint handles file uploads with different validation rules and directory structures
    based on the file_type parameter.
    
    Supported file types:
    - gateway: .md, .mdc, .json files for gateway integration (legacy, default behavior)
    - pdf: PDF documents for API documentation extraction (max 50MB)
    - crypto: Crypto specification files for encryption/decryption including PEM keys (max 1MB)  
    - bank_crypto: Bank UAT Agent crypto files (.pem, .key, .crt) for encryption/decryption (max 1MB)
    - bank_document: Bank UAT Agent API documentation files (.txt, .md, .json, .pdf) (max 50MB)
    - document: General document types (max 10MB)
    
    Args:
        file: The uploaded file
        file_type: Type of file determining validation rules and storage location
        
    Returns:
        FileUploadResponse with file path and metadata
        
    Raises:
        HTTPException: For validation errors or upload failures
    """
    try:
        # Initialize file service
        file_service = FileService()

        # Delegate to service layer
        result = await file_service.upload_file(file, file_type)

        # Convert service result to API response
        return FileUploadResponse(**result.model_dump())

    except HTTPException:
        # Re-raise HTTP exceptions from service
        raise
    except UnicodeDecodeError as e:
        # Handle UTF-8 decode errors that might occur during form parsing
        logger.error("UTF-8 decode error during file upload",
                     upload_filename=file.filename if file else "unknown",
                     upload_file_type=file_type if 'file_type' in locals() else 'unknown',
                     error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Malformed multipart request or corrupted file",
                "details": "The request contains invalid UTF-8 data. This usually indicates a corrupted file upload or malformed multipart form data.",
                "suggestion": "Please ensure your file is not corrupted and try uploading again. If using curl, make sure to use -F instead of --data-raw for file uploads."
            }
        )
    except Exception as e:
        logger.error("File upload failed",
                     upload_filename=file.filename if file else "unknown",
                     upload_file_type=file_type if 'file_type' in locals() else 'unknown',
                     error_type=type(e).__name__,
                     error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "File upload failed",
                "error_type": type(e).__name__,
                "details": "An unexpected error occurred during file upload. Please try again."
            }
        )


@router.post("/parse-content")
@require_role(["dashboard", "admin"])
async def parse_content(
        request: Request,
        file: UploadFile = File(...),
        input_type: str = Form(..., description="Type of input: 'image', 'prd', etc."),
        filename: str = Form(default="", description="Optional filename override"),
        logger: Logger = Depends(get_logger)
):
    """
    Parse uploaded file content based on input type.
    
    This endpoint handles parsing of various file types including:
    - image: Image files (PNG, JPG, etc.) - converts to base64
    - prd: PRD documents (Markdown, text) - extracts structured data
    
    Args:
        file: The uploaded file
        input_type: Type of input determining parsing logic
        filename: Optional filename override (defaults to uploaded filename)
        
    Returns:
        Parsed content dictionary with type-specific structure
        
    Raises:
        HTTPException: For validation errors or parsing failures
    """
    try:
        # Use provided filename or file's original filename
        file_name = filename if filename else (file.filename or "unknown")
        
        # Initialize parsing service
        parsing_service = FileParsingService()
        
        # Parse content
        result = parsing_service.parse_content(file, file_name, input_type)
        
        logger.info("File content parsed successfully",
                   filename=file_name,
                   input_type=input_type,
                   result_type=result.get("type"))
        
        return {
            "success": True,
            "data": result
        }
        
    except ValueError as e:
        logger.error("Invalid parsing request",
                    filename=file.filename,
                    input_type=input_type,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid parsing request",
                "details": str(e),
                "input_type": input_type
            }
        )
    except Exception as e:
        logger.error("File parsing failed",
                    filename=file.filename if file else "unknown",
                    input_type=input_type,
                    error_type=type(e).__name__,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "File parsing failed",
                "error_type": type(e).__name__,
                "details": str(e)
            }
        )
