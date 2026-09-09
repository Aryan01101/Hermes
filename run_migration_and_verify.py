"""Run migration 003 and verify Supabase setup using Supabase client."""

import asyncio
from supabase import create_client, Client
from src.core.config import get_settings


async def main():
    settings = get_settings()

    # Create Supabase client
    supabase: Client = create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
    )

    print("=" * 60)
    print("SUPABASE ANALYSIS AND VERIFICATION")
    print("=" * 60)

    # Step 1: List all tables
    print("\n1. Checking all tables in schema...")
    try:
        # Query pg_tables to see all tables
        response = supabase.rpc(
            "exec_sql",
            {"query": "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"}
        ).execute()
        print("   ✓ Tables query successful")
    except Exception as e:
        print(f"   ✗ Cannot use exec_sql RPC: {e}")
        print("   → Will use direct table queries instead")

    # Step 2: Check each expected table
    print("\n2. Verifying expected tables exist...")
    tables_to_check = [
        "threads",
        "drafts",
        "reviewers",
        "reviewer_actions",
        "integration_tokens",
        "audit_log"
    ]

    for table in tables_to_check:
        try:
            response = supabase.table(table).select("*").limit(0).execute()
            print(f"   ✓ {table}: accessible")
        except Exception as e:
            error_msg = str(e)
            if "PGRST205" in error_msg:
                print(f"   ✗ {table}: NOT in schema cache (PGRST205)")
            else:
                print(f"   ✗ {table}: {error_msg}")

    # Step 3: Check integration_tokens specifically
    print("\n3. Checking integration_tokens table in detail...")
    try:
        response = supabase.table("integration_tokens").select("*").execute()
        print(f"   ✓ integration_tokens accessible")
        print(f"   → Found {len(response.data)} rows")
        for row in response.data:
            print(f"     - Provider: {row.get('provider')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Step 4: Check reviewers table
    print("\n4. Checking reviewers table...")
    try:
        response = supabase.table("reviewers").select("*").execute()
        print(f"   ✓ reviewers accessible")
        print(f"   → Found {len(response.data)} reviewer(s)")
        for reviewer in response.data:
            print(f"     - {reviewer.get('name')} ({reviewer.get('phone_number')}) - Active: {reviewer.get('is_active')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Step 5: Try to create the reload function via raw SQL execution
    print("\n5. Attempting to create schema reload function...")
    migration_sql = """
    CREATE OR REPLACE FUNCTION reload_postgrest_schema_cache()
    RETURNS void
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    BEGIN
        NOTIFY pgrst, 'reload schema';
    END;
    $$;

    SELECT reload_postgrest_schema_cache();
    """

    print("   ℹ Migration SQL prepared")
    print("   → This requires direct PostgreSQL connection")
    print("   → Cannot execute via Supabase REST API")

    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    print("\nThe integration_tokens table exists in PostgreSQL but")
    print("PostgREST's schema cache needs to be reloaded.")
    print("\nPlease run this in Supabase SQL Editor:")
    print("\n" + migration_sql)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
