"""
Notes repository.
The only code in the notes module that writes SQL.
Every function requires `user_id` and filters on it using parameterized queries.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class NotesRepository:
    """Repository handling SQL operations for the notes table."""

    @staticmethod
    async def create_note(
        session: AsyncSession,
        user_id: str | UUID,
        title: str,
        content: str = "",
    ) -> dict[str, Any]:
        """Insert a new note owned by user_id and return its data."""
        query = text("""
            INSERT INTO notes (owner_id, title, content)
            VALUES (:user_id, :title, :content)
            RETURNING id, owner_id, title, content, created_at, updated_at;
        """)
        result = await session.execute(
            query,
            {
                "user_id": str(user_id),
                "title": title,
                "content": content,
            },
        )
        row = result.mappings().one()
        return {
            "id": str(row["id"]),
            "owner_id": str(row["owner_id"]),
            "title": row["title"],
            "content": row["content"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    @staticmethod
    async def list_notes(
        session: AsyncSession,
        user_id: str | UUID,
        query: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List notes belonging to user_id, optionally filtered by title/content search."""
        params: dict[str, Any] = {
            "user_id": str(user_id),
            "limit": limit,
        }
        where_clauses = ["owner_id = :user_id"]

        if query:
            where_clauses.append("(title ILIKE :search OR content ILIKE :search)")
            params["search"] = f"%{query}%"

        sql_str = f"""
            SELECT id, title, created_at
            FROM notes
            WHERE {" AND ".join(where_clauses)}
            ORDER BY created_at DESC
            LIMIT :limit;
        """
        result = await session.execute(text(sql_str), params)
        rows = result.mappings().all()
        return [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    @staticmethod
    async def get_note(
        session: AsyncSession,
        user_id: str | UUID,
        note_id: str | UUID,
    ) -> dict[str, Any] | None:
        """Fetch a single note by id and user_id. Returns None if not found or not owned."""
        sql = text("""
            SELECT id, owner_id, title, content, created_at, updated_at
            FROM notes
            WHERE id = :note_id AND owner_id = :user_id;
        """)
        result = await session.execute(
            sql,
            {
                "note_id": str(note_id),
                "user_id": str(user_id),
            },
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "owner_id": str(row["owner_id"]),
            "title": row["title"],
            "content": row["content"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    @staticmethod
    async def delete_note(
        session: AsyncSession,
        user_id: str | UUID,
        note_id: str | UUID,
    ) -> bool:
        """Delete a note by id and user_id. Returns True if deleted, False if not found."""
        sql = text("""
            DELETE FROM notes
            WHERE id = :note_id AND owner_id = :user_id
            RETURNING id;
        """)
        result = await session.execute(
            sql,
            {
                "note_id": str(note_id),
                "user_id": str(user_id),
            },
        )
        row = result.first()
        return row is not None
