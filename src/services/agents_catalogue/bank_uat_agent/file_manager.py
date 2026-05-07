"""
File Manager for Bank UAT Agent

This module provides comprehensive file management capabilities for the bank UAT agent,
including file operations, directory management, and cleanup utilities.
"""

import os
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from src.providers.logger import Logger


class FileManager:
    """File manager for handling file operations and cleanup"""

    def __init__(self, outputs_dir: Path, temp_dir: Path, archive_dir: Path, logger: Logger):
        """
        Initialize the file manager
        
        Args:
            outputs_dir: Directory for output files
            temp_dir: Directory for temporary files
            archive_dir: Directory for archived files
            logger: Logger instance for logging operations
        """
        self.outputs_dir = Path(outputs_dir)
        self.temp_dir = Path(temp_dir)
        self.archive_dir = Path(archive_dir)
        self.logger = logger
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Track created files for cleanup
        self.created_files: List[Path] = []
        self.created_dirs: List[Path] = []

    def _ensure_directories(self):
        """Ensure all required directories exist"""
        for directory in [self.outputs_dir, self.temp_dir, self.archive_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Ensured directory exists: {directory}")

    def create_output_file(self, filename: str, content: str, subdirectory: str = None) -> Path:
        """
        Create an output file with the specified content
        
        Args:
            filename: Name of the file to create
            content: Content to write to the file
            subdirectory: Optional subdirectory within outputs_dir
            
        Returns:
            Path to the created file
        """
        try:
            if subdirectory:
                output_path = self.outputs_dir / subdirectory
                output_path.mkdir(parents=True, exist_ok=True)
            else:
                output_path = self.outputs_dir
            
            file_path = output_path / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.created_files.append(file_path)
            self.logger.info(f"Created output file: {file_path}")
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"Failed to create output file {filename}: {str(e)}")
            raise

    def create_temp_file(self, prefix: str = "temp", suffix: str = ".tmp", content: str = None) -> Path:
        """
        Create a temporary file
        
        Args:
            prefix: File prefix
            suffix: File suffix
            content: Optional content to write
            
        Returns:
            Path to the created temporary file
        """
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                prefix=prefix,
                suffix=suffix,
                dir=self.temp_dir,
                delete=False,
                encoding='utf-8'
            )
            
            if content:
                temp_file.write(content)
            
            temp_file.close()
            temp_path = Path(temp_file.name)
            
            self.created_files.append(temp_path)
            self.logger.debug(f"Created temporary file: {temp_path}")
            
            return temp_path
            
        except Exception as e:
            self.logger.error(f"Failed to create temporary file: {str(e)}")
            raise

    def copy_file(self, source: Union[str, Path], destination: Union[str, Path], overwrite: bool = False) -> Path:
        """
        Copy a file from source to destination
        
        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing files
            
        Returns:
            Path to the copied file
        """
        try:
            source_path = Path(source)
            dest_path = Path(destination)
            
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")
            
            if dest_path.exists() and not overwrite:
                raise FileExistsError(f"Destination file already exists: {dest_path}")
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(source_path, dest_path)
            
            self.created_files.append(dest_path)
            self.logger.info(f"Copied file from {source_path} to {dest_path}")
            
            return dest_path
            
        except Exception as e:
            self.logger.error(f"Failed to copy file from {source} to {destination}: {str(e)}")
            raise

    def move_file(self, source: Union[str, Path], destination: Union[str, Path], overwrite: bool = False) -> Path:
        """
        Move a file from source to destination
        
        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing files
            
        Returns:
            Path to the moved file
        """
        try:
            source_path = Path(source)
            dest_path = Path(destination)
            
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")
            
            if dest_path.exists() and not overwrite:
                raise FileExistsError(f"Destination file already exists: {dest_path}")
            
            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(source_path), str(dest_path))
            
            self.created_files.append(dest_path)
            self.logger.info(f"Moved file from {source_path} to {dest_path}")
            
            return dest_path
            
        except Exception as e:
            self.logger.error(f"Failed to move file from {source} to {destination}: {str(e)}")
            raise

    def archive_file(self, file_path: Union[str, Path], archive_name: str = None) -> Path:
        """
        Archive a file to the archive directory
        
        Args:
            file_path: Path to the file to archive
            archive_name: Optional custom archive name
            
        Returns:
            Path to the archived file
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if not archive_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            
            archive_path = self.archive_dir / archive_name
            
            # Ensure archive directory exists
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(file_path, archive_path)
            
            self.logger.info(f"Archived file {file_path} to {archive_path}")
            
            return archive_path
            
        except Exception as e:
            self.logger.error(f"Failed to archive file {file_path}: {str(e)}")
            raise

    def cleanup_temp_files(self, max_age_hours: int = 24):
        """
        Clean up temporary files older than specified age
        
        Args:
            max_age_hours: Maximum age in hours for temporary files
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            cleaned_count = 0
            
            for temp_file in self.temp_dir.glob("*"):
                if temp_file.is_file():
                    file_age = datetime.fromtimestamp(temp_file.stat().st_mtime)
                    if file_age < cutoff_time:
                        try:
                            temp_file.unlink()
                            cleaned_count += 1
                            self.logger.debug(f"Cleaned up old temporary file: {temp_file}")
                        except Exception as e:
                            self.logger.warning(f"Failed to clean up temporary file {temp_file}: {str(e)}")
            
            self.logger.info(f"Cleaned up {cleaned_count} old temporary files")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup temporary files: {str(e)}")

    def cleanup_created_files(self):
        """Clean up all files created by this file manager instance"""
        try:
            cleaned_count = 0
            
            for file_path in self.created_files:
                if file_path.exists():
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                        self.logger.debug(f"Cleaned up created file: {file_path}")
                    except Exception as e:
                        self.logger.warning(f"Failed to clean up file {file_path}: {str(e)}")
            
            self.created_files.clear()
            self.logger.info(f"Cleaned up {cleaned_count} created files")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup created files: {str(e)}")

    def manual_cleanup_if_needed(self):
        """Manual cleanup method called by the service when needed"""
        try:
            self.cleanup_temp_files()
            self.logger.info("Manual cleanup completed")
        except Exception as e:
            self.logger.warning(f"Manual cleanup failed: {str(e)}")

    def get_file_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get information about a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary containing file information
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                return {"exists": False, "error": "File not found"}
            
            stat = file_path.stat()
            
            return {
                "exists": True,
                "path": str(file_path),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_file": file_path.is_file(),
                "is_directory": file_path.is_dir(),
                "permissions": oct(stat.st_mode)[-3:]
            }
            
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def list_files(self, directory: Union[str, Path] = None, pattern: str = "*") -> List[Dict[str, Any]]:
        """
        List files in a directory with optional pattern matching
        
        Args:
            directory: Directory to list (defaults to outputs_dir)
            pattern: File pattern to match
            
        Returns:
            List of file information dictionaries
        """
        try:
            if directory is None:
                directory = self.outputs_dir
            else:
                directory = Path(directory)
            
            if not directory.exists():
                return []
            
            files = []
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    files.append(self.get_file_info(file_path))
            
            return files
            
        except Exception as e:
            self.logger.error(f"Failed to list files in {directory}: {str(e)}")
            return []

    def get_directory_size(self, directory: Union[str, Path] = None) -> Dict[str, Any]:
        """
        Get the total size of a directory
        
        Args:
            directory: Directory to measure (defaults to outputs_dir)
            
        Returns:
            Dictionary containing size information
        """
        try:
            if directory is None:
                directory = self.outputs_dir
            else:
                directory = Path(directory)
            
            if not directory.exists():
                return {"size_bytes": 0, "size_mb": 0, "file_count": 0}
            
            total_size = 0
            file_count = 0
            
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1
            
            return {
                "size_bytes": total_size,
                "size_mb": round(total_size / (1024 * 1024), 2),
                "file_count": file_count
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get directory size for {directory}: {str(e)}")
            return {"size_bytes": 0, "size_mb": 0, "file_count": 0, "error": str(e)} 