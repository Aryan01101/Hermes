"""Simple connection test script to verify all services are working.

Run this to quickly verify:
- Database connection (Supabase)
- Anthropic API
- SendGrid API
- Twilio WhatsApp
"""

import asyncio
import os
from typing import Dict

# Import services
from src.core.config import get_settings
from src.services.database import get_database
from src.services.llm import get_llm_service
from src.services.email import get_email_service
from src.services.whatsapp import get_whatsapp_service


async def test_database_connection() -> Dict:
    """Test Supabase database connection."""
    print("\n🔍 Testing Database Connection...")
    try:
        db = get_database()
        # Simple query to verify connection
        settings = get_settings()

        # Test connection by trying to get active reviewers
        reviewers = await db.get_active_reviewers()

        return {
            "status": "✅ SUCCESS",
            "message": f"Connected to Supabase database",
            "details": f"Found {len(reviewers)} active reviewers"
        }
    except Exception as e:
        return {
            "status": "❌ FAILED",
            "message": "Database connection failed",
            "error": str(e)
        }


async def test_anthropic_api() -> Dict:
    """Test Anthropic Claude API."""
    print("\n🔍 Testing Anthropic API...")
    try:
        llm = get_llm_service()

        # Simple test: extract intent from sample email
        result = await llm.extract_intent(
            email_body="Hello, I have a question about my order.",
            subject="Order inquiry"
        )

        if result["success"]:
            return {
                "status": "✅ SUCCESS",
                "message": "Anthropic API working",
                "details": f"Intent detected: {result['intent'].get('intent', 'N/A')}"
            }
        else:
            return {
                "status": "❌ FAILED",
                "message": "Anthropic API call failed",
                "error": result.get("error")
            }
    except Exception as e:
        return {
            "status": "❌ FAILED",
            "message": "Anthropic API connection failed",
            "error": str(e)
        }


async def test_sendgrid_api() -> Dict:
    """Test SendGrid email API (without actually sending)."""
    print("\n🔍 Testing SendGrid API...")
    try:
        email_service = get_email_service()
        settings = get_settings()

        # Verify SendGrid client can be initialized
        if email_service.client:
            return {
                "status": "✅ SUCCESS",
                "message": "SendGrid API initialized",
                "details": f"Configured to send from: {settings.from_email}"
            }
        else:
            return {
                "status": "❌ FAILED",
                "message": "SendGrid client not initialized"
            }
    except Exception as e:
        return {
            "status": "❌ FAILED",
            "message": "SendGrid API connection failed",
            "error": str(e)
        }


async def test_twilio_whatsapp() -> Dict:
    """Test Twilio WhatsApp API (without actually sending)."""
    print("\n🔍 Testing Twilio WhatsApp API...")
    try:
        whatsapp_service = get_whatsapp_service()
        settings = get_settings()

        # Verify Twilio client can be initialized
        if whatsapp_service.client:
            return {
                "status": "✅ SUCCESS",
                "message": "Twilio WhatsApp API initialized",
                "details": f"Configured WhatsApp number: {settings.twilio_whatsapp_number}"
            }
        else:
            return {
                "status": "❌ FAILED",
                "message": "Twilio client not initialized"
            }
    except Exception as e:
        return {
            "status": "❌ FAILED",
            "message": "Twilio WhatsApp connection failed",
            "error": str(e)
        }


async def test_workflow_graph() -> Dict:
    """Test that LangGraph workflow can be initialized."""
    print("\n🔍 Testing LangGraph Workflow...")
    try:
        from src.workflows.graph import get_workflow_graph

        # Try to get workflow graph (will initialize PostgresSaver)
        graph = get_workflow_graph()

        if graph:
            return {
                "status": "✅ SUCCESS",
                "message": "LangGraph workflow initialized",
                "details": "PostgresSaver checkpoint system ready"
            }
        else:
            return {
                "status": "❌ FAILED",
                "message": "Workflow graph initialization failed"
            }
    except Exception as e:
        return {
            "status": "❌ FAILED",
            "message": "LangGraph workflow failed",
            "error": str(e)
        }


async def run_all_tests():
    """Run all connection tests."""
    print("=" * 60)
    print("🚀 HERMES CONNECTION TEST")
    print("=" * 60)

    results = []

    # Test 1: Database
    db_result = await test_database_connection()
    results.append(("Database (Supabase)", db_result))
    print(f"{db_result['status']} - {db_result['message']}")
    if 'details' in db_result:
        print(f"   └─ {db_result['details']}")
    if 'error' in db_result:
        print(f"   └─ Error: {db_result['error']}")

    # Test 2: Anthropic
    anthropic_result = await test_anthropic_api()
    results.append(("Anthropic API", anthropic_result))
    print(f"{anthropic_result['status']} - {anthropic_result['message']}")
    if 'details' in anthropic_result:
        print(f"   └─ {anthropic_result['details']}")
    if 'error' in anthropic_result:
        print(f"   └─ Error: {anthropic_result['error']}")

    # Test 3: SendGrid
    sendgrid_result = await test_sendgrid_api()
    results.append(("SendGrid Email", sendgrid_result))
    print(f"{sendgrid_result['status']} - {sendgrid_result['message']}")
    if 'details' in sendgrid_result:
        print(f"   └─ {sendgrid_result['details']}")
    if 'error' in sendgrid_result:
        print(f"   └─ Error: {sendgrid_result['error']}")

    # Test 4: Twilio WhatsApp
    twilio_result = await test_twilio_whatsapp()
    results.append(("Twilio WhatsApp", twilio_result))
    print(f"{twilio_result['status']} - {twilio_result['message']}")
    if 'details' in twilio_result:
        print(f"   └─ {twilio_result['details']}")
    if 'error' in twilio_result:
        print(f"   └─ Error: {twilio_result['error']}")

    # Test 5: Workflow Graph
    workflow_result = await test_workflow_graph()
    results.append(("LangGraph Workflow", workflow_result))
    print(f"{workflow_result['status']} - {workflow_result['message']}")
    if 'details' in workflow_result:
        print(f"   └─ {workflow_result['details']}")
    if 'error' in workflow_result:
        print(f"   └─ Error: {workflow_result['error']}")

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if "SUCCESS" in result['status'])
    total = len(results)

    for service, result in results:
        print(f"{result['status']} {service}")

    print(f"\n✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 All services are working correctly!")
        print("\n📝 Next steps:")
        print("   1. Start the server: uvicorn src.main:app --reload --port 8000")
        print("   2. Test webhooks using ngrok (see TESTING.md)")
    else:
        print("\n⚠️  Some services failed. Please check the errors above.")
        print("   Review your .env file and ensure all credentials are correct.")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
