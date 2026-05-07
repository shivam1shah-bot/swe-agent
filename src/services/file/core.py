"""
File service core functionality.

Handles file upload validation, processing, and storage.
"""

import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from fastapi import UploadFile, HTTPException, status

from src.providers.config_loader import get_config
from src.services.base import BaseService
from .models import FileUploadResult, FileTypeConfig


class FileService(BaseService):
    """Service for handling file uploads and validation."""

    def __init__(self):
        super().__init__("FileService")
        self._file_type_configs = self._initialize_file_type_configs()

    def _initialize_file_type_configs(self) -> Dict[str, FileTypeConfig]:
        """Initialize file type configurations for legacy file types."""
        config = get_config()

        return {
            "gateway": FileTypeConfig(
                allowed_extensions=config.get("allowed_extensions", {"md", "mdc", "json"}),
                max_size=config.get("max_content_length", 100 * 1024 * 1024),  # 100MB
                upload_subdir=config.get("upload_folder", "uploads"),
                file_prefix=""
            ),
            "document": FileTypeConfig(
                allowed_extensions={".txt", ".md", ".json", ".pdf", ".doc", ".docx"},
                max_size=10 * 1024 * 1024,  # 10MB
                upload_subdir="uploads/documents",
                file_prefix="doc"
            )
        }

    def _validate_file_type(self, file_type: str) -> FileTypeConfig:
        """Validate and get file type configuration."""
        if file_type not in self._file_type_configs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Invalid file_type '{file_type}'. Allowed: {list(self._file_type_configs.keys())}",
                    "file_type": file_type
                }
            )
        return self._file_type_configs[file_type]

    def _validate_filename(self, filename: Optional[str]) -> None:
        """Validate filename is provided."""
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided"
            )

    def _validate_file_extension(self, filename: str, file_type: str,
                                 config: FileTypeConfig) -> str:
        """Validate file extension against allowed extensions."""
        if file_type == "gateway":
            # Legacy validation for backward compatibility
            file_extension = filename.split('.')[-1].lower()
            if file_extension not in config.allowed_extensions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File type '{file_extension}' not allowed. Allowed types: {', '.join(config.allowed_extensions)}"
                )
        else:
            # Enhanced validation with Path
            file_extension = Path(filename).suffix.lower()
            if file_extension not in config.allowed_extensions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": f"Invalid file extension '{file_extension}' for file_type '{file_type}'. Allowed: {list(config.allowed_extensions)}",
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
            self.logger.error(f"UTF-8 decode error reading file {filename}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "File contains invalid binary data or malformed multipart request",
                    "details": "The uploaded file appears to be corrupted or the request is malformed. Please ensure you're uploading a valid file.",
                    "filename": filename,
                    "file_type": file_type
                }
            )
        except Exception as e:
            self.logger.error(f"Error reading file {filename}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Failed to read uploaded file",
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
                    "error": f"File too large. Maximum size for {file_type}: {config.max_size} bytes",
                    "actual_size": file_size,
                    "max_size": config.max_size,
                    "file_type": file_type
                }
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "File is empty",
                    "details": "The uploaded file contains no data. Please ensure you're uploading a valid file with content.",
                    "filename": filename,
                    "file_type": file_type
                }
            )

    def _validate_file_content(self, content: bytes, filename: str, file_type: str,
                               file_extension: str) -> None:
        """Validate file content based on type."""
        if file_type == "pdf" and file_extension == ".pdf":
            # Check if file starts with PDF magic bytes
            if not content.startswith(b'%PDF-'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid PDF file",
                        "details": "The uploaded file does not appear to be a valid PDF document. PDF files must start with '%PDF-'.",
                        "filename": filename,
                        "file_type": file_type
                    }
                )

    def _generate_filename(self, original_filename: str, file_type: str,
                           config: FileTypeConfig) -> tuple[Path, str]:
        """Generate safe filename and full file path."""
        upload_dir = Path(config.upload_subdir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        if file_type == "gateway":
            # Legacy filename generation for backward compatibility
            unique_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{timestamp}_{unique_id}_{original_filename}"
            file_path = upload_dir / safe_filename
            return file_path, safe_filename
        else:
            # Enhanced filename generation with type prefix
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
                              content_type: Optional[str], timestamp: Optional[int] = None) -> FileUploadResult:
        """Create file upload result with appropriate fields."""
        result_data = {
            "success": True,
            "message": f"{file_type.title()} file uploaded successfully",
            "file_path": str(file_path),
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "file_size": file_size,
            "file_type": file_type,
            "content_type": content_type,
        }

        # Add timestamp for non-legacy uploads
        if file_type != "gateway" and timestamp is not None:
            result_data["upload_timestamp"] = timestamp

        # Add type-specific backward compatibility fields
        if file_type == "pdf":
            result_data["pdf_file_path"] = str(file_path)
        elif file_type == "crypto":
            result_data["crypto_file_path"] = str(file_path)
        elif file_type == "document":
            result_data["document_file_path"] = str(file_path)

        return FileUploadResult(**result_data)

    async def upload_file(self, file: UploadFile, file_type: str) -> FileUploadResult:
        """
        Handle file upload with validation and processing.
        
        Delegates to domain-specific services based on file type.
        
        Args:
            file: The uploaded file
            file_type: Type of file determining validation rules and storage location
            
        Returns:
            FileUploadResult with file path and metadata
            
        Raises:
            HTTPException: For validation errors or upload failures
        """
        self._log_operation("upload_file_delegate",
                            upload_filename=file.filename,
                            upload_file_type=file_type)

        # Delegate to domain-specific services
        if file_type in ["bank_crypto", "bank_document"]:
            from src.services.agents_catalogue.bank_uat_agent import BankUATFileUploadService
            bank_service = BankUATFileUploadService()
            return await bank_service.upload_file(file, file_type)

        elif file_type in ["pdf", "crypto"]:
            from src.services.agents_catalogue.api_doc_generator import APIDocGeneratorFileUploadService
            api_doc_service = APIDocGeneratorFileUploadService()
            return await api_doc_service.upload_file(file, file_type)

        # Handle legacy file types (gateway, document) with original logic
        elif file_type in ["gateway", "document"]:
            return await self._handle_legacy_upload(file, file_type)

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Invalid file_type '{file_type}'. Allowed: ['gateway', 'pdf', 'crypto', 'bank_crypto', 'bank_document', 'document']",
                    "file_type": file_type
                }
            )

    async def _handle_legacy_upload(self, file: UploadFile, file_type: str) -> FileUploadResult:
        """Handle legacy file uploads for gateway and document types."""
        try:
            # Validate inputs
            self._validate_filename(file.filename)
            config = self._validate_file_type(file_type)

            # Validate file extension
            file_extension = self._validate_file_extension(file.filename, file_type, config)

            # Read and validate file content
            content = await self._read_file_content(file, file.filename, file_type)
            self._validate_file_size(content, file.filename, file_type, config)
            self._validate_file_content(content, file.filename, file_type, file_extension)

            # Generate filename and save file
            file_path, safe_filename = self._generate_filename(file.filename, file_type, config)
            self._save_file(content, file_path)

            # Log success
            self._log_success("legacy_upload_file",
                              upload_filename=file.filename,
                              saved_path=str(file_path),
                              file_size=len(content),
                              upload_file_type=file_type)

            # Create and return result
            timestamp = int(time.time()) if file_type != "gateway" else None
            return self._create_upload_result(
                file_path, safe_filename, file.filename, len(content),
                file_type, file.content_type, timestamp
            )

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            self._log_error("legacy_upload_file", e,
                            upload_filename=file.filename if file else "unknown",
                            upload_file_type=file_type)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "File upload failed",
                    "error_type": type(e).__name__,
                    "details": "An unexpected error occurred during file upload. Please try again."
                }
            )
