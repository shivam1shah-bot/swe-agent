"""
Admin router for FastAPI.

This module provides administrative endpoints for the SWE Agent system,
including database migrations and system management operations.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import asyncio
import os

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel

from src.providers.database.provider import DatabaseProvider
from src.providers.auth import require_role

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Response models
class MigrationStatusResponse(BaseModel):
    """Response model for migration status."""
    current_version: int
    latest_version: int
    applied_count: int
    available_count: int
    pending_count: int
    up_to_date: bool
    applied_migrations: list[int]
    pending_migrations: list[int]

class MigrationRunResponse(BaseModel):
    """Response model for migration run operations."""
    success: bool
    message: str
    migrations_applied: int
    total_migrations: int
    duration_ms: float
    timestamp: float

class MigrationRollbackResponse(BaseModel):
    """Response model for migration rollback operations."""
    success: bool
    message: str
    rollback_to_version: int
    migrations_rolled_back: int
    duration_ms: float
    timestamp: float

# Dependencies
def get_database_provider(request: Request) -> DatabaseProvider:
    """Dependency to get the database provider instance."""
    try:
        database_provider = getattr(request.app.state, 'database_provider', None)
        if not database_provider:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database provider not initialized in app state"
            )
        return database_provider
    except Exception as e:
        logger.error(f"Failed to get database provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database provider not available: {e}"
        )

@router.get("/migrations/status", response_model=MigrationStatusResponse)
@require_role(["admin"])
async def get_migration_status(
    request: Request,
    database_provider: DatabaseProvider = Depends(get_database_provider)
):
    """
    Get current migration status.
    
    Returns information about applied and pending migrations.
    """
    try:
        logger.info("Getting migration status")
        
        migration_manager = database_provider.get_migration_manager()
        status_info = migration_manager.get_migration_status()
        
        logger.info(f"Migration status retrieved: {status_info}")
        
        return MigrationStatusResponse(
            current_version=status_info["current_version"],
            latest_version=status_info["latest_version"],
            applied_count=status_info["applied_count"],
            available_count=status_info["available_count"],
            pending_count=status_info["pending_count"],
            up_to_date=status_info["up_to_date"],
            applied_migrations=status_info["applied_migrations"],
            pending_migrations=status_info["pending_migrations"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get migration status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration status: {e}"
        )

@router.post("/migrations/run", response_model=MigrationRunResponse)
@require_role(["admin"])
async def run_migrations(
    request: Request,
    database_provider: DatabaseProvider = Depends(get_database_provider)
):
    """
    Run pending database migrations.
    
    Applies all pending migrations to the database.
    """
    start_time = time.time()
    
    try:
        logger.info("Starting migration run via API")
        
        migration_manager = database_provider.get_migration_manager()
        
        # Get pending migrations before running
        pending_migrations = migration_manager.get_pending_migrations()
        total_migrations = len(pending_migrations)
        
        if total_migrations == 0:
            logger.info("No pending migrations to run")
            return MigrationRunResponse(
                success=True,
                message="No pending migrations to run",
                migrations_applied=0,
                total_migrations=0,
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=time.time()
            )
        
        logger.info(f"Running {total_migrations} pending migrations")
        
        # Run migrations
        success = migration_manager.run_migrations()
        
        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        if success:
            logger.info(f"Successfully applied {total_migrations} migrations in {duration_ms}ms")
            return MigrationRunResponse(
                success=True,
                message=f"Successfully applied {total_migrations} migrations",
                migrations_applied=total_migrations,
                total_migrations=total_migrations,
                duration_ms=duration_ms,
                timestamp=time.time()
            )
        else:
            logger.error("Migration run failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Migration run failed - check logs for details"
            )
            
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(f"Failed to run migrations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run migrations: {e}"
        )

@router.post("/migrations/rollback/{target_version}", response_model=MigrationRollbackResponse)
@require_role(["admin"])
async def rollback_migrations(
    request: Request,
    target_version: int,
    database_provider: DatabaseProvider = Depends(get_database_provider)
):
    """
    Rollback migrations to a specific version.
    
    Rolls back all migrations above the specified target version.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting migration rollback to version {target_version}")
        
        migration_manager = database_provider.get_migration_manager()
        
        # Get current applied migrations
        applied_migrations = migration_manager.get_applied_migrations()
        
        if not applied_migrations:
            logger.info("No migrations to rollback")
            return MigrationRollbackResponse(
                success=True,
                message="No migrations to rollback",
                rollback_to_version=target_version,
                migrations_rolled_back=0,
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=time.time()
            )
        
        current_version = max(applied_migrations)
        
        if target_version >= current_version:
            logger.info(f"Already at or below target version {target_version}")
            return MigrationRollbackResponse(
                success=True,
                message=f"Already at or below target version {target_version}",
                rollback_to_version=target_version,
                migrations_rolled_back=0,
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=time.time()
            )
        
        # Calculate migrations to rollback
        migrations_to_rollback = len([v for v in applied_migrations if v > target_version])
        
        logger.info(f"Rolling back {migrations_to_rollback} migrations to version {target_version}")
        
        # Perform rollback
        success = migration_manager.rollback_to_version(target_version)
        
        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        if success:
            logger.info(f"Successfully rolled back {migrations_to_rollback} migrations in {duration_ms}ms")
            return MigrationRollbackResponse(
                success=True,
                message=f"Successfully rolled back {migrations_to_rollback} migrations to version {target_version}",
                rollback_to_version=target_version,
                migrations_rolled_back=migrations_to_rollback,
                duration_ms=duration_ms,
                timestamp=time.time()
            )
        else:
            logger.error("Migration rollback failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Migration rollback failed - check logs for details"
            )
            
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(f"Failed to rollback migrations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback migrations: {e}"
        )



@router.post("/github/refresh-token", response_model=Dict[str, Any])
@require_role(["admin"])
async def refresh_github_token(
    request: Request,
    bot_name: Optional[str] = None
):
    """
    Force refresh GitHub token by submitting a refresh task.

    Query Parameters:
        bot_name: Optional bot identifier (rzp_swe_agent_app or rzp_code_review)
                 If not provided, refreshes all bots

    This triggers an immediate token refresh via the worker task queue.
    """
    try:
        from src.worker.queue_manager import QueueManager
        from src.constants.github_bots import GitHubBot, get_all_bots, get_bot_values

        # Clear any cached status
        cache_keys = ["github_status_cache", "github_cli_status_cache"]
        for cache_key in cache_keys:
            if hasattr(request.app.state, cache_key):
                delattr(request.app.state, cache_key)
            if hasattr(request.app.state, f"{cache_key}_timestamp"):
                delattr(request.app.state, f"{cache_key}_timestamp")

        # Determine which bots to refresh
        bots_to_refresh = []
        if bot_name:
            try:
                bots_to_refresh = [GitHubBot(bot_name)]
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid bot_name: {bot_name}",
                    "valid_bots": get_bot_values()
                }
        else:
            bots_to_refresh = get_all_bots()

        logger.info(f"Triggering GitHub token refresh for {len(bots_to_refresh)} bot(s)")

        queue_manager = QueueManager()
        results = {}

        for bot in bots_to_refresh:
            task_id = f"manual-github-refresh-{bot.value}-{int(datetime.now(timezone.utc).timestamp())}"

            task_data = {
                "task_type": "github_token_refresh",
                "task_id": task_id,
                "parameters": {
                    "bot_name": bot,
                    "immediate": True,
                    "manual_trigger": True,
                    "triggered_by": "admin_api",
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                    "queue_only": True
                },
                "delay_seconds": 0
            }

            success = queue_manager.send_task(task_data)
            results[bot.value] = {
                "success": success,
                "task_id": task_id if success else None
            }

            if success:
                logger.info(f"Manual GitHub token refresh task submitted for {bot.value}: {task_id}")

        overall_success = all(r["success"] for r in results.values())

        return {
            "success": overall_success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bots": results,
            "note": "Token refresh submitted directly to worker queue (queue-only, not tracked in database)."
        }

    except Exception as e:
        logger.error(f"Failed to refresh GitHub tokens: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@router.get("/github/status", response_model=Dict[str, Any])
@require_role(["admin"])
async def get_github_status(request: Request):
    """
    Get comprehensive GitHub authentication status for all configured bots.

    Returns status for each configured GitHub bot including token status,
    git/gh CLI functionality, and API access status.
    """
    try:
        from src.providers.github.auth_service import GitHubAuthService
        from src.constants.github_bots import GitHubBot, get_all_bots, get_bot_values
        from src.providers.github.bootstrap import get_bootstrap_status

        auth_service = GitHubAuthService()

        # Get status for all configured bots
        bots_status = {}

        for bot in get_all_bots():
            try:
                status = await asyncio.wait_for(
                    auth_service.get_comprehensive_status(bot_name=bot),
                    timeout=5.0
                )
                bots_status[bot.value] = status
            except asyncio.TimeoutError:
                bots_status[bot.value] = {
                    "overall_status": "timeout",
                    "error": "Status check timed out"
                }
            except Exception as e:
                logger.error(f"Failed to get status for {bot}: {e}")
                bots_status[bot.value] = {
                    "overall_status": "error",
                    "error": str(e)
                }

        # Get bootstrap status
        try:
            bootstrap_status = await get_bootstrap_status()
        except Exception as e:
            logger.warning(f"Failed to get bootstrap status: {e}")
            bootstrap_status = {"error": str(e)}

        # Determine overall health
        all_healthy = all(
            status.get("overall_status") == "healthy"
            for status in bots_status.values()
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_healthy": all_healthy,
            "bots": bots_status,
            "bootstrap": bootstrap_status,
            "total_bots": len(bots_status),
            "healthy_bots": sum(
                1 for s in bots_status.values()
                if s.get("overall_status") == "healthy"
            )
        }

    except Exception as e:
        logger.error(f"Failed to get GitHub status: {e}")
        return {
            "overall_healthy": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@router.get("/github/token-info", response_model=Dict[str, Any])
@require_role(["admin"])
async def get_github_token_info(
    request: Request,
    bot_name: Optional[str] = None
):
    """
    Get basic GitHub token information.

    Query Parameters:
        bot_name: Optional bot identifier (rzp_swe_agent_app or rzp_code_review)
                 If not provided, returns info for all bots

    Returns lightweight token status without running tests.
    """
    try:
        from src.providers.github.auth_service import GitHubAuthService
        from src.constants.github_bots import GitHubBot, get_all_bots, get_bot_values

        auth_service = GitHubAuthService()

        # If specific bot requested
        if bot_name:
            # Validate bot_name
            try:
                bot = GitHubBot(bot_name)
            except ValueError:
                return {
                    "error": f"Invalid bot_name: {bot_name}",
                    "valid_bots": get_bot_values()
                }

            token_info = await asyncio.wait_for(
                auth_service.get_token_info(bot_name=bot),
                timeout=2.0
            )
            return {
                "bot": bot_name,
                **token_info
            }

        # Return info for all bots
        all_bots_info = {}
        for bot in get_all_bots():
            try:
                info = await asyncio.wait_for(
                    auth_service.get_token_info(bot_name=bot),
                    timeout=2.0
                )
                all_bots_info[bot.value] = info
            except Exception as e:
                all_bots_info[bot.value] = {
                    "authenticated": False,
                    "error": str(e)
                }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bots": all_bots_info
        }

    except Exception as e:
        logger.error(f"Failed to get token info: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@router.post("/github/diagnose-and-fix", response_model=Dict[str, Any])
@require_role(["admin"])
async def diagnose_and_fix_github_auth(
    request: Request,
    bot_name: Optional[str] = None
):
    """
    Diagnose GitHub authentication issues and attempt automatic fixes.

    Query Parameters:
        bot_name: Optional bot identifier. If not provided, diagnoses all bots.
        clear_cache: Whether to clear cache before diagnosis
        force_refresh: Force refresh even if status is healthy
    """
    try:
        from src.providers.github.auth_service import GitHubAuthService
        from src.constants.github_bots import GitHubBot, get_all_bots, get_bot_values
        from src.providers.cache.redis_client import get_redis_client

        logger.info(f"Running GitHub authentication diagnosis for {bot_name or 'all bots'}")

        auth_service = GitHubAuthService()
        cache = get_redis_client()

        # Parse query parameters
        clear_cache = request.query_params.get("clear_cache", "false").lower() == "true"
        force_refresh = request.query_params.get("force_refresh", "false").lower() == "true"

        # Determine which bots to diagnose
        bots_to_diagnose = []
        if bot_name:
            try:
                bots_to_diagnose = [GitHubBot(bot_name)]
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid bot_name: {bot_name}",
                    "valid_bots": get_bot_values()
                }
        else:
            bots_to_diagnose = get_all_bots()

        diagnosis_results = {}

        for bot in bots_to_diagnose:
            bot_str = bot.value if hasattr(bot, 'value') else str(bot)

            # Clear cache if requested
            if clear_cache:
                cache_key = f"github:token:{bot_str}"
                metadata_key = f"github:token:metadata:{bot_str}"
                cache.delete(cache_key)
                cache.delete(metadata_key)
                logger.info(f"Cleared cache for {bot_str}")

            # Get current status
            try:
                current_status = await auth_service.get_comprehensive_status(bot_name=bot)
            except Exception as e:
                diagnosis_results[bot_str] = {
                    "success": False,
                    "error": f"Failed to get status: {str(e)}",
                    "overall_status": "error"
                }
                continue

            # Check if fix is needed
            is_healthy = current_status.get("overall_status") == "healthy"

            if is_healthy and not force_refresh:
                diagnosis_results[bot_str] = {
                    "success": True,
                    "message": "Authentication is working correctly",
                    "overall_status": "healthy",
                    "fix_attempted": False,
                    "current_status": current_status
                }
                continue

            # Submit refresh task
            logger.info(f"Authentication issues detected for {bot_str}, submitting refresh task")

            from src.worker.queue_manager import QueueManager
            queue_manager = QueueManager()

            task_id = f"diagnose-fix-{bot_str}-{int(datetime.now(timezone.utc).timestamp())}"
            task_data = {
                "task_type": "github_token_refresh",
                "task_id": task_id,
                "parameters": {
                    "bot_name": bot,
                    "immediate": True,
                    "diagnosis_fix": True,
                    "triggered_by": "admin_diagnose_fix"
                }
            }

            success = queue_manager.send_task(task_data)

            diagnosis_results[bot_str] = {
                "success": success,
                "message": "Refresh task submitted" if success else "Failed to submit task",
                "fix_attempted": True,
                "task_id": task_id if success else None
            }

        # Determine overall success
        all_successful = all(r["success"] for r in diagnosis_results.values())

        return {
            "success": all_successful,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "bots": diagnosis_results,
            "total_bots": len(diagnosis_results),
            "successful_bots": sum(1 for r in diagnosis_results.values() if r["success"])
        }

    except Exception as e:
        logger.error(f"Failed to diagnose and fix GitHub authentication: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@router.get("/github/cli-sync-status", response_model=Dict[str, Any])
@require_role(["admin"])
async def get_github_cli_sync_status(request: Request):
    """
    Get GitHub CLI sync service status.
    
    Returns information about the background sync service including
    sync status, file existence, and last sync time.
    """
    try:
        from src.providers.github.cli_sync_service import get_cli_sync_service
        
        sync_service = get_cli_sync_service()
        status = sync_service.get_status()
        
        # Add additional status information
        status.update({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pod_id": os.environ.get("HOSTNAME", "unknown"),
            "service_type": "api"
        })
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get CLI sync status: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "running": False
        }

@router.get("/info", response_model=Dict[str, Any])
@require_role(["admin"])
async def get_admin_info(request: Request):
    """
    Get information about available admin endpoints.
    
    Returns documentation about administrative operations.
    """
    return {
        "admin_endpoints": {
            "migration_status": {
                "method": "GET",
                "path": "/api/v1/admin/migrations/status",
                "description": "Get current migration status"
            },
            "run_migrations": {
                "method": "POST",
                "path": "/api/v1/admin/migrations/run",
                "description": "Run pending migrations"
            },
            "rollback_migrations": {
                "method": "POST",
                "path": "/api/v1/admin/migrations/rollback/{target_version}",
                "description": "Rollback migrations to specific version"
            },
            "github_refresh_token": {
                "method": "POST",
                "path": "/api/v1/admin/github/refresh-token",
                "description": "Submit task to refresh GitHub token via worker queue"
            },
            "github_status": {
                "method": "GET",
                "path": "/api/v1/admin/github/status",
                "description": "Get comprehensive GitHub authentication status with git/gh CLI tests"
            },
            "github_token_info": {
                "method": "GET",
                "path": "/api/v1/admin/github/token-info",
                "description": "Get basic GitHub token information quickly"
            },
            "github_diagnose_and_fix": {
                "method": "POST",
                "path": "/api/v1/admin/github/diagnose-and-fix",
                "description": "Diagnose GitHub issues and submit fix task to worker queue"
            },
            "github_cli_sync_status": {
                "method": "GET",
                "path": "/api/v1/admin/github/cli-sync-status",
                "description": "Get GitHub CLI sync service status"
            }
        },
        "timestamp": time.time()
    } 