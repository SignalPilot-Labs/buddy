"""Database initialization — creates tables from ORM models.

Run once at startup before dashboard or agent containers connect.
Idempotent: safe to run multiple times (CREATE TABLE IF NOT EXISTS).
"""

import asyncio

from db.connection import connect, create_tables, close


async def _main() -> None:
    """Connect, create tables, disconnect."""
    await connect()
    await create_tables()
    await close()


if __name__ == "__main__":
    asyncio.run(_main())
