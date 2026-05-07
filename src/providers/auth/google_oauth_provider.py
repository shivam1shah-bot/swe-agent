"""
Google OAuth Provider for handling Google authentication.

This provider manages the OAuth flow for:
1. Application Login - Uses [google_oauth] config for user authentication
2. Google Drive integration - Uses [google_api] config for Drive/Docs access
"""

from typing import Optional, Dict, Any
from google_auth_oauthlib.flow import Flow
import jwt as pyjwt
from src.providers.logger import Logger
from src.providers.config_loader import get_config


class GoogleOAuthProvider:
    """
    Google OAuth provider for Application Login.
    
    Uses the [google_oauth] configuration section for user authentication.
    This is separate from Google Drive integration which uses [google_api].
    """

    def __init__(self, config=None):
        """Initialize the Google OAuth provider for app login."""
        self.logger = Logger(__name__)
        self.config = config or get_config()
        self._credentials = None
        
        # Load OAuth config from [google_oauth] section
        oauth_config = self.config.get('google_oauth', {})
        self.client_id = oauth_config.get('client_id', '')
        self.client_secret = oauth_config.get('client_secret', '')
        self.redirect_uri = oauth_config.get('redirect_uri', '')
        self.scopes = oauth_config.get('scopes', [
            'openid',
            'https://www.googleapis.com/auth/userinfo.email'
        ])
        self.auth_uri = oauth_config.get('auth_uri', 'https://accounts.google.com/o/oauth2/auth')
        self.token_uri = oauth_config.get('token_uri', 'https://oauth2.googleapis.com/token')

    def _create_flow(self) -> Flow:
        """Create OAuth flow with current configuration."""
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": [self.redirect_uri],
                    "auth_uri": self.auth_uri,
                    "token_uri": self.token_uri
                }
            },
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )

    def get_auth_url(self) -> str:
        """
        Generate Google OAuth URL for user authentication.
        
        Returns:
            OAuth URL string for user redirection
        """
        try:
            flow = self._create_flow()
            # Disable PKCE: the Flow is stateless so the code_verifier generated here
            # cannot be persisted for the callback request.
            flow.autogenerate_code_verifier = False
            auth_url, _ = flow.authorization_url(prompt='consent')
            self.logger.info("Generated Google OAuth URL for app login")
            return auth_url
        except Exception:
            self.logger.error("Error generating auth URL")
            raise

    def exchange_code_for_token(self, code: str, state: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback
            state: OAuth state parameter from callback (used to bypass state validation)

        Returns:
            Token information including user info
        """
        try:
            self.logger.info("Exchanging authorization code for token")

            flow = self._create_flow()
            # Sync the session state with the callback state to bypass state mismatch validation
            if state:
                flow.oauth2session._state = state
            flow.fetch_token(code=code)
            self._credentials = flow.credentials
            
            self.logger.info("Successfully exchanged code for token")
            
            # Fetch user info after successful token exchange
            user_info = self.get_user_info()
            return {"status": "success", "user": user_info}
        except Exception as e:
            self.logger.error(f"Error exchanging code for token: {type(e).__name__}: {str(e)}")
            if "invalid_grant" in str(e).lower():
                raise Exception("Authorization code is invalid, expired, or has already been used. Please try the OAuth flow again.")
            raise

    def get_user_info(self) -> Dict[str, Any]:
        """
        Get user profile information from Google.
        
        Returns:
            Dictionary with user details (email)
        """
        try:
            from googleapiclient.discovery import build
            
            if not self._credentials:
                raise Exception("No credentials available. User must authenticate first.")
            
            # Build oauth2 service to get user info
            oauth2_service = build('oauth2', 'v2', credentials=self._credentials)
            user_info = oauth2_service.userinfo().get().execute()
            
            return {
                "email": user_info.get("email")
            }
        except Exception:
            self.logger.error("Error fetching user info")
            # Fallback: try to extract email from id_token without network
            try:
                if self._credentials and getattr(self._credentials, "id_token", None):
                    claims = pyjwt.decode(
                        self._credentials.id_token,
                        options={"verify_signature": False, "verify_aud": False}
                    )
                    email = claims.get("email")
                    if email:
                        return {"email": email}
            except Exception as decode_err:
                self.logger.error("Failed to decode id_token for email")
            # Return empty dict to make failure explicit
            return {}

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated with Google.
        
        Returns:
            True if authenticated, False otherwise
        """
        return self._credentials is not None

    def get_credentials(self):
        """
        Get current OAuth credentials.
        
        Returns:
            Credentials object or None if not authenticated
        """
        return self._credentials


class GoogleDriveOAuthProvider:
    """
    Google OAuth provider for Google Drive integration.
    
    Uses the [google_api] configuration section for Drive/Docs access.
    This is separate from Application Login which uses [google_oauth].
    """

    def __init__(self, config=None):
        """Initialize the Google OAuth provider for Drive integration."""
        self.logger = Logger(__name__)
        self.config = config or get_config()
        self._credentials = None
        self._google_drive_service = None

    def get_google_drive_service(self):
        """Get or create Google Drive service instance."""
        if self._google_drive_service is None:
            from src.services.agents_catalogue.genspec.src.parsers.googleurl_extracter import GoogleDriveService
            # GoogleDriveService expects the google_api subsection
            google_api_config = self.config.get("google_api", {})
            self._google_drive_service = GoogleDriveService(google_api_config)
        return self._google_drive_service

    def get_auth_url(self) -> str:
        """
        Generate Google OAuth URL for Drive authentication.
        
        Returns:
            OAuth URL string for user redirection
        """
        try:
            google_drive_service = self.get_google_drive_service()
            auth_url = google_drive_service.authenticate()
            self.logger.info("Generated Google OAuth URL for Drive access")
            return auth_url
        except Exception as e:
            self.logger.error(f"Error generating auth URL: {str(e)}")
            raise

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Token information
        """
        try:
            self.logger.info("Exchanging authorization code for Drive token")
            google_drive_service = self.get_google_drive_service()
            google_drive_service.exchange_code_for_token(code)
            self._credentials = True  # Mark as authenticated
            self.logger.info("Successfully exchanged code for Drive token")
            return {"status": "success"}
        except Exception as e:
            self.logger.error(f"Error exchanging code for token: {str(e)}")
            raise

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated with Google Drive.
        
        Returns:
            True if authenticated, False otherwise
        """
        return self._credentials is not None

    def get_google_doc_content(self, file_id: str) -> str:
        """
        Fetch content from a Google Doc.
        
        Args:
            file_id: Google Doc file ID
            
        Returns:
            Document content as string
        """
        try:
            self.logger.info(f"Fetching Google Doc content for file: {file_id}")
            google_drive_service = self.get_google_drive_service()
            content = google_drive_service.get_google_doc_content(file_id)
            self.logger.info(f"Successfully fetched content, length: {len(content) if content else 0}")
            return content
        except Exception as e:
            self.logger.error(f"Error fetching Google Doc content: {str(e)}")
            raise

