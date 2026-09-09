"""Update reviewer phone number to the correct WhatsApp number."""

import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def update_reviewer_phone():
    """Update the reviewer's phone number in the database."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        sys.exit(1)

    print("=" * 80)
    print("UPDATING REVIEWER PHONE NUMBER")
    print("=" * 80)

    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")

        # Check current reviewers
        reviewers = await conn.fetch(
            """
            SELECT id, name, phone_number, active
            FROM reviewers
            ORDER BY created_at DESC
            """
        )

        print(f"\n📋 Current reviewers ({len(reviewers)}):")
        for r in reviewers:
            print(
                f"   - ID: {r['id']}, Name: {r['name']}, Phone: {r['phone_number']}, Active: {r['active']}"
            )

        # Update to the correct WhatsApp number
        new_phone = "whatsapp:+918796887516"

        print(f"\n🔧 Updating phone number to: {new_phone}")

        # Update all active reviewers to the correct number
        result = await conn.execute(
            """
            UPDATE reviewers
            SET phone_number = $1
            WHERE active = true
            """,
            new_phone,
        )

        print(f"✅ Updated {result.split()[-1]} reviewer(s)")

        # Verify the update
        updated_reviewers = await conn.fetch(
            """
            SELECT id, name, phone_number, active
            FROM reviewers
            WHERE active = true
            """
        )

        print(f"\n✅ Active reviewers after update:")
        for r in updated_reviewers:
            print(f"   - {r['name']}: {r['phone_number']}")

        await conn.close()
        print("\n✅ Database update complete!")
        print("\nNext email will be sent to the correct WhatsApp number.")

    except Exception as e:
        print(f"\n❌ Update failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(update_reviewer_phone())
