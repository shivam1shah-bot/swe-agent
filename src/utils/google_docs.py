"""
Google Docs client utility.

Provides a reusable GoogleDocsClient that any agent or service in swe-agent
can use to fetch plain-text content from a Google Doc by URL or file ID.

Credential resolution order (automatic, no manual config required):
  1. gcp.google_docs_credentials_json — OAuth user credentials for
     swe-agent@razorpay.com. Populated from credstash key
     GCP__GOOGLE_DOCS_CREDENTIALS_JSON at runtime via update_from_env().
     Allows reading any doc shared with the Razorpay domain.
  2. google.auth.default() — Application Default Credentials (ADC) written
     at app startup from gcp.credentials_json (service account). Requires
     the doc to be explicitly shared with the service account.

If neither credential source is available, fetching is silently disabled
and None is returned.

Usage:
    client = GoogleDocsClient()

    # By full URL
    text = await client.fetch_by_url(
        "https://docs.google.com/document/d/FILE_ID/edit"
    )

    # By file ID directly
    text = await client.fetch_document("1h4mn43oGQaJxrbqO3vswvoNG_BWFanZnq3IndFSASqo")
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from src.utils.google_cloud_auth import is_google_cloud_auth_configured

logger = logging.getLogger(__name__)

# Google Docs readonly OAuth scope.
_GOOGLE_DOCS_SCOPE = "https://www.googleapis.com/auth/documents.readonly"

# Extracts file ID from a Google Docs URL.
# Matches: https://docs.google.com/document/d/{FILE_ID}/...
_GOOGLE_DOC_URL_RE = re.compile(
    r"https?://(?:www\.)?docs\.google\.com/document/d/([A-Za-z0-9_-]+)"
)


class GoogleDocsClient:
    """
    Reusable client for fetching plain-text content from Google Docs.

    Credentials are resolved automatically from the application config —
    callers do not need to pass any auth parameters.

    The client is stateless and safe to instantiate multiple times or share
    across coroutines. All blocking Google API calls are run in a thread via
    asyncio.to_thread() to remain async-safe.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_by_url(self, url: str) -> Optional[str]:
        """
        Fetch a Google Doc's plain-text content given its full URL.

        Args:
            url: Full Google Docs URL, e.g.
                 "https://docs.google.com/document/d/FILE_ID/edit"

        Returns:
            Plain-text content of the document, or None if:
            - The URL is not a valid Google Docs URL
            - Credentials are not configured
            - The fetch fails for any reason (permission, network, etc.)

        Never raises — any error is logged as WARNING and None is returned.
        """
        file_id = self._extract_file_id(url)
        if not file_id:
            logger.warning(
                "GoogleDocsClient: could not extract file ID from URL: %s", url
            )
            return None
        return await self.fetch_document(file_id)

    async def fetch_document(self, file_id: str) -> Optional[str]:
        """
        Fetch a Google Doc's plain-text content by file ID.

        Args:
            file_id: Google Docs file ID (the alphanumeric string in the URL
                     after /document/d/).

        Returns:
            Plain-text content of the document, or None on any error.
            Never raises.
        """
        if not file_id or not file_id.strip():
            logger.warning("GoogleDocsClient: empty file_id provided")
            return None

        if not is_google_cloud_auth_configured() and not self._has_oauth_credentials():
            logger.warning(
                "GoogleDocsClient: no credentials configured — "
                "fetching disabled (file_id=%s)",
                file_id,
            )
            return None

        try:
            content = await asyncio.to_thread(self._fetch_sync, file_id)
        except Exception as exc:
            logger.warning(
                "GoogleDocsClient: failed to fetch document (file_id=%s): %s",
                file_id,
                exc,
            )
            return None

        if not content:
            logger.warning(
                "GoogleDocsClient: document returned empty content (file_id=%s)",
                file_id,
            )
            return None

        logger.warning(
            "GoogleDocsClient: successfully fetched document (file_id=%s, %d chars)",
            file_id,
            len(content),
        )
        return content

    # ------------------------------------------------------------------
    # Private: credential resolution
    # ------------------------------------------------------------------

    def _has_oauth_credentials(self) -> bool:
        """Return True if gcp.google_docs_credentials_json is non-empty in config."""
        try:
            from src.providers.config_loader import get_config

            creds = get_config().get("gcp", {}).get("google_docs_credentials_json", "")
            return bool(creds and creds.strip())
        except Exception:
            return False

    def _load_oauth_credentials(self) -> Optional[Any]:
        """
        Load OAuth user credentials from gcp.google_docs_credentials_json.

        The value is injected by update_from_env() which maps the env var
        GCP__GOOGLE_DOCS_CREDENTIALS_JSON → config['gcp']['google_docs_credentials_json'].

        Returns google.oauth2.credentials.Credentials on success, None if the
        config key is absent/empty or the JSON is invalid.
        """
        try:
            import json

            from google.oauth2.credentials import Credentials  # type: ignore

            from src.providers.config_loader import get_config

            creds_json = get_config().get("gcp", {}).get(
                "google_docs_credentials_json", ""
            )
        except Exception:
            return None

        if not creds_json or not creds_json.strip():
            return None

        try:
            data = json.loads(creds_json)
            return Credentials(
                token=None,
                refresh_token=data["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=data["client_id"],
                client_secret=data["client_secret"],
                scopes=[_GOOGLE_DOCS_SCOPE],
            )
        except Exception as exc:
            logger.warning(
                "GoogleDocsClient: failed to load google_docs_credentials_json: %s",
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Private: synchronous fetch (runs in thread)
    # ------------------------------------------------------------------

    def _fetch_sync(self, file_id: str) -> str:
        """
        Synchronous Google Docs API call — run via asyncio.to_thread().

        Tries OAuth credentials first; falls back to ADC if not available.
        """
        import google.auth  # type: ignore
        from googleapiclient.discovery import build  # type: ignore

        credentials = self._load_oauth_credentials()

        if credentials is None:
            logger.warning(
                "GoogleDocsClient: google_docs_credentials_json not set — "
                "falling back to ADC (file_id=%s)",
                file_id,
            )
            credentials, _ = google.auth.default(scopes=[_GOOGLE_DOCS_SCOPE])
        else:
            logger.warning(
                "GoogleDocsClient: using OAuth credentials from "
                "google_docs_credentials_json (file_id=%s)",
                file_id,
            )

        service = build("docs", "v1", credentials=credentials, cache_discovery=False)
        document = service.documents().get(documentId=file_id).execute()
        return _extract_plain_text(document)

    # ------------------------------------------------------------------
    # Private: URL parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_file_id(url: str) -> Optional[str]:
        """Extract the Google Docs file ID from a full URL."""
        match = _GOOGLE_DOC_URL_RE.search(url)
        return match.group(1) if match else None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_plain_text(document: Dict[str, Any]) -> str:
    """
    Extract plain text from a Google Docs API document response.

    Iterates over the document body content and concatenates paragraph
    text runs, preserving newlines between paragraphs.
    """
    body = document.get("body", {})
    content_blocks = body.get("content", [])
    lines: List[str] = []

    for block in content_blocks:
        paragraph = block.get("paragraph")
        if not paragraph:
            continue

        parts: List[str] = []
        for element in paragraph.get("elements", []):
            text_run = element.get("textRun")
            if text_run:
                parts.append(text_run.get("content", ""))

        paragraph_text = "".join(parts)
        if paragraph_text.strip():
            lines.append(paragraph_text.rstrip("\n"))

    return "\n".join(lines)
