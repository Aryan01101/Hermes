"""Create the initial Microsoft Graph token cache for a personal Outlook inbox."""

import base64
import os
import sys

import msal
from dotenv import load_dotenv

load_dotenv(".env")

client_id = os.getenv("OUTLOOK_CLIENT_ID")
if not client_id:
    sys.exit("OUTLOOK_CLIENT_ID is required in .env before authorizing Outlook.")

token_cache = msal.SerializableTokenCache()
app = msal.PublicClientApplication(
    client_id,
    authority="https://login.microsoftonline.com/consumers",
    token_cache=token_cache,
)
flow = app.initiate_device_flow(scopes=["Mail.ReadWrite", "User.Read", "offline_access"])
if "user_code" not in flow:
    sys.exit(f"Could not start Microsoft device authorization: {flow}")

print(f"Open {flow['verification_uri']} and enter code: {flow['user_code']}")
print("Sign in as the Outlook mailbox Hermes should read, then return here.")
result = app.acquire_token_by_device_flow(flow)

if "access_token" not in result:
    sys.exit(f"Microsoft authorization failed: {result.get('error_description', result)}")

encoded_cache = base64.b64encode(token_cache.serialize().encode("utf-8")).decode("ascii")
print("\nAuthorization succeeded. Add this value to Railway as OUTLOOK_TOKEN_CACHE:")
print(encoded_cache)
