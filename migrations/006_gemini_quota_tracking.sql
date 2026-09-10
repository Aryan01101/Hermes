-- Migration: Gemini API Quota Tracking
-- Description: Add table to track daily Gemini API request quota to prevent exceeding Google's free tier limits
-- Date: 2026-09-11

-- ============================================================================
-- Gemini Quota Tracking Table
-- ============================================================================
-- Tracks daily request count to enforce Gemini API limits (20 requests/day for free tier)

CREATE TABLE IF NOT EXISTS gemini_quota_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quota_date DATE NOT NULL UNIQUE,  -- One record per day
    request_count INTEGER NOT NULL DEFAULT 0,
    daily_limit INTEGER NOT NULL DEFAULT 20,  -- Configurable limit (20 for free tier, higher for paid)
    limit_reached_at TIMESTAMPTZ,  -- When limit was hit (if applicable)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast lookups by date
CREATE INDEX idx_gemini_quota_date ON gemini_quota_tracking(quota_date DESC);

-- ============================================================================
-- Helper Function: Get or Create Today's Quota Record
-- ============================================================================
CREATE OR REPLACE FUNCTION get_todays_gemini_quota()
RETURNS TABLE (
    id UUID,
    quota_date DATE,
    request_count INTEGER,
    daily_limit INTEGER,
    limit_reached_at TIMESTAMPTZ,
    remaining INTEGER
) AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
    v_record RECORD;
BEGIN
    -- Get or create today's record
    INSERT INTO gemini_quota_tracking (quota_date, request_count, daily_limit)
    VALUES (v_today, 0, 20)
    ON CONFLICT (quota_date) DO NOTHING;

    -- Return the record with calculated remaining count
    RETURN QUERY
    SELECT
        q.id,
        q.quota_date,
        q.request_count,
        q.daily_limit,
        q.limit_reached_at,
        GREATEST(0, q.daily_limit - q.request_count) AS remaining
    FROM gemini_quota_tracking q
    WHERE q.quota_date = v_today;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Helper Function: Increment Request Count
-- ============================================================================
CREATE OR REPLACE FUNCTION increment_gemini_quota()
RETURNS TABLE (
    success BOOLEAN,
    request_count INTEGER,
    daily_limit INTEGER,
    remaining INTEGER
) AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
    v_record RECORD;
BEGIN
    -- Get or create today's record
    INSERT INTO gemini_quota_tracking (quota_date, request_count, daily_limit)
    VALUES (v_today, 0, 20)
    ON CONFLICT (quota_date) DO NOTHING;

    -- Increment count and update timestamp
    UPDATE gemini_quota_tracking
    SET
        request_count = request_count + 1,
        updated_at = NOW(),
        limit_reached_at = CASE
            WHEN request_count + 1 >= daily_limit AND limit_reached_at IS NULL
            THEN NOW()
            ELSE limit_reached_at
        END
    WHERE quota_date = v_today
    RETURNING
        true AS success,
        gemini_quota_tracking.request_count,
        gemini_quota_tracking.daily_limit,
        GREATEST(0, gemini_quota_tracking.daily_limit - gemini_quota_tracking.request_count) AS remaining
    INTO v_record;

    RETURN QUERY SELECT v_record.success, v_record.request_count, v_record.daily_limit, v_record.remaining;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Helper Function: Check if quota available
-- ============================================================================
CREATE OR REPLACE FUNCTION check_gemini_quota_available()
RETURNS BOOLEAN AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
    v_count INTEGER;
    v_limit INTEGER;
BEGIN
    -- Get or create today's record
    INSERT INTO gemini_quota_tracking (quota_date, request_count, daily_limit)
    VALUES (v_today, 0, 20)
    ON CONFLICT (quota_date) DO NOTHING;

    -- Check if quota available
    SELECT request_count, daily_limit
    INTO v_count, v_limit
    FROM gemini_quota_tracking
    WHERE quota_date = v_today;

    RETURN v_count < v_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE gemini_quota_tracking IS 'Tracks daily Gemini API request quota to enforce Google API limits';
COMMENT ON COLUMN gemini_quota_tracking.quota_date IS 'Date for this quota record (one per day)';
COMMENT ON COLUMN gemini_quota_tracking.request_count IS 'Number of API requests made today';
COMMENT ON COLUMN gemini_quota_tracking.daily_limit IS 'Maximum requests allowed per day (20 for free tier, configurable)';
COMMENT ON COLUMN gemini_quota_tracking.limit_reached_at IS 'Timestamp when daily limit was first reached';

-- ============================================================================
-- RLS (Row Level Security) - Disable for service role access
-- ============================================================================
ALTER TABLE gemini_quota_tracking ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "Service role has full access to quota tracking"
    ON gemini_quota_tracking
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
