"""Check if WhatsApp quota tracking migration has been applied."""

import asyncio
import asyncpg
from src.core.config import get_settings


async def check_migration():
    """Check if the migration is complete."""
    settings = get_settings()

    print("🔍 Checking WhatsApp quota tracking migration...")
    print(f"Database: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'hidden'}")
    print()

    try:
        # Connect to database
        conn = await asyncpg.connect(settings.database_url)

        # Check 1: Does the table exist?
        table_check = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'whatsapp_quota_tracking'
            );
        """)

        if table_check:
            print("✅ Table 'whatsapp_quota_tracking' exists")

            # Get table structure
            columns = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'whatsapp_quota_tracking'
                ORDER BY ordinal_position;
            """)
            print("   Columns:")
            for col in columns:
                print(f"     - {col['column_name']}: {col['data_type']}")
        else:
            print("❌ Table 'whatsapp_quota_tracking' NOT FOUND")
            print("   👉 You need to run the migration!")
            await conn.close()
            return False

        print()

        # Check 2: Do the functions exist?
        functions_to_check = [
            'get_todays_whatsapp_quota',
            'increment_whatsapp_quota',
            'check_whatsapp_quota_available'
        ]

        for func_name in functions_to_check:
            func_check = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM pg_proc
                    WHERE proname = $1
                );
            """, func_name)

            if func_check:
                print(f"✅ Function '{func_name}' exists")
            else:
                print(f"❌ Function '{func_name}' NOT FOUND")

        print()

        # Check 3: Can we query today's quota?
        try:
            quota_result = await conn.fetch("SELECT * FROM get_todays_whatsapp_quota()")
            if quota_result:
                row = quota_result[0]
                print("✅ Successfully queried today's quota:")
                print(f"   - Date: {row['quota_date']}")
                print(f"   - Messages sent: {row['message_count']}/{row['daily_limit']}")
                print(f"   - Remaining: {row['remaining']}")
                if row['limit_reached_at']:
                    print(f"   - Limit reached at: {row['limit_reached_at']}")
            else:
                print("⚠️  No quota record found (will be created on first message)")
        except Exception as e:
            print(f"❌ Error querying quota: {e}")

        print()

        # Check 4: Row Level Security policies
        policies = await conn.fetch("""
            SELECT policyname, cmd, qual
            FROM pg_policies
            WHERE tablename = 'whatsapp_quota_tracking';
        """)

        if policies:
            print(f"✅ RLS policies exist ({len(policies)} policy/policies)")
            for policy in policies:
                print(f"   - {policy['policyname']}")
        else:
            print("⚠️  No RLS policies found (may be expected)")

        await conn.close()

        print()
        print("=" * 60)
        print("✅ MIGRATION COMPLETE - All checks passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"❌ Error checking migration: {e}")
        print()
        print("This likely means:")
        print("1. Migration hasn't been run yet, OR")
        print("2. Database connection failed")
        print()
        print("👉 Go to Supabase SQL Editor and run:")
        print("   migrations/004_whatsapp_quota_tracking.sql")
        return False


if __name__ == "__main__":
    asyncio.run(check_migration())
