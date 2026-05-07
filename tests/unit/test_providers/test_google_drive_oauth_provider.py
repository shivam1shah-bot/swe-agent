"""
Unit tests for GoogleDriveOAuthProvider.
"""
import pytest
from unittest.mock import Mock, patch
from src.providers.auth.google_oauth_provider import GoogleDriveOAuthProvider


@pytest.mark.unit
class TestGoogleDriveOAuthProvider:
    """Test cases for GoogleDriveOAuthProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = {
            "google_api": {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "redirect_uris": ["http://localhost:28001/google-auth-callback"],
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_get_auth_url_success(self, mock_logger):
        """Auth URL should be returned from the drive service."""
        provider = GoogleDriveOAuthProvider(config=self.mock_config)
        with patch('src.services.agents_catalogue.genspec.src.parsers.googleurl_extracter.GoogleDriveService') as mock_drive_svc:
            svc_instance = Mock()
            svc_instance.authenticate.return_value = "https://accounts.google.com/o/oauth2/auth?client_id=test_client_id"
            mock_drive_svc.return_value = svc_instance

            auth_url = provider.get_auth_url()

            assert "client_id=test_client_id" in auth_url
            svc_instance.authenticate.assert_called_once()

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_exchange_code_for_token_success(self, mock_logger):
        """exchange_code_for_token should mark credentials and return success."""
        provider = GoogleDriveOAuthProvider(config=self.mock_config)
        with patch('src.services.agents_catalogue.genspec.src.parsers.googleurl_extracter.GoogleDriveService') as mock_drive_svc:
            svc_instance = Mock()
            svc_instance.exchange_code_for_token.return_value = None
            mock_drive_svc.return_value = svc_instance

            result = provider.exchange_code_for_token("code123")

            assert result == {"status": "success"}
            assert provider.is_authenticated() is True
            svc_instance.exchange_code_for_token.assert_called_once_with("code123")

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_get_google_doc_content_success(self, mock_logger):
        """get_google_doc_content should fetch doc content via drive service."""
        provider = GoogleDriveOAuthProvider(config=self.mock_config)
        with patch('src.services.agents_catalogue.genspec.src.parsers.googleurl_extracter.GoogleDriveService') as mock_drive_svc:
            svc_instance = Mock()
            svc_instance.get_google_doc_content.return_value = "doc content"
            mock_drive_svc.return_value = svc_instance

            content = provider.get_google_doc_content("file123")

            assert content == "doc content"
            svc_instance.get_google_doc_content.assert_called_once_with("file123")

