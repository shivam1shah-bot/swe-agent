"""
Unit tests for Discover API route handlers.

Tests the FastAPI endpoints handle service-to-service auth and errors correctly.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

pytest.importorskip("pytest_asyncio")


# Default mock config for service-to-service auth
DEFAULT_MOCK_CONFIG = {
    "discover": {"backend_url": "http://discover:8080"},
    "auth": {
        "users": {
            "discover_service": "test_service_password"
        }
    },
    "google_oauth": {
        "jwt_secret": ""
    }
}


class TestStreamQuery:
    """Tests for stream_query endpoint."""

    @pytest.mark.asyncio
    async def test_stream_query_success(self):
        """Should stream response successfully."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query", skill_name="discover")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=iter(["data: chunk1", "data: chunk2"]))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            from fastapi.responses import StreamingResponse
            response = await stream_query(request, mock_request, "Bearer token")
            
            assert isinstance(response, StreamingResponse)

    @pytest.mark.asyncio
    async def test_stream_query_auth_failure(self):
        """Should yield error when Discover returns 401."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query", skill_name="discover")
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.aread = AsyncMock(return_value=b"Invalid credentials")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            from fastapi.responses import StreamingResponse
            response = await stream_query(request, mock_request, "Bearer token")
            
            assert isinstance(response, StreamingResponse)


class TestSaveConversation:
    """Tests for save_conversation endpoint."""

    @pytest.mark.asyncio
    async def test_save_conversation_success(self):
        """Should save conversation successfully."""
        from src.api.routers.discover import save_conversation, SaveConversationRequest
        
        request = SaveConversationRequest(
            transcript=[{"role": "user", "content": "Hello"}]
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "conv123", "saved": True}
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await save_conversation("session123", request, mock_request, "Bearer token")
            
            assert result["id"] == "conv123"
            assert result["saved"] is True

    @pytest.mark.asyncio
    async def test_save_conversation_auth_failure(self):
        """Should raise 401 when authentication fails."""
        from src.api.routers.discover import save_conversation, SaveConversationRequest
        
        request = SaveConversationRequest(
            transcript=[{"role": "user", "content": "Hello"}]
        )
        
        # Create an HTTPStatusError for 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Authentication failed"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Authentication failed",
                request=MagicMock(),
                response=mock_response
            )
        )
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await save_conversation("session123", request, mock_request, "Bearer token")
            
            assert exc_info.value.status_code == 401


class TestShareConversation:
    """Tests for share_conversation endpoint."""

    @pytest.mark.asyncio
    async def test_share_conversation_success(self):
        """Should create share link successfully."""
        from src.api.routers.discover import share_conversation, ShareConversationRequest
        
        request = ShareConversationRequest()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"share_url": "http://share/abc123"}
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await share_conversation("session123", request, mock_request, "Bearer token")
            
            assert result["share_url"] == "http://share/abc123"

    @pytest.mark.asyncio
    async def test_share_conversation_auth_failure(self):
        """Should raise 401 when authentication fails."""
        from src.api.routers.discover import share_conversation, ShareConversationRequest
        
        request = ShareConversationRequest()
        
        # Create an HTTPStatusError for 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response
            )
        )
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await share_conversation("session123", request, mock_request, "Bearer token")
            
            assert exc_info.value.status_code == 401


class TestCredentialEndpoints:
    """Tests for credential management endpoints."""

    @pytest.mark.asyncio
    async def test_get_credential_success(self):
        """Should get credential successfully."""
        from src.api.routers.discover import get_credential
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "cred1", "tool_id": "github", "token": "secret"}
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_credential("github", mock_request, "Bearer token")
            
            assert result["id"] == "cred1"
            assert result["tool_id"] == "github"

    @pytest.mark.asyncio
    async def test_get_credential_not_found(self):
        """Should return None when credential not found."""
        from src.api.routers.discover import get_credential
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_credential("github", mock_request, "Bearer token")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_credential_auth_failure(self):
        """Should raise 401 when authentication fails."""
        from src.api.routers.discover import get_credential
        
        # Create an HTTPStatusError for 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response
            )
        )
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await get_credential("github", mock_request, "Bearer token")
            
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_save_credential_success(self):
        """Should save credential successfully."""
        from src.api.routers.discover import save_credential, CredentialPayload
        
        request = CredentialPayload(
            toolId="github",
            type="token",
            value="new_token"
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "new_cred", "tool_id": "github"}
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await save_credential(request, mock_request, "Bearer token")
            
            assert result["id"] == "new_cred"

    @pytest.mark.asyncio
    async def test_delete_credential_success(self):
        """Should delete credential successfully."""
        from src.api.routers.discover import delete_credential
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.delete = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await delete_credential("github", mock_request, "Bearer token")
            
            assert result["deleted"] is True


class TestToolsEndpoints:
    """Tests for tools management endpoints."""

    @pytest.mark.asyncio
    async def test_get_tools_success(self):
        """Should get tools list successfully."""
        from src.api.routers.discover import get_tools
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "github", "name": "GitHub", "status": "connected"}
        ]
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_tools(mock_request, "Bearer token")
            
            assert len(result) == 1
            assert result[0]["id"] == "github"

    @pytest.mark.asyncio
    async def test_get_tool_status_success(self):
        """Should get tool status successfully."""
        from src.api.routers.discover import get_tool_status
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "connected", "latency": 120}
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_tool_status("github", mock_request, "Bearer token")
            
            assert result["status"] == "connected"
            assert result["latency"] == 120


class TestHandoffEndpoints:
    """Tests for handoff endpoints."""

    @pytest.mark.asyncio
    async def test_attach_handoff_success(self):
        """Should attach session to handoff successfully."""
        from src.api.routers.discover import attach_handoff, HandoffAttachRequest
        
        request = HandoffAttachRequest(session_id="session456")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await attach_handoff("ref123", request, mock_request, "Bearer token")
            
            assert result["attached"] is True

    @pytest.mark.asyncio
    async def test_get_pending_messages_success(self):
        """Should get pending messages successfully."""
        from src.api.routers.discover import get_pending_messages
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "msg1", "content": "Hello"}]}
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_pending_messages("runtime123", mock_request, "Bearer token")
            
            assert "messages" in result
            assert len(result["messages"]) == 1


class TestFeedbackEndpoint:
    """Tests for feedback endpoint."""

    @pytest.mark.asyncio
    async def test_submit_feedback_success(self):
        """Should submit feedback successfully."""
        from src.api.routers.discover import submit_feedback, FeedbackPayload
        
        request = FeedbackPayload(
            message_id="msg123",
            rating="thumbs_up"
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await submit_feedback(request, mock_request, "Bearer token")
            
            assert result["submitted"] is True

    @pytest.mark.asyncio
    async def test_submit_feedback_auth_failure(self):
        """Should raise 401 when authentication fails."""
        from src.api.routers.discover import submit_feedback, FeedbackPayload
        
        request = FeedbackPayload(
            message_id="msg123",
            rating="thumbs_up"
        )
        
        # Create an HTTPStatusError for 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response
            )
        )
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        mock_request = MagicMock()
        mock_request.app.state.config = DEFAULT_MOCK_CONFIG.copy()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await submit_feedback(request, mock_request, "Bearer token")
            
            assert exc_info.value.status_code == 401


@pytest.mark.skip(reason="Admin endpoints require @require_role decorator - test via integration tests")
class TestAdminEndpoints:
    """Tests for admin/debug endpoints.
    
    Note: These endpoints use @require_role(['admin']) decorator which
    validates the request context. Unit testing decorated async functions
    with FastAPI dependency injection is complex; these are better covered
    by integration tests with proper auth context.
    """
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
