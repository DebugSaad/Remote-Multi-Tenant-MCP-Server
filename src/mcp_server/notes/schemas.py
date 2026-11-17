"""
Pydantic schemas and input validation for the notes domain.
Enforces limits from TRD section 5.
"""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateNoteInput(BaseModel):
    """Input schema for create_note."""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Title of the note (1 to 200 characters).",
        ),
    ]
    content: Annotated[
        str,
        Field(
            default="",
            max_length=10000,
            description="Body content of the note (up to 10,000 characters).",
        ),
    ]


class CreateNoteOutput(BaseModel):
    """Output schema for create_note."""
    id: str = Field(description="UUID of the newly created note.")


class ListNotesInput(BaseModel):
    """Input schema for list_notes."""
    model_config = ConfigDict(str_strip_whitespace=True)

    query: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="Optional search query across note title and content.",
        ),
    ]
    limit: Annotated[
        int,
        Field(
            default=20,
            ge=1,
            le=100,
            description="Maximum number of notes to return (1 to 100, default 20).",
        ),
    ]


class NoteSummary(BaseModel):
    """Summary of a note returned in listings."""
    id: str
    title: str
    created_at: str


class GetNoteInput(BaseModel):
    """Input schema for get_note."""
    id: UUID = Field(description="UUID of the note to retrieve.")


class NoteDetail(BaseModel):
    """Detailed view of a single note."""
    id: str
    title: str
    content: str
    created_at: str
    updated_at: str


class DeleteNoteInput(BaseModel):
    """Input schema for delete_note."""
    id: UUID = Field(description="UUID of the note to delete.")


class DeleteNoteOutput(BaseModel):
    """Output schema for delete_note."""
    deleted: bool = Field(default=True, description="Confirmation of deletion.")
