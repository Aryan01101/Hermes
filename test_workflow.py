"""End-to-end workflow test for Hermes v2."""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

# Import services
import sys
sys.path.insert(0, os.path.dirname(__file__))

from src.services.llm import LLMService
from src.services.email import EmailService
from src.services.whatsapp import WhatsAppService

load_dotenv()

print("=" * 80)
print("🧪 HERMES v2 - END-TO-END WORKFLOW TEST")
print("=" * 80)

# Initialize services
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

async def test_workflow():
    """Test the complete email triage workflow."""

    # =========================================================================
    # Step 1: Simulate Email Intake
    # =========================================================================
    print("\n📧 STEP 1: Email Intake")
    print("-" * 80)

    # Create a test email thread
    test_email = {
        "customer_email": "customer@example.com",
        "subject": "Question about my order #12345",
        "message_id": f"<test-{datetime.utcnow().timestamp()}@hermes.test>",
        "in_reply_to": None,
        "references": []
    }

    print(f"📩 Creating test thread...")
    print(f"   From: {test_email['customer_email']}")
    print(f"   Subject: {test_email['subject']}")

    thread_result = supabase.table("threads").insert(test_email).execute()
    thread = thread_result.data[0]
    thread_id = thread['id']

    print(f"✅ Thread created: {thread_id}")

    # =========================================================================
    # Step 2: Intent Extraction
    # =========================================================================
    print("\n🧠 STEP 2: Intent Extraction (using Gemini)")
    print("-" * 80)

    llm_service = LLMService()

    test_body = """
    Hi there,

    I ordered a blue t-shirt (order #12345) last week but haven't received
    a shipping confirmation yet. Can you let me know when it will ship?

    Thanks!
    """

    print(f"📝 Extracting intent from email body...")

    intent_result = await llm_service.extract_intent(
        email_body=test_body,
        subject=test_email['subject']
    )

    if intent_result['success']:
        intent = intent_result['intent']
        print(f"✅ Intent extracted:")
        print(f"   Category: {intent.get('category', 'N/A')}")
        print(f"   Urgency: {intent.get('urgency', 'N/A')}")
        print(f"   Summary: {intent.get('summary', 'N/A')[:80]}...")
    else:
        print(f"❌ Intent extraction failed: {intent_result.get('error')}")
        return

    # =========================================================================
    # Step 3: Draft Generation
    # =========================================================================
    print("\n✍️  STEP 3: Draft Generation")
    print("-" * 80)

    print(f"📝 Generating reply draft...")

    draft_result = await llm_service.draft_reply(
        email_body=test_body,
        subject=test_email['subject'],
        intent_data=intent
    )

    if draft_result['success']:
        draft = draft_result['draft']
        draft_content = draft['content']
        confidence_score = draft.get('confidence', 0.0)

        print(f"✅ Draft generated (confidence: {confidence_score:.2f}):")
        print(f"\n{'-' * 40}")
        print(draft_content[:200] + "..." if len(draft_content) > 200 else draft_content)
        print(f"{'-' * 40}\n")

        # Save draft to database
        draft_data = {
            "thread_id": thread_id,
            "version_number": 1,
            "content": draft_content,
            "confidence_score": confidence_score,
            "status": "pending"
        }

        draft_db_result = supabase.table("drafts").insert(draft_data).execute()
        draft = draft_db_result.data[0]
        draft_id = draft['id']

        print(f"💾 Draft saved to database: {draft_id}")
    else:
        print(f"❌ Draft generation failed: {draft_result.get('error')}")
        return

    # =========================================================================
    # Step 4: WhatsApp Notification
    # =========================================================================
    print("\n📱 STEP 4: WhatsApp Notification to Reviewer")
    print("-" * 80)

    # Get active reviewer
    reviewers_result = supabase.table("reviewers").select("*").eq("active", True).execute()

    if not reviewers_result.data:
        print("⚠️  No active reviewers found - skipping WhatsApp notification")
        print("   (This is expected in test environment)")
    else:
        reviewer = reviewers_result.data[0]
        print(f"👤 Found reviewer: {reviewer['name']} ({reviewer['phone_number']})")

        whatsapp_service = WhatsAppService()

        print(f"📤 Sending WhatsApp notification...")
        print(f"   To: {reviewer['phone_number']}")

        try:
            # Remove 'whatsapp:' prefix for send_draft_for_review (it adds it back)
            phone = reviewer['phone_number'].replace('whatsapp:', '')

            message_result = await whatsapp_service.send_draft_for_review(
                reviewer_phone=phone,
                customer_email=test_email['customer_email'],
                subject=test_email['subject'],
                draft_content=draft_content,
                confidence_score=confidence_score,
                thread_id=thread_id,
                draft_id=draft_id
            )

            if message_result['success']:
                message_sid = message_result['message_sid']
                print(f"✅ WhatsApp sent: {message_sid}")

                # Update draft with WhatsApp SID
                supabase.table("drafts").update({
                    "whatsapp_message_sid": message_sid
                }).eq("id", draft_id).execute()

                print(f"💾 Draft updated with WhatsApp SID")

            else:
                print(f"❌ WhatsApp send failed: {message_result.get('error')}")

        except Exception as e:
            print(f"❌ WhatsApp error: {e}")
            print("   (This is expected if Twilio sandbox number hasn't been verified)")

    # =========================================================================
    # Step 5: Workflow Status
    # =========================================================================
    print("\n📊 WORKFLOW STATUS")
    print("-" * 80)

    print(f"✅ Thread created: {thread_id}")
    print(f"✅ Intent extracted: {intent.get('category', 'N/A')}")
    print(f"✅ Draft generated: {draft_id}")
    print(f"✅ Confidence score: {confidence_score:.2%}")

    # Log audit event
    audit_data = {
        "event_type": "draft_generated",
        "thread_id": thread_id,
        "draft_id": draft_id,
        "actor": "system",
        "details": {
            "test": True,
            "confidence_score": confidence_score,
            "intent_category": intent.get('category')
        }
    }

    supabase.table("audit_log").insert(audit_data).execute()
    print(f"✅ Audit log updated")

    print("\n" + "=" * 80)
    print("🎉 END-TO-END WORKFLOW TEST COMPLETED!")
    print("=" * 80)
    print("\n💡 Next Steps:")
    print("   1. Check Supabase dashboard to see the created records")
    print("   2. Verify WhatsApp message was received (if phone verified)")
    print("   3. Test reviewer actions: APPROVE, FEEDBACK, REJECT")
    print("   4. Test the complete LangGraph workflow with human-in-the-loop")
    print()

if __name__ == "__main__":
    asyncio.run(test_workflow())
