"""
File Download Service for Agents Catalogue

This service provides generic file download functionality for all agents,
eliminating the need for hardcoded use case logic in the API layer.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from src.providers.logger import Logger
from src.services.agents_catalogue.registry import get_service_for_usecase


class FileDownloadService:
    """Generic file download service for all agents."""
    
    def __init__(self, logger: Logger):
        self.logger = logger
    
    def get_file_for_download(
        self, 
        usecase_name: str, 
        task_id: str, 
        file_type: str
    ) -> Tuple[Optional[Path], str]:
        """
        Get file path and filename for download for any use case.
        
        Args:
            usecase_name: Name of the agent (e.g., 'bank-uat-agent', 'api-doc-generator')
            task_id: Task identifier
            file_type: Type of file to download
            
        Returns:
            Tuple of (file_path, suggested_filename) where file_path is None if not found
        """
        try:
            # Get the service for this use case
            service = get_service_for_usecase(usecase_name)
            if not service:
                self.logger.error(f"No service found for use case: {usecase_name}")
                return None, ""
            
            # Check if service has file download capabilities
            if hasattr(service, 'get_downloadable_files'):
                return self._get_file_via_service(service, task_id, file_type)
            else:
                # Fallback to generic file discovery
                return self._get_file_via_generic_discovery(usecase_name, task_id, file_type)
                
        except Exception as e:
            self.logger.exception(f"Error getting file for download", 
                                usecase_name=usecase_name, task_id=task_id, 
                                file_type=file_type, error=str(e))
            return None, ""
    
    def _get_file_via_service(
        self, 
        service, 
        task_id: str, 
        file_type: str
    ) -> Tuple[Optional[Path], str]:
        """Get file using service's downloadable files method."""
        try:
            downloadable_files = service.get_downloadable_files(task_id)
            
            if file_type not in downloadable_files:
                self.logger.warning(f"File type '{file_type}' not available", 
                                  task_id=task_id,
                                  available_types=list(downloadable_files.keys()))
                return None, ""
            
            file_info = downloadable_files[file_type]
            file_path = Path(file_info['path'])
            filename = file_info.get('filename', f"{file_type}_{task_id}.txt")
            
            if file_path.exists():
                self.logger.info(f"File found via service method", 
                               task_id=task_id, file_type=file_type, 
                               file_path=str(file_path))
                return file_path, filename
            else:
                self.logger.warning(f"File path from service does not exist", 
                                  task_id=task_id, file_type=file_type,
                                  file_path=str(file_path))
                return None, filename
                
        except Exception as e:
            self.logger.exception(f"Error getting file via service method", 
                                task_id=task_id, file_type=file_type, error=str(e))
            return None, ""
    
    def _get_file_via_generic_discovery(
        self, 
        usecase_name: str, 
        task_id: str, 
        file_type: str
    ) -> Tuple[Optional[Path], str]:
        """Fallback generic file discovery for services without download methods."""
        self.logger.info(f"Using generic file discovery for {usecase_name}")
        
        # Generic filename pattern
        filename = f"{file_type}_{task_id}.txt"
        
        # Common output directory patterns to search
        search_paths = [
            # Standard uploads pattern
            Path(f"uploads/{usecase_name}/outputs") / filename,
            # Alternative uploads pattern  
            Path(f"/app/uploads/{usecase_name}/outputs") / filename,
            # Temporary directory pattern
            Path(f"tmp/{usecase_name}") / task_id / filename,
            # Simple outputs pattern
            Path(f"outputs/{usecase_name}") / filename,
            # Direct task directory
            Path(task_id) / filename,
        ]
        
        # Try different file extensions
        extensions = ['.txt', '.md', '.json', '.html', '.csv']
        
        for base_path in search_paths:
            # Try exact match first
            if base_path.exists():
                self.logger.info(f"Found file via generic discovery", 
                               task_id=task_id, file_type=file_type,
                               file_path=str(base_path))
                return base_path, base_path.name
            
            # Try different extensions
            for ext in extensions:
                ext_path = base_path.with_suffix(ext)
                if ext_path.exists():
                    suggested_filename = f"{file_type}_{task_id}{ext}"
                    self.logger.info(f"Found file with extension {ext}", 
                                   task_id=task_id, file_type=file_type,
                                   file_path=str(ext_path))
                    return ext_path, suggested_filename
        
        self.logger.warning(f"File not found in any search paths", 
                          task_id=task_id, file_type=file_type,
                          usecase_name=usecase_name,
                          searched_paths=[str(p) for p in search_paths])
        return None, filename
    
    def get_supported_file_types(self, usecase_name: str) -> List[str]:
        """
        Get supported file types for a use case.
        
        Args:
            usecase_name: Name of the agent
            
        Returns:
            List of supported file types
        """
        try:
            service = get_service_for_usecase(usecase_name)
            if not service:
                return []
            
            if hasattr(service, 'get_supported_file_types'):
                return service.get_supported_file_types()
            elif hasattr(service, 'get_downloadable_files'):
                # Try to get types from a sample call
                try:
                    sample_files = service.get_downloadable_files("sample")
                    return list(sample_files.keys()) if sample_files else []
                except:
                    return []
            else:
                # Generic file types
                return ["results", "report", "output", "log"]
                
        except Exception as e:
            self.logger.exception(f"Error getting supported file types", 
                                usecase_name=usecase_name, error=str(e))
            return []


def get_file_download_service(logger: Logger) -> FileDownloadService:
    """Factory function to create file download service."""
    return FileDownloadService(logger) 