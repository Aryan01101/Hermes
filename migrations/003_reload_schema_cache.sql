-- Function to reload PostgREST schema cache
-- Run this in Supabase SQL Editor to fix PGRST205 error

CREATE OR REPLACE FUNCTION reload_postgrest_schema_cache()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    NOTIFY pgrst, 'reload schema';
END;
$$;

-- Execute the function immediately to reload the cache
SELECT reload_postgrest_schema_cache();

-- You can call this function anytime via REST API:
-- POST https://YOUR_SUPABASE_URL/rest/v1/rpc/reload_postgrest_schema_cache
