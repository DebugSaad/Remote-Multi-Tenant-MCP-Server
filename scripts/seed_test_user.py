"""
Seed script to insert the Phase 2 test user.
Connects as postgres (owner) and ensures the test user exists.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.mcp_server.config import TEST_USER_ID, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")


async def seed_test_user(
    user_id: str = TEST_USER_ID,
    external_id: str = "test-user-001",
    email: str = "test@example.com",
    role: str = "user",
) -> None:
    """Insert or verify test user in PostgreSQL."""
    engine = create_async_engine(settings.migration_database_url, echo=False)
    try:
        async with engine.begin() as conn:
            query = text("""
                INSERT INTO users (id, external_id, email, role, is_active)
                VALUES (:id, :external_id, :email, :role, true)
                ON CONFLICT (id) DO UPDATE
                SET external_id = EXCLUDED.external_id,
                    email = EXCLUDED.email,
                    is_active = true
                RETURNING id, external_id, email, role, is_active;
            """)
            result = await conn.execute(
                query,
                {
                    "id": user_id,
                    "external_id": external_id,
                    "email": email,
                    "role": role,
                },
            )
            row = result.mappings().one()
            logger.info("Test user verified in database: %s", dict(row))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_test_user())
