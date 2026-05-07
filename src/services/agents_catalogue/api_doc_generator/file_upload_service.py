"""
File Upload Service for API Doc Generator

Handles PDF and crypto file uploads specific to API documentation generation.
"""

import time
from pathlib import Path

from fastapi import UploadFile, HTTPException, status

from src.services.base import BaseService
from src.services.file.models import FileUploadResult, FileTypeConfig


class APIDocGeneratorFileUploadService(BaseService):
    """Service for handling API doc generator file uploads."""
    
    def __init__(self):
        super().__init__("APIDocGeneratorFileUploadService")
        self._file_type_configs = self._initialize_file_type_configs()
    
    def _initialize_file_type_configs(self) -> dict[str, FileTypeConfig]:
        """Initialize file type configurations for API doc generator."""
        return {
            "pdf": FileTypeConfig(
                allowed_extensions={".pdf"},
                max_size=50 * 1024 * 1024,  # 50MB
                upload_subdir="uploads/api_doc_generator/pdfs",
                file_prefix="pdf_doc"
            ),
            "crypto": FileTypeConfig(
                allowed_extensions={".txt", ".md", ".json", ".pem", ".key", ".crt"},
                max_size=1024 * 1024,  # 1MB
                upload_subdir="uploads/api_doc_generator/crypto",
                file_prefix="crypto_spec"
            )
        }
    
    def _validate_file_type(self, file_type: str) -> FileTypeConfig:
        """Validate and get file type configuration."""
        if file_type not in self._file_type_configs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Invalid file_type '{file_type}' for API Doc Generator. Allowed: {list(self._file_type_configs.keys())}",
                    "file_type": file_type
                }
            )
        return self._file_type_configs[file_type]
    
    def _validate_filename(self, filename: str) -> None:
        """Validate filename is provided."""
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided"
            )
    
    def _validate_file_extension(self, filename: str, file_type: str, 
                                config: FileTypeConfig) -> str:
        """Validate file extension against allowed extensions."""
        file_extension = Path(filename).suffix.lower()
        if file_extension not in config.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Invalid file extension '{file_extension}' for API Doc Generator file_type '{file_type}'. Allowed: {list(config.allowed_extensions)}",
                    "filename": filename,
                    "file_type": file_type
                }
            )
        return file_extension
    
    async def _read_file_content(self, file: UploadFile, filename: str, 
                               file_type: str) -> bytes:
        """Read and validate file content."""
        try:
            content = await file.read()
            return content
        except UnicodeDecodeError as e:
            self.logger.error(f"UTF-8 decode error reading API Doc Generator file {filename}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "File contains invalid binary data or malformed multipart request",
                    "details": "The uploaded file appears to be corrupted or the request is malformed. Please ensure you're uploading a valid file for API documentation generation.",
                    "filename": filename,
                    "file_type": file_type
                }
            )
        except Exception as e:
            self.logger.error(f"Error reading API Doc Generator file {filename}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Failed to read uploaded API Doc Generator file",
                    "details": f"Could not read file content: {str(e)}",
                    "filename": filename,
                    "file_type": file_type
                }
            )
    
    def _validate_file_size(self, content: bytes, filename: str, file_type: str, 
                           config: FileTypeConfig) -> None:
        """Validate file size constraints."""
        file_size = len(content)
        
        if file_size > config.max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "error": f"API Doc Generator file too large. Maximum size for {file_type}: {config.max_size} bytes",
                    "actual_size": file_size,
                    "max_size": config.max_size,
                    "file_type": file_type
                }
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "API Doc Generator file is empty",
                    "details": "The uploaded file contains no data. Please ensure you're uploading a valid file for API documentation generation.",
                    "filename": filename,
                    "file_type": file_type
                }
            )
    
    def _validate_pdf_content(self, content: bytes, filename: str) -> None:
        """Validate PDF-specific file content."""
        # Check if file starts with PDF magic bytes
        if not content.startswith(b'%PDF-'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid PDF file for API documentation generation",
                    "details": "The uploaded file does not appear to be a valid PDF document. PDF files must start with '%PDF-'.",
                    "filename": filename,
                    "file_type": "pdf"
                }
            )
    
    def _validate_crypto_spec_content(self, content: bytes, filename: str, 
                                    file_extension: str) -> None:
        """Validate crypto specification file content."""
        if file_extension == ".pem":
            # Check for PEM format markers
            content_str = content.decode('utf-8', errors='ignore')
            if not any(marker in content_str for marker in [
                "-----BEGIN", "-----END", "CERTIFICATE", "PRIVATE KEY", "PUBLIC KEY"
            ]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid PEM file format for crypto specification",
                        "details": "The uploaded PEM file does not contain valid PEM format markers for API documentation generation.",
                        "filename": filename
                    }
                )
        elif file_extension in [".json", ".txt", ".md"]:
            # Basic validation for text-based crypto specifications
            try:
                content_str = content.decode('utf-8')
                if len(content_str.strip()) == 0:
                    raise ValueError("Empty content")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid text encoding for crypto specification",
                        "details": "The uploaded file must be valid UTF-8 encoded text for API documentation generation.",
                        "filename": filename
                    }
                )
    
    def _generate_filename(self, original_filename: str, file_type: str, 
                          config: FileTypeConfig) -> tuple[Path, str]:
        """Generate safe filename and full file path."""
        upload_dir = Path(config.upload_subdir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = int(time.time())
        safe_filename = f"{config.file_prefix}_{timestamp}_{original_filename}"
        file_path = upload_dir / safe_filename
        return file_path, safe_filename
    
    def _save_file(self, content: bytes, file_path: Path) -> None:
        """Save file content to disk."""
        with open(file_path, 'wb') as f:
            f.write(content)
    
    def _create_upload_result(self, file_path: Path, safe_filename: str, 
                             original_filename: str, file_size: int, file_type: str,
                             content_type: str, timestamp: int) -> FileUploadResult:
        """Create file upload result for API Doc Generator."""
        result_data = {
            "success": True,
            "message": f"API Doc Generator {file_type} file uploaded successfully",
            "file_path": str(file_path),
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "file_size": file_size,
            "file_type": file_type,
            "content_type": content_type,
            "upload_timestamp": timestamp
        }
        
        # Add type-specific backward compatibility fields
        if file_type == "pdf":
            result_data["pdf_file_path"] = str(file_path)
        elif file_type == "crypto":
            result_data["crypto_file_path"] = str(file_path)
        
        return FileUploadResult(**result_data)
    
    async def upload_file(self, file: UploadFile, file_type: str) -> FileUploadResult:
        """
        Handle API Doc Generator file upload with validation and processing.
        
        Args:
            file: The uploaded file
            file_type: Type of file ('pdf' or 'crypto')
            
        Returns:
            FileUploadResult with file path and metadata
            
        Raises:
            HTTPException: For validation errors or upload failures
        """
        self._log_operation("api_doc_generator_upload_file", 
                           upload_filename=file.filename, 
                           upload_file_type=file_type)
        
        try:
            # Validate inputs
            self._validate_filename(file.filename)
            config = self._validate_file_type(file_type)
            
            # Validate file extension
            file_extension = self._validate_file_extension(file.filename, file_type, config)
            
            # Read and validate file content
            content = await self._read_file_content(file, file.filename, file_type)
            self._validate_file_size(content, file.filename, file_type, config)
            
            # Validate content based on file type
            if file_type == "pdf":
                self._validate_pdf_content(content, file.filename)
            elif file_type == "crypto":
                self._validate_crypto_spec_content(content, file.filename, file_extension)
            
            # Generate filename and save file
            file_path, safe_filename = self._generate_filename(file.filename, file_type, config)
            self._save_file(content, file_path)
            
            # Log success
            self._log_success("api_doc_generator_upload_file",
                             upload_filename=file.filename,
                             saved_path=str(file_path),
                             file_size=len(content),
                             upload_file_type=file_type)
            
            # Create and return result
            timestamp = int(time.time())
            return self._create_upload_result(
                file_path, safe_filename, file.filename, len(content),
                file_type, file.content_type, timestamp
            )
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            self._log_error("api_doc_generator_upload_file", e,
                           upload_filename=file.filename if file else "unknown",
                           upload_file_type=file_type)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "API Doc Generator file upload failed",
                    "error_type": type(e).__name__,
                    "details": "An unexpected error occurred during API Doc Generator file upload. Please try again."
                }
            ) 