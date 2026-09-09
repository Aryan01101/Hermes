"""Database migration runner using Supabase client instead of direct psycopg.

This bypasses direct PostgreSQL connection issues by using Supabase's REST API.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()


def run_migrations_via_supabase():
    """Run migrations using Supabase client."""
    print("=" * 60)
    print("🔧 HERMES DATABASE MIGRATION (via Supabase Client)")
    print("=" * 60)

    # Get Supabase credentials
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        print("❌ ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in .env")
        return False

    print(f"\n📡 Connecting to Supabase...")
    print(f"   └─ URL: {supabase_url}")

    try:
        # Create Supabase client
        supabase: Client = create_client(supabase_url, supabase_key)
        print(f"   ✅ Supabase client created")

        # Get migrations directory
        migrations_dir = Path(__file__).parent / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))

        print(f"\n📁 Found {len(migration_files)} migration file(s):")
        for f in migration_files:
            print(f"   └─ {f.name}")

        # Read the migration SQL
        for migration_file in migration_files:
            print(f"\n▶️  Running {migration_file.name}...")
            sql = migration_file.read_text()

            # Execute via Supabase RPC
            # Note: Supabase requires a different approach - we'll use their SQL editor endpoint
            response = supabase.rpc('exec_sql', {'query': sql}).execute()

            print(f"   ✅ Migration executed")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print(f"\n💡 The Supabase client approach failed.")
        print(f"\nAlternative: Run migrations manually in Supabase Dashboard:")
        print(f"   1. Go to https://supabase.com/dashboard/project/mhrmnthecmuvptiorhmz")
        print(f"   2. Click 'SQL Editor' in left sidebar")
        print(f"   3. Copy contents of migrations/001_initial_schema.sql")
        print(f"   4. Paste and click 'Run'")
        return False

    return True


if __name__ == "__main__":
    print("\n⚠️  NOTE: Direct PostgreSQL connection is failing due to network/DNS issues.")
    print("We'll use Supabase's web dashboard to run migrations instead.\n")

    print("🌐 MANUAL MIGRATION STEPS:")
    print("=" * 60)
    print("\n1. Open Supabase Dashboard:")
    print("   https://supabase.com/dashboard/project/mhrmnthecmuvptiorhmz/editor")
    print("\n2. Click 'SQL Editor' in the left sidebar")
    print("\n3. Create a new query")
    print("\n4. Copy and paste the SQL from:")
    print("   migrations/001_initial_schema.sql")
    print("\n5. Click 'Run' button")
    print("\n6. Verify tables were created (you should see 6 new tables)")
    print("\n=" * 60)

    print("\n📄 Opening migration file for you to copy...")

    # Read and display the migration SQL
    migrations_dir = Path(__file__).parent / "migrations"
    migration_file = migrations_dir / "001_initial_schema.sql"

    if migration_file.exists():
        print(f"\n" + "=" * 60)
        print("📋 COPY THIS SQL TO SUPABASE:")
        print("=" * 60)
        sql = migration_file.read_text()
        print(sql)
        print("=" * 60)
    else:
        print(f"\n❌ Migration file not found: {migration_file}")

    print("\n✅ After running the SQL in Supabase Dashboard, come back here and run:")
    print("   python test_connections.py")
