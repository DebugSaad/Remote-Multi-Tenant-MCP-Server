"""
Notes MCP tools.
Thin tool handlers that validate input, delegate to NotesService, and return outputs.
"""

from typing import Any
from pydantic import ValidationError

from mcp.server import MCPServer
from src.mcp_server.notes.schemas import (
    CreateNoteInput,
    DeleteNoteInput,
    GetNoteInput,
    ListNotesInput,
)
from src.mcp_server.notes.service import NotesService
from src.mcp_server.shared.context import get_current_user_id


def register_notes_tools(server: MCPServer) -> None:
    """Register all notes-related tools with the MCP server."""

    @server.tool(
        name="create_note",
        description="Save a private note with a title (1-200 chars) and optional content.",
    )
    async def create_note(title: str, content: str = "") -> dict[str, Any]:
        """Save a new note. Returns the created note ID."""
        try:
            validated = CreateNoteInput(title=title, content=content)
        except ValidationError as e:
            return {"error": f"Invalid input: {e.errors()[0]['msg']}"}

        user_id = get_current_user_id()
        return await NotesService.create_note(user_id, validated.title, validated.content)

    @server.tool(
        name="list_notes",
        description="List the user's private notes, with optional search text and limit.",
    )
    async def list_notes(
        query: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]] | dict[str, str]:
        """List the user's notes."""
        try:
            validated = ListNotesInput(query=query, limit=limit)
        except ValidationError as e:
            return {"error": f"Invalid input: {e.errors()[0]['msg']}"}

        user_id = get_current_user_id()
        return await NotesService.list_notes(user_id, validated.query, validated.limit)

    @server.tool(
        name="get_note",
        description="Read a single note by its UUID.",
    )
    async def get_note(id: str) -> dict[str, Any] | str:
        """Read one note by ID. Returns 'Not found' if missing or unowned."""
        try:
            validated = GetNoteInput(id=id)  # type: ignore[arg-type]
        except ValidationError:
            return "Not found"

        user_id = get_current_user_id()
        note = await NotesService.get_note(user_id, validated.id)
        if note is None:
            return "Not found"
        return note

    @server.tool(
        name="delete_note",
        description="Delete a single note by its UUID.",
    )
    async def delete_note(id: str) -> dict[str, Any] | str:
        """Delete one note by ID. Returns confirmation or 'Not found'."""
        try:
            validated = DeleteNoteInput(id=id)  # type: ignore[arg-type]
        except ValidationError:
            return "Not found"

        user_id = get_current_user_id()
        deleted = await NotesService.delete_note(user_id, validated.id)
        if not deleted:
            return "Not found"
        return {"deleted": True}
