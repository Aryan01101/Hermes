-- Migration: WhatsApp Quota Tracking
-- Description: Add table to track daily WhatsApp message quota to prevent exceeding Twilio limits
-- Date: 2026-09-10

-- ============================================================================
-- WhatsApp Quota Tracking Table
-- ============================================================================
-- Tracks daily message count to enforce Twilio rate limits (30 msg/day for trial)

CREATE TABLE IF NOT EXISTS whatsapp_quota_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quota_date DATE NOT NULL UNIQUE,  -- One record per day
    message_count INTEGER NOT NULL DEFAULT 0,
    daily_limit INTEGER NOT NULL DEFAULT 30,  -- Configurable limit
    limit_reached_at TIMESTAMPTZ,  -- When limit was hit (if applicable)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast lookups by date
CREATE INDEX idx_whatsapp_quota_date ON whatsapp_quota_tracking(quota_date DESC);

-- ============================================================================
-- Helper Function: Get or Create Today's Quota Record
-- ============================================================================
CREATE OR REPLACE FUNCTION get_todays_whatsapp_quota()
RETURNS TABLE (
    id UUID,
    quota_date DATE,
    message_count INTEGER,
    daily_limit INTEGER,
    limit_reached_at TIMESTAMPTZ,
    remaining INTEGER
) AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
    v_record RECORD;
BEGIN
    -- Get or create today's record
    INSERT INTO whatsapp_quota_tracking (quota_date, message_count, daily_limit)
    VALUES (v_today, 0, 30)
    ON CONFLICT (quota_date) DO NOTHING;

    -- Return the record with calculated remaining count
    RETURN QUERY
    SELECT
        q.id,
        q.quota_date,
        q.message_count,
        q.daily_limit,
        q.limit_reached_at,
        GREATEST(0, q.daily_limit - q.message_count) AS remaining
    FROM whatsapp_quota_tracking q
    WHERE q.quota_date = v_today;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Helper Function: Increment Message Count
-- ============================================================================
CREATE OR REPLACE FUNCTION increment_whatsapp_quota()
RETURNS TABLE (
    success BOOLEAN,
    message_count INTEGER,
    daily_limit INTEGER,
    remaining INTEGER
) AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
    v_record RECORD;
BEGIN
    -- Get or create today's record
    INSERT INTO whatsapp_quota_tracking (quota_date, message_count, daily_limit)
    VALUES (v_today, 0, 30)
    ON CONFLICT (quota_date) DO NOTHING;

    -- Increment count and update timestamp
    UPDATE whatsapp_quota_tracking
    SET
        message_count = message_count + 1,
        updated_at = NOW(),
        limit_reached_at = CASE
            WHEN message_count + 1 >= daily_limit AND limit_reached_at IS NULL
            THEN NOW()
            ELSE limit_reached_at
        END
    WHERE quota_date = v_today
    RETURNING
        true AS success,
        whatsapp_quota_tracking.message_count,
        whatsapp_quota_tracking.daily_limit,
        GREATEST(0, whatsapp_quota_tracking.daily_limit - whatsapp_quota_tracking.message_count) AS remaining
    INTO v_record;

    RETURN QUERY SELECT v_record.success, v_record.message_count, v_record.daily_limit, v_record.remaining;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Helper Function: Check if quota available
-- ============================================================================
CREATE OR REPLACE FUNCTION check_whatsapp_quota_available()
RETURNS BOOLEAN AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
    v_count INTEGER;
    v_limit INTEGER;
BEGIN
    -- Get or create today's record
    INSERT INTO whatsapp_quota_tracking (quota_date, message_count, daily_limit)
    VALUES (v_today, 0, 30)
    ON CONFLICT (quota_date) DO NOTHING;

    -- Check if quota available
    SELECT message_count, daily_limit
    INTO v_count, v_limit
    FROM whatsapp_quota_tracking
    WHERE quota_date = v_today;

    RETURN v_count < v_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE whatsapp_quota_tracking IS 'Tracks daily WhatsApp message quota to enforce Twilio rate limits';
COMMENT ON COLUMN whatsapp_quota_tracking.quota_date IS 'Date for this quota record (one per day)';
COMMENT ON COLUMN whatsapp_quota_tracking.message_count IS 'Number of messages sent today';
COMMENT ON COLUMN whatsapp_quota_tracking.daily_limit IS 'Maximum messages allowed per day (30 for trial, configurable)';
COMMENT ON COLUMN whatsapp_quota_tracking.limit_reached_at IS 'Timestamp when daily limit was first reached';

-- ============================================================================
-- RLS (Row Level Security) - Disable for service role access
-- ============================================================================
ALTER TABLE whatsapp_quota_tracking ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "Service role has full access to quota tracking"
    ON whatsapp_quota_tracking
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
