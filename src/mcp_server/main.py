"""
Remote Multi-Tenant MCP Server.
Built with the official MCP Python SDK v2 using MCPServer (ignoring FastMCP).
Phase 2: Database and Domain Tools (Notes and Tasks).
"""

from contextlib import asynccontextmanager
import uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.mcp_server.auth.discovery import get_metadata_response
from src.mcp_server.auth.middleware import AuthMiddleware
from src.mcp_server.config import settings
from src.mcp_server.notes.tools import register_notes_tools
from src.mcp_server.shared.db import close_db, init_db
from src.mcp_server.tasks.tools import register_tasks_tools

# 1. Initialize the low-level MCPServer instance
server = MCPServer(
    name="remote-mcp-server",
    version="0.3.0",
)

# 2. Keep 'ping' tool as a lightweight sanity check
@server.tool(name="ping", description="Health ping tool that returns 'pong'")
def ping() -> str:
    """Simple ping tool returning 'pong'."""
    return "pong"

# 3. Register Phase 2 Domain Tools
register_notes_tools(server)
register_tasks_tools(server)

# 4. Add a GET /health endpoint using @server.custom_route()
@server.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> Response:
    """Public health check endpoint reporting server status."""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "remote-multi-tenant-mcp-server",
            "phase": "Phase 3 - Authentication",
        }
    )

# 5. OAuth 2.0 Protected Resource Metadata Endpoints (RFC 9728)
@server.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
async def oauth_protected_resource(request: Request) -> Response:
    """Return RFC 9728 Protected Resource Metadata (root path)."""
    return get_metadata_response(request)


@server.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET", "OPTIONS"])
async def oauth_protected_resource_mcp(request: Request) -> Response:
    """Return RFC 9728 Protected Resource Metadata (/mcp suffixed path)."""
    return get_metadata_response(request)

# 6. Application Factory for Streamable HTTP ASGI application
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False
)


def create_app() -> Starlette:
    """Create a new Starlette application instance with lifespan DB management and auth."""
    app_instance = server.streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=transport_security,
    )
    _original_lifespan = app_instance.router.lifespan_context

    @asynccontextmanager
    async def app_lifespan(starlette_app: Starlette):
        init_db()
        try:
            async with _original_lifespan(starlette_app):
                yield
        finally:
            await close_db()

    app_instance.router.lifespan_context = app_lifespan
    app_instance.add_middleware(AuthMiddleware)
    return app_instance


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "src.mcp_server.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
