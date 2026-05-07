"""
Health check router for FastAPI.

This module provides comprehensive health check endpoints for the SWE Agent system.
"""

import logging
import time
import json
import os
import subprocess
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, status, Depends, Request

from src.services import TaskService
from src.providers.config_loader import get_config
from ..dependencies import get_cache_service

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

def get_task_service_for_health(request: Request) -> TaskService:
    """Dependency to get the task service instance for health checks."""
    try:
        # Use the task service from app state (initialized during startup)
        return request.app.state.task_service
    except AttributeError as e:
        logger.error(f"Failed to get task service from app state: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Task service not available in app state: {e}"
        )

@router.get("", response_model=Dict[str, Any])
async def overall_health(request: Request, cache_service = Depends(get_cache_service)):
    """
    Overall system health check.
    
    Returns comprehensive health information for all system components.
    """
    
    def fetch_health_status():
        start_time = time.time()
        
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "checks": {}
        }
        
        # Check database health
        try:
            database_provider = getattr(request.app.state, 'database_provider', None)
            if database_provider:
                db_health = database_provider.health_check()
                health_status["checks"]["database"] = db_health
                if db_health["status"] not in ["healthy"]:
                    health_status["status"] = "unhealthy"
            else:
                health_status["checks"]["database"] = {
                    "status": "error",
                    "message": "Database provider not initialized"
                }
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "message": f"Database check failed: {e}"
            }
            health_status["status"] = "unhealthy"
        
        # Check cache health
        try:
            cache_provider = getattr(request.app.state, 'cache_provider', None)
            if cache_provider:
                cache_health = cache_provider.health_check()
                health_status["checks"]["cache"] = cache_health
                if cache_health["status"] not in ["healthy"]:
                    # Cache is optional, so don't mark overall status as unhealthy
                    # but log the issue
                    logger.warning("Cache provider is not healthy but system can continue")
            else:
                health_status["checks"]["cache"] = {
                    "status": "error",
                    "message": "Cache provider not initialized"
                }
                logger.warning("Cache provider not initialized in app state")
        except Exception as e:
            health_status["checks"]["cache"] = {
                "status": "error",
                "message": f"Cache check failed: {e}"
            }
            logger.warning(f"Cache health check failed: {e}")
        
        # Check services health - verify app state services are accessible
        try:
            task_service = request.app.state.task_service
            agents_catalogue_service = request.app.state.agents_catalogue_service
            
            # Basic health check on the initialized services
            task_health = task_service.health_check()
            agents_catalogue_health = agents_catalogue_service.health_check()
            
            health_status["checks"]["services"] = {
                "status": "healthy",
                "message": "Services initialized and accessible from app state",
                "task_service": task_health["status"],
                "agents_catalogue_service": agents_catalogue_health["status"]
            }
        except AttributeError as e:
            health_status["checks"]["services"] = {
                "status": "unhealthy", 
                "message": f"Services not found in app state: {e}"
            }
            health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["services"] = {
                "status": "unhealthy",
                "message": f"Services health check failed: {e}"
            }
            health_status["status"] = "unhealthy"
        
        # Check configuration
        try:
            config = get_config()
            if config:
                health_status["checks"]["configuration"] = {
                    "status": "healthy",
                    "message": "Configuration loaded successfully"
                }
            else:
                health_status["checks"]["configuration"] = {
                    "status": "unhealthy",
                    "message": "Configuration not loaded"
                }
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["configuration"] = {
                "status": "unhealthy",
                "message": f"Configuration check failed: {e}"
            }
            health_status["status"] = "unhealthy"
        
        # Calculate response time
        end_time = time.time()
        health_status["response_time_ms"] = round((end_time - start_time) * 1000, 2)
        
        return health_status
    
    try:
        # Use cache service to get health status with 30-second TTL
        health_status = cache_service.get_health_status(fetch_health_status)
        
        # Set HTTP status code
        if health_status["status"] != "healthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health_status
            )
        
        logger.debug(f"Health check completed with status: {health_status['status']}")
        return health_status
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in overall_health endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )

@router.get("/database", response_model=Dict[str, Any])
async def database_health(request: Request):
    """
    Database-specific health check.
    
    Returns detailed information about database connectivity and status.
    """
    try:
        database_provider = getattr(request.app.state, 'database_provider', None)
        if not database_provider:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "error",
                    "message": "Database provider not initialized",
                    "timestamp": time.time()
                }
            )
        
        health = database_provider.health_check()
        
        if health["status"] not in ["healthy"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health
            )
        
        logger.debug("Database health check passed")
        return health
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "message": f"Database health check failed: {e}",
                "timestamp": time.time()
            }
        )

@router.get("/services", response_model=Dict[str, Any])
async def services_health(task_service: TaskService = Depends(get_task_service_for_health)):
    """
    Services-specific health check.
    
    Returns detailed information about service layer status.
    """
    try:
        health = task_service.health_check()
        
        if health["status"] != "healthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health
            )
        
        logger.debug("Services health check passed")
        return health
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Services health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "message": f"Services health check failed: {e}",
                "timestamp": time.time()
            }
        )

@router.get("/cache", response_model=Dict[str, Any])
async def cache_health(request: Request):
    """
    Cache-specific health check.
    
    Returns detailed information about cache connectivity and status.
    """
    try:
        cache_provider = getattr(request.app.state, 'cache_provider', None)
        if not cache_provider:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "error",
                    "message": "Cache provider not initialized",
                    "timestamp": time.time()
                }
            )
        
        health = cache_provider.health_check()
        
        if health["status"] not in ["healthy"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health
            )
        
        logger.debug("Cache health check passed")
        return health
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "message": f"Cache health check failed: {e}",
                "timestamp": time.time()
            }
        )

@router.get("/cache/stats", response_model=Dict[str, Any])
async def cache_stats(request: Request):
    """
    Cache statistics endpoint.
    
    Returns detailed cache performance and usage statistics.
    """
    try:
        cache_provider = getattr(request.app.state, 'cache_provider', None)
        if not cache_provider:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "Cache provider not initialized",
                    "timestamp": time.time()
                }
            )
        
        stats = cache_provider.get_stats()
        return {
            "cache_stats": stats,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Cache stats failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache statistics: {e}"
        )



@router.get("/readiness", response_model=Dict[str, Any])
async def readiness_probe(request: Request):
    """
    Kubernetes readiness probe endpoint.
    
    Returns 200 if the service is ready to accept traffic.
    """
    try:
        # Check if essential services are ready
        database_provider = getattr(request.app.state, 'database_provider', None)
        if not database_provider:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "ready": False,
                    "message": "Database provider not initialized",
                    "timestamp": time.time()
                }
            )
        
        db_health = database_provider.health_check()
        
        if db_health["status"] not in ["healthy"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "ready": False,
                    "message": "Database not ready",
                    "timestamp": time.time()
                }
            )
        
        return {
            "ready": True,
            "message": "Service is ready",
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "ready": False,
                "message": f"Readiness check failed: {e}",
                "timestamp": time.time()
            }
        )

@router.get("/liveness", response_model=Dict[str, Any])
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint.
    
    Returns 200 if the service is alive (basic functionality check).
    """
    return {
        "alive": True,
        "message": "Service is alive",
        "timestamp": time.time()
    }

@router.get("/metrics", response_model=Dict[str, Any])
async def health_metrics(request: Request, cache_service = Depends(get_cache_service)):
    """
    Health metrics endpoint.
    
    Returns detailed metrics about system health and performance.
    """
    
    def fetch_health_metrics():
        metrics = {
            "timestamp": time.time(),
            "database": {},
            "services": {},
            "system": {}
        }
        
        # Database metrics
        try:
            database_provider = getattr(request.app.state, 'database_provider', None)
            if database_provider:
                db_health = database_provider.health_check()
                metrics["database"] = {
                    "status": db_health["status"],
                    "connection_pool": db_health.get("connection_pool", {}),
                    "response_time_ms": db_health.get("response_time_ms", 0)
                }
            else:
                metrics["database"] = {
                    "status": "error",
                    "error": "Database provider not initialized"
                }
        except Exception as e:
            metrics["database"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Service metrics
        try:
            task_service = getattr(request.app.state, 'task_service', None)
            if task_service:
                service_health = task_service.health_check()
                metrics["services"] = {
                    "task_service": {
                        "status": service_health["status"],
                        "response_time_ms": service_health.get("response_time_ms", 0)
                    }
                }
            else:
                metrics["services"] = {
                    "task_service": {
                        "status": "error",
                        "error": "Task service not initialized"
                    }
                }
        except Exception as e:
            metrics["services"] = {
                "task_service": {
                    "status": "error",
                    "error": str(e)
                }
            }

        return metrics
    
    try:
        # Use cache service to get health metrics with 1-minute TTL
        metrics = cache_service.get_health_metrics(fetch_health_metrics)
        return metrics
        
    except Exception as e:
        logger.error(f"Health metrics failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve health metrics: {e}"
        )

@router.get("/agents", response_model=Dict[str, Any])
async def get_agents_status(cache_service = Depends(get_cache_service)):
    """
    Get status of available agents.
    
    Returns information about agent availability and status.
    """
    
    def fetch_agents_status():
        agents = []
        
        # Check Claude Code agent
        claude_status = _check_claude_agent_status()
        agents.append({
            "name": "Claude Code",
            "type": "claude_code",
            "status": claude_status,
            "description": "AI-powered code generation and analysis using Claude"
        })
        
        # Add placeholder for future agents
        agents.append({
            "name": "More Agents",
            "type": "coming_soon",
            "status": "coming_soon",
            "description": "Additional AI agents coming soon"
        })
        
        return {
            "agents": agents,
            "total_count": len([a for a in agents if a["status"] != "coming_soon"]),
            "active_count": len([a for a in agents if a["status"] == "active"]),
            "timestamp": time.time()
        }
    
    try:
        # Use cache service to get agents status with 1-minute TTL
        agents_status = cache_service.get_agents_status(fetch_agents_status)
        return agents_status
        
    except Exception as e:
        logger.error(f"Error getting agents status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agents status: {e}"
        )

@router.get("/mcp-servers", response_model=Dict[str, Any])
async def get_mcp_servers_status(cache_service = Depends(get_cache_service)):
    """
    Get status of MCP (Multi-Context Provider) servers.
    
    Returns information about MCP server availability and status.
    """
    
    def fetch_mcp_servers_status():
        mcp_servers = _get_mcp_servers()
        
        return {
            "servers": mcp_servers,
            "total_count": len(mcp_servers),
            "available_count": len([s for s in mcp_servers if s["status"] == "available"]),
            "unavailable_count": len([s for s in mcp_servers if s["status"] == "unavailable"]),
            "unknown_count": len([s for s in mcp_servers if s["status"] == "unknown"]),
            "timestamp": time.time()
        }
    
    try:
        # Use cache service to get MCP servers status with 1-minute TTL
        mcp_servers_status = cache_service.get_mcp_servers_status(fetch_mcp_servers_status)
        return mcp_servers_status
        
    except Exception as e:
        logger.error(f"Error getting MCP servers status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get MCP servers status: {e}"
        )

@router.get("/mcp-servers/{server_id}/tools", response_model=Dict[str, Any])
async def get_mcp_server_tools(server_id: str):
    """
    Get the list of tools available for a specific MCP server.

    Reads the allowed_tools configuration from the Claude Code agent and
    returns the tools that belong to the given server (prefix mcp__<server_id>__).
    """
    try:
        from src.providers.config_loader import get_config
        config = get_config()
        allowed_tools_str = config.get("agent", {}).get(
            "allowed_tools",
            ""
        )

        # Fall back to reading directly from the agent defaults if not in config
        if not allowed_tools_str:
            from src.agents.terminal_agents.claude_code import ClaudeCodeTool
            tool_instance = ClaudeCodeTool.__new__(ClaudeCodeTool)
            # Parse the default value from the class definition
            import inspect
            source = inspect.getsource(ClaudeCodeTool.__init__)
            import re
            match = re.search(r'allowed_tools",\s*"([^"]+)"', source)
            allowed_tools_str = match.group(1) if match else ""

        prefix = f"mcp__{server_id}__"
        tools = [
            {"name": t.replace(prefix, ""), "full_name": t}
            for t in allowed_tools_str.split(",")
            if t.strip().startswith(prefix)
        ]

        return {"server_id": server_id, "tools": tools, "count": len(tools)}

    except Exception as e:
        logger.error(f"Error getting tools for MCP server {server_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tools for MCP server: {e}"
        )


def _check_claude_agent_status() -> str:
    """Check if Claude Code agent is available."""
    try:
        # Check if claude command is available
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ, "SHELL": "/bin/bash"}
        )
        if result.returncode == 0:
            return "active"
        else:
            return "unavailable"
    except subprocess.TimeoutExpired:
        return "unknown"
    except Exception:
        return "unavailable"

def _get_mcp_servers() -> List[Dict[str, Any]]:
    """Get the list of available MCP servers from configuration and check their status."""
    mcp_servers = []

    try:
        # Get the path to the MCP configuration file
        current_dir = os.getcwd()
        possible_paths = [
            os.path.join("src", "providers", "mcp", "mcp-servers.json"),
            os.path.join(current_dir, "src", "providers", "mcp", "mcp-servers.json"),
        ]

        mcp_config_path = None
        for path in possible_paths:
            if os.path.exists(path):
                mcp_config_path = path
                break

        if not mcp_config_path:
            logger.warning(f"Could not find MCP config file in any of these paths: {possible_paths}")
            return mcp_servers

        with open(mcp_config_path, "r") as f:
            mcp_data = json.load(f)

            if isinstance(mcp_data, dict) and "mcpServers" in mcp_data:
                # Transform server configs to UI display format
                for server_id, server_config in mcp_data["mcpServers"].items():
                    # Check the status of each server
                    server_status = _check_mcp_server_status(server_id, server_config)

                    # Create a friendly display name
                    display_name = _get_mcp_display_name(server_id)

                    server_info = {
                        "name": display_name,
                        "type": server_id,
                        "status": server_status,
                        "description": _get_mcp_description(server_id)
                    }
                    mcp_servers.append(server_info)

    except Exception as e:
        logger.error(f"Error loading MCP servers: {e}")

    return mcp_servers

def _get_mcp_display_name(server_id: str) -> str:
    """Get a friendly display name for MCP servers."""
    display_names = {
        "github": "Github",
        "sequentialthinking": "Sequential Thinking",
        "memory": "Memory",
        "prod-coralogix": "Prod-coralogix",
        "blade-mcp": "Blade MCP",
        "devstack": "Devstack",
        "redash-stage": "Redash-stage",
        "prod-datalake": "Prod-datalake",
        "devrev-mcp": "DevRev MCP"
    }
    return display_names.get(server_id, server_id.capitalize())

def _check_mcp_server_status(server_id: str, server_config: dict) -> str:
    """Check if an MCP server is available and running."""
    try:
        # Check transport type first
        transport_type = server_config.get("type", "")

        # For HTTP/SSE based servers, check if the URL is accessible
        if transport_type in ["streamable-http", "http", "sse"]:
            url = server_config.get("url", "")
            if url:
                # For HTTP-based MCP servers, we assume they're available if URL is configured
                # A full connectivity check would require making an HTTP request which could be slow
                # and is better done by Claude CLI's health check
                return "available"
            else:
                logger.warning(f"MCP server {server_id} has HTTP transport but no URL configured")
                return "unavailable"

        # For stdio-based servers, check command availability
        command = server_config.get("command", "")
        args = server_config.get("args", [])

        # Special handling for mcp-remote servers
        if command == "npx" and args and args[0] == "mcp-remote":
            # mcp-remote servers are considered available if npx is available
            result = subprocess.run(
                ["npx", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "available" if result.returncode == 0 else "unavailable"

        # For Docker-based servers, check if docker is available
        if command == "docker":
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "available" if result.returncode == 0 else "unavailable"

        # For npm-based servers, check if npx is available
        elif command == "npx":
            result = subprocess.run(
                ["npx", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "available" if result.returncode == 0 else "unavailable"

        # For other commands, check if the command exists
        elif command:
            if os.path.exists(command):
                return "available"
            else:
                result = subprocess.run(
                    ["which", command],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return "available" if result.returncode == 0 else "unavailable"

    except subprocess.TimeoutExpired:
        return "unknown"
    except Exception as e:
        logger.warning(f"Error checking status for MCP server {server_id}: {e}")
        return "unknown"

    return "unknown"

def _get_mcp_description(server_id: str) -> str:
    """Get a friendly description for each MCP server."""
    descriptions = {
        "github": "GitHub repository access, PR management, and issue tracking",
        "sequentialthinking": "Sequential thinking and reasoning capabilities",
        "memory": "Persistent memory and context storage",
        "prod-coralogix": "Coralogix logging and monitoring integration",
        "blade-mcp": "Razorpay Blade design system integration",
        "devstack": "Development stack management and deployment",
        "redash-stage": "Redash staging environment integration",
        "prod-datalake": "Production data lake access and analytics",
        "devrev-mcp": "DevRev work management - tickets, issues, incidents, and customer support"
    }
    return descriptions.get(server_id, f"{server_id.capitalize()} integration")


@router.get("/github", response_model=Dict[str, Any])
async def github_health(cache_service = Depends(get_cache_service)):
    """
    GitHub-specific health check.
    
    Returns detailed information about GitHub authentication and CLI tools status.
    """
    
    def fetch_github_health():
        try:
            from src.providers.github.auth_service import GitHubAuthService
            
            auth_service = GitHubAuthService()
            
            # Get comprehensive status with timeout
            import asyncio
            try:
                status_task = asyncio.create_task(auth_service.get_comprehensive_status())
                comprehensive_status = asyncio.get_event_loop().run_until_complete(
                    asyncio.wait_for(status_task, timeout=3.0)
                )
            except asyncio.TimeoutError:
                return {
                    "status": "timeout",
                    "message": "GitHub status check timed out",
                    "timestamp": time.time()
                }
            
            # Determine overall health
            overall_status = comprehensive_status.get("overall_status", "unknown")
            
            health_status = {
                "status": "healthy" if overall_status == "healthy" else "unhealthy",
                "overall_status": overall_status,
                "token_info": comprehensive_status.get("token_info", {}),
                "git_config": comprehensive_status.get("git_config", {}),
                "tests": comprehensive_status.get("tests", {}),
                "timestamp": time.time()
            }
            
            return health_status
            
        except Exception as e:
            logger.error(f"GitHub health check failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": time.time()
            }
    
    try:
        # Use cache service with 30-second TTL
        github_health_status = cache_service.get_health_status(fetch_github_health)
        
        if github_health_status["status"] not in ["healthy"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=github_health_status
            )
        
        return github_health_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub health endpoint failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "message": f"GitHub health check failed: {e}",
                "timestamp": time.time()
            }
        )


@router.get("/github/token", response_model=Dict[str, Any])
async def github_token_health():
    """
    GitHub token-specific health check.
    
    Returns lightweight token status without running CLI tests.
    """
    try:
        from src.providers.github.auth_service import GitHubAuthService
        
        auth_service = GitHubAuthService()
        
        # Get basic token info with timeout
        import asyncio
        try:
            token_info = await asyncio.wait_for(
                auth_service.get_token_info(),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "timeout",
                    "message": "Token check timed out",
                    "timestamp": time.time()
                }
            )
        
        if not token_info.get("authenticated", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "unauthenticated",
                    "message": "No valid GitHub token available",
                    "token_info": token_info,
                    "timestamp": time.time()
                }
            )
        
        return {
            "status": "healthy",
            "message": "GitHub token is available and valid",
            "token_info": token_info,
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub token health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "message": str(e),
                "timestamp": time.time()
            }
        )


@router.get("/github/git", response_model=Dict[str, Any])
async def github_git_health():
    """
    GitHub git functionality health check.
    
    Tests git commands and repository access.
    """
    try:
        from src.providers.github.auth_service import GitHubAuthService
        
        auth_service = GitHubAuthService()
        
        # Test git access
        import asyncio
        try:
            git_test = await asyncio.wait_for(
                auth_service.test_git_access(),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "timeout",
                    "message": "Git access test timed out",
                    "timestamp": time.time()
                }
            )
        
        if not git_test.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "unhealthy",
                    "message": "Git access test failed",
                    "test_result": git_test,
                    "timestamp": time.time()
                }
            )
        
        return {
            "status": "healthy",
            "message": "Git functionality is working",
            "test_result": git_test,
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub git health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "message": str(e),
                "timestamp": time.time()
            }
        )


@router.get("/github/gh", response_model=Dict[str, Any])
async def github_gh_health():
    """
    GitHub CLI (gh) functionality health check.
    
    Tests gh CLI commands and authentication.
    """
    try:
        from src.providers.github.auth_service import GitHubAuthService
        
        auth_service = GitHubAuthService()
        
        # Test gh CLI access
        import asyncio
        try:
            gh_test = await asyncio.wait_for(
                auth_service.test_gh_access(),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "timeout",
                    "message": "gh CLI access test timed out",
                    "timestamp": time.time()
                }
            )
        
        if not gh_test.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "unhealthy",
                    "message": "gh CLI access test failed",
                    "test_result": gh_test,
                    "timestamp": time.time()
                }
            )
        
        return {
            "status": "healthy",
            "message": "gh CLI functionality is working",
            "test_result": gh_test,
            "timestamp": time.time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub gh CLI health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "message": str(e),
                "timestamp": time.time()
            }
        )


@router.get("/discover", response_model=Dict[str, Any])
async def discover_health(request: Request, cache_service = Depends(get_cache_service)):
    """
    Discover backend health check.

    Tests connectivity to Discover backend service via Basic Auth.
    """

    def fetch_discover_health():
        try:
            config = get_config()
            discover_config = config.get("discover", {})

            backend_url = discover_config.get("backend_url", "")

            if not backend_url:
                return {
                    "status": "not_configured",
                    "message": "Discover backend URL not configured",
                    "timestamp": time.time()
                }

            # Basic connectivity check - test if backend is reachable
            # We'll make a lightweight request to the tools endpoint
            import httpx
            import asyncio

            try:
                # Quick connectivity test with short timeout
                # Use HEAD request to /api/v1/tools for lightweight check
                async def _test_connectivity():
                    async with httpx.AsyncClient(base_url=backend_url, timeout=5.0) as client:
                        response = await client.get("/api/v1/tools")
                        return response.status_code < 500  # Consider any non-5xx as "reachable"

                # Run the async function in sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    is_reachable = loop.run_until_complete(_test_connectivity())
                finally:
                    loop.close()

                if not is_reachable:
                    return {
                        "status": "unreachable",
                        "message": "Discover backend returned error response",
                        "backend_url": backend_url,
                        "timestamp": time.time()
                    }

            except Exception as conn_err:
                logger.warning(f"Discover connectivity test failed: {conn_err}")
                return {
                    "status": "unreachable",
                    "message": f"Cannot connect to Discover backend: {str(conn_err)}",
                    "backend_url": backend_url,
                    "timestamp": time.time()
                }

            return {
                "status": "healthy",
                "message": "Discover backend is reachable",
                "backend_url": backend_url,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Discover health check failed: {e}")
            return {
                "status": "error",
                "message": f"Health check error: {str(e)}",
                "timestamp": time.time()
            }
    
    try:
        # Use cache service with 30-second TTL to avoid hammering Discover
        discover_health_status = cache_service.get_health_status(fetch_discover_health)
        
        # Determine HTTP status based on health status
        if discover_health_status["status"] in ["unreachable", "error"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=discover_health_status
            )
        
        return discover_health_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Discover health endpoint failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "message": f"Discover health check failed: {e}",
                "timestamp": time.time()
            }
        ) 