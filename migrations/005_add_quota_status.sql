-- Migration: Add pending_whatsapp_quota status to threads table
-- Description: Allow the new status used when WhatsApp quota is exceeded
-- Date: 2026-09-10

-- Drop the old constraint
ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_status_check;

-- Add the new constraint with all required statuses
ALTER TABLE threads ADD CONSTRAINT threads_status_check
CHECK (status IN (
    'open',                    -- DEFAULT status from migration 001
    'resolved',                -- Used when email sent to customer
    'new',
    'processing',
    'pending_review',
    'approved',
    'sent',
    'rejected',
    'failed',
    'pending_whatsapp_quota'   -- NEW STATUS (added in this migration)
));

-- Comment
COMMENT ON CONSTRAINT threads_status_check ON threads IS
'Valid thread statuses including all legacy and new values';
