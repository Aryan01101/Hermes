-- ============================================================================
-- CORRECTED SQL - Run this in Supabase SQL Editor
-- ============================================================================

-- Step 1: Create and execute schema reload function
CREATE OR REPLACE FUNCTION reload_postgrest_schema_cache()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    NOTIFY pgrst, 'reload schema';
END;
$$;

SELECT reload_postgrest_schema_cache();

-- Step 2: Fix reviewer status (correct column name is 'active', not 'is_active')
UPDATE reviewers
SET active = true
WHERE phone_number = 'whatsapp:+918796887516';

-- ============================================================================
-- Expected Output:
-- - Line 15: "Success. No rows returned" (function created and executed)
-- - Line 20: "Success. 1 rows affected" (reviewer updated)
-- ============================================================================
