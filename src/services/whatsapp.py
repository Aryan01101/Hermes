"""WhatsApp service for sending notifications via Twilio."""

import logging
from typing import Dict, Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for sending WhatsApp messages via Twilio."""

    def __init__(self) -> None:
        """Initialize WhatsApp service with Twilio client."""
        settings = get_settings()
        self.client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
        )
        self.whatsapp_number = settings.twilio_whatsapp_number
        self.enable_quota_tracking = settings.whatsapp_enable_quota_tracking
        self.send_confirmations = settings.whatsapp_send_confirmations
        self.daily_message_limit = settings.twilio_daily_message_limit

    # =========================================================================
    # Send Draft for Review
    # =========================================================================

    async def send_draft_for_review(
        self,
        reviewer_phone: str,
        customer_email: str,
        subject: str,
        draft_content: str,
        confidence_score: float,
        thread_id: str,
        draft_id: str,
    ) -> Dict[str, any]:
        """
        Send draft to reviewer via WhatsApp for approval.

        Message format:
        ---
        New email from: customer@example.com
        Subject: Question about product

        Draft reply:
        [draft content]

        Confidence: 85%

        Reply with:
        - APPROVE to send
        - FEEDBACK: [your suggestions]
        - REJECT to discard
        ---

        Args:
            reviewer_phone: Reviewer WhatsApp number (format: +1234567890)
            customer_email: Customer email address
            subject: Email subject
            draft_content: Draft reply content
            confidence_score: AI confidence (0.0-1.0)
            thread_id: Thread UUID for tracking
            draft_id: Draft UUID for tracking

        Returns:
            Dict with send status and message SID
        """
        # Import here to avoid circular dependency
        from src.services.database import get_database

        db = get_database()

        try:
            # Check quota if tracking is enabled
            if self.enable_quota_tracking:
                quota_available = await db.check_whatsapp_quota_available()
                if not quota_available:
                    quota_status = await db.get_whatsapp_quota_status()
                    logger.warning(
                        f"WhatsApp quota exceeded: {quota_status['message_count']}/{quota_status['daily_limit']} "
                        f"messages sent today. Limit reached at {quota_status.get('limit_reached_at')}"
                    )
                    return {
                        "success": False,
                        "error": "quota_exceeded",
                        "quota_status": quota_status,
                        "message": f"Daily WhatsApp message limit reached ({quota_status['daily_limit']} messages/day). "
                        f"Messages will resume tomorrow or upgrade your Twilio account.",
                    }

            # Format confidence as percentage
            confidence_pct = int(confidence_score * 100)

            # Build message
            message_body = f"""📧 New email from: {customer_email}
Subject: {subject}

📝 Draft reply:
{draft_content}

🤖 Confidence: {confidence_pct}%

Reply:
• APPROVE - Send this reply
• FEEDBACK: [your suggestions] - Request changes
• REJECT - Discard and handle manually

Thread: {thread_id[:8]}..."""

            # Send WhatsApp message
            message = self.client.messages.create(
                from_=self.whatsapp_number,
                to=f"whatsapp:{reviewer_phone}",
                body=message_body,
            )

            logger.info(
                f"Draft sent to {reviewer_phone} via WhatsApp. SID: {message.sid}"
            )

            # Increment quota if tracking is enabled
            if self.enable_quota_tracking:
                quota_result = await db.increment_whatsapp_quota()
                logger.info(
                    f"WhatsApp quota updated: {quota_result['message_count']}/{quota_result['daily_limit']} "
                    f"({quota_result['remaining']} remaining)"
                )

            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status,
            }

        except TwilioRestException as e:
            # Specific handling for Twilio rate limit errors
            if e.status == 429:
                logger.error(
                    f"Twilio rate limit exceeded (HTTP 429): {e.msg}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error": "rate_limit_exceeded",
                    "error_code": e.code,
                    "message": f"Twilio rate limit exceeded: {e.msg}. "
                    "Please upgrade your Twilio account or wait for the limit to reset.",
                }
            else:
                logger.error(
                    f"Twilio API error (HTTP {e.status}): {e.msg}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error": "twilio_api_error",
                    "error_code": e.code,
                    "message": str(e.msg),
                }

        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}", exc_info=True)
            return {
                "success": False,
                "error": "unknown_error",
                "message": str(e),
            }

    # =========================================================================
    # Parse Reviewer Response
    # =========================================================================

    def parse_reviewer_response(
        self, response_text: str
    ) -> Dict[str, any]:
        """
        Parse reviewer's WhatsApp response.

        Expected formats:
        - "APPROVE"
        - "FEEDBACK: Please mention the refund policy"
        - "REJECT"

        Args:
            response_text: WhatsApp message body from reviewer

        Returns:
            Dict with action and optional feedback text
        """
        response_lower = response_text.strip().lower()

        # Check for APPROVE
        if response_lower.startswith("approve"):
            return {
                "action": "approve",
                "feedback": None,
            }

        # Check for REJECT
        if response_lower.startswith("reject"):
            return {
                "action": "reject",
                "feedback": None,
            }

        # Check for FEEDBACK
        if response_lower.startswith("feedback"):
            # Extract feedback text after "FEEDBACK:"
            feedback_text = response_text.strip()
            if ":" in feedback_text:
                feedback_text = feedback_text.split(":", 1)[1].strip()

            return {
                "action": "feedback",
                "feedback": feedback_text,
            }

        # Unknown response
        logger.warning(f"Unknown reviewer response: {response_text}")
        return {
            "action": "unknown",
            "feedback": response_text,
        }

    # =========================================================================
    # Send Confirmation
    # =========================================================================

    async def send_confirmation(
        self,
        reviewer_phone: str,
        action: str,
        details: str | None = None,
    ) -> Dict[str, any]:
        """
        Send confirmation message to reviewer after processing their response.

        Args:
            reviewer_phone: Reviewer WhatsApp number
            action: Action taken (sent, redrafting, rejected)
            details: Optional details to include

        Returns:
            Dict with send status
        """
        # Import here to avoid circular dependency
        from src.services.database import get_database

        db = get_database()

        try:
            # Check if confirmations are enabled
            if not self.send_confirmations:
                logger.info(
                    f"Confirmation skipped (disabled): {action} for {reviewer_phone}"
                )
                return {
                    "success": True,
                    "skipped": True,
                    "message": "Confirmations disabled to save quota",
                }

            # Check quota if tracking is enabled
            if self.enable_quota_tracking:
                quota_available = await db.check_whatsapp_quota_available()
                if not quota_available:
                    quota_status = await db.get_whatsapp_quota_status()
                    logger.warning(
                        f"WhatsApp quota exceeded, skipping confirmation: "
                        f"{quota_status['message_count']}/{quota_status['daily_limit']}"
                    )
                    return {
                        "success": False,
                        "error": "quota_exceeded",
                        "skipped": True,
                        "quota_status": quota_status,
                    }

            # Build confirmation message based on action
            if action == "sent":
                message_body = "✅ Reply sent to customer!"
            elif action == "redrafting":
                message_body = f"🔄 Redrafting with your feedback:\n{details}"
            elif action == "rejected":
                message_body = "❌ Draft discarded. Handle manually."
            else:
                message_body = f"✓ Action: {action}"

            # Send confirmation
            message = self.client.messages.create(
                from_=self.whatsapp_number,
                to=f"whatsapp:{reviewer_phone}",
                body=message_body,
            )

            logger.info(f"Confirmation sent to {reviewer_phone}")

            # Increment quota if tracking is enabled
            if self.enable_quota_tracking:
                quota_result = await db.increment_whatsapp_quota()
                logger.info(
                    f"WhatsApp quota updated: {quota_result['message_count']}/{quota_result['daily_limit']} "
                    f"({quota_result['remaining']} remaining)"
                )

            return {
                "success": True,
                "message_sid": message.sid,
            }

        except TwilioRestException as e:
            if e.status == 429:
                logger.error(
                    f"Twilio rate limit exceeded (HTTP 429) sending confirmation: {e.msg}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error": "rate_limit_exceeded",
                    "skipped": True,
                }
            else:
                logger.error(
                    f"Twilio API error (HTTP {e.status}) sending confirmation: {e.msg}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error": "twilio_api_error",
                    "skipped": True,
                }

        except Exception as e:
            logger.error(f"Failed to send confirmation: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "skipped": True,
            }


# Singleton instance
_whatsapp_service: Optional[WhatsAppService] = None


def get_whatsapp_service() -> WhatsAppService:
    """Get or create WhatsApp service instance."""
    global _whatsapp_service
    if _whatsapp_service is None:
        _whatsapp_service = WhatsAppService()
    return _whatsapp_service
