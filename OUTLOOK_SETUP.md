# Outlook inbox setup

Hermes reads a personal Outlook.com Inbox through Microsoft Graph using delegated
access. It polls unread messages every 60 seconds, marks a message read only after
Hermes processes it successfully, and keeps refreshed OAuth tokens in Supabase.

## 1. Register the Microsoft app

1. Sign in to the [Microsoft Entra admin center](https://entra.microsoft.com/).
2. Open **App registrations** → **New registration** and name it `Hermes`.
3. Choose **Personal Microsoft accounts only** and select **Register**.
4. Copy the **Application (client) ID**.
5. Open **Authentication** and enable **Allow public client flows**.
6. Open **API permissions** → **Add a permission** → **Microsoft Graph** →
   **Delegated permissions**, then add `Mail.ReadWrite` and `User.Read`.

`Mail.ReadWrite` is required because Hermes marks an email read after processing;
it does not use Microsoft Graph to send email.

## 2. Create the Supabase token table

In Supabase, open **SQL Editor**, paste the contents of
`migrations/002_outlook_integration_tokens.sql`, and run it once.

## 3. Authorize the Outlook mailbox

Add the client ID to your local `.env` without committing it:

```text
OUTLOOK_CLIENT_ID=<Application client ID>
```

Install the updated dependencies, then run:

```bash
python scripts/authorize_outlook.py
```

Open the displayed Microsoft URL, enter the one-time code, and sign in as
`aadhikari678@outlook.com`. Copy the resulting `OUTLOOK_TOKEN_CACHE` value.

## 4. Configure Railway

In Railway → Hermes → Variables, add:

```text
OUTLOOK_POLLING_ENABLED=true
OUTLOOK_CLIENT_ID=<Application client ID>
OUTLOOK_TOKEN_CACHE=<value printed by authorize_outlook.py>
OUTLOOK_POLL_INTERVAL_SECONDS=60
```

Redeploy the service. After the first successful token refresh, Hermes stores the
refreshed cache in Supabase; keep the Railway cache value as a recovery seed.

## 5. Test

Send a test email from a different mailbox to `aadhikari678@outlook.com`. Within
one minute, Railway logs should show an Outlook message being processed and a
WhatsApp draft should reach the active reviewer.
