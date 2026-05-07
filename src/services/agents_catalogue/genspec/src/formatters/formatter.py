"""
Base formatter interface for formatting specification outputs.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseFormatter(ABC):
    """
    Abstract base class for all formatters.
    """
    
    @abstractmethod
    def format(self, spec_data: Dict[str, Any], **kwargs) -> str:
        """
        Format the specification data into the desired output format.
        
        Args:
            spec_data: The specification data to format
            **kwargs: Additional formatter-specific arguments
            
        Returns:
            Formatted specification as a string
        """
        pass
    
    @abstractmethod
    def get_extension(self) -> str:
        """
        Get the file extension for this formatter's output.
        
        Returns:
            File extension (e.g., "md", "html", "pdf")
        """
        pass 