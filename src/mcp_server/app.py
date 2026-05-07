"""
MCP FastAPI Application.

This module creates a standalone FastAPI application for the MCP service
that runs independently from the main SWE Agent API service.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config.settings import get_mcp_settings
from .dependencies import cleanup_dependencies
from .router import router
from src.providers.telemetry import setup_telemetry, is_metrics_initialized


def create_mcp_app() -> FastAPI:
    """
    Create and configure the MCP FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    settings = get_mcp_settings()
    
    # Create FastAPI app
    app = FastAPI(
        title="SWE Agent MCP Server",
        description="Model Context Protocol server for SWE Agent - provides MCP wrapper around SWE Agent API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        debug=settings.debug
    )
    
    # Add CORS middleware for MCP clients
    app.add_middleware(
        CORSMiddleware,
        # nosemgrep: python.fastapi.security.wildcard-cors.wildcard-cors
        allow_origins=["*"],  # MCP clients can be from anywhere
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Add request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request, call_next):
        import time
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    # Include MCP router at root level (no prefix)
    app.include_router(router, tags=["mcp"])
    
    # Health check endpoint
    @app.get("/")
    async def root():
        """Root endpoint - basic service info."""
        return {
            "service": "SWE Agent MCP Server",
            "version": "1.0.0",
            "status": "running",
            "environment": settings.environment_name,
            "debug": settings.debug,
            "config": {
                "mcp_base_url": settings.mcp_base_url,
                "api_base_url": settings.api_base_url,
                "host": settings.host,
                "port": settings.port
            },
            "docs": "/docs",
            "mcp_endpoints": {
                "jsonrpc": "/",
                "health": "/health", 
                "tools": "/tools",
                "info": "/info"
            }
        }
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler for unhandled errors."""
        import traceback
        
        # Log the error (in production, use proper logging)
        print(f"Unhandled error: {exc}")
        print(traceback.format_exc())
        
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": {"error_type": type(exc).__name__}
                },
                "id": None
            }
        )
    
    # Telemetry is normally initialised by the process entry-point
    # (commands/mcp_server.py) BEFORE uvicorn.run(), so the startup event
    # is kept lightweight and the port opens immediately.
    #
    # Fallback: when uvicorn runs with reload=True (dev mode), the child
    # subprocess starts with a clean interpreter — _metrics_initialized is
    # False.  In that case the startup event initialises telemetry itself.

    # Startup event
    @app.on_event("startup")
    async def startup_event():
        """Application startup tasks."""
        print("Starting SWE Agent MCP Server...")
        print(f"Environment: {settings.environment_name}")
        print(f"Host: {settings.host}:{settings.port}")
        print(f"MCP Base URL: {settings.mcp_base_url}")
        print(f"API Service: {settings.api_base_url}")
        print(f"Debug Mode: {settings.debug}")
        print(f"Log Level: {settings.log_level}")
        print(f"Documentation: {settings.mcp_base_url}/docs")

        # Fallback for reload subprocess — parent already initialised in
        # commands/mcp_server.py, but the child process has a fresh state.
        if not is_metrics_initialized():
            try:
                config = settings.config
                telemetry_config = config.get("telemetry", {})
                telemetry_config["service_name"] = "swe-agent-mcp"
                labels = telemetry_config.get("labels", {})
                labels["service"] = "mcp"
                telemetry_config["labels"] = labels
                telemetry_config["enabled"] = True
                setup_telemetry(telemetry_config)
            except Exception as e:
                print(f"Telemetry init failed: {e}")

        print(f"Telemetry: {'ready' if is_metrics_initialized() else 'not available'}")
        print("MCP Server startup complete")
    
    # Shutdown event  
    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown tasks."""
        print("Shutting down SWE Agent MCP Server...")
        await cleanup_dependencies()

        print("MCP Server shutdown complete")

    return app


# Create the app instance
app = create_mcp_app() 