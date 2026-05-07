"""
Feature gates for review capabilities.

Controls incremental rollout of advanced review features
(skill-driven auto-approve, smart exclusion, skill auto-generation, etc.).
"""

import logging
from typing import List

from src.providers.config_loader import get_config

logger = logging.getLogger(__name__)


def is_rcore_v2_plus_enabled(repository: str) -> bool:
    """
    Check if a repository is whitelisted for rCoRe v2++ features.

    Reads [rcore_v2_plus] config section. Returns False if the section
    is missing or the global flag is disabled (safe default).

    Args:
        repository: Repository in "owner/repo" format

    Returns:
        True if the repo has v2++ features enabled
    """
    config = get_config()
    v2_config = config.get("rcore_v2_plus", {})

    if not v2_config.get("enabled", False):
        logger.info(
            "rCoRe v2++ globally disabled — skipping auto-approve for %s",
            repository,
        )
        return False

    enabled_repos: List[str] = v2_config.get("enabled_repos", [])
    logger.info(
        "rCoRe v2++ enabled, whitelisted repos: %s, checking repo: %s",
        enabled_repos, repository,
    )

    # Wildcard: ["*"] enables all repos
    if "*" in enabled_repos:
        logger.info("Wildcard '*' in whitelist — auto-approve allowed for %s", repository)
        return True

    # Case-insensitive match
    repo_lower = repository.lower()
    is_whitelisted = any(r.lower() == repo_lower for r in enabled_repos)

    if is_whitelisted:
        logger.info("Repo %s is whitelisted — auto-approve flow allowed", repository)
    else:
        logger.info(
            "Repo %s is NOT in whitelist %s — auto-approve flow blocked",
            repository, enabled_repos,
        )

    return is_whitelisted


def is_skill_auto_generation_enabled() -> bool:
    """
    Check if on-the-fly skill generation is enabled.

    When disabled, reviews proceed with only pre-existing skills —
    no LLM call to generate missing risk-assessment / code-review skills.

    Reads [skill_auto_generation] config section.
    Defaults to False (disabled) if the section is missing.

    Returns:
        True if skill auto-generation is enabled
    """
    config = get_config()
    sg_config = config.get("skill_auto_generation", {})
    enabled = sg_config.get("enabled", False)

    if not enabled:
        logger.info("Skill auto-generation is disabled")
    else:
        logger.info("Skill auto-generation is enabled")

    return enabled
