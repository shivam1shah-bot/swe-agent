"""
Authentication router for Google OAuth.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from urllib.parse import urlparse

from src.providers.auth.google_oauth_provider import GoogleOAuthProvider
from src.providers.config_loader import get_config
from src.providers.logger import Logger
from src.utils.jwt import create_access_token

router = APIRouter()
logger = Logger(__name__)

# Models
class LoginResponse(BaseModel):
    auth_url: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

def get_google_auth_provider() -> GoogleOAuthProvider:
    """Dependency to get Google OAuth provider."""
    return GoogleOAuthProvider()

@router.get("/login", response_model=LoginResponse)
async def login(
    provider: GoogleOAuthProvider = Depends(get_google_auth_provider)
):
    """
    Get Google OAuth login URL.
    """
    try:
        auth_url = provider.get_auth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Error generating auth URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate authentication URL")

# Allowed email domain for authentication
ALLOWED_EMAIL_DOMAIN = "@razorpay.com"

def _validate_ui_base_url(ui_base_url: str, allowed_hosts: Optional[list[str]] = None) -> str:
    """
    Validate that ui_base_url points to an allowed host to prevent open redirects.
    Raises HTTPException if invalid.
    """
    parsed = urlparse(ui_base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid UI base URL")

    allowed = set(allowed_hosts or [])
    allowed.add(parsed.netloc)

    if parsed.netloc not in allowed:
        raise HTTPException(status_code=400, detail="Unauthorized redirect target")

    return ui_base_url.rstrip("/")

@router.get("/google_oauth/callback")
async def callback(
    code: str,
    request: Request,
    state: Optional[str] = Query(default=None),
    provider: GoogleOAuthProvider = Depends(get_google_auth_provider)
):
    """
    Handle Google OAuth callback.
    Exchanges code for token and returns JWT access token.
    Only allows users with @razorpay.com email domain.
    """
    try:
        # Get config for redirect URLs
        config = get_config()
        raw_ui_base_url = config.get("app", {}).get("ui_base_url", "http://localhost:28001")
        allowed_redirect_hosts = config.get("app", {}).get("allowed_redirect_hosts", [])
        ui_base_url = _validate_ui_base_url(raw_ui_base_url, allowed_redirect_hosts)

        # Exchange code for Google token and get user info
        result = provider.exchange_code_for_token(code, state=state)
        user_info = result.get("user", {})
        email = user_info.get("email", "")
        if not email:
            raise HTTPException(status_code=500, detail="Authentication failed: unable to fetch user email")
        email_lower = email.lower()
        
        # Validate email domain - only allow @razorpay.com
        if not email_lower.endswith(ALLOWED_EMAIL_DOMAIN):
            logger.warning(f"Access denied for email: {email} (not a Razorpay account)")
            return RedirectResponse(url=f"{ui_base_url}/login?error=unauthorized_domain")
        
        # Create application JWT token (email-based authentication)
        access_token = create_access_token(
            data={
                "sub": email_lower,
                "role": "dashboard"  # Dashboard role for authenticated users
            }
        )
        
        # Redirect to frontend with token
        from urllib.parse import quote
        token_param = quote(access_token, safe="")
        redirect_url = f"{ui_base_url}/auth/callback?token={token_param}"
        return RedirectResponse(url=redirect_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in auth callback: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed")

@router.get("/status")
async def auth_status():
    """
    Return auth enablement status from configuration.
    """
    config = get_config()
    auth_enabled = config.get("auth", {}).get("enabled", True)
    return {"auth_enabled": auth_enabled}


@router.get("/me")
async def get_current_user_info(request: Request):
    """
    Get current user information from token.
    """
    config = get_config()
    auth_enabled = config.get("auth", {}).get("enabled", True)

    # If auth is disabled, return empty payload (bypass auth in local/dev)
    if not auth_enabled:
        return {}

    # This relies on the auth middleware populating request.state.current_user
    user = getattr(request.state, "current_user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user


@router.get("/me/profile")
async def get_user_profile(request: Request):
    """
    Return the current user's linked identities across all platforms.

    Aggregates:
    - Dashboard (email / display name from JWT)
    - Slack (handle and user ID from user_connector table)
    - DevRev (created_by email stored during task triggers)
    - GitHub (username looked up via GitHub API by email)
    """
    config = get_config()
    auth_enabled = config.get("auth", {}).get("enabled", True)

    if not auth_enabled:
        return {"email": None, "identities": {}}

    user = getattr(request.state, "current_user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    email = user.get("email") or user.get("username") or ""

    # Pull connector_id blob for this user from user_connector table
    connector_data: dict = {}
    try:
        import json as _json
        from sqlalchemy import text as _text
        from src.providers.database.connection import get_engine as _get_engine

        engine = _get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                _text("SELECT connector_id FROM user_connector WHERE user_email = :email"),
                {"email": email},
            ).fetchone()
            if row and row[0]:
                connector_data = _json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
    except Exception as exc:
        logger.warning(f"Could not fetch user_connector for {email}: {exc}")

    # GitHub: look up by email via GitHub API (search endpoint)
    github_username: Optional[str] = None
    try:
        from src.providers.github.auth_service import GitHubAuthService

        gh_service = GitHubAuthService()
        token = await gh_service.get_token()
        if token and email:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.github.com/search/users",
                    params={"q": f"{email} in:email", "per_page": 1},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    if items:
                        github_username = items[0].get("login")
    except Exception as exc:
        logger.warning(f"GitHub username lookup failed for {email}: {exc}")

    # Build identities dict — only include keys with actual values
    identities: dict = {}

    if email:
        identities["dashboard"] = {"username": email}

    slack_handle = connector_data.get("slack_handle")
    slack_id = connector_data.get("slack_id")
    if slack_handle or slack_id:
        identities["slack"] = {
            k: v for k, v in {"handle": slack_handle, "user_id": slack_id}.items() if v
        }

    if github_username:
        identities["github"] = {"username": github_username}

    devrev_email = connector_data.get("created_by")
    if devrev_email:
        identities["devrev"] = {"email": devrev_email}

    return {
        "email": email,
        "display_name": email.split("@")[0].replace(".", " ").title() if email else None,
        "identities": identities,
    }

