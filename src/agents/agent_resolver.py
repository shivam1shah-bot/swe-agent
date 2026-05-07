"""
Agent resolver — fetches agent definitions from the claude-plugins repo
and parses their YAML frontmatter into structured configuration.

Teams define agents in razorpay/claude-plugins as .md files with YAML
frontmatter declaring skills, description, etc. This module resolves an
agent name to its configuration so the autonomous agent pipeline can:
  1. Install the declared skills (from agent-skills repo)
  2. Inject the agent body as additional system prompt instructions
"""

import logging
import os
import subprocess
import threading
import time
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PLUGINS_REPO = "razorpay/claude-plugins"
PLUGINS_BRANCH = os.environ.get("AGENT_PLUGINS_BRANCH", "master")
CACHE_DIR = os.environ.get("AGENT_PLUGINS_CACHE_DIR", "/tmp/claude-plugins-cache")
CACHE_TTL_SECONDS = int(os.environ.get("AGENT_PLUGINS_CACHE_TTL", "3600"))


@dataclass
class AgentConfig:
    """Parsed agent definition from a claude-plugins .md file."""

    name: str
    skills: List[str] = field(default_factory=list)
    body: str = ""
    description: str = ""
    max_turns: Optional[int] = None
    raw_frontmatter: Dict = field(default_factory=dict)
    source_path: str = ""


def _parse_agent_md(file_path: str) -> Optional[AgentConfig]:
    """Parse a single agent .md file into an AgentConfig.

    Expected format:
        ---
        name: my-agent
        skills: skill-a, skill-b
        description: ...
        maxTurns: 50
        ---
        # Body markdown here...
    """
    try:
        with open(file_path, "r") as f:
            content = f.read()
    except OSError as e:
        logger.warning(f"Cannot read agent file {file_path}: {e}")
        return None

    # Split on --- markers
    parts = content.split("---", 2)
    if len(parts) < 3:
        logger.warning(f"Agent file {file_path} missing YAML frontmatter markers")
        return None

    frontmatter_raw = parts[1].strip()
    body = parts[2].strip()

    try:
        frontmatter = yaml.safe_load(frontmatter_raw) or {}
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {file_path}: {e}")
        return None

    name = frontmatter.get("name", "")
    if not name:
        logger.warning(f"Agent file {file_path} has no 'name' in frontmatter")
        return None

    # Parse skills — can be a YAML list or comma-separated string
    skills_raw = frontmatter.get("skills", [])
    if isinstance(skills_raw, str):
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
    elif isinstance(skills_raw, list):
        skills = [str(s).strip() for s in skills_raw if str(s).strip()]
    else:
        skills = []

    return AgentConfig(
        name=name,
        skills=skills,
        body=body,
        description=frontmatter.get("description", ""),
        max_turns=frontmatter.get("maxTurns"),
        raw_frontmatter=frontmatter,
        source_path=file_path,
    )


class AgentPluginCache:
    """Thread-safe cache for the claude-plugins repo clone."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_refresh: float = 0
        self._agents: Dict[str, AgentConfig] = {}

    def _clone_or_pull(self) -> bool:
        """Clone or pull the claude-plugins repo into the cache directory."""
        repo_dir = os.path.join(CACHE_DIR, "claude-plugins")

        try:
            if os.path.isdir(os.path.join(repo_dir, ".git")):
                result = subprocess.run(
                    ["git", "pull", "--ff-only"],
                    capture_output=True, text=True, cwd=repo_dir, timeout=60,
                )
                if result.returncode != 0:
                    logger.warning(f"git pull failed: {result.stderr[:200]}")
                    return False
                logger.info("Refreshed claude-plugins cache via git pull")
            else:
                os.makedirs(CACHE_DIR, exist_ok=True)
                result = subprocess.run(
                    ["gh", "repo", "clone", PLUGINS_REPO, repo_dir,
                     "--", "--depth", "1", "--single-branch", "--branch", PLUGINS_BRANCH],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    logger.error(f"Failed to clone {PLUGINS_REPO}: {result.stderr[:200]}")
                    return False
                logger.info(f"Cloned {PLUGINS_REPO} into {repo_dir}")

            return True
        except Exception as e:
            logger.error(f"Error refreshing claude-plugins cache: {e}")
            return False

    def _scan_agents(self) -> Dict[str, AgentConfig]:
        """Scan all plugins/*/agents/*.md files and build name→config map."""
        agents: Dict[str, AgentConfig] = {}
        plugins_dir = os.path.join(CACHE_DIR, "claude-plugins", "plugins")

        if not os.path.isdir(plugins_dir):
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return agents

        for plugin_entry in os.scandir(plugins_dir):
            if not plugin_entry.is_dir():
                continue
            agents_dir = os.path.join(plugin_entry.path, "agents")
            if not os.path.isdir(agents_dir):
                continue

            for file_entry in os.scandir(agents_dir):
                if not file_entry.name.endswith(".md"):
                    continue

                file_path = file_entry.path
                config = _parse_agent_md(file_path)
                if config:
                    if config.name in agents:
                        logger.warning(
                            f"Duplicate agent name '{config.name}' "
                            f"in {file_path}, overwriting previous from {agents[config.name].source_path}"
                        )
                    agents[config.name] = config

        logger.info(f"Scanned {len(agents)} agents from claude-plugins: {list(agents.keys())}")
        return agents

    def refresh_if_stale(self) -> None:
        """Refresh the cache if TTL has expired."""
        now = time.time()
        if now - self._last_refresh < CACHE_TTL_SECONDS and self._agents:
            return

        with self._lock:
            # Double-check after acquiring lock (re-read time to avoid stale comparison)
            if time.time() - self._last_refresh < CACHE_TTL_SECONDS and self._agents:
                return

            if self._clone_or_pull():
                self._agents = self._scan_agents()
                self._last_refresh = time.time()
            elif not self._agents:
                logger.warning("No cached agents available and refresh failed")

    def get_agent(self, agent_name: str) -> Optional[AgentConfig]:
        """Get an agent config by name, refreshing cache if needed."""
        self.refresh_if_stale()
        return self._agents.get(agent_name)

    def list_agents(self) -> List[str]:
        """List all available agent names."""
        self.refresh_if_stale()
        return list(self._agents.keys())


# Module-level singleton
_cache = AgentPluginCache()


def resolve_agent(agent_name: str) -> Optional[AgentConfig]:
    """Resolve an agent name to its configuration.

    Fetches from the claude-plugins repo (cached), parses frontmatter,
    and returns the AgentConfig. Returns None if agent not found.
    """
    if not agent_name:
        return None

    config = _cache.get_agent(agent_name)
    if config:
        logger.info(
            f"Resolved agent '{agent_name}': skills={config.skills}, "
            f"body_length={len(config.body)}, source={config.source_path}"
        )
    else:
        logger.warning(f"Agent '{agent_name}' not found in claude-plugins")

    return config


def list_available_agents() -> List[str]:
    """List all agent names available from claude-plugins."""
    return _cache.list_agents()


# ---------------------------------------------------------------------------
# Plugin installation helpers
# ---------------------------------------------------------------------------


def _copy_dir_contents(src_dir: str, dst_dir: str) -> None:
    """
    Recursively copy the contents of src_dir into dst_dir.

    Existing files are preserved (not overwritten) so that repo-local assets
    always take precedence over plugin-provided defaults.
    """
    import shutil

    os.makedirs(dst_dir, exist_ok=True)
    for entry in os.scandir(src_dir):
        dst_path = os.path.join(dst_dir, entry.name)
        if entry.is_dir(follow_symlinks=False):
            _copy_dir_contents(entry.path, dst_path)
        elif entry.is_file(follow_symlinks=False):
            if not os.path.exists(dst_path):
                shutil.copy2(entry.path, dst_path)


def install_all_plugins(target_dir: str, task_id: Optional[str] = None) -> None:
    """
    Install all plugins from the razorpay/claude-plugins repo into *target_dir*.

    Assets from each plugin directory are copied into the matching Claude
    sub-directory inside target_dir:

        plugins/<plugin>/commands/ → <target_dir>/.claude/commands/
        plugins/<plugin>/agents/   → <target_dir>/.claude/agents/
        plugins/<plugin>/skills/   → <target_dir>/.claude/skills/
        plugins/<plugin>/hooks/    → <target_dir>/.claude/hooks/

    The copy is non-destructive: if a destination file already exists it is
    left untouched so that repo-local content always takes precedence.

    The function delegates cache management (clone/pull) to the same
    :class:`AgentPluginCache` singleton used by :func:`resolve_agent`, so
    no additional network round-trips are needed when both are called for the
    same task.
    """
    _cache.refresh_if_stale()

    plugins_dir = os.path.join(CACHE_DIR, "claude-plugins", "plugins")
    if not os.path.isdir(plugins_dir):
        logger.warning(
            f"claude-plugins directory not found at {plugins_dir}; "
            "skipping plugin installation",
            extra={"task_id": task_id},
        )
        return

    os.makedirs(target_dir, exist_ok=True)

    # Sub-directories within each plugin that map to .claude/ counterparts
    PLUGIN_ASSET_DIRS = ["commands", "agents", "skills", "hooks"]

    installed_count = 0
    for plugin_entry in os.scandir(plugins_dir):
        if not plugin_entry.is_dir():
            continue

        plugin_name = plugin_entry.name
        plugin_dir = plugin_entry.path
        any_installed = False

        for asset_dir in PLUGIN_ASSET_DIRS:
            src = os.path.join(plugin_dir, asset_dir)
            if not os.path.isdir(src):
                continue

            dst = os.path.join(target_dir, ".claude", asset_dir)
            try:
                _copy_dir_contents(src, dst)
                any_installed = True
                logger.debug(
                    f"Installed plugin asset '{plugin_name}/{asset_dir}' → "
                    f"{dst}",
                    extra={"task_id": task_id, "plugin": plugin_name},
                )
            except Exception as e:
                logger.warning(
                    f"Failed to copy plugin '{plugin_name}/{asset_dir}': {e}",
                    extra={"task_id": task_id, "plugin": plugin_name},
                )

        if any_installed:
            installed_count += 1
            logger.info(
                f"Installed claude-plugin '{plugin_name}' into {target_dir}",
                extra={"task_id": task_id, "plugin": plugin_name},
            )

    logger.info(
        f"claude-plugins installation complete: {installed_count} plugins "
        f"installed into {target_dir}/.claude/",
        extra={"task_id": task_id},
    )
