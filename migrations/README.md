# Database Migrations

This directory contains SQL migration scripts for the Hermes v2 database schema.

## Running Migrations

### Via Supabase Dashboard

1. Go to your Supabase project
2. Navigate to SQL Editor
3. Copy the contents of `001_initial_schema.sql`
4. Run the SQL

### Via CLI (Coming Soon)

We'll add programmatic migration support in Phase 2.2.

## Migration Files

- `001_initial_schema.sql`: Initial database schema with all core tables, indexes, and helper functions

## Schema Overview

### Core Tables

1. **threads**: Email conversation threads
   - Tracked by Message-ID/References headers
   - Status: open, pending_review, resolved

2. **drafts**: AI-generated reply versions
   - Multiple versions per thread
   - WhatsApp SID for reply-to-quote disambiguation
   - Status: pending, stale, approved, rejected

3. **reviewer_actions**: Reviewer interactions
   - approve, feedback, reject actions
   - Links to draft and reviewer

4. **reviewers**: Active WhatsApp reviewer roster
   - Phone numbers
   - Active/inactive flag

5. **audit_log**: Complete audit trail
  - All events with timestamps
  - Actor attribution
  - Flexible JSONB details

6. **integration_tokens** (migration `002`): Persisted OAuth token cache for
   delegated Microsoft Graph Outlook and Gmail API access.

### Helper Functions

- `get_latest_draft(thread_id)`: Get current active draft
- `mark_pending_drafts_stale(thread_id)`: Handle trailing email edge case

### LangGraph Integration

LangGraph's Postgres checkpointer will automatically create:
- `checkpoints`
- `checkpoint_writes`
- `checkpoint_blobs`

These tables store graph state for durable `interrupt()` functionality.
