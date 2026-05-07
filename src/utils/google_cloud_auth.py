"""
Google Cloud Authentication Utility

This utility sets up Google Cloud application default credentials during 
application startup using only the [gcp] configuration section.
"""

import os
from typing import Optional

try:
    from src.providers.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def setup_google_cloud_credentials(credentials_json: Optional[str] = None) -> bool:
    """
    Set up Google Cloud credentials for the application.
    
    Args:
        credentials_json: Optional JSON string of service account credentials.
                         If not provided, will check for existing credentials.
    
    Returns:
        bool: True if credentials are set up successfully, False otherwise.
    """
    default_creds_path = "/root/.config/gcloud/application_default_credentials.json"
    
    # Setup credentials if provided
    if credentials_json:
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(default_creds_path), exist_ok=True)

            # Write credentials directly to the standard path
            with open(default_creds_path, 'w') as f:
                f.write(credentials_json)

            logger.info(f"Google Cloud credentials written to {default_creds_path}")
            logger.info("Application default credentials configured")
            return True

        except Exception as e:
            logger.error(f"Failed to write credentials to {default_creds_path}: {e}")
            return False
    else:
        # Check if application default credentials exist
        if os.path.exists(default_creds_path):
            logger.info(f"Using existing application default credentials from: {default_creds_path}")
            return True
        else:
            logger.warning("No credentials provided and no application default credentials found")
            logger.warning(f"Expected credentials at: {default_creds_path}")
            return False


def initialize_google_cloud_auth_from_config(config: dict) -> bool:
    """
    Initialize Google Cloud authentication from application config.
    
    Args:
        config: Application configuration dictionary
        
    Returns:
        bool: True if credentials are set up successfully, False otherwise.
    """
    google_adk_config = config.get("google_adk", {})
    gcp_config = config.get("gcp", {})
    
    # Check if Vertex AI is enabled
    use_vertex_ai = google_adk_config.get("use_vertex_ai", True)
    if not use_vertex_ai:
        logger.info("Vertex AI disabled in config - skipping Google Cloud auth setup")
        return True
    
    # Set Google Cloud project and region - prefer gcp config, fallback to google_adk
    project_id = gcp_config.get("project_id") or google_adk_config.get("project_id")
    location = gcp_config.get("region") or google_adk_config.get("location")
    
    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        logger.info(f"Set GOOGLE_CLOUD_PROJECT={project_id}")
    
    if location:
        os.environ["GOOGLE_CLOUD_REGION"] = location
        logger.info(f"Set GOOGLE_CLOUD_REGION={location}")
        os.environ["GOOGLE_CLOUD_LOCATION"] = location
        logger.info(f"Set GOOGLE_CLOUD_LOCATION={location}")
    
    # Enable Vertex AI for Google ADK
    if use_vertex_ai:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        logger.info("Set GOOGLE_GENAI_USE_VERTEXAI=TRUE")
    
    # Look for credentials - prefer gcp config, fallback to google_adk
    credentials_json = gcp_config.get("credentials_json") or google_adk_config.get("service_account_credentials")
    
    return setup_google_cloud_credentials(credentials_json)


def is_google_cloud_auth_configured() -> bool:
    """
    Check if Google Cloud authentication is already configured.
    
    Returns:
        bool: True if authentication is configured, False otherwise.
    """
    # Check default credential path
    default_creds_path = "/root/.config/gcloud/application_default_credentials.json"
    if os.path.exists(default_creds_path):
        logger.debug(f"Google Cloud auth configured at: {default_creds_path}")
        return True
    
    return False
