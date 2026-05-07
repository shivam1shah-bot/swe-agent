"""
Unit tests for Google Cloud Authentication utility.

Tests for src.utils.google_cloud_auth module.
"""

import os
import tempfile
import shutil
from unittest.mock import patch, mock_open, MagicMock
import pytest

from src.utils.google_cloud_auth import (
    setup_google_cloud_credentials,
    initialize_google_cloud_auth_from_config,
    is_google_cloud_auth_configured
)


class TestSetupGoogleCloudCredentials:
    """Test cases for setup_google_cloud_credentials function."""

    @patch('src.utils.google_cloud_auth.logger')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_setup_credentials_with_json(self, mock_file, mock_makedirs, mock_logger):
        """Test setting up credentials with provided JSON."""
        credentials_json = '{"type": "service_account", "project_id": "test-project"}'
        default_creds_path = "/root/.config/gcloud/application_default_credentials.json"
        
        result = setup_google_cloud_credentials(credentials_json)
        
        assert result is True
        mock_makedirs.assert_called_once_with(os.path.dirname(default_creds_path), exist_ok=True)
        mock_file.assert_called_once_with(default_creds_path, 'w')
        mock_file.return_value.write.assert_called_once_with(credentials_json)
        assert mock_logger.info.call_count >= 2

    @patch('src.utils.google_cloud_auth.logger')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_setup_credentials_write_failure(self, mock_file, mock_makedirs, mock_logger):
        """Test handling of write failure when setting up credentials."""
        credentials_json = '{"type": "service_account"}'
        mock_file.side_effect = IOError("Permission denied")
        
        result = setup_google_cloud_credentials(credentials_json)
        
        assert result is False
        mock_logger.error.assert_called_once()
        assert "Failed to write credentials" in str(mock_logger.error.call_args)

    @patch('src.utils.google_cloud_auth.logger')
    @patch('os.path.exists')
    def test_setup_credentials_existing_file(self, mock_exists, mock_logger):
        """Test using existing credentials file."""
        default_creds_path = "/root/.config/gcloud/application_default_credentials.json"
        mock_exists.return_value = True
        
        result = setup_google_cloud_credentials(None)
        
        assert result is True
        mock_exists.assert_called_once_with(default_creds_path)
        mock_logger.info.assert_called_once()
        assert "existing application default credentials" in str(mock_logger.info.call_args)

    @patch('src.utils.google_cloud_auth.logger')
    @patch('os.path.exists')
    def test_setup_credentials_no_file_no_json(self, mock_exists, mock_logger):
        """Test when no credentials file exists and no JSON provided."""
        default_creds_path = "/root/.config/gcloud/application_default_credentials.json"
        mock_exists.return_value = False
        
        result = setup_google_cloud_credentials(None)
        
        assert result is False
        mock_exists.assert_called_once_with(default_creds_path)
        assert mock_logger.warning.call_count >= 2


class TestInitializeGoogleCloudAuthFromConfig:
    """Test cases for initialize_google_cloud_auth_from_config function."""

    @patch('src.utils.google_cloud_auth.setup_google_cloud_credentials')
    @patch('src.utils.google_cloud_auth.logger')
    @patch.dict(os.environ, {}, clear=False)
    def test_initialize_with_gcp_config(self, mock_logger, mock_setup):
        """Test initialization with GCP config."""
        config = {
            "google_adk": {"use_vertex_ai": True},
            "gcp": {
                "project_id": "test-project",
                "region": "us-central1",
                "credentials_json": '{"type": "service_account"}'
            }
        }
        mock_setup.return_value = True
        
        result = initialize_google_cloud_auth_from_config(config)
        
        assert result is True
        assert os.environ["GOOGLE_CLOUD_PROJECT"] == "test-project"
        assert os.environ["GOOGLE_CLOUD_REGION"] == "us-central1"
        assert os.environ["GOOGLE_CLOUD_LOCATION"] == "us-central1"
        assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "TRUE"
        mock_setup.assert_called_once_with('{"type": "service_account"}')

    @patch('src.utils.google_cloud_auth.setup_google_cloud_credentials')
    @patch('src.utils.google_cloud_auth.logger')
    @patch.dict(os.environ, {}, clear=False)
    def test_initialize_with_google_adk_config(self, mock_logger, mock_setup):
        """Test initialization with google_adk config fallback."""
        config = {
            "google_adk": {
                "use_vertex_ai": True,
                "project_id": "adk-project",
                "location": "us-east1",
                "service_account_credentials": '{"type": "service_account", "project": "adk-project"}'
            },
            "gcp": {}
        }
        mock_setup.return_value = True
        
        result = initialize_google_cloud_auth_from_config(config)
        
        assert result is True
        assert os.environ["GOOGLE_CLOUD_PROJECT"] == "adk-project"
        assert os.environ["GOOGLE_CLOUD_REGION"] == "us-east1"
        assert os.environ["GOOGLE_CLOUD_LOCATION"] == "us-east1"
        mock_setup.assert_called_once_with('{"type": "service_account", "project": "adk-project"}')

    @patch('src.utils.google_cloud_auth.logger')
    @patch.dict(os.environ, {}, clear=False)
    def test_initialize_vertex_ai_disabled(self, mock_logger):
        """Test initialization when Vertex AI is disabled."""
        config = {
            "google_adk": {"use_vertex_ai": False}
        }
        
        result = initialize_google_cloud_auth_from_config(config)
        
        assert result is True
        mock_logger.info.assert_called_once()
        assert "Vertex AI disabled" in str(mock_logger.info.call_args)
        assert "GOOGLE_GENAI_USE_VERTEXAI" not in os.environ

    @patch('src.utils.google_cloud_auth.setup_google_cloud_credentials')
    @patch('src.utils.google_cloud_auth.logger')
    @patch.dict(os.environ, {}, clear=False)
    def test_initialize_without_project_or_region(self, mock_logger, mock_setup):
        """Test initialization without project_id or region."""
        config = {
            "google_adk": {"use_vertex_ai": True},
            "gcp": {}
        }
        mock_setup.return_value = True
        
        result = initialize_google_cloud_auth_from_config(config)
        
        assert result is True
        assert "GOOGLE_CLOUD_PROJECT" not in os.environ
        assert "GOOGLE_CLOUD_REGION" not in os.environ
        assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "TRUE"

    @patch('src.utils.google_cloud_auth.setup_google_cloud_credentials')
    @patch('src.utils.google_cloud_auth.logger')
    @patch.dict(os.environ, {}, clear=False)
    def test_initialize_setup_failure(self, mock_logger, mock_setup):
        """Test initialization when setup_google_cloud_credentials fails."""
        config = {
            "google_adk": {"use_vertex_ai": True},
            "gcp": {"credentials_json": '{"type": "service_account"}'}
        }
        mock_setup.return_value = False
        
        result = initialize_google_cloud_auth_from_config(config)
        
        assert result is False


class TestIsGoogleCloudAuthConfigured:
    """Test cases for is_google_cloud_auth_configured function."""

    @patch('src.utils.google_cloud_auth.logger')
    @patch('os.path.exists')
    def test_auth_configured_exists(self, mock_exists, mock_logger):
        """Test when credentials file exists."""
        mock_exists.return_value = True
        
        result = is_google_cloud_auth_configured()
        
        assert result is True
        mock_exists.assert_called_once_with("/root/.config/gcloud/application_default_credentials.json")
        mock_logger.debug.assert_called_once()

    @patch('src.utils.google_cloud_auth.logger')
    @patch('os.path.exists')
    def test_auth_configured_not_exists(self, mock_exists, mock_logger):
        """Test when credentials file does not exist."""
        mock_exists.return_value = False
        
        result = is_google_cloud_auth_configured()
        
        assert result is False
        mock_exists.assert_called_once_with("/root/.config/gcloud/application_default_credentials.json")

