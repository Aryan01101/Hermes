# Gmail inbox setup

Hermes reads a personal Gmail Inbox through delegated Gmail API access. It polls
unread Inbox messages every 60 seconds, removes the `UNREAD` label only after a
message is processed successfully, and keeps refreshed OAuth credentials in
Supabase. No custom domain, forwarding rule, or Google Workspace subscription is
required.

## 1. Create Google OAuth credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/), create a
   project named `Hermes`, and select it.
2. Open **APIs & Services** → **Library**, search for **Gmail API**, and select
   **Enable**.
3. Open **Google Auth platform**. Complete **Branding** using your Gmail address
   as the support and contact email.
4. Under **Audience**, select **External**, then add the Gmail account Hermes
   should read as a **Test user**. Keeping the app in Testing is fine when only
   your own account uses it. Google expires refresh tokens for external apps in
   Testing after seven days, so re-run authorization then. For a long-running
   inbox, publish and complete Google's required verification for the Gmail
   scope.
5. Under **Data Access**, add the Gmail API scope
   `https://www.googleapis.com/auth/gmail.modify`.
6. Open **Clients** → **Create client** → choose **Desktop app**. Download the
   resulting JSON file and keep it outside this repository.

## 2. Authorize the Gmail mailbox locally

Install the updated dependencies, then run this command with the downloaded file:

```bash
python scripts/authorize_gmail.py /path/to/client_secret.json
```

Your browser opens Google's consent screen. Sign in to the Gmail mailbox Hermes
should read and approve the requested access. Copy the resulting
`GMAIL_TOKEN_CACHE` value. It contains a refresh token, so do not commit it or
share it in chat.

## 3. Configure Railway

The existing `integration_tokens` table from
`migrations/002_outlook_integration_tokens.sql` is also used for Gmail. If you
have not run that migration yet, run it in Supabase SQL Editor first.

In Railway → Hermes → Variables, add:

```text
GMAIL_POLLING_ENABLED=true
GMAIL_TOKEN_CACHE=<value printed by authorize_gmail.py>
GMAIL_POLL_INTERVAL_SECONDS=60
```

Keep `OUTLOOK_POLLING_ENABLED=false` while testing Gmail so only one mailbox is
being monitored. Railway redeploys after you save the variables.

## 4. Test

Mark old unread mail as read if you do not want Hermes to process it, then send a
new message from a different mailbox to the connected Gmail address. Within one
minute, Railway logs should show a Gmail message being processed and the active
reviewer should receive the WhatsApp draft.
