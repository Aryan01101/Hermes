"""Reload PostgREST schema cache by sending NOTIFY command."""

import asyncio
import asyncpg
from src.core.config import get_settings


async def reload_schema_cache() -> None:
    """Send NOTIFY command to reload PostgREST schema cache."""
    settings = get_settings()

    # Extract connection details from DATABASE_URL
    conn = await asyncpg.connect(settings.database_url)
    try:
        print("Connected to database")

        # Send NOTIFY command to reload schema cache
        await conn.execute("NOTIFY pgrst, 'reload schema';")
        print("✓ Sent NOTIFY pgrst, 'reload schema' command")

        # Wait a moment for PostgREST to process
        await asyncio.sleep(2)
        print("✓ PostgREST schema cache should now be reloaded")

    finally:
        await conn.close()
        print("Disconnected from database")


if __name__ == "__main__":
    asyncio.run(reload_schema_cache())
