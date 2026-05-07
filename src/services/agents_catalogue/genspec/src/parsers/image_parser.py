"""
Parser for image files (PNG, JPEG, etc.).
"""

import os
import base64
from typing import Dict, Any, Optional
from src.services.agents_catalogue.genspec.src.parsers.base_parser import BaseParser


class ImageParser(BaseParser):
    """
    Parser for image files.
    """
    
    def __init__(self):
        """
        Initialize the image parser.
        """
        # Supported image extensions
        self.supported_extensions = ['.png', '.jpg', '.jpeg', '.gif']
    
    def validate(self, content: str) -> bool:
        """
        Validate if the content is an image file path.

        Args:
            content: The content to validate (file path)
            
        Returns:
            True if the content is an image file path, False otherwise
        """
        # Check if content is a file path to an image
        if not content:
            return False
        
        # If content is a file path
        if os.path.isfile(content):
            _, ext = os.path.splitext(content.lower())
            return ext in self.supported_extensions
        
        return False
    
    def parse(self, content: str, **kwargs) -> Dict[str, Any]:
        """
        Parse an image file.
        
        Args:
            content: The file path to the image
            **kwargs: Additional parser-specific arguments
            
        Returns:
            Dictionary containing the parsed image data
        """
        if not self.validate(content):
            return {"error": "Invalid image file path"}
        
        try:
            # Get file information
            file_path = content
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            _, file_ext = os.path.splitext(file_path.lower())
            
            # Read the image file as binary
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            # Encode the image as base64
            base64_data = base64.b64encode(image_data).decode('utf-8')
            # Determine the image type
            image_type = file_ext.replace('.', '')
            if image_type == 'jpg':
                image_type = 'jpeg'
            
            return {
                "type": "image",
                "content": file_path,  # Store the file path
                "file_name": file_name,
                "file_size": file_size,
                "file_extension": file_ext,
                "image_type": image_type,
                "base64_data": base64_data,
                "data_uri": f"data:image/{image_type};base64,{base64_data}"
            }
        except Exception as e:
            return {
                "error": f"Error parsing image: {str(e)}",
                "content": content
            } 
    
    def parseBase64(self, base64_data: str, image_type: str) -> Dict[str, Any]:
        """
        Parse an image from base64 data.
        
        Args:
            base64_data: The base64 encoded image data
            
        Returns:
            Dictionary containing the parsed image data
        """
        try:
            base64_bytes = base64_data.encode('utf-8')
            # Encode the image as base64
            base64_data = base64.b64encode(base64_bytes)
            
            return {
                "type": "image",
                "base64_data": base64_data,
                "data_uri": f"data:image/{image_type};base64,{base64_data}"
            }
        except Exception as e:
            return {
                "error": f"Error parsing base64 image: {str(e)}",
                "base64_data": base64_data
            }