"""Test which Anthropic models are available with this API key."""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

# Get API key
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("❌ No ANTHROPIC_API_KEY found")
    exit(1)

print(f"🔑 Testing API key: {api_key[:20]}...")
print("=" * 60)

# Models to test
models = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "claude-3-5-sonnet",  # No date
    "claude-3-opus",
    "claude-3-sonnet",
    "claude-3-haiku",
]

client = Anthropic(api_key=api_key)

for model in models:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"✅ {model:35} - SUCCESS")
        print(f"   Response: {response.content[0].text}")
        break  # Found a working model!
    except Exception as e:
        error_msg = str(e)
        if "not_found_error" in error_msg:
            print(f"❌ {model:35} - NOT FOUND")
        elif "authentication" in error_msg:
            print(f"🔒 {model:35} - AUTH ERROR")
            break  # API key is invalid
        else:
            print(f"⚠️  {model:35} - ERROR: {error_msg[:50]}")

print("=" * 60)
