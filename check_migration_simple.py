"""Simple check for WhatsApp quota tracking migration using Supabase client."""

from src.core.config import get_settings
from supabase import create_client


def check_migration():
    """Check if the migration is complete using Supabase client."""
    settings = get_settings()

    print("🔍 Checking WhatsApp quota tracking migration...")
    print()

    try:
        # Create Supabase client
        client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_role_key,
        )

        # Try to query the whatsapp_quota_tracking table
        print("Checking if 'whatsapp_quota_tracking' table exists...")
        response = client.table("whatsapp_quota_tracking").select("*").limit(1).execute()

        print("✅ SUCCESS! Table 'whatsapp_quota_tracking' exists and is accessible")
        print()

        if response.data:
            print("📊 Current quota data:")
            for record in response.data:
                print(f"   - Date: {record.get('quota_date')}")
                print(f"   - Messages: {record.get('message_count')}/{record.get('daily_limit')}")
                print(f"   - Remaining: {record.get('daily_limit', 0) - record.get('message_count', 0)}")
        else:
            print("ℹ️  No quota records yet (will be created automatically on first message)")

        print()
        print("=" * 60)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 60)
        print()
        print("Your database is ready. The quota tracking will activate")
        print("automatically when the first WhatsApp message is sent.")
        return True

    except Exception as e:
        error_msg = str(e)
        print(f"❌ MIGRATION NOT COMPLETE")
        print()
        print(f"Error: {error_msg}")
        print()

        if "relation" in error_msg.lower() or "does not exist" in error_msg.lower():
            print("The table doesn't exist yet. You need to:")
            print()
            print("1. Go to Supabase Dashboard → SQL Editor")
            print("2. Open migrations/004_whatsapp_quota_tracking.sql")
            print("3. Copy and paste the entire SQL into the editor")
            print("4. Click 'Run' to execute")
            print()
        else:
            print("Unexpected error. Please check:")
            print("- SUPABASE_URL is correct in .env")
            print("- SUPABASE_SERVICE_ROLE_KEY is correct in .env")
            print("- Your Supabase project is accessible")

        return False


if __name__ == "__main__":
    check_migration()
