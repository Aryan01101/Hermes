# Quick Connection Test Guide

## Simple 2-Minute Test

This test will verify all your services are working **without sending any actual emails or WhatsApp messages**.

---

## Step 1: Run the Connection Test

```bash
python test_connections.py
```

---

## Step 2: What You Should See

### ✅ All Services Working (Success Output):

```
============================================================
🚀 HERMES CONNECTION TEST
============================================================

🔍 Testing Database Connection...
✅ SUCCESS - Connected to Supabase database
   └─ Found 0 active reviewers

🔍 Testing Anthropic API...
✅ SUCCESS - Anthropic API working
   └─ Intent detected: question

🔍 Testing SendGrid API...
✅ SUCCESS - SendGrid API initialized
   └─ Configured to send from: aadhikari678@outlook.com

🔍 Testing Twilio WhatsApp API...
✅ SUCCESS - Twilio WhatsApp API initialized
   └─ Configured WhatsApp number: whatsapp:+14155238886

🔍 Testing LangGraph Workflow...
✅ SUCCESS - LangGraph workflow initialized
   └─ PostgresSaver checkpoint system ready

============================================================
📊 TEST SUMMARY
============================================================
✅ SUCCESS Database (Supabase)
✅ SUCCESS Anthropic API
✅ SUCCESS SendGrid Email
✅ SUCCESS Twilio WhatsApp
✅ SUCCESS LangGraph Workflow

✅ Passed: 5/5
❌ Failed: 0/5

🎉 All services are working correctly!

📝 Next steps:
   1. Start the server: uvicorn src.main:app --reload --port 8000
   2. Test webhooks using ngrok (see TESTING.md)
============================================================
```

---

## Step 3: Understand the Results

| Test | What It Checks |
|------|----------------|
| **Database** | Can connect to Supabase PostgreSQL |
| **Anthropic API** | Can call Claude API and extract intent |
| **SendGrid** | SendGrid client initializes with your API key |
| **Twilio WhatsApp** | Twilio client initializes with your credentials |
| **LangGraph Workflow** | PostgresSaver checkpoint system works |

---

## Common Issues and Fixes

### ❌ Database Connection Failed

**Error:** `connection refused` or `authentication failed`

**Fix:**
```bash
# Check your DATABASE_URL in .env
# Format should be:
DATABASE_URL=postgresql://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

### ❌ Anthropic API Failed

**Error:** `Invalid API key` or `401 Unauthorized`

**Fix:**
```bash
# Check your ANTHROPIC_API_KEY in .env
# Should start with: sk-ant-api03-
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### ❌ SendGrid Failed

**Error:** `Unauthorized` or `Invalid API key`

**Fix:**
```bash
# Check your SENDGRID_API_KEY in .env
# Should start with: SG.
SENDGRID_API_KEY=SG.xxxxx
```

### ❌ Twilio WhatsApp Failed

**Error:** `Authentication failed`

**Fix:**
```bash
# Check your Twilio credentials in .env
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

---

## What This Test Does NOT Do

- ✗ Send actual emails
- ✗ Send actual WhatsApp messages
- ✗ Modify your database
- ✗ Use up API credits (except 1 small Anthropic test call)

This is a **safe, read-only test** that just verifies connections work.

---

## Next Step: Test the Full Workflow

Once all 5 tests pass, you can test the complete email workflow:

1. **Start the server:**
   ```bash
   uvicorn src.main:app --reload --port 8000
   ```

2. **Expose it with ngrok:**
   ```bash
   ngrok http 8000
   ```

3. **Follow the complete test in `TESTING.md`**

---

## Troubleshooting

If any test fails:

1. Check the error message for details
2. Verify the corresponding credential in your `.env` file
3. Make sure there are no extra spaces or quotes around values
4. Ensure you're using the correct format for each credential

**Need help?** The error messages will tell you exactly which service failed and why.
