"""Database migration runner for Hermes.

This script runs SQL migrations on the Supabase database.
"""

import asyncio
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def run_migrations():
    """Run all SQL migration files."""
    print("=" * 60)
    print("🔧 HERMES DATABASE MIGRATION RUNNER")
    print("=" * 60)

    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in .env file")
        return False

    print(f"\n📡 Connecting to database...")
    print(f"   └─ Host: {database_url.split('@')[1].split(':')[0] if '@' in database_url else 'unknown'}")

    # Get migrations directory
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        print(f"❌ ERROR: Migrations directory not found: {migrations_dir}")
        return False

    # Get all SQL files, sorted by name
    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        print(f"❌ ERROR: No migration files found in {migrations_dir}")
        return False

    print(f"\n📁 Found {len(migration_files)} migration file(s):")
    for f in migration_files:
        print(f"   └─ {f.name}")

    try:
        # Connect to database
        print(f"\n🔌 Establishing database connection...")
        conn = psycopg.connect(database_url)

        # Run each migration
        for migration_file in migration_files:
            print(f"\n▶️  Running {migration_file.name}...")

            # Read SQL file
            sql = migration_file.read_text()

            # Execute SQL
            with conn.cursor() as cur:
                cur.execute(sql)

            print(f"   ✅ Successfully executed {migration_file.name}")

        # Commit all changes
        conn.commit()
        print(f"\n✅ All migrations committed successfully!")

        # Verify tables were created
        print(f"\n🔍 Verifying database schema...")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            tables = cur.fetchall()

        print(f"\n📊 Found {len(tables)} tables:")
        for table in tables:
            print(f"   ✅ {table[0]}")

        # Close connection
        conn.close()

        print("\n" + "=" * 60)
        print("🎉 MIGRATION COMPLETE!")
        print("=" * 60)
        print("\nYour database is now ready for Hermes v2.")
        print("\n📝 Next step: Run connection test again:")
        print("   python test_connections.py")
        print("=" * 60)

        return True

    except psycopg.Error as e:
        print(f"\n❌ DATABASE ERROR: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Check your DATABASE_URL in .env")
        print("   2. Ensure your Supabase database is accessible")
        print("   3. Verify your database password is correct")
        return False

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        return False


if __name__ == "__main__":
    success = run_migrations()
    exit(0 if success else 1)
