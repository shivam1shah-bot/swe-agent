"""
Unit tests for BladeSubAgent.

Tests the Blade Design System sub-agent including:
- Frontend file detection (should_execute hook)
- Blade component extraction
- Prompt rendering via pr-prompt-kit
- Response parsing
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from pr_prompt_kit import PRAgentKit

from src.agents.review_agents.subagent_base import ReviewSubAgentBase
from src.agents.review_agents.subagents import BladeSubAgent
from src.agents.review_agents.constants import SubAgentCategory, CATEGORY_LABELS
from src.agents.review_agents.subagent_registry import SubAgentRegistry


class TestBladeSubAgentProperties:
    """Test BladeSubAgent properties."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_category_returns_blade(self, mock_get_instance, mock_pr_agent_kit):
        """Test that category returns 'blade'."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        assert agent.category == "blade"
        assert agent.category == SubAgentCategory.BLADE.value

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_category_label_returns_blade_design_system(self, mock_get_instance, mock_pr_agent_kit):
        """Test that category_label returns 'BLADE'."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        assert agent.category_label == "BLADE"
        assert agent.category_label == CATEGORY_LABELS[SubAgentCategory.BLADE.value]

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_inherits_from_base(self, mock_get_instance, mock_pr_agent_kit):
        """Test that BladeSubAgent inherits from ReviewSubAgentBase."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        assert isinstance(agent, ReviewSubAgentBase)

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_can_be_instantiated(self, mock_get_instance, mock_pr_agent_kit):
        """Test that BladeSubAgent can be instantiated."""
        mock_get_instance.return_value = MagicMock()

        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
            confidence_threshold=0.7,
        )

        assert agent is not None
        assert agent._working_directory == "/tmp/test"
        assert agent._confidence_threshold == 0.7


class TestBladeSubAgentShouldExecute:
    """Test BladeSubAgent.should_execute() hook."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_should_execute_returns_true_for_tsx_files(self, mock_get_instance, mock_pr_agent_kit):
        """Test should_execute returns True for .tsx files."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = "+++ b/src/components/Button.tsx"
        should_run, skip_reason = agent.should_execute(diff)

        assert should_run is True
        assert skip_reason is None

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_should_execute_returns_true_for_jsx_files(self, mock_get_instance, mock_pr_agent_kit):
        """Test should_execute returns True for .jsx files."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = "+++ b/src/App.jsx"
        should_run, skip_reason = agent.should_execute(diff)

        assert should_run is True
        assert skip_reason is None

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_should_execute_returns_true_for_js_files(self, mock_get_instance, mock_pr_agent_kit):
        """Test should_execute returns True for .js files."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = "+++ b/src/utils.js"
        should_run, skip_reason = agent.should_execute(diff)

        assert should_run is True
        assert skip_reason is None

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_should_execute_returns_true_for_css_files(self, mock_get_instance, mock_pr_agent_kit):
        """Test should_execute returns True for .css files."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = "+++ b/styles/main.css"
        should_run, skip_reason = agent.should_execute(diff)

        assert should_run is True
        assert skip_reason is None

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_should_execute_returns_false_for_python_only(self, mock_get_instance, mock_pr_agent_kit):
        """Test should_execute returns False for Python-only diff."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = "+++ b/src/main.py"
        should_run, skip_reason = agent.should_execute(diff)

        assert should_run is False
        assert skip_reason == "No frontend files detected in diff"

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_should_execute_returns_false_for_go_only(self, mock_get_instance, mock_pr_agent_kit):
        """Test should_execute returns False for Go-only diff."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = "+++ b/pkg/handler.go"
        should_run, skip_reason = agent.should_execute(diff)

        assert should_run is False
        assert skip_reason == "No frontend files detected in diff"

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_should_execute_returns_true_for_mixed_files(self, mock_get_instance, mock_pr_agent_kit):
        """Test should_execute returns True when mixed frontend and backend files."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = """+++ b/src/main.py
+++ b/ui/App.tsx"""
        should_run, skip_reason = agent.should_execute(diff)

        assert should_run is True
        assert skip_reason is None


class TestBladeSubAgentComponentExtraction:
    """Test BladeSubAgent Blade component extraction."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_extracts_single_component(self, mock_get_instance, mock_pr_agent_kit):
        """Test extraction of a single Blade component."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = """import { Button } from '@razorpay/blade/components';"""
        components = agent._extract_blade_components(diff)

        assert components == ["Button"]

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_extracts_multiple_components(self, mock_get_instance, mock_pr_agent_kit):
        """Test extraction of multiple Blade components."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = """import { Button, Card, TextInput } from '@razorpay/blade/components';"""
        components = agent._extract_blade_components(diff)

        assert set(components) == {"Button", "Card", "TextInput"}

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_handles_aliased_imports(self, mock_get_instance, mock_pr_agent_kit):
        """Test handling of aliased imports."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = """import { Button as BladeButton } from '@razorpay/blade';"""
        components = agent._extract_blade_components(diff)

        assert components == ["Button"]

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_returns_empty_for_no_blade_imports(self, mock_get_instance, mock_pr_agent_kit):
        """Test returns empty list when no Blade imports."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = """import React from 'react';
import { useState } from 'react';"""
        components = agent._extract_blade_components(diff)

        assert components == []

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_deduplicates_components(self, mock_get_instance, mock_pr_agent_kit):
        """Test that duplicate components are deduplicated."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = """import { Button } from '@razorpay/blade';
import { Button, Card } from '@razorpay/blade/components';"""
        components = agent._extract_blade_components(diff)

        assert set(components) == {"Button", "Card"}
        assert len(components) == 2


class TestBladeSubAgentPromptRendering:
    """Test BladeSubAgent prompt rendering with pr-prompt-kit."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_render_prompt_uses_pr_prompt_kit(self, mock_get_instance):
        """Test _render_prompt uses pr-prompt-kit's render_subagent."""
        mock_get_instance.return_value = MagicMock()
        # Use real PRAgentKit to test actual prompt rendering
        real_kit = PRAgentKit()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=real_kit,
        )

        diff = "+++ b/App.tsx\nimport { Button } from '@razorpay/blade';"
        result = agent._render_prompt(
            diff=diff,
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="Test description",
            branch="feature/test",
        )

        assert result.system is not None
        assert result.user is not None
        # Name is set by pr-prompt-kit template
        assert result.name is not None

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_render_prompt_returns_valid_structure(self, mock_get_instance):
        """Test _render_prompt returns valid RenderedPrompt structure."""
        mock_get_instance.return_value = MagicMock()
        real_kit = PRAgentKit()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=real_kit,
        )

        diff = "+++ b/App.tsx\nimport { Button } from '@razorpay/blade';"
        result = agent._render_prompt(
            diff=diff,
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Verify the structure, not the content (content is managed by pr-prompt-kit)
        assert result.system is not None
        assert result.user is not None
        assert len(result.system) > 0
        assert len(result.user) > 0

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_user_prompt_contains_pr_context(self, mock_get_instance):
        """Test user prompt contains PR context."""
        mock_get_instance.return_value = MagicMock()
        real_kit = PRAgentKit()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=real_kit,
        )

        diff = "+++ b/App.tsx"
        result = agent._render_prompt(
            diff=diff,
            pr_number=123,
            repository="org/repo",
            title="Test PR Title",
            description="Test description",
            branch="feature/test",
        )

        assert "org/repo" in result.user
        assert "123" in result.user
        assert "Test PR Title" in result.user
        assert "Test description" in result.user

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_user_prompt_includes_detected_components(self, mock_get_instance):
        """Test user prompt includes detected Blade components."""
        mock_get_instance.return_value = MagicMock()
        real_kit = PRAgentKit()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=real_kit,
        )

        diff = "+++ b/App.tsx\nimport { Button, Card } from '@razorpay/blade';"
        result = agent._render_prompt(
            diff=diff,
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Components are now rendered in user prompt via Jinja template
        assert "Button" in result.user
        assert "Card" in result.user

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_render_prompt_passes_blade_components_variable(self, mock_get_instance):
        """Test that blade_components are passed as template variable."""
        mock_get_instance.return_value = MagicMock()
        mock_kit = MagicMock()
        mock_kit.render_subagent.return_value = MagicMock(
            system="System prompt",
            user="User prompt",
            name="test",
        )

        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_kit,
        )

        diff = "+++ b/App.tsx\nimport { Button, Card } from '@razorpay/blade';"
        agent._render_prompt(
            diff=diff,
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        # Verify render_subagent was called with blade_components
        mock_kit.render_subagent.assert_called_once()
        call_args = mock_kit.render_subagent.call_args
        variables = call_args[1]["variables"]
        assert "blade_components" in variables
        assert set(variables["blade_components"]) == {"Button", "Card"}


class TestBladeSubAgentResponseParsing:
    """Test BladeSubAgent response parsing."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_valid_response(self, mock_get_instance, mock_pr_agent_kit):
        """Test parsing a valid YAML response."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        response = """
suggestions:
  - file: src/App.tsx
    line: 10
    importance: 7
    confidence: 0.85
    description: "Use tertiary variant only with primary color"
    suggestion_code: '<Button variant="tertiary" color="primary">'
"""
        result = agent._parse_response(response)

        assert len(result) == 1
        assert result[0]["file"] == "src/App.tsx"
        assert result[0]["line"] == 10
        assert result[0]["category"] == "BLADE"

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_empty_response(self, mock_get_instance, mock_pr_agent_kit):
        """Test parsing empty response."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        result = agent._parse_response("")

        assert result == []

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_parse_empty_suggestions(self, mock_get_instance, mock_pr_agent_kit):
        """Test parsing response with empty suggestions."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        result = agent._parse_response("suggestions: []")

        assert result == []


class TestBladeSubAgentExecution:
    """Test BladeSubAgent execution flow."""

    @pytest.fixture(autouse=True)
    def mock_temp_file(self):
        """Mock tempfile/os operations for stream-json output file."""
        with patch("src.agents.review_agents.subagent_base.tempfile.mkstemp", return_value=(999, "/tmp/fake-output.jsonl")), \
             patch("src.agents.review_agents.subagent_base.os.close"), \
             patch("src.agents.review_agents.subagent_base.os.path.exists", return_value=True), \
             patch("src.agents.review_agents.subagent_base.os.unlink"):
            yield

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_skips_for_backend_only_diff(self, mock_get_instance, mock_pr_agent_kit):
        """Test that execute skips for backend-only diff."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        result = await agent.execute(
            diff="+++ b/main.py",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        assert result.success is True
        assert result.skipped is True
        assert result.skip_reason == "No frontend files detected in diff"
        assert result.suggestions == []

    @pytest.mark.asyncio
    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    async def test_execute_runs_for_frontend_diff(self, mock_get_instance, mock_pr_agent_kit, mock_claude_tool):
        """Test that execute runs for frontend diff."""
        mock_get_instance.return_value = mock_claude_tool
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        result = await agent.execute(
            diff="+++ b/App.tsx\nimport { Button } from '@razorpay/blade';",
            pr_number=123,
            repository="org/repo",
            title="Test PR",
            description="",
            branch="main",
        )

        assert result.success is True
        assert result.skipped is False
        assert result.category == "blade"


class TestBladeSubAgentRegistration:
    """Test BladeSubAgent registry integration."""

    def test_blade_is_registered(self):
        """Test that BladeSubAgent is registered in the registry."""
        from src.agents.review_agents import subagents  # noqa: F401

        assert SubAgentRegistry.is_registered("blade")
        assert SubAgentRegistry.get("blade") == BladeSubAgent

    def test_blade_in_core_categories(self):
        """Test that blade is in CORE_CATEGORIES."""
        from src.agents.review_agents.constants import CORE_CATEGORIES

        assert "blade" in CORE_CATEGORIES

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_blade_created_via_registry(self, mock_get_instance, mock_pr_agent_kit, temp_working_dir):
        """Test BladeSubAgent can be created via registry."""
        mock_get_instance.return_value = MagicMock()

        agent = SubAgentRegistry.create_agent(
            category="blade",
            working_directory=temp_working_dir,
            kit=mock_pr_agent_kit,
        )

        assert isinstance(agent, BladeSubAgent)
        assert agent.category == "blade"


class TestBladeSubAgentEdgeCases:
    """Test BladeSubAgent edge cases."""

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_handles_malformed_import(self, mock_get_instance, mock_pr_agent_kit):
        """Test handling of malformed Blade imports."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = """import { from '@razorpay/blade';"""  # Malformed
        components = agent._extract_blade_components(diff)

        assert components == []

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_ignores_lowercase_imports(self, mock_get_instance, mock_pr_agent_kit):
        """Test that lowercase imports (not components) are ignored."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = """import { useTheme, useBreakpoint } from '@razorpay/blade';"""
        components = agent._extract_blade_components(diff)

        # Hooks start with lowercase, should not be extracted as components
        assert components == []

    @patch("src.agents.review_agents.subagent_base.ClaudeCodeTool.get_instance")
    def test_extracts_from_blade_subpaths(self, mock_get_instance, mock_pr_agent_kit):
        """Test extraction from various Blade import paths."""
        mock_get_instance.return_value = MagicMock()
        agent = BladeSubAgent(
            working_directory="/tmp/test",
            kit=mock_pr_agent_kit,
        )

        diff = """import { Button } from '@razorpay/blade/components';
import { Amount } from '@razorpay/blade/tokens';"""
        components = agent._extract_blade_components(diff)

        assert set(components) == {"Button", "Amount"}
