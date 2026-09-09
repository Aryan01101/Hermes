"""Test and validate Gmail OAuth token from Railway."""

import base64
import json
import sys
from datetime import datetime

# Railway's GMAIL_TOKEN_CACHE
RAILWAY_TOKEN = "eyJ0b2tlbiI6ICJ5YTI5LmEwQWRNRDZFaHd5UUo3LWRteEd1Um5aVnJabkJZcU94ZlpXQVQxUm9XVlVlTGQwSV9HQ283OW80YTRQWlpCVThMQmtLSENubHpZb0hkc2hwUDRlQzllSUcyRmt1WU1JZU1tdXRoQUtQZXNvTHZJYWZvXzlRQ0QwTjVTOGprNlRURk9HTFVFV2RsNllyejZ2bUFqUC0wSUpWZWpLbjZkT2RHbjJ1YlNRVzYyeS16cTRYLW1uck80VHMwZGlsQXdVMDVNMlVGNFlGY2FDZ1lLQVlNU0FSRVNGUUhHWDJNaWR1OVZycExNTlhFNzJpdlVOVm50TUEwMjA2IiwgInJlZnJlc2hfdG9rZW4iOiAiMS8vMGdBZjZjT2kzXzNkVENnWUlBUkFBR0JBU053Ri1MOUlyeWF2SW9XcWdRN1lWaVIydkFGRHVUMG55SEgzeXBEeWtpanRzaTR3RjhQbFFud3JYLV9QZS1fbFdZbEVpVnZMQVZzUSIsICJ0b2tlbl91cmkiOiAiaHR0cHM6Ly9vYXV0aDIuZ29vZ2xlYXBpcy5jb20vdG9rZW4iLCAiY2xpZW50X2lkIjogIjY0MTA5MzQ1NjY1NC11bjBjc2JzNnB1MG8zOWtvMDQ5ZHJzdmpqMWZlb25lOS5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbSIsICJjbGllbnRfc2VjcmV0IjogIkdPQ1NQWC11a0xXeDRlYU8wcUFMcExzUTdxcmlNZlZ5WkRFIiwgInNjb3BlcyI6IFsiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vYXV0aC9nbWFpbC5tb2RpZnkiXSwgInVuaXZlcnNlX2RvbWFpbiI6ICJnb29nbGVhcGlzLmNvbSIsICJhY2NvdW50IjogIiIsICJleHBpcnkiOiAiMjAyNi0wOS0wOVQxODo0MjowNVoifQ=="

print("=" * 80)
print("GMAIL TOKEN VALIDATION TEST")
print("=" * 80)

# Decode the token
print("\n1. Decoding GMAIL_TOKEN_CACHE from Railway...")
try:
    decoded_bytes = base64.b64decode(RAILWAY_TOKEN)
    decoded_str = decoded_bytes.decode("utf-8")
    credentials = json.loads(decoded_str)
    print("✅ Token decoded successfully")
except Exception as e:
    print(f"❌ Failed to decode token: {e}")
    sys.exit(1)

# Display token structure
print("\n2. Token Structure:")
print(f"   - Has access token: {'token' in credentials}")
print(f"   - Has refresh token: {'refresh_token' in credentials}")
print(f"   - Client ID: {credentials.get('client_id', 'MISSING')[:30]}...")
print(f"   - Scopes: {credentials.get('scopes', 'MISSING')}")

# Check expiry
print("\n3. Token Expiry Check:")
if "expiry" in credentials:
    expiry_str = credentials["expiry"]
    print(f"   - Expiry timestamp: {expiry_str}")

    # Parse the expiry
    try:
        expiry_dt = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
        now = datetime.now(expiry_dt.tzinfo)

        if now > expiry_dt:
            print(f"   ❌ TOKEN IS EXPIRED (expired {(now - expiry_dt).total_seconds() / 3600:.1f} hours ago)")
            print(f"   - Expired at: {expiry_dt}")
            print(f"   - Current time: {now}")
        else:
            print(f"   ✅ Token is still valid (expires in {(expiry_dt - now).total_seconds() / 3600:.1f} hours)")
    except Exception as e:
        print(f"   ⚠️  Could not parse expiry: {e}")
else:
    print("   ⚠️  No expiry field in token")

# Test with Google API
print("\n4. Testing Gmail API Access...")
try:
    import httpx
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    # Create credentials
    creds = Credentials.from_authorized_user_info(credentials, ["https://www.googleapis.com/auth/gmail.modify"])

    # Check if valid
    print(f"   - Credentials valid: {creds.valid}")
    print(f"   - Credentials expired: {creds.expired}")

    # Try to refresh if needed
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print("   - Attempting to refresh token...")
            creds.refresh(Request())
            print("   ✅ Token refreshed successfully")
            print(f"   - New expiry: {creds.expiry}")
        else:
            print("   ❌ Cannot refresh - no refresh token or not expired")

    # Make a test API call
    print("\n   - Making test API call to Gmail...")
    import asyncio

    async def test_gmail_api():
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {creds.token}"}
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params={"q": "in:inbox is:unread", "maxResults": "1"}
            )
            print(f"   - Response status: {response.status_code}")

            if response.status_code == 200:
                print("   ✅ Gmail API access successful!")
                data = response.json()
                print(f"   - Found {len(data.get('messages', []))} unread message(s)")
            elif response.status_code == 403:
                print("   ❌ Gmail API returned 403 Forbidden")
                print(f"   - Response: {response.text}")

                # Parse error
                try:
                    error_data = response.json()
                    print(f"   - Error details: {json.dumps(error_data, indent=2)}")
                except:
                    pass
            else:
                print(f"   ❌ Gmail API returned {response.status_code}")
                print(f"   - Response: {response.text}")

    asyncio.run(test_gmail_api())

except ImportError as e:
    print(f"   ⚠️  Missing dependencies: {e}")
    print("   Run: pip install google-auth httpx")
except Exception as e:
    print(f"   ❌ API test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
