# Fix Connection Issues - Step by Step

## Issues Found:

1. ❌ **Database tables don't exist** - Migration not run
2. ❌ **Claude model outdated** - Using deprecated `claude-3-5-sonnet-20241022`
3. ❌ **Wrong psycopg version** - Need psycopg3, not psycopg2

## Fixes Applied:

1. ✅ Updated Claude model to `claude-3-5-sonnet-20250219`
2. ✅ Updated `requirements.txt` to use `psycopg[binary]==3.2.3`
3. ✅ Created migration runner script

---

## Step 1: Install Updated Dependencies

```bash
pip install -r requirements.txt
```

**Why:** This installs the correct `psycopg` version (v3) that LangGraph needs.

**Expected output:**
```
Successfully installed psycopg-3.2.3 ...
```

---

## Step 2: Run Database Migrations

```bash
python run_migrations.py
```

**Why:** This creates all the database tables (threads, drafts, reviewers, etc.) in your Supabase database.

**Expected output:**
```
🔧 HERMES DATABASE MIGRATION RUNNER
============================================================
📡 Connecting to database...
📁 Found 1 migration file(s):
   └─ 001_initial_schema.sql
🔌 Establishing database connection...
▶️  Running 001_initial_schema.sql...
   ✅ Successfully executed 001_initial_schema.sql
✅ All migrations committed successfully!
🔍 Verifying database schema...
📊 Found 6 tables:
   ✅ audit_log
   ✅ drafts
   ✅ reviewer_actions
   ✅ reviewers
   ✅ threads
   ✅ [checkpoint tables...]
🎉 MIGRATION COMPLETE!
```

---

## Step 3: Run Connection Test Again

```bash
python test_connections.py
```

**Expected output (all passing):**
```
============================================================
🚀 HERMES CONNECTION TEST
============================================================
✅ SUCCESS Database (Supabase)
   └─ Found 0 active reviewers
✅ SUCCESS Anthropic API
   └─ Intent detected: question
✅ SUCCESS SendGrid Email
   └─ Configured to send from: aadhikari678@outlook.com
✅ SUCCESS Twilio WhatsApp
   └─ Configured WhatsApp number: whatsapp:+14155238886
✅ SUCCESS LangGraph Workflow
   └─ PostgresSaver checkpoint system ready

✅ Passed: 5/5
❌ Failed: 0/5

🎉 All services are working correctly!
```

---

## Troubleshooting

### If pip install fails:

```bash
# Try upgrading pip first
pip install --upgrade pip

# Then retry
pip install -r requirements.txt
```

### If migration fails with "connection refused":

Check your `.env` file `DATABASE_URL` format:
```
DATABASE_URL=postgresql://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

**Note:** If your password contains special characters like `#`, you may need to URL-encode them:
- `#` becomes `%23`
- `@` becomes `%40`
- etc.

Example:
```
# If password is: Hermes#713765
DATABASE_URL=postgresql://postgres:Hermes%23713765@db.xxxxx.supabase.co:5432/postgres
```

### If Anthropic API still fails:

The model was updated to `claude-3-5-sonnet-20250219`. If this doesn't work, you can manually set it in `.env`:

```bash
# Add this line to your .env
CLAUDE_MODEL=claude-3-5-sonnet-20250219
```

---

## Summary

You need to run **2 commands**:

```bash
pip install -r requirements.txt
python run_migrations.py
python test_connections.py
```

After these steps, all 5 connection tests should pass!
