"""Add a test reviewer to the database."""

import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

print("=" * 60)
print("➕ ADDING TEST REVIEWER")
print("=" * 60)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

# Test reviewer data (matching actual schema: phone_number, name, active)
test_reviewer = {
    "phone_number": "whatsapp:+1234567890",  # Must match Twilio WhatsApp format
    "name": "Test Reviewer",
    "active": True
}

try:
    # Insert the reviewer
    result = supabase.table("reviewers").insert(test_reviewer).execute()

    if result.data:
        reviewer = result.data[0]
        print(f"\n✅ SUCCESS - Test reviewer added!")
        print(f"   ID: {reviewer['id']}")
        print(f"   Name: {reviewer['name']}")
        print(f"   Phone: {reviewer['phone_number']}")
        print(f"   Active: {reviewer['active']}")

        # Verify by querying active reviewers
        print("\n🔍 Verifying active reviewers in database...")
        active = supabase.table("reviewers").select("*").eq("active", True).execute()
        print(f"   Total active reviewers: {len(active.data)}")

    else:
        print("\n⚠️  WARNING - No data returned from insert")

except Exception as e:
    print(f"\n❌ ERROR - Failed to add reviewer: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
