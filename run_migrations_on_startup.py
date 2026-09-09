"""Run database migrations on Railway startup.

This ensures the integration_tokens table exists before the application starts.
"""

import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv


async def run_migrations():
    """Create integration_tokens table if it doesn't exist."""
    # Load environment variables
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        sys.exit(1)

    print("🔧 Running database migrations...")
    print(f"📡 Connecting to database...")

    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")

        # Check if integration_tokens table exists
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'integration_tokens'
            )
            """
        )

        if exists:
            print("✅ integration_tokens table already exists")
        else:
            print("📝 Creating integration_tokens table...")

            # Create the table
            await conn.execute(
                """
                CREATE TABLE integration_tokens (
                    provider TEXT PRIMARY KEY,
                    token_cache TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            # Create the updated_at trigger function
            await conn.execute(
                """
                CREATE OR REPLACE FUNCTION update_integration_tokens_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )

            # Create the trigger
            await conn.execute(
                """
                DROP TRIGGER IF EXISTS update_integration_tokens_updated_at ON integration_tokens;
                CREATE TRIGGER update_integration_tokens_updated_at
                    BEFORE UPDATE ON integration_tokens
                    FOR EACH ROW
                    EXECUTE FUNCTION update_integration_tokens_updated_at();
                """
            )

            # Enable RLS
            await conn.execute(
                """
                ALTER TABLE integration_tokens ENABLE ROW LEVEL SECURITY;
                """
            )

            print("✅ integration_tokens table created successfully")

        await conn.close()
        print("✅ Database migrations complete")
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_migrations())
