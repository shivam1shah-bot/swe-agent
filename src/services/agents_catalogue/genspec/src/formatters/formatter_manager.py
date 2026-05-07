"""
Formatter manager to coordinate all formatters.
"""

from typing import Dict, Any, List, Optional
from .formatter import BaseFormatter
from .markdown_formatter import MarkdownFormatter
from .html_formatter import HTMLFormatter
import os


class FormatterManager:
    """
    Manager for all formatters.
    """
    
    def __init__(self):
        """
        Initialize the formatter manager with all available formatters.
        """
        self.formatters = {
            "markdown": MarkdownFormatter(),
            "html": HTMLFormatter()
        }
    
    def format_spec(self, spec_data: Dict[str, Any], format_type: str = "markdown", **kwargs) -> str:
        """
        Format specification data using the specified formatter.
        
        Args:
            spec_data: The specification data to format
            format_type: The type of formatter to use
            **kwargs: Additional formatter-specific arguments
            
        Returns:
            Formatted specification as a string
        """
        formatter = self.get_formatter(format_type)
        
        if formatter:
            try:
                return formatter.format(spec_data, **kwargs)
            except Exception as e:
                return f"Error formatting specification: {str(e)}"
        else:
            return f"No formatter found for format type: {format_type}"
    
    def get_formatter(self, format_type: str) -> Optional[BaseFormatter]:
        """
        Get a formatter by type.
        
        Args:
            format_type: The type of formatter to get
            
        Returns:
            The formatter or None if not found
        """
        return self.formatters.get(format_type.lower())
    
    def get_available_formats(self) -> List[str]:
        """
        Get a list of available format types.
        
        Returns:
            List of format types
        """
        return list(self.formatters.keys())
    
    def save_formatted_spec(self, spec_data: Dict[str, Any], output_path: str, 
                           format_type: str = "markdown", **kwargs) -> str:
        """
        Format and save specification to a file.
        
        Args:
            spec_data: The specification data to format
            output_path: The base path to save the file (without extension)
            format_type: The type of formatter to use
            **kwargs: Additional formatter-specific arguments
            
        Returns:
            Path to the saved file or error message
        """
        formatter = self.get_formatter(format_type)
        
        if not formatter:
            return f"No formatter found for format type: {format_type}"
        
        try:
            formatted_content = formatter.format(spec_data, **kwargs)
            extension = formatter.get_extension()
            
            # Add extension if not already present
            if not output_path.endswith(f".{extension}"):
                output_path = f"{output_path}.{extension}"
            
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            
            return output_path
        except Exception as e:
            return f"Error saving formatted specification: {str(e)}" 