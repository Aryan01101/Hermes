# Hermes Testing Setup - Step-by-Step Guide

This guide will walk you through setting up all the credentials needed for testing Hermes v2.

**Estimated time:** 30-45 minutes
**Estimated cost:** $0-5 (mostly free tiers)

---

## Step 1: Database (Supabase) - 10 minutes

### Why: Store threads, drafts, and events

### Instructions:

1. **Go to** [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. **Sign up** with GitHub or email (free tier available)
3. **Create new project:**
   - Name: `hermes-test`
   - Database password: Choose a strong password (save it!)
   - Region: Choose closest to you
   - Wait 2-3 minutes for project to initialize
4. **Get credentials:**
   - Click on "Settings" (gear icon) in left sidebar
   - Go to **API** section:
     - Copy `Project URL` → This is your `SUPABASE_URL`
     - Scroll down to "Project API keys"
     - Copy `service_role` key (NOT anon key) → This is your `SUPABASE_SERVICE_ROLE_KEY`
   - Go to **Database** section:
     - Scroll to "Connection string" section
     - Select "URI" tab
     - Copy the connection string → This is your `DATABASE_URL`
     - Replace `[YOUR-PASSWORD]` in the string with your actual database password

5. **Update .env.test:**
   ```bash
   SUPABASE_URL=https://yourproject.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
   DATABASE_URL=postgresql://postgres.yourproject:[password]@...
   ```

---

## Step 2: Claude API (Anthropic) - 5 minutes

### Why: Generate draft email responses

### Instructions:

1. **Go to** [https://console.anthropic.com/](https://console.anthropic.com/)
2. **Sign up** with email
3. **Verify email** (check your inbox)
4. **Add payment method** (required even for free $5 credit)
   - Go to "Billing" section
   - Add credit card (won't be charged immediately)
   - You get $5 free credit to start
5. **Create API Key:**
   - Go to "API Keys" section
   - Click "Create Key"
   - Name: `Hermes Test`
   - Copy key (starts with `sk-ant-`) → **Save immediately, you won't see it again!**

6. **Update .env.test:**
   ```bash
   ANTHROPIC_API_KEY=sk-ant-api03-xxx...
   ```

**Cost estimate:** ~$0.01-0.05 per email draft (~$1 for 100 test emails)

---

## Step 3: Email Service (SendGrid) - 10 minutes

### Why: Send emails to customers

### Instructions:

1. **Go to** [https://signup.sendgrid.com/](https://signup.sendgrid.com/)
2. **Sign up** (Free tier: 100 emails/day forever)
3. **Verify email address**
4. **Complete onboarding questions** (select "Transactional" email type)
5. **Create API Key:**
   - Go to Settings > **API Keys**
   - Click "Create API Key"
   - Name: `Hermes Test`
   - Permissions: Select **Full Access**
   - Click "Create & View"
   - Copy key (starts with `SG.`) → **Save immediately!**

6. **Verify Sender Email** (CRITICAL STEP):
   - Go to Settings > **Sender Authentication**
   - Click "Verify a Single Sender"
   - Fill in:
     - From Name: Your name or company name
     - From Email: **Your real email address** (e.g., yourname@gmail.com)
     - Reply To: Same as From Email
     - Company details (can use personal info)
   - Click "Create"
   - **Check your email inbox** and click verification link
   - Wait for "Verified" status (usually instant)

7. **Update .env.test:**
   ```bash
   SENDGRID_API_KEY=SG.xxx...
   INTAKE_EMAIL_ADDRESS=support@yourdomain.com  # Can be any email for testing
   FROM_EMAIL=yourname@gmail.com  # MUST be the verified email
   FROM_NAME=Your Name
   ```

**Important:** `FROM_EMAIL` must exactly match the verified sender email!

---

## Step 4: WhatsApp (Twilio) - 15 minutes

### Why: Send approval notifications to reviewers

### Instructions:

1. **Go to** [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio)
2. **Sign up** (Free trial: $15 credit)
3. **Verify phone number** (they'll send verification code)
4. **Complete onboarding** (skip the "build your first app" tutorial)
5. **Get Account Credentials:**
   - On dashboard, find **Account Info** panel
   - Copy `Account SID` (starts with `AC`)
   - Copy `Auth Token` (click to reveal)

6. **Set up WhatsApp Sandbox:**
   - In left sidebar: Messaging > **Try it out** > **Send a WhatsApp message**
   - You'll see instructions like: "Send 'join \<code\>' to +1 415 523 8886"
   - **On your phone:**
     - Open WhatsApp
     - Start new chat with **+1 415 523 8886**
     - Send the message: `join your-sandbox-code` (use the exact code shown)
     - You should get confirmation: "You are all set!"
   - Your Twilio WhatsApp number is: `whatsapp:+14155238886`

7. **Update .env.test:**
   ```bash
   TWILIO_ACCOUNT_SID=ACxxx...
   TWILIO_AUTH_TOKEN=xxx...
   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
   ```

**Note:** Sandbox is for testing only. For production, you'll need to apply for WhatsApp Business API (separate process).

---

## Step 5: Install Dependencies - 2 minutes

```bash
# Make sure you're in the Hermes project directory
cd /Users/laxus/Desktop/Projects/Hermes

# Install Python dependencies
pip install -r requirements.txt

# Install test dependencies
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

---

## Step 6: Verify Setup - 2 minutes

### Check that .env.test is complete:

```bash
cat .env.test | grep "your-"
```

**Expected:** No output (all placeholders replaced)

### Run basic unit tests:

```bash
pytest tests/unit/ -v
```

**Expected:** 7/7 tests passing ✅

---

## Step 7: Set Up Database Tables - 5 minutes

### Create database schema:

Check if you have database migration files:

```bash
ls src/models/
```

If you have migration files, run them. Otherwise, you'll need to create the schema manually when you run the app for the first time.

### Quick test:

```bash
# Start the development server
uvicorn src.main:app --reload --port 8000
```

Visit: http://localhost:8000/health

**Expected response:**
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

---

## Step 8: Set Up Webhooks (For Manual Testing) - 10 minutes

### Install ngrok:

```bash
# Download from https://ngrok.com/download
# Or install via homebrew:
brew install ngrok

# Sign up at https://dashboard.ngrok.com/signup
# Get auth token from https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### Start ngrok:

```bash
# In a separate terminal
ngrok http 8000
```

You'll see output like:
```
Forwarding   https://abc123.ngrok.io -> http://localhost:8000
```

**Save this URL!** You'll need it for webhooks.

### Configure SendGrid Webhook:

1. Go to SendGrid: Settings > **Inbound Parse**
2. Click "Add Host & URL"
3. Destination URL: `https://your-ngrok-url.ngrok.io/webhooks/email`
4. Click "Add"
5. Note: You may need a domain to receive emails (or use SendGrid's testing tools)

### Configure Twilio WhatsApp Webhook:

1. Go to Twilio: Messaging > Try it out > Sandbox
2. Find "WHEN A MESSAGE COMES IN" field
3. Enter: `https://your-ngrok-url.ngrok.io/webhooks/whatsapp`
4. Method: HTTP POST
5. Click "Save"

---

## Testing Checklist ✅

After completing all steps, you should have:

- [x] Supabase project created with database credentials
- [x] Anthropic API key with $5 free credit
- [x] SendGrid account with verified sender email
- [x] Twilio account with WhatsApp sandbox activated
- [x] All credentials filled in `.env.test`
- [x] Dependencies installed
- [x] Unit tests passing (7/7)
- [x] Development server running (port 8000)
- [x] ngrok exposing local server
- [x] Webhooks configured in SendGrid and Twilio

---

## Next Steps

1. **Run unit tests:**
   ```bash
   pytest tests/unit/ -v
   ```

2. **Run integration tests** (uses mocks, no API calls):
   ```bash
   pytest tests/integration/ -v
   ```

3. **Manual end-to-end test:**
   - Follow `TESTING.md` starting at "Manual Testing Scenarios"
   - Send a real test email
   - Verify WhatsApp notification
   - Approve and verify reply sent

---

## Troubleshooting

### "Database connection refused"
- Check DATABASE_URL is correct
- Verify Supabase project is active
- Check your password is correct in the connection string

### "Anthropic API error: Invalid API key"
- Verify key starts with `sk-ant-`
- Check no extra spaces in `.env.test`
- Ensure billing is set up in Anthropic console

### "SendGrid: Sender email not verified"
- Go to SendGrid > Sender Authentication
- Check email is marked as "Verified"
- FROM_EMAIL must exactly match verified email

### "Twilio WhatsApp: Unauthorized"
- Verify you sent "join \<code\>" to WhatsApp sandbox
- Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are correct
- Ensure webhook URL is HTTPS (ngrok provides this)

---

## Support Resources

- **Supabase Docs:** https://supabase.com/docs
- **Anthropic API Docs:** https://docs.anthropic.com/
- **SendGrid Docs:** https://docs.sendgrid.com/
- **Twilio WhatsApp Docs:** https://www.twilio.com/docs/whatsapp
- **Hermes Testing Guide:** See `TESTING.md` in this repo

---

**Ready to test?** Start with unit tests, then move to manual testing with real webhooks!
