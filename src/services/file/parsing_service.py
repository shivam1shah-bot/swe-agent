"""
File parsing service for handling various file formats and content types.

This service provides parsing functionality for PRD documents, images,
and other content formats used by the agents catalogue.
"""

import base64
import re
from typing import Dict, Any
from fastapi import UploadFile
from src.providers.logger import Logger


def _consolidate_architecture_image_for_ui(parsed_data: Dict[str, Any], text_content: str = None) -> Dict[str, Any]:
    """
    Consolidate architecture image to single location for UI display.
    
    This function finds architecture images from various locations in parsed data
    and consolidates them to a single location for consistent UI rendering.
    
    Args:
        parsed_data: Parsed data from PRD parser
        text_content: Optional raw text content to search for image references
        
    Returns:
        Parsed data with consolidated architecture image
    """
    try:
        # Create a copy to avoid modifying original
        consolidated = parsed_data.copy()
        
        # Find architecture image from various locations
        architecture_image = None
        
        # Check sections.current_architecture first
        if 'sections' in consolidated and isinstance(consolidated['sections'], dict):
            sections = consolidated['sections']
            if 'current_architecture' in sections and isinstance(sections['current_architecture'], str):
                if sections['current_architecture'].startswith('data:image/'):
                    architecture_image = sections['current_architecture']
        
        # If no architecture image found in sections, search for image references in the raw content
        if not architecture_image and text_content:
            # Look for image references in the format [image1]: <data:image/png;base64,...>
            image_refs = re.findall(r'\[image\d+\]: <(data:image/[^>]+)>', text_content)
            if image_refs:
                architecture_image = image_refs[0]  # Use the first image found
        
        # Also check if there are any image references in the sections content
        if not architecture_image and 'sections' in consolidated:
            for section_name, section_content in consolidated['sections'].items():
                if isinstance(section_content, str):
                    # Look for image references in section content
                    image_refs = re.findall(r'\[image\d+\]: <(data:image/[^>]+)>', section_content)
                    if image_refs:
                        architecture_image = image_refs[0]
                        break
        
        # If we found an architecture image, consolidate it to architecture.content
        if architecture_image:
            # Create architecture object
            consolidated['architecture'] = {
                'content': architecture_image,
                'type': 'image',
                'file_name': 'architecture_diagram.png'
            }
            
            # Remove from sections to avoid duplication
            if 'sections' in consolidated and 'current_architecture' in consolidated['sections']:
                del consolidated['sections']['current_architecture']
        
        return consolidated
        
    except Exception as e:
        return parsed_data


class FileParsingService:
    """Service for parsing various file formats."""

    def __init__(self):
        """Initialize the file parsing service."""
        self.logger = Logger(__name__)

    def parse_content(self, file: UploadFile, filename: str, input_type: str) -> Dict[str, Any]:
        """
        Parse uploaded content based on type.
        
        Args:
            file: Uploaded file object
            filename: Name of the file
            input_type: Type of input (image, prd, etc.)
            
        Returns:
            Parsed content dictionary
        """
        try:
            if input_type == "image":
                return self._parse_image(file, filename)
            elif input_type == "prd":
                return self._parse_prd(file)
            else:
                raise ValueError(f"Unsupported input type: {input_type}")
        except Exception as e:
            self.logger.error(f"Error parsing content: {str(e)}")
            raise

    def _parse_image(self, file: UploadFile, filename: str) -> Dict[str, Any]:
        """Parse image file and convert to base64."""
        file_content = file.file.read()
        base64_data = base64.b64encode(file_content).decode('utf-8')
        file_extension = filename.split('.')[-1]
        
        return {
            "type": "image",
            "content": filename,
            "file_name": filename,
            "file_extension": file_extension,
            "image_type": file_extension,
            "base64_data": base64_data,
            "data_uri": f"data:{file_extension};base64,{base64_data}"
        }

    def _parse_prd(self, file: UploadFile) -> Dict[str, Any]:
        """Parse PRD document."""
        from src.services.agents_catalogue.genspec.src.parsers.prd_parser import PRDParser
        
        file_content = file.file.read()
        decoded_content = file_content.decode('utf-8')
        
        prd_parser = PRDParser()
        parsed_data = prd_parser.parse(decoded_content)
        
        return {
            "title": parsed_data.get("title"),
            "sections": parsed_data.get("sections"),
            "requirements": parsed_data.get("requirements"),
            "user_stories": parsed_data.get("user_stories")
        }

    def parse_google_doc(self, doc_url: str, oauth_provider) -> Dict[str, Any]:
        """
        Parse Google Doc content.
        
        Args:
            doc_url: Google Doc URL
            oauth_provider: OAuth provider instance
            
        Returns:
            Parsed content dictionary
        """
        try:
            # Extract file ID from URL
            from src.services.agents_catalogue.genspec.src.parsers.parser_manager import ParserManager
            from src.providers.config_loader import get_config
            
            config = get_config()
            parser_manager = ParserManager(config)
            file_id = parser_manager.extract_file_id_from_url(doc_url)
            
            # Fetch content
            doc_content = oauth_provider.get_google_doc_content(file_id)
            
            if not doc_content or len(doc_content.strip()) < 10:
                raise ValueError("Google Doc appears to be empty or inaccessible")
            
            # Parse content
            from src.services.agents_catalogue.genspec.src.parsers.prd_parser import PRDParser
            prd_parser = PRDParser()
            
            try:
                parsed_data = prd_parser.parse(doc_content)
            except Exception as e:
                self.logger.warning(f"Error parsing PRD content, returning raw: {str(e)}")
                parsed_data = {
                    "title": "Parsed Google Doc",
                    "sections": {"raw_content": doc_content},
                    "requirements": [],
                    "user_stories": []
                }
            
            # Consolidate architecture image
            consolidated_parsed_data = _consolidate_architecture_image_for_ui(parsed_data, doc_content)
            
            return {
                "text_content": doc_content,
                "parsed_data": consolidated_parsed_data
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing Google Doc: {str(e)}")
            raise

