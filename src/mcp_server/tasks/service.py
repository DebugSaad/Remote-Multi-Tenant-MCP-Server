from datetime import date
from typing import Any
from uuid import UUID

from src.mcp_server.shared.db import get_db_transaction
from src.mcp_server.tasks.repository import TasksRepository


class TasksService:
    """Service providing task management operations within a transactional boundary."""

    @staticmethod
    async def add_task(
        user_id: str | UUID,
        title: str,
        due_date: date | None = None,
    ) -> dict[str, str]:
        """Add a new task within a single transaction and return its ID."""
        async with get_db_transaction(str(user_id)) as session:
            task = await TasksRepository.add_task(
                session=session,
                user_id=str(user_id),
                title=title,
                due_date=due_date,
            )
            return {"id": task["id"]}

    @staticmethod
    async def list_tasks(
        user_id: str | UUID,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List user's tasks matching optional status filter within a transaction."""
        async with get_db_transaction(str(user_id)) as session:
            return await TasksRepository.list_tasks(
                session=session,
                user_id=str(user_id),
                status=status,
                limit=limit,
            )

    @staticmethod
    async def complete_task(
        user_id: str | UUID,
        task_id: str | UUID,
    ) -> dict[str, str] | None:
        """Mark a task as done. Returns dict with id and status, or None if not found/unowned."""
        async with get_db_transaction(str(user_id)) as session:
            return await TasksRepository.complete_task(
                session=session,
                user_id=str(user_id),
                task_id=str(task_id),
            )
