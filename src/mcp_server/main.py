"""
Phase 1: Minimal Streamable HTTP MCP Server
Built with the official MCP Python SDK v2 using MCPServer (ignoring FastMCP).
"""

import os
import uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# 1. Initialize the low-level MCPServer instance
server = MCPServer(
    name="remote-mcp-server",
    version="0.1.0",
)

# 2. Register the 'ping' tool using the @server.tool() decorator
@server.tool(name="ping", description="Health ping tool that returns 'pong'")
def ping() -> str:
    """Simple ping tool returning 'pong'."""
    return "pong"

# 3. Add a GET /health endpoint using @server.custom_route()
@server.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> Response:
    """Public health check endpoint reporting server status."""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "remote-multi-tenant-mcp-server",
            "phase": "Phase 1 - Hello World",
        }
    )

# 4. Create the Streamable HTTP ASGI application
# Disable DNS rebinding protection in local development so MCP Inspector can connect
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False
)

app = server.streamable_http_app(
    streamable_http_path="/mcp",
    transport_security=transport_security,
)

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run(
        "src.mcp_server.main:app",
        host=host,
        port=port,
        reload=True,
    )
