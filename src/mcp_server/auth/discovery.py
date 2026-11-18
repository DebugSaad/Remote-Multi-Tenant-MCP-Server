"""
OAuth 2.0 Protected Resource Metadata (RFC 9728).
Provides discovery endpoints for MCP clients to discover the Keycloak authorization server.
"""

from typing import Any
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.mcp_server.config import settings


def get_protected_resource_metadata() -> dict[str, Any]:
    """Return RFC 9728 Protected Resource Metadata."""
    return {
        "resource": settings.mcp_resource_url,
        "authorization_servers": [settings.auth_issuer_url],
        "scopes_supported": [settings.mcp_scope],
        "bearer_methods_supported": ["header"],
    }


def get_metadata_response(request: Request) -> Response:
    """Return protected resource metadata with CORS headers."""
    if request.method == "OPTIONS":
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, Mcp-Session-Id",
            },
        )

    return JSONResponse(
        get_protected_resource_metadata(),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Mcp-Session-Id",
        },
    )
