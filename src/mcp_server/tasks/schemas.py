"""
Pydantic schemas and input validation for the tasks domain.
Enforces limits from TRD section 5.
"""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AddTaskInput(BaseModel):
    """Input schema for add_task."""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Title of the task (1 to 200 characters).",
        ),
    ]
    due_date: Annotated[
        date | None,
        Field(
            default=None,
            description="Optional task due date in ISO format (YYYY-MM-DD).",
        ),
    ]


class AddTaskOutput(BaseModel):
    """Output schema for add_task."""
    id: str = Field(description="UUID of the newly created task.")


class ListTasksInput(BaseModel):
    """Input schema for list_tasks."""
    model_config = ConfigDict(str_strip_whitespace=True)

    status: Annotated[
        Literal["open", "done"] | None,
        Field(
            default=None,
            description="Optional status filter: 'open' or 'done'.",
        ),
    ]
    limit: Annotated[
        int,
        Field(
            default=20,
            ge=1,
            le=100,
            description="Maximum number of tasks to return (1 to 100, default 20).",
        ),
    ]


class TaskItem(BaseModel):
    """Task item returned in listings."""
    id: str
    title: str
    due_date: str | None = None
    status: str


class CompleteTaskInput(BaseModel):
    """Input schema for complete_task."""
    id: UUID = Field(description="UUID of the task to mark as completed.")


class CompleteTaskOutput(BaseModel):
    """Output schema for complete_task."""
    id: str = Field(description="UUID of the completed task.")
    status: Literal["done"] = Field(default="done", description="Updated task status.")
