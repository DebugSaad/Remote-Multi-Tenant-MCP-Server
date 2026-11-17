from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TasksRepository:
    """Repository handling SQL operations for the tasks table."""

    @staticmethod
    async def add_task(
        session: AsyncSession,
        user_id: str | UUID,
        title: str,
        due_date: date | None = None,
    ) -> dict[str, Any]:
        """Insert a new task owned by user_id and return its data."""
        sql = text("""
            INSERT INTO tasks (owner_id, title, due_date, status)
            VALUES (:user_id, :title, :due_date, 'open')
            RETURNING id, owner_id, title, due_date, status, created_at;
        """)
        result = await session.execute(
            sql,
            {
                "user_id": str(user_id),
                "title": title,
                "due_date": due_date,
            },
        )
        row = result.mappings().one()
        return {
            "id": str(row["id"]),
            "owner_id": str(row["owner_id"]),
            "title": row["title"],
            "due_date": row["due_date"].isoformat() if row["due_date"] else None,
            "status": row["status"],
            "created_at": row["created_at"].isoformat(),
        }

    @staticmethod
    async def list_tasks(
        session: AsyncSession,
        user_id: str | UUID,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List tasks belonging to user_id, optionally filtered by status ('open' or 'done')."""
        params: dict[str, Any] = {
            "user_id": str(user_id),
            "limit": limit,
        }
        where_clauses = ["owner_id = :user_id"]

        if status:
            where_clauses.append("status = :status")
            params["status"] = status

        sql_str = f"""
            SELECT id, title, due_date, status
            FROM tasks
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
                "due_date": r["due_date"].isoformat() if r["due_date"] else None,
                "status": r["status"],
            }
            for r in rows
        ]

    @staticmethod
    async def complete_task(
        session: AsyncSession,
        user_id: str | UUID,
        task_id: str | UUID,
    ) -> dict[str, Any] | None:
        """Mark a task as 'done' for user_id. Returns updated info or None if not found/not owned."""
        sql = text("""
            UPDATE tasks
            SET status = 'done'
            WHERE id = :task_id AND owner_id = :user_id
            RETURNING id, status;
        """)
        result = await session.execute(
            sql,
            {
                "task_id": str(task_id),
                "user_id": str(user_id),
            },
        )
        row = result.mappings().first()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "status": row["status"],
        }
