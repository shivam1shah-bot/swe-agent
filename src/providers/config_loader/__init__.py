"""
Configuration loader package for handling environment-specific configurations.
"""

import os
import json
try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]  # Python 3.9/3.10 fallback
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import quote
from .env_loader import EnvConfigLoader
import logging

logger = logging.getLogger(__name__)

# Global instance to hold the loaded configuration
_config_instance: Optional[EnvConfigLoader] = None


def _setup_telemetry_config(config: Dict[str, Any]) -> None:
    """
    Setup telemetry configuration with defaults.
    
    Ensures telemetry configuration exists with all required fields and default values.
    
    Args:
        config: Configuration dictionary to update
    """
    # Ensure telemetry configuration exists
    if "telemetry" not in config:
        config["telemetry"] = {}
    
    telemetry_config = config["telemetry"]
    
    # Set telemetry defaults if not present
    if "enabled" not in telemetry_config:
        telemetry_config["enabled"] = True
    if "exporter" not in telemetry_config:
        telemetry_config["exporter"] = "prometheus"
    if "metrics_path" not in telemetry_config:
        telemetry_config["metrics_path"] = "/metrics"
    # Only set default metrics_port if not explicitly set (allows None to disable)
    # Default to 8080 for Prometheus scraping on separate port
    if "metrics_port" not in telemetry_config:
        telemetry_config["metrics_port"] = 8080  # Default port for separate metrics server
    if "service_name" not in telemetry_config:
        telemetry_config["service_name"] = "swe-agent"
    if "service_version" not in telemetry_config:
        telemetry_config["service_version"] = "1.0.0"
    
    # Ensure labels dictionary exists
    if "labels" not in telemetry_config:
        telemetry_config["labels"] = {}
    
    # Add environment name to labels if not already set
    env_name = config.get("environment", {}).get("name", "")
    if env_name and "environment" not in telemetry_config["labels"]:
        telemetry_config["labels"]["environment"] = env_name
    
    # Ensure prometheus config exists
    if "prometheus" not in telemetry_config:
        telemetry_config["prometheus"] = {}

def get_config() -> Dict[str, Any]:
    """
    Loads configuration using EnvConfigLoader and returns it as a dictionary.

    Ensures the configuration is loaded only once (singleton pattern).
    """
    global _config_instance

    if _config_instance is None:
        logger.debug("Initializing configuration loader for the first time.")
        _config_instance = EnvConfigLoader()
        _config_instance.update_from_env()

    # Get the complete configuration
    config = _config_instance.get_all()

    # Legacy compatibility: ensure some computed values are set
    if not config.get("root_dir"):
        # Get the project root (3 levels up from src/providers/config_loader)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config["root_dir"] = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

    if not config.get("upload_folder"):
        config["upload_folder"] = os.path.join(config["root_dir"], "uploads")

    # Ensure allowed extensions set exists
    config["allowed_extensions"] = {"txt", "pdf", "md", "c", "cpp", "py", "js", "html", "css", "java", "rs", "go", "ts", "json", "yaml", "yml", "toml", "sh", "ipynb", "jsx", "tsx"}

    # Generate database URI from configuration
    db_config = config.get("database", {})
    db_uri = db_config.get("uri")
    if not db_uri and db_config:
        db_type = db_config.get("type", "mysql").lower()
        db_user = db_config.get("user")
        db_password = db_config.get("password", "password")
        db_host = db_config.get("host", "localhost")
        db_name = db_config.get("name", "swe_agent")

        # URL-encode username and password to handle special characters
        encoded_user = quote(db_user, safe='') if db_user else ''
        encoded_password = quote(db_password, safe='')

        # Ensure database config exists before setting URI
        if "database" not in config:
            config["database"] = {}

        if db_type == "mysql":
            db_port = db_config.get("port", 3306)
            config["database"]["uri"] = f"mysql+pymysql://{encoded_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
        elif db_type == "postgresql":
            db_port = db_config.get("port", 5432)
            config["database"]["uri"] = f"postgresql://{encoded_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"

    # Setup telemetry configuration with defaults
    _setup_telemetry_config(config)
    
    # Legacy field mappings for backward compatibility
    # Check for debug in both top-level and nested structure
    debug_value = config.get("debug", False) or config.get("app", {}).get("debug", False)

    config.update({
        "ENVIRONMENT": config.get("environment", "base"),
        "DEBUG": 1 if debug_value else 0,
        "LOG_LEVEL": config.get("log_level", "INFO"),
        "ROOT_DIR": config.get("root_dir"),
        "UPLOAD_FOLDER": config.get("upload_folder"),
        "ALLOWED_EXTENSIONS": config.get("allowed_extensions"),
        "MAX_CONTENT_LENGTH": config.get("max_content_length", 100 * 1024 * 1024),
        "MYSQL_DB_HOST": config.get("database", {}).get("host", "localhost"),
        "MYSQL_DB_USER": config.get("database", {}).get("user", "swe_agent"),
        "MYSQL_DB_PASS": config.get("database", {}).get("password", "swe_agent_password"),
        "MYSQL_DB_NAME": config.get("database", {}).get("name", "swe_agent"),
        "DB_SCHEMA_VERSION": config.get("db_schema_version", 3),

        "SHOW_RECENT_TASKS": 1 if config.get("show_recent_tasks", False) else 0,
        "MAX_RECENT_TASKS": config.get("max_recent_tasks", 5),
        "DEFAULT_AGENT": config.get("default_agent", "autonomous_agent"),
        "AGENT_CONFIG": {}
    })

    return config

def get_aws_config(service_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get AWS configuration for a specific service with fallback to global config.

    Args:
        service_name: Name of the service (e.g., 'claude_code', 'workers', 'queue_manager')
                     If None, returns global AWS config

    Returns:
        Dict containing AWS configuration with keys:
        - access_key_id
        - secret_access_key
        - session_token
        - region
        - endpoint_url
    """
    config = get_config()

    # Get global AWS config as fallback
    global_aws_config = config.get("aws", {})

    # If no service specified, return global config
    if not service_name:
        return global_aws_config.copy()

    # Get service-specific config
    service_config = config.get("aws", {}).get("services", {}).get(service_name, {})

    # Merge service-specific config with global config (service-specific takes precedence)
    merged_config = global_aws_config.copy()
    merged_config.update(service_config)

    logger.debug(f"AWS config for service '{service_name}': region={merged_config.get('region')}, "
                f"has_access_key={bool(merged_config.get('access_key_id'))}")

    return merged_config

def get_claude_code_config() -> Dict[str, Any]:
    """
    Get Claude Code agent configuration with provider selection.

    Returns:
        Dict containing Claude Code configuration with:
        - provider: 'bedrock' or 'vertex_ai'
        - region: Region setting for the provider
        - gcp: GCP configuration if vertex_ai is selected
        - aws: AWS configuration if bedrock is selected
    """
    config = get_config()

    # Get agent configuration
    agent_config = config.get("agents", {}).get("claude_code", {})

    # Determine provider from configuration only
    provider = agent_config.get("provider", "vertex_ai")

    # Get region from agent config (with fallback to us-east5)
    region = agent_config.get("region", "us-east5")

    result = {
        "provider": provider,
        "region": region
    }

    if provider == "vertex_ai":
        # Get GCP configuration
        gcp_config = config.get("gcp", {})

        # Validate credentials_json if present in config
        credentials_json = gcp_config.get("credentials_json", "")
        if credentials_json:
            try:
                # Parse JSON to validate it
                json.loads(credentials_json)
                logger.debug("GCP credentials loaded from configuration")
            except json.JSONDecodeError:
                logger.warning("GCP credentials_json in configuration is not valid JSON")

        result["gcp"] = gcp_config

    elif provider == "bedrock":
        # Get AWS configuration for Claude service
        result["aws"] = get_aws_config("claude")

    logger.debug(f"Claude Code config: provider={provider}, region={region}")
    return result

__all__ = ['EnvConfigLoader', 'get_config', 'get_aws_config', 'get_claude_code_config']