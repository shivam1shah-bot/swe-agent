"""
Agent Skills router.

Endpoints:
  GET  /api/v1/agent-skills/global/list    - list skills (cache-first)
  POST /api/v1/agent-skills/global/refresh - force-refresh cache (for cron)
"""

import asyncio
import json
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.providers.auth import require_role
from src.providers.logger import Logger
from ..dependencies import get_logger

router = APIRouter()

_SKILLS_CACHE_KEY = "swe-agent:skills:list"
_SKILLS_CACHE_TTL = 365 * 24 * 60 * 60  # 1 year — refreshed on demand via /global/refresh

_frontmatter_re = re.compile(r'^---\s*\n(.*?)\n---', re.DOTALL)
_name_re = re.compile(r'^name:\s*(.+)$', re.MULTILINE)
_desc_re = re.compile(r'^description:\s*(.+)$', re.MULTILINE)

_REPO_OWNER = "razorpay"
_REPO_NAME = "agent-skills"
_REPO_BRANCH = "master"

# GraphQL batch size — GitHub allows large queries but we chunk to stay safe
_GQL_CHUNK_SIZE = 50


def _parse_frontmatter(content: str) -> Optional[Dict[str, str]]:
    fm = _frontmatter_re.match(content)
    if not fm:
        return None
    fm_text = fm.group(1)
    name_m = _name_re.search(fm_text)
    desc_m = _desc_re.search(fm_text)
    name = name_m.group(1).strip().strip('"\'') if name_m else None
    description = desc_m.group(1).strip().strip('"\'') if desc_m else ""
    return {"name": name, "description": description} if name else None


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
            detail={"error": "Timeout fetching skills", "error_code": "SKILLS_LIST_TIMEOUT"}
        )
    if proc.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": f"GitHub API error: {err.decode(errors='replace')[:200]}", "error_code": "SKILLS_GITHUB_ERROR"}
        )
    return json.loads(out)


async def _fetch_skills_from_github() -> List[Dict[str, str]]:
    """
    Fetch all SKILL.md paths via the tree API, then batch-fetch their contents
    via GraphQL (one aliased query per chunk of paths). Much faster than
    spawning one subprocess per file.
    """
    # Step 1: get recursive tree to find all SKILL.md paths
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
            detail={"error": "Timeout fetching skills tree", "error_code": "SKILLS_LIST_TIMEOUT"}
        )
    if proc.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": f"Failed to fetch skills tree: {err.decode(errors='replace')[:200]}", "error_code": "SKILLS_GITHUB_ERROR"}
        )

    tree = json.loads(out).get("tree", [])
    skill_paths = [
        item["path"] for item in tree
        if item["type"] == "blob" and item["path"].upper().endswith("SKILL.MD")
    ]

    if not skill_paths:
        return []

    # Step 2: batch-fetch file contents via GraphQL aliases (one round-trip per chunk)
    skills: List[Dict[str, str]] = []

    for i in range(0, len(skill_paths), _GQL_CHUNK_SIZE):
        chunk = skill_paths[i:i + _GQL_CHUNK_SIZE]

        # Build aliased GraphQL query: each file gets alias f0, f1, f2...
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
            parsed = _parse_frontmatter(text)
            if parsed:
                skills.append(parsed)

    return skills


@router.get("/global/list",
            summary="List Available Agent Skills",
            description="Returns skills from razorpay/agent-skills (served from cache, populated on first call).")
@require_role(["dashboard", "admin"])
async def list_agent_skills(
    request: Request,
    logger: Logger = Depends(get_logger)
):
    from src.providers.cache import cache_provider

    try:
        cached = cache_provider.get(_SKILLS_CACHE_KEY)
        if cached is not None:
            logger.info(f"Skills served from cache ({len(cached)} skills)")
            return cached

        skills = await _fetch_skills_from_github()
        if skills:
            cache_provider.set(_SKILLS_CACHE_KEY, skills, ttl=_SKILLS_CACHE_TTL)
        logger.info(f"Listed {len(skills)} agent skills (fetched from GitHub)")
        return skills

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing agent skills", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to list agent skills: {str(e)}", "error_code": "SKILLS_LIST_ERROR"}
        )


@router.post("/global/refresh",
             summary="Refresh Agent Skills Cache",
             description="Fetches latest skills from GitHub and updates the cache. Intended for cron use.")
@require_role(["dashboard", "admin"])
async def refresh_agent_skills(
    request: Request,
    logger: Logger = Depends(get_logger)
):
    from src.providers.cache import cache_provider

    try:
        skills = await _fetch_skills_from_github()
        cache_provider.set(_SKILLS_CACHE_KEY, skills, ttl=_SKILLS_CACHE_TTL)
        logger.info(f"Skills cache refreshed ({len(skills)} skills)")
        return {"refreshed": True, "count": len(skills)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error refreshing agent skills", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to refresh agent skills: {str(e)}", "error_code": "SKILLS_REFRESH_ERROR"}
        )
