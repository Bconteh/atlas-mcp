"""
Unified entry point: starts FastAPI (REST + SSE for React UI) on port 8000
and mounts the MCP SSE server at /mcp for LLM clients.
"""
import logging
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_cached_settings
from .api_router import router as api_router
from .mcp_server import mcp  # MCPServer instance

logging.basicConfig(
    level=logging.DEBUG if get_cached_settings().debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

settings = get_cached_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Atlas Change Request Management via MCP (Model Context Protocol).\n\n"
            "- REST API for the React UI: `/api/*`\n"
            "- MCP SSE endpoint for LLM clients: `/mcp/sse`\n"
            "- MCP messages endpoint: `/mcp/messages`"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS – allow React dev server and production origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST routes (React UI)
    app.include_router(api_router)

    # Mount MCP SSE app (for LLM clients like Claude Desktop, Copilot, etc.)
    # sse_app() returns a Starlette ASGI app — host='0.0.0.0' allows external connections
    mcp_app = mcp.sse_app(host="0.0.0.0")
    app.mount("/mcp", mcp_app)

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "message": f"Welcome to {settings.app_name}",
            "environment": settings.environment,
            "endpoints": {
                "api_docs": "/docs",
                "rest_api": "/api",
                "mcp_sse": "/mcp/sse",
                "health": "/api/health",
            },
        }

    logger.info(f"🚀 {settings.app_name} v{settings.app_version} ({settings.environment.upper()}) initialized")
    return app


app = create_app()


def run_stdio():
    """Run the MCP server in stdio mode (for direct Claude Desktop / CLI integration)."""
    import asyncio
    logger.info("Starting MCP server in stdio mode...")
    asyncio.run(mcp.run_stdio_async())


def run_server():
    """Run the unified HTTP server."""
    logger.info(f"Starting HTTP server on {settings.host}:{settings.port}")
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        run_stdio()
    else:
        run_server()

