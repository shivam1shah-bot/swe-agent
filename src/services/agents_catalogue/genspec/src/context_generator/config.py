"""
Configuration module for Context Generator.
"""

import os
import yaml
from typing import Dict, List, Any, Optional


class Config:
    """
    Configuration manager for Context Generator.
    """
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, will look for context.yaml or context.json
                         in the current directory.
        """
        self.config_path = config_path
        self.config_data = {}
        self.prompts = []
        self.imports = []
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Returns:
            Dict containing the configuration data.
        """
        if not self.config_path:
            # Try to find config file in current directory
            if os.path.exists("context.yaml"):
                self.config_path = "context.yaml"
            elif os.path.exists("context.json"):
                self.config_path = "context.json"
            else:
                # Create default config
                self.config_data = {
                    "documents": []
                }
                return self.config_data
        
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                import yaml
                self.config_data = yaml.safe_load(f)
            else:
                import json
                self.config_data = json.load(f)
        
        # Process imports if any
        if "import" in self.config_data:
            self._process_imports(self.config_data["import"])
        
        # Extract prompts
        if "prompts" in self.config_data:
            self.prompts = self.config_data["prompts"]
        
        return self.config_data
    
    def _process_imports(self, imports: List[Dict[str, str]]) -> None:
        """
        Process imports from the configuration.
        
        Args:
            imports: List of import configurations.
        """

        import requests

        for imp in imports:
            if imp.get("type") == "url":
                url = imp.get("url")
                if url:
                    try:
                        response = requests.get(url)
                        response.raise_for_status()
                        
                        if url.endswith('.yaml') or url.endswith('.yml'):
                            import yaml
                            imported_data = yaml.safe_load(response.text)
                        else:
                            import json
                            imported_data = json.loads(response.text)
                        
                        # Merge prompts
                        if "prompts" in imported_data:
                            self.prompts.extend(imported_data["prompts"])
                            
                        # Track imports
                        self.imports.append({
                            "type": "url",
                            "url": url,
                            "status": "success"
                        })
                    except Exception as e:
                        self.imports.append({
                            "type": "url",
                            "url": url,
                            "status": "error",
                            "error": str(e)
                        })
    
    def save(self, path: Optional[str] = None) -> None:
        """
        Save configuration to file.
        
        Args:
            path: Path to save the configuration file. If None, will use the original path.
        """
        save_path = path or self.config_path or "context.yaml"
        
        with open(save_path, 'w') as f:
            if save_path.endswith('.yaml') or save_path.endswith('.yml'):
                import yaml
                yaml.dump(self.config_data, f)
            else:
                import json
                json.dump(self.config_data, f, indent=2)
    
    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a prompt by ID.
        
        Args:
            prompt_id: ID of the prompt to retrieve.
            
        Returns:
            The prompt configuration or None if not found.
        """
        for prompt in self.prompts:
            if prompt.get("id") == prompt_id:
                return prompt
        return None 