"""Error handling utilities for graceful error management."""

import json
import logging
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors that can occur in the system."""

    QUOTA_EXCEEDED = "quota_exceeded"  # External API quota exhausted
    RATE_LIMITED = "rate_limited"  # Twilio/external rate limit (HTTP 429)
    INVALID_EMAIL = "invalid_email"  # Spam/non-business email filtered out
    LLM_FAILURE = "llm_failure"  # Gemini/Claude API error
    DATABASE_ERROR = "database_error"  # DB constraint/connection issue
    NETWORK_ERROR = "network_error"  # Timeout/connection failure
    UNKNOWN = "unknown"  # Unexpected error


class ErrorRecoveryAction(Enum):
    """What action was taken to recover from the error."""

    MARKED_PROCESSED = "marked_processed"  # Email marked as read, won't retry
    THREAD_FAILED = "thread_failed"  # Thread marked as failed
    QUOTA_WAIT = "quota_wait"  # Waiting for quota reset
    FALLBACK_STATUS = "fallback_status"  # Used fallback DB status
    CIRCUIT_OPENED = "circuit_opened"  # Circuit breaker triggered
    SKIPPED = "skipped"  # Email skipped/filtered
    NO_ACTION = "no_action"  # Error logged only


def log_workflow_error(
    error_category: ErrorCategory,
    title: str,
    email_context: Optional[Dict[str, Any]] = None,
    thread_id: Optional[str] = None,
    draft_id: Optional[str] = None,
    error_details: Optional[Dict[str, Any]] = None,
    recovery_action: Optional[ErrorRecoveryAction] = None,
    recovery_message: Optional[str] = None,
    will_retry: bool = False,
) -> None:
    """
    Log a workflow error with structured context.

    Args:
        error_category: Category of error
        title: Brief error title
        email_context: Email context (sender, subject, message_id)
        thread_id: Thread ID if applicable
        draft_id: Draft ID if applicable
        error_details: Additional error details
        recovery_action: What action was taken
        recovery_message: Human-readable recovery message
        will_retry: Whether system will retry this operation

    Example:
        log_workflow_error(
            error_category=ErrorCategory.QUOTA_EXCEEDED,
            title="Gemini API quota exhausted",
            email_context={"from": "customer@example.com", "subject": "Help needed"},
            thread_id="abc-123",
            error_details={"quota_used": 20, "quota_limit": 20},
            recovery_action=ErrorRecoveryAction.THREAD_FAILED,
            recovery_message="Thread marked as 'failed'",
            will_retry=False
        )

        Logs:
        ❌ [QUOTA_EXCEEDED] Gemini API quota exhausted
           Email: customer@example.com | Subject: Help needed
           Thread: abc-123
           Error Details: {"quota_used": 20, "quota_limit": 20}
           Action: Thread marked as 'failed'
           Recovery: Will NOT retry
    """
    # Build log message
    prefix = "❌" if not will_retry else "⚠️"
    lines = [f"{prefix} [{error_category.value.upper()}] {title}"]

    # Add context
    if email_context:
        ctx_parts = []
        if "from" in email_context:
            ctx_parts.append(f"From: {email_context['from']}")
        if "subject" in email_context:
            ctx_parts.append(f"Subject: {email_context['subject']}")
        if "message_id" in email_context:
            ctx_parts.append(f"Message ID: {email_context['message_id']}")
        if ctx_parts:
            lines.append(f"   {'| '.join(ctx_parts)}")

    if thread_id:
        lines.append(f"   Thread: {thread_id}")
    if draft_id:
        lines.append(f"   Draft: {draft_id}")

    # Add error details
    if error_details:
        lines.append(f"   Error Details: {json.dumps(error_details, indent=6)}")

    # Add recovery action
    if recovery_action:
        lines.append(f"   Action: {recovery_message or recovery_action.value}")

    # Add retry status
    retry_status = "Will retry" if will_retry else "Will NOT retry"
    lines.append(f"   Recovery: {retry_status}")

    # Log as error
    logger.error("\n".join(lines))


def log_email_skipped(
    reason: str,
    from_email: str,
    subject: str,
    message_id: Optional[str] = None,
    additional_info: Optional[str] = None,
) -> None:
    """
    Log when an email is skipped/filtered.

    Example:
        log_email_skipped(
            reason="Automated notification (facebookmail.com)",
            from_email="birthdays@facebookmail.com",
            subject="🎂 It's Grace Fry's birthday today"
        )

        Logs:
        ⏭️  [INVALID_EMAIL] Skipped email from birthdays@facebookmail.com
           Reason: Automated notification (facebookmail.com)
           Subject: 🎂 It's Grace Fry's birthday today
           Action: Marked as read, NOT processing
    """
    lines = [
        f"⏭️  [INVALID_EMAIL] Skipped email from {from_email}",
        f"   Reason: {reason}",
        f"   Subject: {subject}",
    ]

    if message_id:
        lines.append(f"   Message ID: {message_id}")

    if additional_info:
        lines.append(f"   {additional_info}")

    lines.append("   Action: Marked as read, NOT processing")

    logger.info("\n".join(lines))


def log_quota_pause(
    quota_name: str,
    current_usage: int,
    quota_limit: int,
    reset_time: Optional[str] = None,
) -> None:
    """
    Log when system pauses due to quota exhaustion.

    Example:
        log_quota_pause(
            quota_name="Gemini API",
            current_usage=20,
            quota_limit=20,
            reset_time="2026-09-11T00:00:00Z"
        )

        Logs:
        ⏸️  [QUOTA_EXCEEDED] Gmail polling paused - Gemini API quota exhausted
           Current Usage: 20/20 requests
           ⏰ Quota resets at: 2026-09-11T00:00:00Z
           Action: Polling will resume automatically after reset
    """
    lines = [
        f"⏸️  [QUOTA_EXCEEDED] Gmail polling paused - {quota_name} quota exhausted",
        f"   Current Usage: {current_usage}/{quota_limit} requests",
    ]

    if reset_time:
        lines.append(f"   ⏰ Quota resets at: {reset_time}")
    else:
        lines.append("   ⏰ Quota resets at: Tomorrow 00:00 UTC")

    lines.append("   Action: Polling will resume automatically after reset")

    logger.warning("\n".join(lines))


def log_circuit_breaker_opened(failure_count: int, reset_timeout_minutes: int) -> None:
    """
    Log when circuit breaker opens.

    Example:
        log_circuit_breaker_opened(failure_count=3, reset_timeout_minutes=60)

        Logs:
        🚨 [CIRCUIT_OPENED] Too many consecutive failures (3)
           Action: Gmail polling STOPPED
           Recovery: Will auto-reset in 60 minutes
           Manual Reset: Restart the service to reset immediately
    """
    lines = [
        f"🚨 [CIRCUIT_OPENED] Too many consecutive failures ({failure_count})",
        "   Action: Gmail polling STOPPED",
        f"   Recovery: Will auto-reset in {reset_timeout_minutes} minutes",
        "   Manual Reset: Restart the service to reset immediately",
    ]

    logger.error("\n".join(lines))


def log_database_constraint_violation(
    thread_id: str,
    attempted_status: str,
    fallback_status: str,
    error_message: str,
) -> None:
    """
    Log database constraint violations.

    Example:
        log_database_constraint_violation(
            thread_id="abc-123",
            attempted_status="pending_whatsapp_quota",
            fallback_status="failed",
            error_message="Check constraint threads_status_check violated"
        )

        Logs:
        ❌ [DATABASE_ERROR] Database constraint violation
           Thread: abc-123
           Attempted Status: pending_whatsapp_quota
           Error: Check constraint threads_status_check violated
           ⚠️  ACTION REQUIRED: Check if database migration is needed
           Fallback: Using status 'failed'
    """
    lines = [
        "❌ [DATABASE_ERROR] Database constraint violation",
        f"   Thread: {thread_id}",
        f"   Attempted Status: {attempted_status}",
        f"   Error: {error_message}",
        "   ⚠️  ACTION REQUIRED: Check if database migration is needed",
        f"   Fallback: Using status '{fallback_status}'",
    ]

    logger.error("\n".join(lines))
