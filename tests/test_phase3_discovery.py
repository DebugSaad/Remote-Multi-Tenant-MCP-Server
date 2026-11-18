"""
Automated tests for OAuth 2.0 Protected Resource Discovery (RFC 9728)
and unauthenticated 401 challenge with WWW-Authenticate header.
"""

from starlette.testclient import TestClient
from src.mcp_server.config import settings
from src.mcp_server.main import create_app


def test_root_protected_resource_metadata() -> None:
    """Verify GET /.well-known/oauth-protected-resource returns RFC 9728 metadata."""
    app = create_app()
    with TestClient(app, base_url="http://localhost:8000") as client:
        res = client.get("/.well-known/oauth-protected-resource")
        assert res.status_code == 200
        data = res.json()
        assert data["resource"] == settings.mcp_resource_url
        assert settings.auth_issuer_url in data["authorization_servers"]
        assert settings.mcp_scope in data["scopes_supported"]
        assert "header" in data["bearer_methods_supported"]
        assert res.headers.get("access-control-allow-origin") == "*"


def test_mcp_suffixed_protected_resource_metadata() -> None:
    """Verify GET /.well-known/oauth-protected-resource/mcp returns RFC 9728 metadata."""
    app = create_app()
    with TestClient(app, base_url="http://localhost:8000") as client:
        res = client.get("/.well-known/oauth-protected-resource/mcp")
        assert res.status_code == 200
        data = res.json()
        assert data["resource"] == settings.mcp_resource_url
        assert settings.auth_issuer_url in data["authorization_servers"]
        assert settings.mcp_scope in data["scopes_supported"]


def test_cors_preflight_on_discovery_endpoint() -> None:
    """Verify OPTIONS request on discovery endpoint returns 204 with CORS headers."""
    app = create_app()
    with TestClient(app, base_url="http://localhost:8000") as client:
        res = client.options("/.well-known/oauth-protected-resource")
        assert res.status_code == 204
        assert res.headers.get("access-control-allow-origin") == "*"
        assert "GET" in res.headers.get("access-control-allow-methods", "")


def test_unauthenticated_request_returns_401_challenge() -> None:
    """Verify unauthenticated request to /mcp returns 401 with WWW-Authenticate header."""
    app = create_app()
    with TestClient(app, base_url="http://localhost:8000") as client:
        res = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "unauthenticated-client", "version": "1.0"},
                },
            },
        )
        assert res.status_code == 401
        www_auth = res.headers.get("www-authenticate", "")
        assert "Bearer" in www_auth
        assert 'resource_metadata="' in www_auth
        assert settings.mcp_scope in www_auth

        # Check expected metadata URL in header
        expected_meta_url = f"{settings.mcp_resource_url.rstrip('/')}/.well-known/oauth-protected-resource/mcp"
        assert expected_meta_url in www_auth
        assert f'scope="{settings.mcp_scope}"' in www_auth

        # Verify JSON error body
        body = res.json()
        assert body["error"] == "unauthorized"


def test_bearer_token_passes_auth_middleware() -> None:
    """Verify request with Bearer token passes the auth barrier."""
    app = create_app()
    with TestClient(app, base_url="http://localhost:8000") as client:
        res = client.post(
            "/mcp",
            headers={"Authorization": "Bearer mock-token"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-runner", "version": "1.0"},
                },
            },
        )
        # Should NOT be 401 Unauthorized
        assert res.status_code == 200
        assert "mcp-session-id" in res.headers
