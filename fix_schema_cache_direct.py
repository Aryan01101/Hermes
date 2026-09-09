"""Directly connect to PostgreSQL and reload schema cache."""

import psycopg2
from src.core.config import get_settings


def main():
    settings = get_settings()

    print("Connecting to PostgreSQL...")

    # Connect using the DATABASE_URL
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        print("✓ Connected to PostgreSQL")

        # Step 1: Create the reload function
        print("\n1. Creating reload_postgrest_schema_cache function...")
        cursor.execute("""
            CREATE OR REPLACE FUNCTION reload_postgrest_schema_cache()
            RETURNS void
            LANGUAGE plpgsql
            SECURITY DEFINER
            AS $$
            BEGIN
                NOTIFY pgrst, 'reload schema';
            END;
            $$;
        """)
        print("   ✓ Function created")

        # Step 2: Execute the function to reload schema
        print("\n2. Executing reload_postgrest_schema_cache()...")
        cursor.execute("SELECT reload_postgrest_schema_cache();")
        print("   ✓ NOTIFY command sent to PostgREST")

        # Step 3: Fix reviewer is_active status
        print("\n3. Fixing reviewer is_active status...")
        cursor.execute("""
            UPDATE reviewers
            SET is_active = true
            WHERE phone_number = 'whatsapp:+919879687516';
        """)
        rows_updated = cursor.rowcount
        print(f"   ✓ Updated {rows_updated} reviewer(s)")

        # Step 4: Verify integration_tokens table exists
        print("\n4. Verifying integration_tokens table...")
        cursor.execute("""
            SELECT COUNT(*) FROM integration_tokens;
        """)
        count = cursor.fetchone()[0]
        print(f"   ✓ integration_tokens table exists with {count} row(s)")

        print("\n" + "=" * 60)
        print("SUCCESS! Schema cache reload complete.")
        print("=" * 60)
        print("\nPostgREST should now recognize the integration_tokens table.")
        print("Wait 2-3 seconds for PostgREST to process the NOTIFY.")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
        print("\nDisconnected from database.")


if __name__ == "__main__":
    main()
