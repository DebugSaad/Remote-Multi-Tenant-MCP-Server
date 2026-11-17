"""
Notes service layer.
Sits between tools and repository, managing transactions and business rules.
"""

from typing import Any
from uuid import UUID

from src.mcp_server.notes.repository import NotesRepository
from src.mcp_server.shared.db import get_db_transaction


class NotesService:
    """Service providing note management operations within a transactional boundary."""

    @staticmethod
    async def create_note(
        user_id: str | UUID,
        title: str,
        content: str = "",
    ) -> dict[str, str]:
        """Create a new note within a single transaction and return its ID."""
        async with get_db_transaction(str(user_id)) as session:
            note = await NotesRepository.create_note(
                session=session,
                user_id=str(user_id),
                title=title,
                content=content,
            )
            return {"id": note["id"]}

    @staticmethod
    async def list_notes(
        user_id: str | UUID,
        query: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List user's notes matching optional search criteria within a transaction."""
        async with get_db_transaction(str(user_id)) as session:
            return await NotesRepository.list_notes(
                session=session,
                user_id=str(user_id),
                query=query,
                limit=limit,
            )

    @staticmethod
    async def get_note(
        user_id: str | UUID,
        note_id: str | UUID,
    ) -> dict[str, Any] | None:
        """Retrieve a specific note owned by the user. Returns None if not found/unowned."""
        async with get_db_transaction(str(user_id)) as session:
            return await NotesRepository.get_note(
                session=session,
                user_id=str(user_id),
                note_id=str(note_id),
            )

    @staticmethod
    async def delete_note(
        user_id: str | UUID,
        note_id: str | UUID,
    ) -> bool:
        """Delete a note owned by the user. Returns True if deleted, False if not found."""
        async with get_db_transaction(str(user_id)) as session:
            return await NotesRepository.delete_note(
                session=session,
                user_id=str(user_id),
                note_id=str(note_id),
            )
