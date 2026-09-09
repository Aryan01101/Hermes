# Restart PostgREST to Fix Schema Cache

## Problem

The NOTIFY command was executed successfully, but PostgREST still shows PGRST205 error. This means PostgREST needs to be restarted to reload its schema cache.

## Solution: Restart PostgREST Service

### Method 1: Pause and Resume Project (Recommended)

1. Go to: https://supabase.com/dashboard/project/mhrmnthecmuvptiorhmz/settings/general
2. Scroll down to **"Pause project"** section
3. Click **"Pause project"** button
4. Wait 30 seconds for the project to fully pause
5. Click **"Resume project"** button
6. Wait 1-2 minutes for all services to restart

This will restart PostgREST and force it to rebuild the schema cache from scratch.

### Method 2: Restart API Service (If available)

Some Supabase plans have a "Restart API" option:

1. Go to: https://supabase.com/dashboard/project/mhrmnthecmuvptiorhmz/settings/api
2. Look for a "Restart" or "Restart API" button
3. Click it and wait 1-2 minutes

## After Restart

Run this command to verify the fix worked:

```bash
curl "https://mhrmnthecmuvptiorhmz.supabase.co/rest/v1/integration_tokens?select=*" \
  -H "apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1ocm1udGhlY211dnB0aW9yaG16Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODcyOTYxMywiZXhwIjoyMTA0MzA1NjEzfQ.SHdO0n1HQNIGy2S6pzizE2Xs6th4WqQYq7mCAdFF9gQ" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1ocm1udGhlY211dnB0aW9yaG16Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODcyOTYxMywiZXhwIjoyMTA0MzA1NjEzfQ.SHdO0n1HQNIGy2S6pzizE2Xs6th4WqQYq7mCAdFF9gQ"
```

**Success response**: `[]` (empty array) or data rows
**Failure response**: `{"code":"PGRST205",...}`

## Why This is Needed

PostgREST loads its schema cache when it starts. The NOTIFY command should reload it, but:
1. PostgREST might not be configured to listen to NOTIFY
2. The notification might not have been delivered
3. A restart is the most reliable way to rebuild the cache

After restart, PostgREST will scan all tables again and the integration_tokens table will be in the cache.

## Next Steps After Fix

Once the table is accessible:
1. Railway will automatically poll Gmail on next interval (60 seconds)
2. Check Railway logs for Gmail polling activity
3. Send a test email to verify end-to-end flow
