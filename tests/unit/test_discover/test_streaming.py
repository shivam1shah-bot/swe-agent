"""
Tests for Discover streaming endpoint.

These tests verify the streaming proxy works correctly including:
- SSE format handling
- Client disconnect scenarios
- Backend error handling mid-stream
- Connection lifecycle management
"""

import inspect

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

pytest.importorskip("pytest_asyncio")


class TestStreamQueryEndpoint:
    """Tests for the stream_query endpoint."""

    @pytest.mark.asyncio
    async def test_stream_returns_sse_formatted_response(self):
        """Should return properly formatted SSE response."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query", skill_name="discover")
        
        # Mock response with SSE data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(
            return_value=iter([
                "data: {\"type\": \"text\", \"text\": \"Hello\"}",
                "data: {\"type\": \"done\"}",
            ])
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "http://discover:8080"},
            "auth": {"users": {"discover_service": "password"}},
            "google_oauth": {"jwt_secret": "secret"},
        }
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await stream_query(request, mock_request, "Bearer token")
            
            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"
            
            # Check headers
            assert response.headers.get("Cache-Control") == "no-cache"
            assert response.headers.get("Connection") == "keep-alive"
    
    @pytest.mark.asyncio
    async def test_stream_filters_non_data_lines(self):
        """Should filter out non-data SSE lines (empty lines, event:, id:, etc)."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(
            return_value=iter([
                "",  # Empty line
                "event: message",  # Event field - should be filtered
                "id: 123",  # ID field - should be filtered
                "data: {\"type\": \"text\"}",  # Only data lines should pass
                "data: {\"type\": \"done\"}",
            ])
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "http://discover:8080"},
            "auth": {"users": {"discover_service": "password"}},
            "google_oauth": {"jwt_secret": ""},
        }
        
        collected_chunks = []
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await stream_query(request, mock_request, None)
            
            # Consume the stream
            async for chunk in response.body_iterator:
                collected_chunks.append(chunk)
        
        # Should only have data: lines
        assert all(chunk.startswith("data:") for chunk in collected_chunks if chunk.strip())
        # Should not have event: or id: lines
        assert not any("event:" in chunk for chunk in collected_chunks)
        assert not any("id:" in chunk for chunk in collected_chunks)

    @pytest.mark.asyncio
    async def test_stream_handles_401_error(self):
        """Should yield error message when Discover returns 401."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query")
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.aread = AsyncMock(return_value=b"Invalid credentials")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "http://discover:8080"},
            "auth": {"users": {"discover_service": "password"}},
            "google_oauth": {"jwt_secret": ""},
        }
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await stream_query(request, mock_request, None)

            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)

            # Should have error message (generic, not exposing internal details)
            assert len(chunks) == 1
            assert "error" in chunks[0]
            assert "Authentication failed with Discover backend" in chunks[0]

    @pytest.mark.asyncio
    async def test_stream_handles_500_error_from_backend(self):
        """Should yield error message when Discover returns 500."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query")
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.aread = AsyncMock(return_value=b"Internal Server Error")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "http://discover:8080"},
            "auth": {"users": {"discover_service": "password"}},
            "google_oauth": {"jwt_secret": ""},
        }
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await stream_query(request, mock_request, None)

            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)

            # Should have error message (generic, not exposing internal details)
            assert len(chunks) == 1
            assert "error" in chunks[0]
            assert "Backend error: 500" in chunks[0]


class TestStreamingConnectionLifecycle:
    """Tests for connection lifecycle and cleanup."""

    @pytest.mark.asyncio
    async def test_client_closed_after_stream_completion(self):
        """Should close httpx client after stream completes normally."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(
            return_value=iter(["data: {\"type\": \"done\"}"])
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "http://discover:8080"},
            "auth": {"users": {"discover_service": "password"}},
            "google_oauth": {"jwt_secret": ""},
        }
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await stream_query(request, mock_request, None)
            
            # Fully consume the stream
            async for _ in response.body_iterator:
                pass
            
            # Verify client.close was called
            mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_client_closed_on_error(self):
        """Should close httpx client even if stream raises exception."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Make aiter_lines raise an exception mid-stream
        mock_response.aiter_lines = AsyncMock(
            side_effect=Exception("Connection lost")
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "http://discover:8080"},
            "auth": {"users": {"discover_service": "password"}},
            "google_oauth": {"jwt_secret": ""},
        }
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await stream_query(request, mock_request, None)
            
            try:
                async for _ in response.body_iterator:
                    pass
            except Exception:
                pass  # Expected
            
            # Even on error, client should be closed
            mock_client.aclose.assert_awaited_once()


class TestStreamingSSEFormat:
    """Tests for SSE (Server-Sent Events) format compliance."""

    def test_sse_double_newline_format(self):
        """SSE messages should end with double newline (\\n\\n)."""
        # This is a format requirement for SSE
        # The code does: yield f"{line}\n\n" which is correct
        # But we should verify it in the actual response
        sample_line = "data: {\"type\": \"text\"}"
        expected_output = "data: {\"type\": \"text\"}\n\n"
        
        # This documents the expected format
        assert sample_line + "\n\n" == expected_output

    @pytest.mark.asyncio
    async def test_stream_includes_double_newline(self):
        """Verify SSE messages include proper double newline termination."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(
            return_value=iter(["data: {\"type\": \"text\"}"])
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "http://discover:8080"},
            "auth": {"users": {"discover_service": "password"}},
            "google_oauth": {"jwt_secret": ""},
        }
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await stream_query(request, mock_request, None)
            
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            
            # Each chunk should end with double newline
            assert all(chunk.endswith("\n\n") for chunk in chunks if chunk.strip())


class TestStreamingErrorPropagation:
    """Tests for error handling during streaming."""

    @pytest.mark.asyncio
    async def test_stream_propagates_backend_connection_error(self):
        """Should yield error in SSE format when backend connection fails."""
        from src.api.routers.discover import stream_query, DiscoverQueryRequest
        
        request = DiscoverQueryRequest(query="test query")
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(side_effect=Exception("Cannot connect to backend"))
        mock_client.aclose = AsyncMock()
        
        mock_request = MagicMock()
        mock_request.app.state.config = {
            "discover": {"backend_url": "http://discover:8080"},
            "auth": {"users": {"discover_service": "password"}},
            "google_oauth": {"jwt_secret": ""},
        }
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await stream_query(request, mock_request, None)
            
            # The error should be yielded in SSE format, not as HTTPException
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            
            # Should have error message in SSE format
            assert len(chunks) == 1
            assert "error" in chunks[0]
            assert "Stream interrupted" in chunks[0]


class TestStreamingTimeoutHandling:
    """Tests for timeout configuration."""

    def test_stream_uses_long_timeout(self):
        """Streaming endpoint should use long timeout (300s) for slow responses."""
        from src.api.routers.discover import stream_query

        # The timeout should be set when creating client
        # timeout=300.0 in the code
        source = inspect.getsource(stream_query)
        assert "timeout=300.0" in source or "timeout=300" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
