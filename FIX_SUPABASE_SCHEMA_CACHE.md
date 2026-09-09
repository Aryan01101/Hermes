# Fix Supabase Schema Cache Issue

## Problem Diagnosed

✓ **Analysis Complete**: 5 out of 6 tables are accessible via REST API
✗ **Issue Found**: `integration_tokens` table has PGRST205 error (not in schema cache)

The table **exists** in PostgreSQL but PostgREST doesn't know about it yet.

## Solution: Reload PostgREST Schema Cache

### Option 1: Supabase SQL Editor (RECOMMENDED - Fastest)

1. Go to: https://supabase.com/dashboard/project/mhrmnthecmuvptiorhmz/sql
2. Copy and paste this SQL:

```sql
-- Create function to reload schema cache
CREATE OR REPLACE FUNCTION reload_postgrest_schema_cache()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    NOTIFY pgrst, 'reload schema';
END;
$$;

-- Execute immediately
SELECT reload_postgrest_schema_cache();
```

3. Click "Run"
4. You should see: "Success. No rows returned"

### Option 2: Restart PostgREST (Alternative)

If Option 1 doesn't work, restart the PostgREST service:

1. Go to: https://supabase.com/dashboard/project/mhrmnthecmuvptiorhmz/settings/general
2. Scroll to "Pause project" section
3. Click "Pause project" and wait 30 seconds
4. Click "Resume project"

This forces PostgREST to rebuild its entire schema cache.

## Verification

After running either option, verify the fix worked:

```bash
curl "https://mhrmnthecmuvptiorhmz.supabase.co/rest/v1/integration_tokens?select=*" \
  -H "apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1ocm1udGhlY211dnB0aW9yaG16Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODcyOTYxMywiZXhwIjoyMTA0MzA1NjEzfQ.SHdO0n1HQNIGy2S6pzizE2Xs6th4WqQYq7mCAdFF9gQ" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1ocm1udGhlY211dnB0aW9yaG16Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODcyOTYxMywiZXhwIjoyMTA0MzA1NjEzfQ.SHdO0n1HQNIGy2S6pzizE2Xs6th4WqQYq7mCAdFF9gQ"
```

**Expected Success Response**: `[]` (empty array) or data rows
**Error Response (not fixed)**: `{"code":"PGRST205",...}`

## Additional Fix: Update Reviewer Status

I noticed the reviewer has `is_active: null` instead of `true`. Fix this in SQL Editor:

```sql
UPDATE reviewers
SET is_active = true
WHERE phone_number = 'whatsapp:+919879687516';
```

## After Schema Cache is Reloaded

1. Railway will automatically pick up the change on next poll (60 seconds)
2. Check Railway logs for Gmail polling activity
3. Send a test email to verify end-to-end flow

## Why This Happened

When migration `002_outlook_integration_tokens.sql` was run, it created the table in PostgreSQL, but PostgREST's in-memory schema cache wasn't notified. The `NOTIFY pgrst, 'reload schema'` command tells PostgREST to refresh its cache and discover the new table.
