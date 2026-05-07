"""
Base parser interface for parsing different types of inputs.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseParser(ABC):
    """
    Abstract base class for all parsers.
    """
    
    @abstractmethod
    def parse(self, content: str, **kwargs) -> Dict[str, Any]:
        """
        Parse the input content and return structured data.
        
        Args:
            content: The content to parse
            **kwargs: Additional parser-specific arguments
            
        Returns:
            Dictionary containing the parsed data
        """
        pass
    
    @abstractmethod
    def validate(self, content: str) -> bool:
        """
        Validate if the content can be parsed by this parser.
        
        Args:
            content: The content to validate
            
        Returns:
            True if the content can be parsed, False otherwise
        """
        pass
    
    @staticmethod
    def get_parser_for_content(content: str, parsers: list) -> Optional['BaseParser']:
        """
        Get the appropriate parser for the given content.
        
        Args:
            content: The content to parse
            parsers: List of available parsers
            
        Returns:
            The appropriate parser or None if no parser can handle the content
        """
        for parser in parsers:
            if parser.validate(content):
                return parser
        return None 