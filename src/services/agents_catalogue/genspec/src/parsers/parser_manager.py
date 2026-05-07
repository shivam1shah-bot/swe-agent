"""
Parser manager to coordinate all parsers.
"""

import os
import re
from typing import Dict, Any, List, Optional
from src.services.agents_catalogue.genspec.src.parsers.googleurl_extracter import GoogleDriveService
from src.services.agents_catalogue.genspec.src.parsers.base_parser import BaseParser
from src.services.agents_catalogue.genspec.src.parsers.mermaid_parser import MermaidParser
from src.services.agents_catalogue.genspec.src.parsers.prd_parser import PRDParser
from src.services.agents_catalogue.genspec.src.parsers.image_parser import ImageParser


class ParserManager:
    """
    Manager for all parsers.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the parser manager with available parsers."""
        self.parsers = {
            'mermaid': MermaidParser(),
            'prd': PRDParser(),
            'image': ImageParser()
        }
        self.config = config
    
    def parse_content(self, content: str = "", file_path: str = "", repo_path: str = "", is_directory: bool = False, url: str = "", parser_preffered: str = "") -> Dict[str, Any]:
        """
        Parse the content using the appropriate parser.
        """
        try:
            if url:
                file_id = self.extract_file_id_from_url(url)
                google_drive_service = GoogleDriveService(self.config['google_api'])
                auth_url = google_drive_service.authenticate()
                
                # Return the auth URL first
                return {"auth_url": auth_url}

            # Handle file path
            elif file_path:
                if not os.path.exists(file_path):
                    return {"error": f"File not found: {file_path}"}
                    
                # Check if it's an image file
                _, ext = os.path.splitext(file_path.lower())
                if ext in ['.png', '.jpg', '.jpeg', '.gif']:
                    for parser in self.parsers.values():
                        if isinstance(parser, ImageParser):
                            return parser.parse(file_path)
                
                # If not an image, read the file content
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    return {"error": f"Error reading file {file_path}: {str(e)}"}
            
            # Handle repository path - not supported anymore
            if repo_path:
                return {"error": "Code repository parsing is not supported in this version"}
            # Try to find an appropriate parser for content
            if (parser_preffered == "prd"): 
                parser = self.parsers.get('prd')
            elif (parser_preffered == "mermaid"):
                parser = self.parsers.get('mermaid')
            elif (parser_preffered == "image"):
                parser = self.parsers.get('image')
            else:
                parser = self._get_parser_for_content(content)
            
            if parser:
                try:
                    return parser.parse(content)
                except Exception as e:
                    return {
                        "error": f"Error parsing content: {str(e)}",
                        "content_type": parser.__class__.__name__
                    }
            else:
                return {
                    "error": "No suitable parser found for the content",
                    "content": content[:100] + "..." if len(content) > 100 else content
                }
        except Exception as e:
            # self.logger.error(f"Failed to parse content: {e}")
            print(f"Failed to parse content: {e}")
            raise

    def parse_all_types_of_content(self, content: str = "", file_path: str = "", repo_path: str = "", is_directory: bool = False, url: str = "", parser_preffered: str = "") -> Dict[str, Any]:
        """
        Parse the content using the appropriate parser.
        """
        try:
            if url:
                file_id = self.extract_file_id_from_url(url)
                google_drive_service = GoogleDriveService(self.config['google_api'])
                auth_url = google_drive_service.authenticate()
                
                # Return the auth URL first
                return {"auth_url": auth_url}

            # Handle file path
            elif file_path:
                # Check if it's an image file
                _, ext = os.path.splitext(file_path.lower())
                if ext in ['.png', '.jpg', '.jpeg', '.gif']:
                    for parser in self.parsers.values():
                        if isinstance(parser, ImageParser):
                            return parser.parse(file_path)
                
                # If not an image, read the file content
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    return {"error": f"Error reading file {file_path}: {str(e)}"}
            
            # Handle repository path - not supported anymore
            if repo_path:
                return {"error": "Code repository parsing is not supported in this version"}
            # Try to find an appropriate parser for content
            if (parser_preffered == "prd"): 
                parser = self.parsers.get('prd')
            elif (parser_preffered == "mermaid"):
                parser = self.parsers.get('mermaid')
            elif (parser_preffered == "image"):
                parser = self.parsers.get('image')
            else:
                parser = self._get_parser_for_content(content)
            
            if parser:
                try:
                    return parser.parse(content)
                except Exception as e:
                    return {
                        "error": f"Error parsing content: {str(e)}",
                        "content_type": parser.__class__.__name__
                    }
            else:
                return {
                    "error": "No suitable parser found for the content",
                    "content": content[:100] + "..." if len(content) > 100 else content
                }
        except Exception as e:
            # self.logger.error(f"Failed to parse content: {e}")
            print(f"Failed to parse content: {e}")
            raise
    
    def parse_content_after_auth(self, content_with_images: Dict[str, Any], parser_preffered: str = "") -> Dict[str, Any]:
        """
        Parse the content after authorization is confirmed.
        """
        try:
            
            content = content_with_images['text_content']
            images = content_with_images['images']

            # Try to find an appropriate parser for content
            if parser_preffered == "prd":
                parser = self.parsers.get('prd')
            elif parser_preffered == "mermaid":
                parser = self.parsers.get('mermaid')
            elif parser_preffered == "image":
                parser = self.parsers.get('image')
            else:
                parser = self._get_parser_for_content(content)
            
            if parser:
                try:
                    return parser.parse(content)
                except Exception as e:
                    return {
                        "error": f"Error parsing content: {str(e)}",
                        "content_type": parser.__class__.__name__
                    }
            else:
                return {
                    "error": "No suitable parser found for the content",
                    "content": content[:100] + "..." if len(content) > 100 else content
                }
        except Exception as e:
            return {"error": f"Failed to parse content: {str(e)}"}
    
    def _get_parser_for_content(self, content: str) -> Optional[BaseParser]:
        """
        Get the appropriate parser for the given content.
        
        Args:
            content: The content to parse
            
        Returns:
            The appropriate parser or None if no parser can handle the content
        """
        for parser in self.parsers.values():
            if parser.validate(content):
                return parser
        return None
    
    def get_available_parsers(self) -> List[str]:
        """
        Get a list of available parser names.
        
        Returns:
            List of parser names
        """
        return [parser.__class__.__name__ for parser in self.parsers.values()] 

    def extract_file_id_from_url(self, url: str) -> str:
        """
        Extracts the file ID from a Google Docs URL or directly from a file ID.
        
        Args:
            url: The Google Docs URL or file ID.
            
        Returns:
            The file ID as a string.
            
        Raises:
            ValueError: If the URL does not contain a valid file ID.
        """
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
        if match:
            return match.group(1)
        else:
            raise ValueError("Invalid Google Docs URL or file ID: Unable to extract file ID.")
