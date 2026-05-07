"""
Main FastAPI application module.

This module creates and configures the FastAPI application instance with all
necessary middleware, dependencies, and route handlers.
"""

from contextlib import asynccontextmanager
import time
from typing import AsyncGenerator, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.providers.cache.provider import CacheProvider
from src.providers.config_loader import get_config
from src.providers.database.provider import DatabaseProvider
from src.providers.logger import Logger
from src.providers.telemetry import setup_telemetry
from src.services import TaskService, AgentsCatalogueService
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.utils.google_cloud_auth import initialize_google_cloud_auth_from_config

def _configure_cors(app: FastAPI, config: Any) -> None:
    """
    Configure CORS middleware with environment-specific allowed origins.

    For development: Allow common localhost ports for flexibility
    For staging/prod: Restrict to specific configured origins only

    Args:
        app: FastAPI application instance
        config: Application configuration object
    """
    logger = Logger("CORS")

    # Get URLs from environment configuration
    # Note: config is a dictionary, so we need to access nested values directly
    app_config = config.get("app", {})
    env_config = config.get("environment", {})

    ui_base_url = app_config.get("ui_base_url", "")
    api_base_url = app_config.get("api_base_url", "")

    # Get environment name from loaded configuration
    app_env = env_config.get("name", "dev")

    # Determine CORS origins based on environment
    if app_env in ["dev", "development", "dev_docker"]:
        # Development: Allow common localhost ports for flexibility
        # Focus on common frontend development ports to reduce security risk
        frontend_ports = [3000, 3001, 3002, 3003, 4200, 4201, 5173, 5174, 28001]  # React, Angular, Vite, Docker UI
        api_ports = [8000, 8001, 8002, 8003, 28002, 28003]  # Common API development ports, MCP ports, Docker API
        common_ports = frontend_ports + api_ports

        allowed_origins = []

        # Add HTTP and HTTPS for common development ports
        for port in common_ports:
            allowed_origins.extend([
                f"http://localhost:{port}",
                f"https://localhost:{port}",
                f"http://127.0.0.1:{port}",
                f"https://127.0.0.1:{port}",
            ])

        # Also add the specific UI URL if configured, even if it's localhost
        if ui_base_url:
            allowed_origins.append(ui_base_url)
            logger.info(f"Added configured UI URL for dev environment: {ui_base_url}")

        logger.info(f"Development environment detected - allowing {len(common_ports)} common development ports (frontend + API)")

    else:
        # Staging/Production: Strict origin control
        allowed_origins = []

        # Add environment-specific UI URL
        if ui_base_url:
            allowed_origins.append(ui_base_url)
            logger.info(f"Added environment-specific UI URL: {ui_base_url}")

        # Add any additional CORS origins configured in the environment (e.g. legacy domains)
        additional_origins = app_config.get("additional_cors_origins", [])
        for origin in additional_origins:
            allowed_origins.append(origin)
            logger.info(f"Added additional CORS origin: {origin}")

        # Optionally add API URL for staging if needed for debugging
        if app_env in ["stage"] and api_base_url:
            allowed_origins.append(api_base_url)
            logger.info(f"Added API URL for staging environment: {api_base_url}")

        logger.info(f"Production/Staging environment detected - using strict origin control")

    # Remove duplicates while preserving order
    unique_origins = []
    for origin in allowed_origins:
        if origin not in unique_origins:
            unique_origins.append(origin)

    logger.info(f"Configuring CORS for environment '{app_env}' with {len(unique_origins)} origins")

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=unique_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Orchestrates startup (telemetry, DB, cache, GitHub auth, background tasks)
    and teardown (connections, background workers) for the application.
    """
    logger = Logger("FastAPI")

    # Startup
    logger.info("Starting up FastAPI application...")

    # Load configuration
    config = get_config()
    logger.debug("Configuration loaded")

    # Initialize telemetry/metrics with API-specific service labels
    try:
        telemetry_config = config.get("telemetry", {})
        telemetry_config["service_name"] = "swe-agent-api"
        labels = telemetry_config.get("labels", {})
        labels["service"] = "api"
        telemetry_config["labels"] = labels
        setup_telemetry(telemetry_config)

        # API-specific: initialise HTTP middleware metrics (already imported
        # by create_app → MetricsMiddleware, so this is a warm sys.modules hit).
        from src.api.middleware.metrics import initialize_http_metrics
        initialize_http_metrics()
    except Exception as e:
        logger.warning(f"Telemetry init failed, continuing without metrics: {e}", exc_info=True)

    # Initialize Google Cloud authentication
    logger.debug("Lifespan startup: Initializing Google Cloud authentication...")
    try:
        google_auth_success = initialize_google_cloud_auth_from_config(config)
        
        if google_auth_success:
            logger.info("Google Cloud authentication initialized successfully")
        else:
            logger.info("Google Cloud authentication not configured - continuing without GCP credentials")
            
        # Store the initialization result for health checks and service availability
        app.state.google_cloud_auth_configured = google_auth_success
        
    except Exception as e:
        logger.error(f"Failed to initialize Google Cloud authentication: {e}")
        app.state.google_cloud_auth_configured = False

    # Initialize database provider
    logger.debug("Lifespan startup: Initializing database provider...")
    database_provider = DatabaseProvider()
    database_provider.initialize(config)
    logger.info("Database provider initialized")

    # Auto-run migrations for dev environments
    env_name = config.get("environment", {}).get("name", "")
    if env_name in ["dev", "dev_docker"]:
        logger.info(f"Dev environment detected ({env_name}), running migrations automatically...")
        try:
            from src.migrations.manager import MigrationManager
            from src.providers.database.connection import get_engine

            # Get database engine
            engine = get_engine()

            # Initialize migration manager and run migrations
            migration_manager = MigrationManager(engine)
            success = migration_manager.run_migrations()

            if success:
                logger.info("✅ Database migrations completed successfully")
            else:
                logger.warning("⚠️ Database migrations encountered issues")

        except Exception as e:
            logger.error(f"❌ Failed to run migrations: {e}")
            logger.warning("Continuing startup - migrations will need to be run manually")

    # Initialize cache and application services
    from src.providers.cache import cache_provider
    cache_provider.initialize(config)
    task_service = TaskService(config, database_provider)
    agents_catalogue_service = AgentsCatalogueService(config, database_provider)
    from src.services.cache_service import CacheService
    cache_service = CacheService()
    from src.services.pr_review_service import PRReviewService
    pr_review_service = PRReviewService(config, database_provider)

    # Initialize GitHub authentication with new bootstrap system
    logger.debug("Lifespan startup: Initializing GitHub authentication...")
    try:
        from src.providers.github.bootstrap import initialize_github_auth
        # Initialize GitHub auth synchronously during startup
        github_init_result = await initialize_github_auth()
        
        if github_init_result.get("success", False):
            logger.info("GitHub authentication system initialized successfully")
            if github_init_result.get("bootstrap_performed", False):
                logger.info(f"Token type: {github_init_result.get('token_info', {}).get('token_type', 'unknown')}")
        else:
            # In development, this might be expected if no token is configured
            if github_init_result.get("development_mode", False):
                logger.info("GitHub authentication not configured for development environment")
            else:
                logger.warning(f"GitHub authentication initialization failed: {github_init_result.get('error')}")
                
        # Store the initialization result for health checks
        app.state.github_init_result = github_init_result
        
    except Exception as e:
        logger.error(f"Failed to initialize GitHub authentication: {e}")
        app.state.github_init_result = {"success": False, "error": str(e)}

    # Initialize GitHub CLI sync service
    logger.debug("Lifespan startup: Starting GitHub CLI sync service...")
    try:
        from src.providers.github.cli_sync_service import start_cli_sync_service
        await start_cli_sync_service(sync_interval=300)  # 5 minutes
        logger.info("GitHub CLI sync service started")
        
    except Exception as e:
        logger.error(f"Failed to start GitHub CLI sync service: {e}")
        logger.info("Application will continue without GitHub CLI integration")
        app.state.github_init_result = {"success": False, "error": str(e)}

    # Initialize Slack integration (optional — non-fatal if not configured)
    logger.debug("Lifespan startup: Initializing Slack integration...")
    try:
        from src.providers.slack import initialize_slack
        slack_enabled = initialize_slack(config)
        if slack_enabled:
            logger.info("Slack integration initialized successfully")

            app_token = config.get("slack", {}).get("app_token", "").strip()
            bot_token = config.get("slack", {}).get("bot_token", "").strip()
            if app_token:
                from src.providers.slack.socket_mode import start_socket_mode
                sm_started = start_socket_mode(bot_token=bot_token, app_token=app_token)
                if sm_started:
                    logger.info("Slack Socket Mode started — /swe-agent is live without a public URL")
                else:
                    logger.warning("Slack Socket Mode failed to start")
        else:
            logger.info("Slack integration disabled or not configured — skipping")
        app.state.slack_enabled = slack_enabled
    except Exception as e:
        logger.warning(f"Slack initialization failed (non-fatal): {e}")
        app.state.slack_enabled = False

    # Store services in app state for dependency injection
    app.state.config = config
    app.state.database_provider = database_provider
    app.state.cache_provider = cache_provider
    app.state.task_service = task_service
    app.state.agents_catalogue_service = agents_catalogue_service
    app.state.cache_service = cache_service
    app.state.pr_review_service = pr_review_service

    logger.info("FastAPI application startup completed")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application...")

    # Clean up database connections
    if hasattr(app.state, 'database_provider'):
        try:
            app.state.database_provider.close()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error("Error closing database connections", error=str(e))

    # Clean up cache connections
    if hasattr(app.state, 'cache_provider'):
        try:
            app.state.cache_provider.close()
            logger.info("Cache connections closed")
        except Exception as e:
            logger.error("Error closing cache connections", error=str(e))

    # Flush and shut down OTEL event emitter
    try:
        from src.providers.telemetry.otel_events import shutdown_otel_events
        shutdown_otel_events()
    except Exception as e:
        logger.warning(f"OTEL event emitter shutdown failed: {e}")

    # Stop GitHub CLI sync service
    try:
        from src.providers.github.cli_sync_service import stop_cli_sync_service
        await stop_cli_sync_service()
        logger.info("GitHub CLI sync service stopped")
    except Exception as e:
        logger.warning(f"GitHub CLI sync service shutdown failed: {e}")

    # Stop Slack Socket Mode
    try:
        from src.providers.slack.socket_mode import stop_socket_mode
        stop_socket_mode()
    except Exception as e:
        logger.warning(f"Slack Socket Mode shutdown failed: {e}")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    # Create FastAPI app with lifespan
    app = FastAPI(
        title="Razorpay Vyom API",
        description="API for Razorpay Vyom",
        version="1.0.0",
        lifespan=lifespan
    )

    # Configure CORS with environment-specific settings
    config = get_config()
    _configure_cors(app, config)

    # Middleware is applied in REVERSE registration order in Starlette:
    # the LAST add_middleware call becomes the OUTERMOST layer (first to see requests).
    # We want: request → BasicAuth → RateLimit → Handler
    # So: register RateLimit first (innermost), then BasicAuth second (outermost).

    # 1. Rate limiting — registered first → innermost → runs after auth,
    #    so request.state.current_user is already populated when it fires.
    rate_limit_config = config.get("rate_limit", {})
    app.add_middleware(
        RateLimitMiddleware,
        enabled=rate_limit_config.get("enabled", True),
        requests_per_window=rate_limit_config.get("requests_per_window", 100),
        window_seconds=rate_limit_config.get("window_seconds", 60),
        included_paths=[
            "/api/v1/agents",
        ],
    )

    # 2. Basic Authentication — registered second → outermost → runs first,
    #    populating request.state.current_user before rate limiting checks it.
    from .middleware import BasicAuthMiddleware
    app.add_middleware(BasicAuthMiddleware)

    # Add HTTP metrics middleware
    from .middleware.metrics import MetricsMiddleware
    app.add_middleware(MetricsMiddleware)

    # Add global exception handler for unhandled errors
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Global exception handler to convert unhandled exceptions to appropriate HTTP responses.
        """
        logger = Logger("GlobalExceptionHandler")

        # Log the error for debugging, being careful with potential binary data in exceptions
        try:
            exc_str = str(exc)
            # Limit the exception string length to prevent logging massive binary data
            if len(exc_str) > 500:
                exc_str = exc_str[:500] + "... (truncated)"
            logger.error(f"Unhandled exception for {request.method} {request.url}: {exc_str}", exc_info=True)
        except Exception as log_exc:
            # If logging the exception fails (e.g., due to encoding issues), log a safe message
            logger.error(f"Unhandled exception for {request.method} {request.url}: <exception logging failed: {type(exc).__name__}>")

        # Handle file not found errors as 404
        if isinstance(exc, (FileNotFoundError, RuntimeError)):
            if "does not exist" in str(exc) or "not found" in str(exc).lower():
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Resource not found", "error_type": "not_found"}
                )

        # Handle permission errors as 403
        if isinstance(exc, PermissionError):
            return JSONResponse(
                status_code=403,
                content={"detail": "Permission denied", "error_type": "permission_denied"}
            )

        # For all other exceptions, return 500 with generic message
        # Don't expose internal error details in production
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_type": "internal_error"
            }
        )

    # Add request timing middleware (keep for backward compatibility)
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # Include API routers
    from .routers import tasks, health, agents_catalogue, admin, files, code_review, streaming, pr_review, auth, plugin_metrics,comment_analyzer, agent_skills, agents, slack, schedules, plugins_catalogue, discover, pulse

    app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
    app.include_router(agents_catalogue.router, prefix="/api/v1/agents-catalogue", tags=["agents-catalogue"])
    app.include_router(agent_skills.router, prefix="/api/v1/agent-skills", tags=["agent-skills"])
    app.include_router(plugins_catalogue.router, prefix="/api/v1/plugins-catalogue", tags=["plugins-catalogue"])
    app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(code_review.router, prefix="/api/v1/code-review", tags=["code-review"])
    app.include_router(streaming.router, prefix="/api/v1/streaming", tags=["streaming"])
    app.include_router(discover.router, prefix="/api/v1/discover", tags=["discover"])
    app.include_router(pr_review.router, prefix="/api/v1/pr-review", tags=["pr-review"])
    app.include_router(plugin_metrics.router, prefix="/api/v1/external_metrics/claude_plugins", tags=["external-metrics", "claude-plugins"])
    app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["schedules"])
    app.include_router(slack.router, prefix="/api/v1/slack", tags=["slack"])
    app.include_router(comment_analyzer.router, prefix="/api/v1/comment-analyzer", tags=["comment-analyzer"])
    app.include_router(pulse.router, prefix="/api/v1/pulse", tags=["pulse"])

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint for API service."""
        return {
            "message": "Razorpay Vyom API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
            "service": "api"
        }

    # Health check endpoint at root level
    @app.get("/health")
    async def health_check():
        """Simple health check endpoint."""
        return {"status": "healthy", "timestamp": time.time(), "service": "api"}

    return app

# Create the application instance
app = create_app()

# API info endpoint
@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": "Razorpay Vyom API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/api/v1/health",
            "tasks": "/api/v1/tasks",
            "agents_catalogue": "/api/v1/agents-catalogue",
            "files": "/api/v1/files",
            "admin": "/api/v1/admin",
            "code_review": "/api/v1/code-review",
            "pr_review": "/api/v1/pr-review"
        }
    }