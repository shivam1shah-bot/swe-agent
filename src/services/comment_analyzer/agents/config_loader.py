"""
Sub-Agent Configuration Loader

Utility for loading and merging sub-agent configurations from JSON files.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SubAgentConfigLoader:
    """Loads and manages sub-agent configurations"""

    # Base directory for config files
    CONFIG_DIR = Path(__file__).parent / "configs"

    @classmethod
    def load_config(cls, sub_agent_name: str) -> Dict[str, Any]:
        """
        Load configuration for a sub-agent from its JSON config file.

        Args:
            sub_agent_name: Name of the sub-agent (e.g., "i18n", "security")

        Returns:
            Dictionary containing the configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        config_file = cls.CONFIG_DIR / f"{sub_agent_name}.json"

        if not config_file.exists():
            raise FileNotFoundError(
                f"Config file not found for sub-agent '{sub_agent_name}' at {config_file}"
            )

        logger.info(f"Loading config for sub-agent '{sub_agent_name}' from {config_file}")

        with open(config_file, 'r') as f:
            config = json.load(f)

        logger.info(f"✓ Config loaded for '{sub_agent_name}'")
        return config

    @classmethod
    def merge_config(cls, default_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two configuration dictionaries.

        Override config takes precedence over default config.
        Nested dictionaries are merged recursively.

        Args:
            default_config: Default configuration
            override_config: Override configuration

        Returns:
            Merged configuration dictionary
        """
        merged = default_config.copy()

        for key, value in override_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # Deep merge for nested dictionaries
                merged[key] = cls.merge_config(merged[key], value)
            else:
                # Direct override for non-dict values or new keys
                merged[key] = value

        return merged

    @classmethod
    def load_and_merge(cls, sub_agent_name: str, override_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Load default config from JSON file and merge with runtime overrides.

        Args:
            sub_agent_name: Name of the sub-agent
            override_config: Optional runtime configuration to merge

        Returns:
            Merged configuration dictionary
        """
        default_config = cls.load_config(sub_agent_name)

        if override_config:
            logger.info(f"Merging runtime config overrides for '{sub_agent_name}'")
            return cls.merge_config(default_config, override_config)

        return default_config

    @classmethod
    def list_available_configs(cls) -> list[str]:
        """
        List all available sub-agent configurations.

        Returns:
            List of sub-agent names that have config files
        """
        if not cls.CONFIG_DIR.exists():
            return []

        config_files = cls.CONFIG_DIR.glob("*.json")
        return [f.stem for f in config_files]
