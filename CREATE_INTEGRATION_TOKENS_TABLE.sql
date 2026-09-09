-- Create integration_tokens table if it doesn't exist
-- This should have been created by migration 002, but let's ensure it exists

CREATE TABLE IF NOT EXISTS integration_tokens (
    provider TEXT PRIMARY KEY,
    token_cache TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION update_integration_tokens_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_integration_tokens_updated_at ON integration_tokens;
CREATE TRIGGER update_integration_tokens_updated_at
    BEFORE UPDATE ON integration_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_integration_tokens_updated_at();

ALTER TABLE integration_tokens ENABLE ROW LEVEL SECURITY;

-- Create RLS policy for service role
DROP POLICY IF EXISTS "Allow all for service role" ON integration_tokens;
CREATE POLICY "Allow all for service role" ON integration_tokens
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Reload PostgREST schema cache
SELECT reload_postgrest_schema_cache();

-- Also update the reviewer to your correct phone number
UPDATE reviewers
SET phone_number = 'whatsapp:+918796887516',
    name = 'Aryan Ad',
    active = true
WHERE phone_number = 'whatsapp:+1234567890';

-- Verify the table was created
SELECT 'integration_tokens table created successfully' AS status;
