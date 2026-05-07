"""
FastAPI routers package.

This package contains the FastAPI router modules that replace Flask blueprints.
"""

from . import tasks, health, agents_catalogue, agents, admin, files, code_review, plugin_metrics, agent_skills, schedules, plugins_catalogue, discover, pulse

__all__ = ["tasks", "health", "agents_catalogue", "agents", "admin", "files", "code_review", "plugin_metrics", "agent_skills", "schedules", "plugins_catalogue", "discover", "pulse"]
