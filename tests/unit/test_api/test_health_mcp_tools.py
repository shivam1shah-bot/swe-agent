"""
Unit tests for GET /api/v1/health/mcp-servers/{server_id}/tools endpoint.
"""

import pytest
from unittest.mock import patch
from fastapi import HTTPException

from src.api.routers.health import get_mcp_server_tools

ALLOWED_TOOLS = (
    "Task,Bash,Glob,"
    "mcp__memory__create_entities,mcp__memory__read_graph,"
    "mcp__blade-mcp__hi_blade,mcp__blade-mcp__get_blade_component_docs,"
    "mcp__devrev-mcp__create_ticket,mcp__devrev-mcp__get_ticket,mcp__devrev-mcp__update_ticket,"
    "mcp__sequentialthinking__sequentialthinking"
)

PATCH_TARGET = "src.providers.config_loader.get_config"


@pytest.fixture
def mock_cfg():
    with patch(PATCH_TARGET, return_value={"agent": {"allowed_tools": ALLOWED_TOOLS}}):
        yield


@pytest.mark.asyncio
class TestGetMcpServerTools:

    async def test_returns_tools_for_devrev(self, mock_cfg):
        result = await get_mcp_server_tools("devrev-mcp")
        assert result["server_id"] == "devrev-mcp"
        assert result["count"] == 3
        names = [t["name"] for t in result["tools"]]
        assert "create_ticket" in names
        assert "get_ticket" in names
        assert "update_ticket" in names

    async def test_tools_have_correct_full_name(self, mock_cfg):
        result = await get_mcp_server_tools("memory")
        for tool in result["tools"]:
            assert tool["full_name"].startswith("mcp__memory__")
            assert tool["name"] == tool["full_name"].replace("mcp__memory__", "")

    async def test_returns_empty_for_unknown_server(self, mock_cfg):
        result = await get_mcp_server_tools("nonexistent-server")
        assert result["count"] == 0
        assert result["tools"] == []

    async def test_non_mcp_tools_excluded(self, mock_cfg):
        result = await get_mcp_server_tools("devrev-mcp")
        names = [t["name"] for t in result["tools"]]
        assert "Bash" not in names
        assert "Task" not in names
        assert "Glob" not in names

    async def test_sequential_thinking(self, mock_cfg):
        result = await get_mcp_server_tools("sequentialthinking")
        assert result["count"] == 1
        assert result["tools"][0]["name"] == "sequentialthinking"
        assert result["tools"][0]["full_name"] == "mcp__sequentialthinking__sequentialthinking"

    async def test_blade_mcp_tools(self, mock_cfg):
        result = await get_mcp_server_tools("blade-mcp")
        assert result["count"] == 2
        names = [t["name"] for t in result["tools"]]
        assert "hi_blade" in names
        assert "get_blade_component_docs" in names

    async def test_raises_500_on_error(self):
        with patch(PATCH_TARGET, side_effect=RuntimeError("boom")):
            with pytest.raises(HTTPException) as exc_info:
                await get_mcp_server_tools("devrev-mcp")
            assert exc_info.value.status_code == 500

    async def test_no_mcp_tools_in_config_returns_empty(self):
        with patch(PATCH_TARGET, return_value={"agent": {"allowed_tools": "Task,Bash,Glob"}}):
            result = await get_mcp_server_tools("devrev-mcp")
            assert result["count"] == 0
            assert result["tools"] == []

    async def test_missing_agent_key_falls_back_to_source(self):
        # When agent key is absent, falls back to inspect on claude_code.py — just verify shape
        with patch(PATCH_TARGET, return_value={}):
            result = await get_mcp_server_tools("devrev-mcp")
            assert "server_id" in result
            assert "tools" in result
            assert "count" in result
            assert result["server_id"] == "devrev-mcp"
