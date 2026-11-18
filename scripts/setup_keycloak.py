"""
Keycloak Configuration Script for MCP Server (Phase 3).
Sets up:
- Realm: mcp
- Public Client: mcp-inspector with PKCE (S256)
- Audience Mapper: ensures access tokens contain MCP_RESOURCE_URL in aud
- Role: admin
- Test Users: Ali (regular tenant user) and Sara (admin user)
- Exports realm configuration to infra/keycloak/mcp-realm.json
"""

import json
import logging
from pathlib import Path
import sys
import httpx

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mcp_server.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("keycloak-setup")

KEYCLOAK_BASE_URL = "http://127.0.0.1:8080"
REALM_NAME = "mcp"
CLIENT_ID = "mcp-inspector"
MCP_RESOURCE_URL = "http://localhost:8000"


def get_admin_token(client: httpx.Client, password: str) -> str:
    """Authenticate with Keycloak master realm as admin."""
    res = client.post(
        f"{KEYCLOAK_BASE_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "admin",
            "password": password,
        },
    )
    res.raise_for_status()
    return res.json()["access_token"]


def setup_realm(client: httpx.Client, headers: dict) -> None:
    """Ensure the 'mcp' realm exists."""
    res = client.get(f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}", headers=headers)
    if res.status_code == 200:
        logger.info("Realm '%s' already exists.", REALM_NAME)
        return

    logger.info("Creating realm '%s'...", REALM_NAME)
    create_res = client.post(
        f"{KEYCLOAK_BASE_URL}/admin/realms",
        json={
            "realm": REALM_NAME,
            "enabled": True,
            "displayName": "Remote MCP Multi-Tenant Realm",
            "accessTokenLifespan": 900,  # 15 minutes
            "ssoSessionIdleTimeout": 1800,  # 30 minutes
        },
        headers=headers,
    )
    create_res.raise_for_status()
    logger.info("Realm '%s' created successfully.", REALM_NAME)


def setup_admin_role(client: httpx.Client, headers: dict) -> dict:
    """Ensure the 'admin' realm role exists."""
    roles_res = client.get(f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/roles", headers=headers)
    roles_res.raise_for_status()
    existing_roles = roles_res.json()

    admin_role = next((r for r in existing_roles if r["name"] == "admin"), None)
    if admin_role:
        logger.info("Realm role 'admin' already exists.")
        return admin_role

    logger.info("Creating realm role 'admin'...")
    create_res = client.post(
        f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/roles",
        json={"name": "admin", "description": "Administrator role with tenant management access"},
        headers=headers,
    )
    create_res.raise_for_status()
    # Fetch created role
    res = client.get(f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/roles/admin", headers=headers)
    res.raise_for_status()
    logger.info("Realm role 'admin' created successfully.")
    return res.json()


def setup_inspector_client(client: httpx.Client, headers: dict) -> str:
    """Ensure the public PKCE client 'mcp-inspector' exists with audience mapper."""
    clients_res = client.get(f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/clients", headers=headers)
    clients_res.raise_for_status()
    clients = clients_res.json()

    existing_client = next((c for c in clients if c["clientId"] == CLIENT_ID), None)
    client_uuid: str

    if existing_client:
        client_uuid = existing_client["id"]
        logger.info("Client '%s' already exists (UUID: %s).", CLIENT_ID, client_uuid)
    else:
        logger.info("Creating client '%s' with PKCE (S256)...", CLIENT_ID)
        create_res = client.post(
            f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/clients",
            json={
                "clientId": CLIENT_ID,
                "name": "MCP Inspector",
                "enabled": True,
                "publicClient": True,
                "standardFlowEnabled": True,
                "directAccessGrantsEnabled": True,
                "serviceAccountsEnabled": False,
                "redirectUris": [
                    "http://localhost:*",
                    "http://127.0.0.1:*",
                    "http://localhost:5173/*",
                    "http://127.0.0.1:5173/*",
                ],
                "webOrigins": ["*"],
                "attributes": {
                    "pkce.code.challenge.method": "S256",
                    "post.logout.redirect.uris": "+",
                },
            },
            headers=headers,
        )
        create_res.raise_for_status()

        # Retrieve the newly created client UUID
        lookup_res = client.get(f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/clients?clientId={CLIENT_ID}", headers=headers)
        lookup_res.raise_for_status()
        client_uuid = lookup_res.json()[0]["id"]
        logger.info("Client '%s' created with UUID: %s.", CLIENT_ID, client_uuid)

    # Configure Audience Mapper (resolves Keycloak 26.7 lack of resource parameter)
    mappers_res = client.get(
        f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/clients/{client_uuid}/protocol-mappers/models",
        headers=headers,
    )
    mappers_res.raise_for_status()
    mappers = mappers_res.json()

    aud_mapper = next((m for m in mappers if m["name"] == "mcp-resource-audience"), None)
    if not aud_mapper:
        logger.info("Adding oidc-audience-mapper for '%s' to client '%s'...", MCP_RESOURCE_URL, CLIENT_ID)
        mapper_res = client.post(
            f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/clients/{client_uuid}/protocol-mappers/models",
            json={
                "name": "mcp-resource-audience",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "consentRequired": False,
                "config": {
                    "included.custom.audience": MCP_RESOURCE_URL,
                    "id.token.claim": "false",
                    "access.token.claim": "true",
                    "introspection.token.claim": "true",
                },
            },
            headers=headers,
        )
        mapper_res.raise_for_status()
        logger.info("Audience mapper added successfully.")
    else:
        logger.info("Audience mapper already present on client.")

    return client_uuid


def setup_user(client: httpx.Client, headers: dict, username: str, email: str, first: str, last: str, password: str) -> str:
    """Ensure a user exists with password credentials."""
    users_res = client.get(f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/users?username={username}", headers=headers)
    users_res.raise_for_status()
    users = users_res.json()

    user_uuid: str
    if users:
        user_uuid = users[0]["id"]
        logger.info("User '%s' already exists (UUID: %s).", username, user_uuid)
    else:
        logger.info("Creating user '%s' (%s)...", username, email)
        create_res = client.post(
            f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/users",
            json={
                "username": username,
                "email": email,
                "firstName": first,
                "lastName": last,
                "enabled": True,
                "emailVerified": True,
            },
            headers=headers,
        )
        create_res.raise_for_status()

        lookup = client.get(f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/users?username={username}", headers=headers)
        lookup.raise_for_status()
        user_uuid = lookup.json()[0]["id"]
        logger.info("User '%s' created with UUID: %s.", username, user_uuid)

    # Set password
    pw_res = client.put(
        f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/users/{user_uuid}/reset-password",
        json={"type": "password", "value": password, "temporary": False},
        headers=headers,
    )
    pw_res.raise_for_status()
    logger.info("Password set for user '%s'.", username)
    return user_uuid


def assign_role_to_user(client: httpx.Client, headers: dict, user_uuid: str, role_obj: dict) -> None:
    """Assign a realm role to a user."""
    res = client.post(
        f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/users/{user_uuid}/role-mappings/realm",
        json=[role_obj],
        headers=headers,
    )
    res.raise_for_status()
    logger.info("Assigned role '%s' to user UUID %s.", role_obj["name"], user_uuid)


def verify_token_issuance(username: str, password: str) -> dict:
    """Verify that password grant issues a valid token with aud matching MCP_RESOURCE_URL."""
    with httpx.Client() as client:
        res = client.post(
            f"{KEYCLOAK_BASE_URL}/realms/{REALM_NAME}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "username": username,
                "password": password,
            },
        )
        res.raise_for_status()
        token_data = res.json()
        access_token = token_data["access_token"]

        # Decode JWT payload (base64url)
        import base64
        payload_part = access_token.split(".")[1]
        padded = payload_part + "=" * (-len(payload_part) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))

        logger.info("Token verified for user '%s':", username)
        logger.info("  - sub (external_id): %s", claims.get("sub"))
        logger.info("  - aud: %s", claims.get("aud"))
        logger.info("  - roles: %s", claims.get("realm_access", {}).get("roles"))

        # Assertions
        aud = claims.get("aud")
        aud_list = [aud] if isinstance(aud, str) else (aud or [])
        assert MCP_RESOURCE_URL in aud_list, f"MCP_RESOURCE_URL '{MCP_RESOURCE_URL}' not in token audience {aud_list}"
        return claims


def export_realm(client: httpx.Client, headers: dict, out_path: Path) -> None:
    """Export realm configuration to file for versioning."""
    res = client.get(f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}", headers=headers)
    res.raise_for_status()
    realm_data = res.json()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(realm_data, indent=2), encoding="utf-8")
    logger.info("Exported realm configuration to %s", out_path)


def main():
    logger.info("Connecting to Keycloak Admin at %s...", KEYCLOAK_BASE_URL)
    with httpx.Client(timeout=15.0) as client:
        admin_token = get_admin_token(client, password="admin_super_secret")
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

        # 1. Setup Realm
        setup_realm(client, headers)

        # 2. Setup Admin Role
        admin_role = setup_admin_role(client, headers)

        # 3. Setup Inspector Client with PKCE and Audience Mapper
        setup_inspector_client(client, headers)

        # 4. Setup Test User: Ali
        ali_uuid = setup_user(client, headers, "ali", "ali@example.com", "Ali", "Tenant", "password123")

        # 5. Setup Test User: Sara (with admin role)
        sara_uuid = setup_user(client, headers, "sara", "sara@example.com", "Sara", "Admin", "password123")
        assign_role_to_user(client, headers, sara_uuid, admin_role)

        # 6. Verify Token Issuance & Audience Mapper
        logger.info("\n--- Verifying Token Issuance ---")
        ali_claims = verify_token_issuance("ali", "password123")
        sara_claims = verify_token_issuance("sara", "password123")
        assert "admin" in sara_claims.get("realm_access", {}).get("roles", [])

        # 7. Export Realm JSON
        export_realm(client, headers, Path("infra/keycloak/mcp-realm.json"))

        logger.info("\nKeycloak configured successfully!")
        logger.info("Realm: %s", REALM_NAME)
        logger.info("Issuer: %s/realms/%s", KEYCLOAK_BASE_URL, REALM_NAME)
        logger.info("Client: %s (PKCE S256, Audience Mapper: %s)", CLIENT_ID, MCP_RESOURCE_URL)
        logger.info("User Ali: %s (UUID: %s)", "ali@example.com", ali_uuid)
        logger.info("User Sara: %s (UUID: %s, Role: admin)", "sara@example.com", sara_uuid)


if __name__ == "__main__":
    main()
