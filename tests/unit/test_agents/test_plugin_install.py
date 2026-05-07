"""
Requirement-driven tests for:

  "Make agents/run API work with claude-plugins repo. Install all plugins from
   razorpay/claude-plugins@master to the agent before starting headless invocation."

What we validate:
  1. Plugins are installed BEFORE the headless Claude invocation starts.
  2. Plugin install failure does NOT abort the task — Claude still runs.
  3. All plugin asset types (commands, agents, skills, hooks) are installed
     into the agent's working directory under .claude/.
  4. Existing .claude/ files in the working directory are never overwritten.
  5. Plugins are fetched from the 'master' branch by default.
"""

import logging
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_plugin_cache(cache_root: Path) -> None:
    """
    Build a fake razorpay/claude-plugins cache with two plugins,
    covering all four asset types: commands, agents, skills, hooks.
    """
    plugins = {
        "blade": {
            "commands": ["blade-cmd.md"],
            "skills": ["blade-skill.md"],
        },
        "api-style": {
            "agents": ["api-agent.md"],
            "hooks": ["post-run.sh"],
        },
    }
    for plugin_name, assets in plugins.items():
        for asset_type, files in assets.items():
            asset_dir = cache_root / "claude-plugins" / "plugins" / plugin_name / asset_type
            asset_dir.mkdir(parents=True, exist_ok=True)
            for fname in files:
                (asset_dir / fname).write_text(f"# {fname}")


def _make_tool():
    """Return an AutonomousAgentTool with infrastructure mocked out."""
    from src.agents.autonomous_agent import AutonomousAgentTool

    tool = AutonomousAgentTool.__new__(AutonomousAgentTool)
    tool.claude_tool = MagicMock()
    tool.anthropic_model = "claude-sonnet-4-5"
    tool.disable_prompt_caching = False
    tool.mcp_config_path = "/fake/mcp.json"
    tool.env_vars = {}
    return tool


# ---------------------------------------------------------------------------
# 1. Plugins are installed BEFORE the headless Claude invocation starts
# ---------------------------------------------------------------------------

class TestPluginsInstalledBeforeClaude:

    def test_plugin_install_happens_before_run_agent(self, tmp_path):
        """
        The plugin installation step must complete before _run_agent() is called.
        """
        tool = _make_tool()
        call_order = []

        def record_install(*args, **kwargs):
            call_order.append("install_plugins")

        def record_run(*args, **kwargs):
            call_order.append("run_agent")
            return {"content": "done"}

        tool._install_claude_plugins = MagicMock(side_effect=record_install)
        tool._run_agent = MagicMock(side_effect=record_run)
        tool._inject_skills = MagicMock()
        tool._exclude_skills_from_git = MagicMock()

        tool.execute({"prompt": "do the task", "working_dir": str(tmp_path)})

        assert call_order.index("install_plugins") < call_order.index("run_agent"), (
            "Plugin installation must happen before the headless Claude invocation"
        )

    def test_plugin_install_is_called_every_execution(self, tmp_path):
        """
        Every call to agents/run must trigger plugin installation,
        not just the first one.
        """
        tool = _make_tool()
        tool._install_claude_plugins = MagicMock()
        tool._run_agent = MagicMock(return_value={"content": "done"})
        tool._inject_skills = MagicMock()
        tool._exclude_skills_from_git = MagicMock()

        params = {"prompt": "task", "working_dir": str(tmp_path)}
        tool.execute(params)
        tool.execute(params)

        assert tool._install_claude_plugins.call_count == 2, (
            "Plugins must be installed on every invocation"
        )


# ---------------------------------------------------------------------------
# 2. Plugin install failure does NOT abort the task
# ---------------------------------------------------------------------------

class TestPluginInstallFailureIsNonFatal:

    def test_claude_still_runs_when_plugin_install_fails(self, tmp_path):
        """
        If the underlying claude-plugins clone/copy fails for any reason,
        the headless Claude invocation must still proceed.

        We fail install_all_plugins (not the wrapper) so that the wrapper's
        own exception handling is what's being exercised — not bypassed.
        """
        tool = _make_tool()
        tool._run_agent = MagicMock(return_value={"content": "done"})
        tool._inject_skills = MagicMock()
        tool._exclude_skills_from_git = MagicMock()

        with patch("src.agents.agent_resolver.install_all_plugins",
                   side_effect=RuntimeError("clone failed")):
            tool.execute({"prompt": "do the task", "working_dir": str(tmp_path)})

        assert tool._run_agent.called, (
            "_run_agent must be called even when plugin installation fails internally"
        )

    def test_task_returns_success_when_plugin_install_fails(self, tmp_path):
        """
        A plugin install failure must not surface as a task failure.

        We fail install_all_plugins (not the wrapper) so that the wrapper's
        own exception handling is what's being exercised — not bypassed.
        """
        tool = _make_tool()
        tool._run_agent = MagicMock(return_value={"content": "done"})
        tool._inject_skills = MagicMock()
        tool._exclude_skills_from_git = MagicMock()

        with patch("src.agents.agent_resolver.install_all_plugins",
                   side_effect=Exception("network error")):
            result = tool.execute({"prompt": "do the task", "working_dir": str(tmp_path)})

        assert result.get("success") is True, (
            "Task must succeed even if plugin installation fails internally"
        )

    def test_failure_is_logged_as_warning_not_error(self, tmp_path, caplog):
        """
        Plugin install failures must be logged as warnings so they are
        visible in logs but do not indicate a task error.
        """
        from src.agents.autonomous_agent import AutonomousAgentTool

        tool = _make_tool()
        with patch("src.agents.agent_resolver.install_all_plugins",
                   side_effect=Exception("network error")), \
             caplog.at_level(logging.WARNING, logger="src.agents.autonomous_agent"):
            tool._install_claude_plugins(str(tmp_path))

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warning_records, "A WARNING must be logged when plugin install fails"


# ---------------------------------------------------------------------------
# 3. All plugin asset types are installed into the working directory
# ---------------------------------------------------------------------------

class TestAllPluginAssetsAreInstalled:

    def test_commands_agents_skills_hooks_all_installed(self, tmp_path):
        """
        Every asset type declared in the requirement — commands, agents,
        skills, hooks — must land in <working_dir>/.claude/<asset-type>/.
        """
        from src.agents import agent_resolver

        cache_dir = tmp_path / "cache"
        _make_plugin_cache(cache_dir)
        target = tmp_path / "workspace"

        with patch.object(agent_resolver._cache, "refresh_if_stale"), \
             patch("src.agents.agent_resolver.CACHE_DIR", str(cache_dir)):
            agent_resolver.install_all_plugins(str(target))

        assert (target / ".claude" / "commands" / "blade-cmd.md").exists(), \
            "commands/ assets must be installed"
        assert (target / ".claude" / "skills" / "blade-skill.md").exists(), \
            "skills/ assets must be installed"
        assert (target / ".claude" / "agents" / "api-agent.md").exists(), \
            "agents/ assets must be installed"
        assert (target / ".claude" / "hooks" / "post-run.sh").exists(), \
            "hooks/ assets must be installed"

    def test_assets_from_all_plugins_are_installed(self, tmp_path):
        """
        Assets from every plugin in the repo must be installed,
        not just the first one encountered.
        """
        from src.agents import agent_resolver

        cache_dir = tmp_path / "cache"
        _make_plugin_cache(cache_dir)
        target = tmp_path / "workspace"

        with patch.object(agent_resolver._cache, "refresh_if_stale"), \
             patch("src.agents.agent_resolver.CACHE_DIR", str(cache_dir)):
            agent_resolver.install_all_plugins(str(target))

        # Both plugins must be present
        assert (target / ".claude" / "commands" / "blade-cmd.md").exists(), \
            "'blade' plugin assets must be installed"
        assert (target / ".claude" / "agents" / "api-agent.md").exists(), \
            "'api-style' plugin assets must be installed"


# ---------------------------------------------------------------------------
# 4. Existing .claude/ files are never overwritten
# ---------------------------------------------------------------------------

class TestNonDestructiveInstall:

    def test_repo_local_claude_files_are_preserved(self, tmp_path):
        """
        If the repository already has .claude/ files, the plugin installer
        must not overwrite them. Repo-local content always takes precedence.
        """
        from src.agents import agent_resolver

        cache_dir = tmp_path / "cache"
        _make_plugin_cache(cache_dir)
        target = tmp_path / "workspace"

        # Simulate a repo-local command file that conflicts with a plugin file
        existing_file = target / ".claude" / "commands" / "blade-cmd.md"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("repo-local content — must not be overwritten")

        with patch.object(agent_resolver._cache, "refresh_if_stale"), \
             patch("src.agents.agent_resolver.CACHE_DIR", str(cache_dir)):
            agent_resolver.install_all_plugins(str(target))

        assert existing_file.read_text() == "repo-local content — must not be overwritten", (
            "Plugin installer must not overwrite existing .claude/ files"
        )


# ---------------------------------------------------------------------------
# 5. Plugins are fetched from the 'master' branch by default
# ---------------------------------------------------------------------------

def test_plugins_fetched_from_master_branch_by_default(monkeypatch):
    """
    The requirement specifies razorpay/claude-plugins@master.
    When no override is set, the default branch must be 'master'.
    """
    monkeypatch.delenv("AGENT_PLUGINS_BRANCH", raising=False)

    import importlib
    import src.agents.agent_resolver as ar
    importlib.reload(ar)

    assert ar.PLUGINS_BRANCH == "master", (
        "Plugins must be fetched from 'master' branch of razorpay/claude-plugins"
    )
