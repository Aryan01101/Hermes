"""Authorize a personal Gmail inbox and print credentials for Railway."""

import argparse
import base64
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

parser = argparse.ArgumentParser(
    description="Authorize Gmail using a downloaded Google OAuth desktop-client JSON file."
)
parser.add_argument("client_secret_file", help="Path to the downloaded OAuth client JSON")
args = parser.parse_args()

try:
    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret_file, GMAIL_SCOPES)
except OSError as exc:
    sys.exit(f"Could not read the OAuth client file: {exc}")

credentials = flow.run_local_server(port=0, prompt="consent")
if not credentials.refresh_token:
    sys.exit("Google did not return a refresh token. Revoke Hermes access and try again.")

encoded_credentials = base64.b64encode(credentials.to_json().encode("utf-8")).decode("ascii")
print("\nAuthorization succeeded. Add this value to Railway as GMAIL_TOKEN_CACHE:")
print(encoded_credentials)
