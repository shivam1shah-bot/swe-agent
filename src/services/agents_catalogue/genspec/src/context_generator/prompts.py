"""
Prompts module for Context Generator.

This module provides functionality for loading and managing prompts from various sources.
"""

import os
import json
import yaml
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Manager for loading and retrieving prompts.
    """
    
    def __init__(self):
        """
        Initialize the prompt manager.
        """
        self.prompts = {}
    
    def load_prompts_from_config(self, config_data: Dict[str, Any]) -> None:
        """
        Load prompts from configuration data.
        
        Args:
            config_data: Configuration data containing prompts.
        """
        if "prompts" in config_data:
            for prompt in config_data["prompts"]:
                prompt_id = prompt.get("id")
                if prompt_id:
                    self.prompts[prompt_id] = prompt
                    logger.debug(f"Loaded prompt: {prompt_id}")
    
    def load_prompts_from_file(self, file_path: str) -> None:
        """
        Load prompts from a file.
        
        Args:
            file_path: Path to the file containing prompts.
        """
        if not os.path.exists(file_path):
            logger.error(f"Prompt file not found: {file_path}")
            return
        
        try:
            with open(file_path, 'r') as f:
                if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
                
                if "prompts" in data:
                    for prompt in data["prompts"]:
                        prompt_id = prompt.get("id")
                        if prompt_id:
                            self.prompts[prompt_id] = prompt
                            logger.debug(f"Loaded prompt: {prompt_id}")
        except Exception as e:
            logger.error(f"Error loading prompts from file {file_path}: {str(e)}")
    
    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a prompt by ID.
        
        Args:
            prompt_id: ID of the prompt to retrieve.
            
        Returns:
            The prompt configuration or None if not found.
        """
        return self.prompts.get(prompt_id)
    
    def get_prompt_content(self, prompt_id: str) -> Optional[str]:
        """
        Get the content of a prompt by ID.
        
        Args:
            prompt_id: ID of the prompt to retrieve.
            
        Returns:
            The prompt content or None if not found.
        """
        prompt = self.get_prompt(prompt_id)
        if prompt and "messages" in prompt:
            for message in prompt["messages"]:
                if message.get("role") == "user" and "content" in message:
                    return message["content"]
        return None
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """
        Get a list of all available prompts.
        
        Returns:
            List of prompt configurations.
        """
        return list(self.prompts.values()) 