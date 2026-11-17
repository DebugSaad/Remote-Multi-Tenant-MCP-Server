"""
Interactive MCP test client.
Connects to the running server on http://127.0.0.1:8000/mcp,
initializes an MCP session, lists tools, and calls create_note and add_task.
"""

import json
import httpx

BASE_URL = "http://127.0.0.1:8000"


def main():
    print(f"Connecting to MCP Server at {BASE_URL}...")
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Health check
        health = client.get("/health")
        print(f"[1] GET /health -> {health.status_code}: {health.json()}")

        # 2. Initialize
        headers = {"Accept": "application/json, text/event-stream"}
        init_res = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0"},
                },
            },
            headers=headers,
        )
        if init_res.status_code != 200:
            print(f"[-] Initialize failed ({init_res.status_code}): {init_res.text}")
            return

        session_id = init_res.headers.get("mcp-session-id")
        print(f"[2] Initialized! Session ID: {session_id}")
        headers["mcp-session-id"] = session_id

        # 3. Initialized notification
        ack = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=headers,
        )
        print(f"[3] Handshake ack -> {ack.status_code}")

        def parse_mcp_response(res_text: str):
            for line in res_text.splitlines():
                if line.startswith("data: "):
                    return json.loads(line[6:])
            return json.loads(res_text)

        # 4. List tools
        tools_res = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers=headers,
        )
        tools_data = parse_mcp_response(tools_res.text)
        tools = [t["name"] for t in tools_data["result"]["tools"]]
        print(f"[4] Registered Tools ({len(tools)}): {tools}")

        # 5. Create Note
        note_res = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "create_note",
                    "arguments": {
                        "title": "Interactive Client Note",
                        "content": "Created via scripts/test_client.py",
                    },
                },
            },
            headers=headers,
        )
        note_data = parse_mcp_response(note_res.text)
        print(f"[5] create_note -> {note_data.get('result')}")

        # 6. Add Task
        task_res = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "add_task",
                    "arguments": {
                        "title": "Interactive Client Task",
                        "due_date": "2026-12-31",
                    },
                },
            },
            headers=headers,
        )
        task_data = parse_mcp_response(task_res.text)
        print(f"[6] add_task -> {task_data.get('result')}")

        # 7. List Tasks
        list_tasks_res = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "list_tasks", "arguments": {"status": "open"}},
            },
            headers=headers,
        )
        list_tasks_data = parse_mcp_response(list_tasks_res.text)
        print(f"[7] list_tasks (open) -> {list_tasks_data.get('result')}")

        print("\nAll live MCP operations completed successfully!")


if __name__ == "__main__":
    main()
