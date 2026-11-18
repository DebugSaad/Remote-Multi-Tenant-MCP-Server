"""
Authentication Middleware for MCP Server (Phase 3).
Enforces Bearer authentication on protected endpoints (/mcp).
Returns 401 with WWW-Authenticate header containing resource_metadata and scope when token is missing.
"""

import json
from starlette.datastructures import Headers
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from src.mcp_server.config import settings

PUBLIC_PREFIXES = (
    "/health",
    "/.well-known/",
)


class AuthMiddleware:
    """ASGI Middleware checking for Bearer token presence on protected routes."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # Allow CORS preflight and public endpoints without authentication
        if method == "OPTIONS" or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        auth_header = headers.get("authorization")

        # Check for missing or invalid Authorization header
        if not auth_header or not auth_header.strip().lower().startswith("bearer "):
            metadata_url = f"{settings.mcp_resource_url.rstrip('/')}/.well-known/oauth-protected-resource/mcp"
            www_auth = f'Bearer resource_metadata="{metadata_url}", scope="{settings.mcp_scope}"'

            response = JSONResponse(
                {
                    "error": "unauthorized",
                    "error_description": "Authentication required. Bearer token missing.",
                },
                status_code=401,
                headers={
                    "WWW-Authenticate": www_auth,
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Expose-Headers": "WWW-Authenticate, Mcp-Session-Id",
                },
            )
            await response(scope, receive, send)
            return

        # Token is present: proceed to MCP pipeline
        await self.app(scope, receive, send)
