"""
Plugins Catalogue router.

Endpoints:
  GET  /api/v1/plugins-catalogue/list                    - list plugins (cache-first)
  POST /api/v1/plugins-catalogue/refresh                 - force-refresh cache
  GET  /api/v1/plugins-catalogue/{plugin_dir}/agents     - fetch agent frontmatter on demand

Note: Uses gh CLI subprocess (same pattern as agent_skills.py) since GitHub auth
is managed via `gh auth login` / CLI sync service in this codebase.
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Union

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from src.providers.auth import require_role
from src.providers.cache import cache_provider
from src.providers.logger import Logger
from ..dependencies import get_logger

router = APIRouter()

_PLUGINS_CACHE_KEY = "swe-agent:plugins:list"
_PLUGINS_CACHE_TTL = 365 * 24 * 60 * 60  # 1 year — refreshed on demand

_REPO_OWNER = "razorpay"
_REPO_NAME = "claude-plugins"
_REPO_BRANCH = "master"

_GQL_CHUNK_SIZE = 50

# Allowlist for valid slug characters — prevents GraphQL injection
_SAFE_SLUG_RE = re.compile(r'^[a-zA-Z0-9_\-]+$')


# ── Pydantic response models ──────────────────────────────────────────────────

class PluginItem(BaseModel):
    name: str
    plugin_dir: str
    description: str
    version: Optional[str] = None
    keywords: List[str] = []
    homepage: Optional[str] = None
    mcp_servers: bool = False
    agent_count: int = 0
    agents: List[str] = []
    command_count: int = 0
    skill_count: int = 0
    has_hooks: bool = False
    has_mcp: bool = False
    has_lsp: bool = False


class AgentItem(BaseModel):
    slug: str
    name: str
    description: str
    fields: Dict[str, Union[str, List[str]]] = {}


class RefreshResponse(BaseModel):
    refreshed: bool
    count: int


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_plugin_json(content: str, path: str) -> Optional[Dict[str, Any]]:
    """Parse a plugin.json file and extract relevant fields."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None

    name = data.get("name")
    if not name:
        return None

    parts = path.split("/")
    plugin_dir = parts[1] if len(parts) >= 3 else name

    return {
        "name": name,
        "plugin_dir": plugin_dir,
        "description": data.get("description", ""),
        "version": data.get("version"),
        "keywords": data.get("keywords", []),
        "homepage": data.get("homepage"),
        "mcp_servers": bool(data.get("mcpServers")),
    }


async def _gh_graphql(query: str) -> dict:
    """Run a gh api graphql call and return parsed JSON."""
    proc = await asyncio.create_subprocess_exec(
        "gh", "api", "graphql", "-f", f"query={query}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": "Timeout fetching plugins", "error_code": "PLUGINS_LIST_TIMEOUT"}
        )
    if proc.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": f"GitHub API error: {err.decode(errors='replace')[:200]}", "error_code": "PLUGINS_GITHUB_ERROR"}
        )
    return json.loads(out)


def _collect_plugin_stats(plugin_dir: str, all_paths: List[str]) -> Dict[str, Any]:
    """Derive component counts and agent file list for a plugin from the repo tree."""
    base = f"plugins/{plugin_dir}/"

    agents_prefix = f"{base}agents/"
    agents = [
        p[len(agents_prefix):].replace(".md", "")
        for p in all_paths
        if p.startswith(agents_prefix) and p.endswith(".md") and "/" not in p[len(agents_prefix):]
    ]

    commands_prefix = f"{base}commands/"
    command_count = sum(
        1 for p in all_paths
        if p.startswith(commands_prefix) and p.endswith(".md") and "/" not in p[len(commands_prefix):]
    )

    skills_prefix = f"{base}skills/"
    skill_count = sum(
        1 for p in all_paths
        if p.startswith(skills_prefix) and p.endswith("skill.md")
        and p[len(skills_prefix):].count("/") == 1  # skills/<name>/skill.md
    )

    has_hooks = any(p == f"{base}hooks/hooks.json" for p in all_paths)
    has_mcp = any(p == f"{base}.mcp.json" for p in all_paths)
    has_lsp = any(p == f"{base}.lsp.json" for p in all_paths)

    return {
        "agent_count": len(agents),
        "agents": agents,
        "command_count": command_count,
        "skill_count": skill_count,
        "has_hooks": has_hooks,
        "has_mcp": has_mcp,
        "has_lsp": has_lsp,
    }


async def _fetch_plugins_from_github() -> List[Dict[str, Any]]:
    """
    Fetch all plugin.json paths via the tree API, then batch-fetch their contents
    via GraphQL. Collects agent list, skill/command/hook/mcp/lsp counts per plugin.
    """
    proc = await asyncio.create_subprocess_exec(
        "gh", "api",
        f"repos/{_REPO_OWNER}/{_REPO_NAME}/git/trees/{_REPO_BRANCH}?recursive=1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=20)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": "Timeout fetching plugins tree", "error_code": "PLUGINS_LIST_TIMEOUT"}
        )
    if proc.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": f"Failed to fetch plugins tree: {err.decode(errors='replace')[:200]}", "error_code": "PLUGINS_GITHUB_ERROR"}
        )

    tree = json.loads(out).get("tree", [])
    all_paths = [item["path"] for item in tree if item["type"] == "blob"]

    plugin_json_paths = [
        p for p in all_paths
        if p.startswith("plugins/") and p.endswith("/.claude-plugin/plugin.json")
    ]

    if not plugin_json_paths:
        return []

    plugins: List[Dict[str, Any]] = []

    for i in range(0, len(plugin_json_paths), _GQL_CHUNK_SIZE):
        chunk = plugin_json_paths[i:i + _GQL_CHUNK_SIZE]
        aliases = "\n".join(
            f'f{j}: object(expression: "{_REPO_BRANCH}:{path}") {{ ... on Blob {{ text }} }}'
            for j, path in enumerate(chunk)
        )
        query = f"""
        {{
          repository(owner: "{_REPO_OWNER}", name: "{_REPO_NAME}") {{
            {aliases}
          }}
        }}
        """
        result = await _gh_graphql(query)
        repo_data = result.get("data", {}).get("repository", {})

        for j, path in enumerate(chunk):
            blob = repo_data.get(f"f{j}")
            if not blob:
                continue
            text = blob.get("text", "")
            if not text:
                continue
            parsed = _parse_plugin_json(text, path)
            if parsed:
                plugins.append(parsed)

    for plugin in plugins:
        stats = _collect_plugin_stats(plugin["plugin_dir"], all_paths)
        plugin.update(stats)

    return plugins


_FM_KNOWN_FIELDS = {
    "name", "description", "tools", "disallowedTools", "model",
    "permissionMode", "maxTurns", "skills", "mcpServers", "hooks",
    "memory", "background", "isolation",
}

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n?', re.DOTALL)


def _parse_agent_md(slug: str, content: str) -> Dict[str, Any]:
    """Extract supported frontmatter fields from an agent .md file using yaml.safe_load."""
    fm_match = _FRONTMATTER_RE.match(content)
    fields: Dict[str, Any] = {}
    if fm_match:
        try:
            raw = yaml.safe_load(fm_match.group(1)) or {}
            fields = {k: v for k, v in raw.items() if k in _FM_KNOWN_FIELDS}
        except yaml.YAMLError:
            pass

    # Normalise list fields to List[str], scalar fields to str
    normalised: Dict[str, Union[str, List[str]]] = {}
    for k, v in fields.items():
        if k in ("name", "description"):
            continue
        if isinstance(v, list):
            normalised[k] = [str(i) for i in v]
        else:
            normalised[k] = str(v)

    return {
        "slug": slug,
        "name": str(fields.get("name", slug)),
        "description": str(fields.get("description", "")),
        "fields": normalised,
    }


async def _fetch_agent_contents(plugin_dir: str, agent_slugs: List[str]) -> List[Dict[str, Any]]:
    """Batch-fetch all agent .md files for a plugin via GraphQL aliases."""
    # Validate all slugs before interpolation
    safe_slugs = [s for s in agent_slugs if _SAFE_SLUG_RE.match(s)]

    agents: List[Dict[str, Any]] = []
    for i in range(0, len(safe_slugs), _GQL_CHUNK_SIZE):
        chunk = safe_slugs[i:i + _GQL_CHUNK_SIZE]
        aliases = "\n".join(
            f'f{j}: object(expression: "{_REPO_BRANCH}:plugins/{plugin_dir}/agents/{slug}.md") {{ ... on Blob {{ text }} }}'
            for j, slug in enumerate(chunk)
        )
        query = f"""
        {{
          repository(owner: "{_REPO_OWNER}", name: "{_REPO_NAME}") {{
            {aliases}
          }}
        }}
        """
        result = await _gh_graphql(query)
        repo_data = result.get("data", {}).get("repository", {})

        for j, slug in enumerate(chunk):
            blob = repo_data.get(f"f{j}")
            if not blob:
                continue
            text = blob.get("text", "")
            if text:
                agents.append(_parse_agent_md(slug, text))

    return agents


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/list",
            response_model=List[PluginItem],
            summary="List Available Plugins",
            description="Returns plugins from razorpay/claude-plugins (served from cache, populated on first call).")
@require_role(["dashboard", "admin"])
async def list_plugins(
    request: Request,
    logger: Logger = Depends(get_logger)
):
    try:
        cached = cache_provider.get(_PLUGINS_CACHE_KEY)
        if cached is not None:
            logger.info(f"Plugins served from cache ({len(cached)} plugins)")
            return cached

        plugins = await _fetch_plugins_from_github()
        if plugins:
            cache_provider.set(_PLUGINS_CACHE_KEY, plugins, ttl=_PLUGINS_CACHE_TTL)
        logger.info(f"Listed {len(plugins)} plugins (fetched from GitHub)")
        return plugins

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing plugins", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to list plugins: {str(e)}", "error_code": "PLUGINS_LIST_ERROR"}
        )


@router.post("/refresh",
             response_model=RefreshResponse,
             summary="Refresh Plugins Cache",
             description="Fetches latest plugins from GitHub and updates the cache.")
@require_role(["dashboard", "admin"])
async def refresh_plugins(
    request: Request,
    logger: Logger = Depends(get_logger)
):
    try:
        plugins = await _fetch_plugins_from_github()
        cache_provider.set(_PLUGINS_CACHE_KEY, plugins, ttl=_PLUGINS_CACHE_TTL)
        logger.info(f"Plugins cache refreshed ({len(plugins)} plugins)")
        return {"refreshed": True, "count": len(plugins)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error refreshing plugins", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to refresh plugins: {str(e)}", "error_code": "PLUGINS_REFRESH_ERROR"}
        )


@router.get("/{plugin_dir}/agents",
            response_model=List[AgentItem],
            summary="Fetch Agent Frontmatter",
            description="Returns parsed frontmatter of all root-level agent .md files for a plugin. Fetched on demand.")
@require_role(["dashboard", "admin"])
async def get_plugin_agents(
    plugin_dir: str,
    request: Request,
    logger: Logger = Depends(get_logger)
):
    # Validate plugin_dir against cached allowlist
    if not _SAFE_SLUG_RE.match(plugin_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid plugin_dir", "error_code": "INVALID_PLUGIN_DIR"}
        )

    cached_plugins: Optional[List[Dict[str, Any]]] = cache_provider.get(_PLUGINS_CACHE_KEY)
    if cached_plugins is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Plugin cache is cold — call /list first", "error_code": "CACHE_COLD"}
        )

    known_dirs = {p["plugin_dir"] for p in cached_plugins}
    if plugin_dir not in known_dirs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": f"Plugin '{plugin_dir}' not found", "error_code": "PLUGIN_NOT_FOUND"}
        )

    agent_slugs: List[str] = next(
        (p["agents"] for p in cached_plugins if p["plugin_dir"] == plugin_dir), []
    )
    if not agent_slugs:
        return []

    try:
        agents = await _fetch_agent_contents(plugin_dir, agent_slugs)
        logger.info(f"Fetched {len(agents)} agent files for plugin '{plugin_dir}'")
        return agents

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agents for plugin '{plugin_dir}'", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch agents: {str(e)}", "error_code": "PLUGIN_AGENTS_ERROR"}
        )
