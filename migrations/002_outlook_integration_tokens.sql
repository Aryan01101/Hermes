-- Persistent OAuth token cache for Microsoft Graph delegated access.
-- Service-role access bypasses RLS; no browser or anonymous role can read this table.

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
