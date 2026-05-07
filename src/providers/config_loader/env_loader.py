"""
Environment configuration loader that loads from TOML files.
"""

import os
import toml
from typing import Dict, Any, Optional, Union
from pathlib import Path


class EnvConfigLoader:
    """
    Configuration loader that loads settings from TOML files in a layered approach.

    The load order is as follows, with later files overriding earlier ones:
    1. Base template: `environments/env.default.toml`
    2. Environment template: `environments/env.{APP_ENV}.toml`
    3. Local base override: `environments/env.default.local.toml` (optional, gitignored)
    4. Local environment override: `environments/env.{APP_ENV}.local.toml` (optional, gitignored)
    """

    def __init__(self, env_name: Optional[str] = None):
        """
        Initialize the config loader.

        Args:
            env_name: Environment name (dev, stage, prod, dev_docker). If None, uses APP_ENV from environment.
        """
        self.env_name = env_name or os.getenv("APP_ENV", "dev")
        self.config: Dict[str, Any] = {}

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """
        Load configuration from TOML files, applying overrides in a specific order.
        """
        project_root = Path.cwd()
        environments_dir = project_root / "environments"

        # Define the load order
        load_paths = [
            environments_dir / "env.default.toml",
            environments_dir / f"env.{self.env_name}.toml",
        ]

        for path in load_paths:
            self._load_toml_file(path)

    def _load_toml_file(self, file_path: Path) -> None:
        """
        Load configuration from a specific TOML file if it exists.

        Args:
            file_path: Path to the TOML file to load
        """
        if not file_path.exists():
            # The base default config is the only one that we might consider "required".
            # All others are optional (env-specific, or local overrides).
            if file_path.name == "env.default.toml":
                 print(f"Warning: Default template config file not found at {file_path}")
            return

        print(f"Loading config from: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                toml_config = toml.load(f)
                self._deep_merge(self.config, toml_config)
        except Exception as e:
            print(f"Error loading TOML file {file_path.name}: {e}")

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """
        Deep merge update dictionary into base dictionary.

        Args:
            base: Base dictionary to merge into
            update: Dictionary with updates to merge
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key: Key in dot notation (e.g., "cache.redis.port")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        parts = key.split('.')
        current = self.config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get an entire configuration section.

        Args:
            section: Section name

        Returns:
            Dictionary containing the section configuration
        """
        return self.config.get(section, {})

    def get_all(self) -> Dict[str, Any]:
        """
        Get the entire configuration dictionary.

        Returns:
            Complete configuration dictionary
        """
        return self.config.copy()

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.

        Args:
            key: Key in dot notation (e.g., "cache.redis.port")
            value: Value to set
        """
        parts = key.split('.')
        current = self.config

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def update_from_env(self) -> None:
        """
        Update configuration from environment variables.
        Environment variables with double underscores will override TOML values.
        Format: SECTION__SUBSECTION__KEY=value becomes config['section']['subsection']['key'] = value
        """
        for env_key, env_value in os.environ.items():
            if '__' in env_key:
                # Convert environment variable to config key
                parts = env_key.lower().split('__')

                # Navigate to the nested location
                current = self.config
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                # Convert value to appropriate type
                converted_value = self._convert_value(env_value)
                current[parts[-1]] = converted_value

    def _convert_value(self, value: str) -> Union[str, int, float, bool]:
        """
        Convert string value to appropriate Python type.

        Args:
            value: String value to convert

        Returns:
            Converted value
        """
        # Handle empty strings
        if not value:
            return ""

        # Handle boolean values
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False

        # Handle numeric values
        try:
            # Try integer first
            if '.' not in value:
                return int(value)
            else:
                return float(value)
        except ValueError:
            pass

        # Return as string
        return value

    def __repr__(self) -> str:
        return f"EnvConfigLoader(env_name='{self.env_name}')"