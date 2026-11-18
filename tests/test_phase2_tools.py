"""
Automated test suite for Phase 2 MCP tools.
Tests all 7 domain tools + ping over the MCP Streamable HTTP protocol.
"""

import json
from collections.abc import Iterator
import pytest
from starlette.testclient import TestClient

from src.mcp_server.main import create_app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Module-scoped TestClient ensuring full lifespan and single task group."""
    app = create_app()
    with TestClient(
        app,
        base_url="http://testserver",
        headers={"Authorization": "Bearer test-phase2-token"},
    ) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def mcp_session(client: TestClient) -> Iterator[str]:
    """Initialize an MCP Streamable HTTP session and perform initialized handshake."""
    # 1. Initialize
    init_res = client.post(
        "/mcp",
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
    assert init_res.status_code == 200
    session_id = init_res.headers["mcp-session-id"]

    # 2. Handshake ack
    ack_res = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={"mcp-session-id": session_id},
    )
    assert ack_res.status_code in (200, 202)

    yield session_id


def call_tool(client: TestClient, session_id: str, call_id: int, name: str, args: dict):
    """Helper to execute an MCP tool and extract result."""
    res = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
        headers={"mcp-session-id": session_id},
    )
    assert res.status_code == 200
    # Streamable HTTP returns SSE lines: "event: message\ndata: {...}\n\n"
    lines = res.text.strip().split("\n")
    data_line = next(line for line in lines if line.startswith("data: "))
    payload = json.loads(data_line[6:])["result"]

    if "structuredContent" in payload:
        sc = payload["structuredContent"]
        return sc.get("result", sc)
    return payload["content"][0]["text"]


def test_tools_list(client: TestClient, mcp_session: str) -> None:
    """Verify all 8 tools are registered and advertised."""
    res = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers={"mcp-session-id": mcp_session},
    )
    assert res.status_code == 200
    lines = res.text.strip().split("\n")
    data_line = next(line for line in lines if line.startswith("data: "))
    tools = json.loads(data_line[6:])["result"]["tools"]
    tool_names = [t["name"] for t in tools]

    expected = [
        "ping",
        "create_note",
        "list_notes",
        "get_note",
        "delete_note",
        "add_task",
        "list_tasks",
        "complete_task",
    ]
    for exp in expected:
        assert exp in tool_names, f"Missing tool: {exp}"


def test_notes_tools_crud(client: TestClient, mcp_session: str) -> None:
    """Verify Notes CRUD tools: create, get, list, delete, and not found handling."""
    # 1. create_note
    create_res = call_tool(
        client, mcp_session, 10, "create_note", {"title": "Pytest Note", "content": "Pytest content"}
    )
    assert "id" in create_res
    note_id = create_res["id"]

    # 2. get_note
    get_res = call_tool(client, mcp_session, 11, "get_note", {"id": note_id})
    assert get_res["title"] == "Pytest Note"
    assert get_res["content"] == "Pytest content"

    # 3. get_note with non-existent UUID -> "Not found"
    missing = call_tool(
        client, mcp_session, 12, "get_note", {"id": "00000000-0000-0000-0000-999999999999"}
    )
    assert missing == "Not found"

    # 4. list_notes
    notes = call_tool(client, mcp_session, 13, "list_notes", {"query": "Pytest"})
    assert any(n["id"] == note_id for n in notes)

    # 5. delete_note
    del_res = call_tool(client, mcp_session, 14, "delete_note", {"id": note_id})
    assert del_res == {"deleted": True}

    # 6. delete_note on already deleted note -> "Not found"
    del_again = call_tool(client, mcp_session, 15, "delete_note", {"id": note_id})
    assert del_again == "Not found"


def test_tasks_tools_crud(client: TestClient, mcp_session: str) -> None:
    """Verify Tasks CRUD tools: add, list, complete, and not found handling."""
    # 1. add_task
    add_res = call_tool(
        client, mcp_session, 20, "add_task", {"title": "Pytest Task", "due_date": "2026-12-15"}
    )
    assert "id" in add_res
    task_id = add_res["id"]

    # 2. list_tasks (open)
    tasks = call_tool(client, mcp_session, 21, "list_tasks", {"status": "open"})
    assert any(t["id"] == task_id for t in tasks)

    # 3. complete_task
    complete_res = call_tool(client, mcp_session, 22, "complete_task", {"id": task_id})
    assert complete_res == {"id": task_id, "status": "done"}

    # 4. complete_task on non-existent UUID -> "Not found"
    missing = call_tool(
        client, mcp_session, 23, "complete_task", {"id": "00000000-0000-0000-0000-999999999999"}
    )
    assert missing == "Not found"
