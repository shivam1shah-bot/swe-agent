"""
Shared fixtures for review agents unit tests.

Provides mock objects and sample data for testing sub-agents,
registry, and base class functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch


@pytest.fixture
def mock_claude_tool():
    """Mock ClaudeCodeTool for testing sub-agents."""
    mock_tool = MagicMock()
    mock_tool.execute = AsyncMock(
        return_value={
            "result": """
suggestions:
  - file: test.py
    line: 10
    importance: 8
    confidence: 0.9
    description: "Test issue found"
    suggestion_code: "fixed_code()"
"""
        }
    )
    return mock_tool


@pytest.fixture
def mock_claude_tool_empty():
    """Mock ClaudeCodeTool that returns empty suggestions."""
    mock_tool = MagicMock()
    mock_tool.execute = AsyncMock(return_value={"result": "suggestions: []"})
    return mock_tool


@pytest.fixture
def mock_claude_tool_error():
    """Mock ClaudeCodeTool that returns an error."""
    mock_tool = MagicMock()
    mock_tool.execute = AsyncMock(
        return_value={"error": True, "message": "Claude execution failed"}
    )
    return mock_tool


@pytest.fixture
def mock_pr_agent_kit():
    """Mock PRAgentKit for testing prompt rendering."""
    mock_kit = MagicMock()
    mock_rendered = MagicMock()
    mock_rendered.system = "You are a code reviewer specialized in finding bugs."
    mock_rendered.user = "Review this diff:\n--- a/file.py\n+++ b/file.py"
    mock_kit.render_subagent.return_value = mock_rendered

    # Add style guide support for StyleGuideSubAgent
    mock_style_guide = MagicMock()
    mock_style_guide.language = "python"
    mock_style_guide.content = (
        "You are a Python style guide reviewer.\n"
        "Confidence threshold: {{ confidence_threshold }}\n"
        "Check for PEP 8 compliance and naming conventions."
    )
    mock_kit.prompts.get_style_guide.return_value = mock_style_guide

    return mock_kit


@pytest.fixture
def sample_pr_context():
    """Sample PR context for testing sub-agent execution."""
    return {
        "diff": "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old_code()\n+new_code()",
        "pr_number": 123,
        "repository": "org/repo",
        "title": "Test PR: Fix bug in module",
        "description": "This PR fixes a critical bug in the module.",
        "branch": "feature/fix-bug",
    }


@pytest.fixture
def sample_yaml_response():
    """Sample YAML response from Claude for parsing tests."""
    return """
suggestions:
  - file: src/main.py
    line: 42
    importance: 7
    confidence: 0.85
    description: "Potential null pointer dereference"
    suggestion_code: "if value is not None:"
  - file: src/utils.py
    line: 100
    importance: 5
    confidence: 0.75
    description: "Missing error handling"
    suggestion_code: "try:\\n    process()\\nexcept Exception as e:\\n    logger.error(e)"
"""


@pytest.fixture
def sample_yaml_response_with_category():
    """Sample YAML response with category already set."""
    return """
suggestions:
  - file: src/main.py
    line: 42
    importance: 7
    confidence: 0.85
    description: "Potential null pointer"
    category: "EXISTING_CATEGORY"
"""


@pytest.fixture
def invalid_yaml_response():
    """Invalid YAML response for error handling tests."""
    return """
this is not valid yaml:
  - [broken structure
  key without value
"""


@pytest.fixture
def temp_working_dir(tmp_path):
    """Temporary working directory for tests."""
    return str(tmp_path)


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset SubAgentRegistry before each test to ensure isolation."""
    # Import here to avoid circular imports
    from src.agents.review_agents.subagent_registry import SubAgentRegistry

    # Store original state
    original_registry = SubAgentRegistry._registry.copy()

    yield

    # Restore original state after test
    SubAgentRegistry._registry = original_registry


@pytest.fixture
def clean_registry():
    """Provide a clean registry for tests that need complete isolation."""
    from src.agents.review_agents.subagent_registry import SubAgentRegistry

    # Clear the registry
    SubAgentRegistry.clear()

    yield SubAgentRegistry

    # Re-import subagents to restore registrations
    from src.agents.review_agents import subagents  # noqa: F401
