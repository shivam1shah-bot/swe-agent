"""
Unit tests for Google OAuth provider.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.providers.auth.google_oauth_provider import GoogleOAuthProvider


@pytest.mark.unit
class TestGoogleOAuthProvider:
    """Test cases for GoogleOAuthProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = {
            "google_oauth": {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "redirect_uri": "http://localhost:28002/api/v1/auth/google_oauth/callback",
                "scopes": ["openid", "https://www.googleapis.com/auth/userinfo.email"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }

    @patch('src.providers.auth.google_oauth_provider.get_config')
    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_init_with_config(self, mock_logger, mock_get_config):
        """Test initialization with provided config."""
        provider = GoogleOAuthProvider(config=self.mock_config)
        
        assert provider.config == self.mock_config
        assert provider._credentials is None
        assert provider._credentials is None
        mock_get_config.assert_not_called()

    @patch('src.providers.auth.google_oauth_provider.get_config')
    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_init_without_config(self, mock_logger, mock_get_config):
        """Test initialization without config uses get_config."""
        mock_get_config.return_value = self.mock_config
        
        provider = GoogleOAuthProvider()
        
        assert provider.config == self.mock_config
        assert provider._credentials is None
        mock_get_config.assert_called_once()

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_get_auth_url_success(self, mock_logger):
        """Test successful generation of auth URL."""
        provider = GoogleOAuthProvider(config=self.mock_config)
        with patch.object(provider, '_create_flow') as mock_flow:
            mock_flow.return_value.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?client_id=test_client_id", None)
            auth_url = provider.get_auth_url()
            assert "client_id=test_client_id" in auth_url
            mock_flow.return_value.authorization_url.assert_called_once()

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_get_auth_url_error(self, mock_logger):
        """Test error handling in get_auth_url."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        provider = GoogleOAuthProvider(config=self.mock_config)
        with patch.object(provider, '_create_flow') as mock_flow:
            mock_flow.side_effect = Exception("OAuth error")

            with pytest.raises(Exception, match="OAuth error"):
                provider.get_auth_url()
            
            mock_logger_instance.error.assert_called_once()
            assert "Error generating auth URL" in str(mock_logger_instance.error.call_args)

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_exchange_code_for_token_success(self, mock_logger):
        """Test successful token exchange."""
        provider = GoogleOAuthProvider(config=self.mock_config)
        with patch.object(provider, '_create_flow') as mock_flow:
            mock_flow.return_value.fetch_token.return_value = None
            mock_flow.return_value.credentials = {"access_token": "token"}
            with patch.object(provider, 'get_user_info', return_value={"email": "test"}) as mock_user_info:
                result = provider.exchange_code_for_token("test_auth_code")
                assert result == {"status": "success", "user": {"email": "test"}}
                assert provider._credentials == {"access_token": "token"}
                mock_flow.return_value.fetch_token.assert_called_once_with(code="test_auth_code")
                mock_user_info.assert_called_once()

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_exchange_code_for_token_error(self, mock_logger):
        """Test error handling in exchange_code_for_token."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance

        provider = GoogleOAuthProvider(config=self.mock_config)
        with patch.object(provider, '_create_flow') as mock_flow:
            mock_flow.return_value.fetch_token.side_effect = Exception("Token exchange error")

            with pytest.raises(Exception, match="Token exchange error"):
                provider.exchange_code_for_token("test_auth_code")
            
            assert provider._credentials is None  # Should not be set on error
            mock_logger_instance.error.assert_called_once()
            assert "Error exchanging code for token" in str(mock_logger_instance.error.call_args)

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_is_authenticated_false(self, mock_logger):
        """Test is_authenticated returns False when not authenticated."""
        provider = GoogleOAuthProvider(config=self.mock_config)
        
        assert provider.is_authenticated() is False

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_is_authenticated_true(self, mock_logger):
        """Test is_authenticated returns True when authenticated."""
        provider = GoogleOAuthProvider(config=self.mock_config)
        provider._credentials = True
        
        assert provider.is_authenticated() is True

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_get_credentials_not_authenticated(self, mock_logger):
        """Test get_credentials returns None when not authenticated."""
        provider = GoogleOAuthProvider(config=self.mock_config)
        
        assert provider.get_credentials() is None

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_get_credentials_authenticated(self, mock_logger):
        """Test get_credentials returns credentials when authenticated."""
        provider = GoogleOAuthProvider(config=self.mock_config)
        provider._credentials = {"access_token": "test_token", "expires_in": 3600}
        
        credentials = provider.get_credentials()
        
        assert credentials == {"access_token": "test_token", "expires_in": 3600}

    @patch('src.providers.auth.google_oauth_provider.Logger')
    def test_integration_auth_flow(self, mock_logger):
        """Test complete authentication flow."""
        provider = GoogleOAuthProvider(config=self.mock_config)
        # Step 1: Get auth URL
        with patch.object(provider, '_create_flow') as mock_flow:
            mock_flow.return_value.authorization_url.return_value = ("https://oauth.url", None)
            auth_url = provider.get_auth_url()
            assert auth_url == "https://oauth.url"
            assert provider.is_authenticated() is False
        # Step 2: Exchange code for token
        with patch.object(provider, '_create_flow') as mock_flow:
            mock_flow.return_value.fetch_token.return_value = None
            mock_flow.return_value.credentials = {"access_token": "token"}
            with patch.object(provider, 'get_user_info', return_value={"email": "test"}):
                result = provider.exchange_code_for_token("auth_code_123")
                assert result == {"status": "success", "user": {"email": "test"}}
                assert provider.is_authenticated() is True
                assert provider._credentials == {"access_token": "token"}

