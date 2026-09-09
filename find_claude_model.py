"""Find which Claude model names work with this API key."""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key)

print("=" * 60)
print("🔍 FINDING WORKING CLAUDE MODEL")
print("=" * 60)

# Try model patterns for 2026
models_to_try = [
    # Latest aliases
    "claude-sonnet-latest",
    "claude-opus-latest",
    "claude-haiku-latest",

    # Dated versions (2025-2026 likely formats)
    "claude-sonnet-4-20260101",
    "claude-sonnet-4",
    "claude-4-sonnet",
    "claude-3.7-sonnet",
    "claude-3.6-sonnet",
    "claude-3.5-sonnet-20250320",

    # Older stable versions
    "claude-3-5-sonnet-20241022",
    "claude-3-opus-20240229",
]

for model in models_to_try:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"\n✅ FOUND WORKING MODEL: {model}")
        print(f"   Response: {response.content[0].text}")
        print(f"\n{'=' * 60}")
        print(f"🎉 Use this model: {model}")
        print(f"{'=' * 60}")
        break
    except Exception as e:
        error = str(e)
        if "not_found_error" in error:
            print(f"❌ {model:40} - NOT FOUND")
        elif "overloaded" in error:
            print(f"⏳ {model:40} - OVERLOADED (exists!)")
        else:
            print(f"⚠️  {model:40} - {error[:50]}")
