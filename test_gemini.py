"""Quick test for Gemini API integration."""

import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

print("=" * 60)
print("🧪 GEMINI API TEST")
print("=" * 60)

# Get API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("\n❌ ERROR: GEMINI_API_KEY not found in .env")
    print("\n📝 To get a Gemini API key:")
    print("   1. Visit: https://makersuite.google.com/app/apikey")
    print("   2. Click 'Create API key'")
    print("   3. Add to .env: GEMINI_API_KEY=your-key-here")
    exit(1)

print(f"\n🔑 API Key found: {api_key[:20]}...")

# Configure Gemini
genai.configure(api_key=api_key)

# Test with a simple prompt
print("\n🧠 Testing Gemini 1.5 Flash...")
try:
    model = genai.GenerativeModel('gemini-3.6-flash')
    response = model.generate_content("Say hello and confirm you're working!")

    print(f"✅ SUCCESS!")
    print(f"\n📝 Response:")
    print(f"   {response.text}")

    print("\n" + "=" * 60)
    print("🎉 GEMINI IS WORKING!")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\n💡 Check:")
    print("   1. API key is correct")
    print("   2. You have API quota remaining")
    print("   3. Internet connection is working")
    exit(1)
