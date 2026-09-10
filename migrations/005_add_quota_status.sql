-- Migration: Add pending_whatsapp_quota status to threads table
-- Description: Allow the new status used when WhatsApp quota is exceeded
-- Date: 2026-09-10

-- Drop the old constraint
ALTER TABLE threads DROP CONSTRAINT IF EXISTS threads_status_check;

-- Add the new constraint with the additional status
ALTER TABLE threads ADD CONSTRAINT threads_status_check
CHECK (status IN (
    'new',
    'processing',
    'pending_review',
    'approved',
    'sent',
    'rejected',
    'failed',
    'pending_whatsapp_quota'  -- NEW STATUS
));

-- Comment
COMMENT ON CONSTRAINT threads_status_check ON threads IS
'Valid thread statuses including pending_whatsapp_quota for rate limit handling';
