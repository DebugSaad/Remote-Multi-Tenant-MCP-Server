"""
Tasks MCP tools.
Thin tool handlers that validate input, delegate to TasksService, and return outputs.
"""

from typing import Any
from pydantic import ValidationError

from mcp.server import MCPServer
from src.mcp_server.shared.context import get_current_user_id
from src.mcp_server.tasks.schemas import (
    AddTaskInput,
    CompleteTaskInput,
    ListTasksInput,
)
from src.mcp_server.tasks.service import TasksService


def register_tasks_tools(server: MCPServer) -> None:
    """Register all task-related tools with the MCP server."""

    @server.tool(
        name="add_task",
        description="Track a task with a title (1-200 chars) and optional due date (YYYY-MM-DD). Does not send reminders.",
    )
    async def add_task(title: str, due_date: str | None = None) -> dict[str, Any]:
        """Add a task. Returns the created task ID."""
        try:
            validated = AddTaskInput(title=title, due_date=due_date)  # type: ignore[arg-type]
        except ValidationError as e:
            return {"error": f"Invalid input: {e.errors()[0]['msg']}"}

        user_id = get_current_user_id()
        return await TasksService.add_task(user_id, validated.title, validated.due_date)

    @server.tool(
        name="list_tasks",
        description="List the user's tasks, optionally filtered by status ('open' or 'done') and limit.",
    )
    async def list_tasks(
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]] | dict[str, str]:
        """List tasks."""
        try:
            validated = ListTasksInput(status=status, limit=limit)  # type: ignore[arg-type]
        except ValidationError as e:
            return {"error": f"Invalid input: {e.errors()[0]['msg']}"}

        user_id = get_current_user_id()
        return await TasksService.list_tasks(user_id, validated.status, validated.limit)

    @server.tool(
        name="complete_task",
        description="Mark a task as done by its UUID.",
    )
    async def complete_task(id: str) -> dict[str, Any] | str:
        """Mark a task done. Returns updated status or 'Not found'."""
        try:
            validated = CompleteTaskInput(id=id)  # type: ignore[arg-type]
        except ValidationError:
            return "Not found"

        user_id = get_current_user_id()
        completed = await TasksService.complete_task(user_id, validated.id)
        if completed is None:
            return "Not found"
        return completed
