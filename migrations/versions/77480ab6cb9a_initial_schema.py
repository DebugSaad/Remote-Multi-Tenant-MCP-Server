"""initial_schema

Revision ID: 77480ab6cb9a
Revises: 
Create Date: 2026-11-17 21:36:23.131722

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '77480ab6cb9a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Ensure pgcrypto extension exists for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # 1. Table: users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('external_id', sa.Text(), nullable=False),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=False, server_default=sa.text("'user'")),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('external_id', name='uq_users_external_id'),
    )

    # 2. Table: notes
    op.create_table(
        'notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('char_length(title) BETWEEN 1 AND 200', name='notes_title_length_check'),
        sa.CheckConstraint('char_length(content) <= 10000', name='notes_content_length_check'),
    )
    # Index: notes_owner_idx on (owner_id, created_at DESC)
    op.execute("CREATE INDEX notes_owner_idx ON notes (owner_id, created_at DESC);")

    # 3. Table: tasks
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('char_length(title) BETWEEN 1 AND 200', name='tasks_title_length_check'),
        sa.CheckConstraint("status IN ('open', 'done')", name='tasks_status_check'),
    )
    # Index: tasks_owner_idx on (owner_id, status)
    op.execute("CREATE INDEX tasks_owner_idx ON tasks (owner_id, status);")

    # 4. Table: audit_log
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tool_name', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    # Index: audit_user_idx on (user_id, created_at DESC)
    op.execute("CREATE INDEX audit_user_idx ON audit_log (user_id, created_at DESC);")

    # 5. Insert Phase 2 hardcoded test user
    op.execute("""
        INSERT INTO users (id, external_id, email, role, is_active)
        VALUES ('00000000-0000-0000-0000-000000000001', 'test-user-001', 'test@example.com', 'user', true)
        ON CONFLICT (id) DO NOTHING;
    """)

    # 6. Principle of least privilege: GRANT app_user only what it needs (single statement per execute for asyncpg)
    op.execute("GRANT SELECT ON users TO app_user;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON notes TO app_user;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tasks TO app_user;")
    op.execute("GRANT SELECT, INSERT ON audit_log TO app_user;")


def downgrade() -> None:
    # Revoke permissions from app_user (single statement per execute for asyncpg)
    op.execute("REVOKE ALL ON audit_log FROM app_user;")
    op.execute("REVOKE ALL ON tasks FROM app_user;")
    op.execute("REVOKE ALL ON notes FROM app_user;")
    op.execute("REVOKE ALL ON users FROM app_user;")

    op.drop_table('audit_log')
    op.drop_table('tasks')
    op.drop_table('notes')
    op.drop_table('users')
