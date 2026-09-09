"""Check Anthropic API status and available features."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

print("=" * 60)
print("🔍 ANTHROPIC API STATUS CHECK")
print("=" * 60)
print(f"\nAPI Key: {api_key[:20]}...")

# Try a simple request
response = requests.post(
    "https://api.anthropic.com/v1/messages",
    headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
    json={
        "model": "claude-3-opus-20240229",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "Hi"}]
    }
)

print(f"\nStatus Code: {response.status_code}")
print(f"Response: {response.text[:500]}")

if response.status_code == 401:
    print("\n❌ AUTHENTICATION FAILED - API key is invalid or expired")
elif response.status_code == 404:
    print("\n⚠️  MODEL NOT FOUND - This is expected (we're testing)")
    print("   But at least the API key is being accepted!")
elif response.status_code == 200:
    print("\n✅ SUCCESS - API key and model both work!")
