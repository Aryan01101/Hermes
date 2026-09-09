"""Webhook endpoints for email and WhatsApp."""

import logging
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ValidationError
from twilio.request_validator import RequestValidator

from src.core.config import get_settings
from src.services.database import get_database
from src.services.email import get_email_service
from src.services.inbound import process_inbound_email
from src.services.whatsapp import get_whatsapp_service
from src.workflows.graph import get_workflow_graph
from src.workflows.state import create_redraft_state

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Email Webhook (SendGrid Inbound Parse)
# =============================================================================


class EmailWebhookPayload(BaseModel):
    """SendGrid inbound email webhook payload."""

    from_email: str
    subject: str
    text: str
    html: str | None = None
    headers: str | None = None


@router.post("/email")
async def email_webhook(request: Request) -> Dict[str, Any]:
    """
    Receive inbound emails from SendGrid Inbound Parse webhook.

    SendGrid sends multipart/form-data, so we need to parse it differently.

    Flow:
    1. Parse email from SendGrid payload
    2. Extract Message-ID, In-Reply-To, References headers
    3. Find or create thread
    4. Create initial state and invoke LangGraph workflow
    5. Workflow will extract intent, draft reply, and send to WhatsApp
    6. Return success (workflow continues in background via checkpoints)

    Returns:
        Dict[str, Any]: Webhook response
    """
    try:
        # Parse form data from SendGrid
        form = await request.form()
        form_data = {key: value for key, value in form.items()}

        logger.info(f"Received email webhook from {form_data.get('from', 'unknown')}")

        # Parse the SendGrid form into the shared inbound-email format.
        email_service = get_email_service()
        parsed_email = email_service.parse_sendgrid_payload(form_data)
        return await process_inbound_email(parsed_email)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email webhook error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process email: {str(e)}",
        )


# =============================================================================
# WhatsApp Webhook (Twilio)
# =============================================================================


class WhatsAppMessage(BaseModel):
    """Twilio WhatsApp incoming message."""

    From: str  # Format: whatsapp:+1234567890
    To: str
    Body: str
    MessageSid: str
    OriginalRepliedMessageSid: str | None = None


async def parse_whatsapp_message(request: Request) -> tuple[WhatsAppMessage, bool]:
    """Parse a Twilio form webhook or a JSON request used by local tests."""
    content_type = request.headers.get("content-type", "")
    is_twilio_form = "application/x-www-form-urlencoded" in content_type

    if is_twilio_form:
        form_data = dict(await request.form())
        settings = get_settings()
        signature = request.headers.get("x-twilio-signature")

        if settings.environment == "production":
            validator = RequestValidator(settings.twilio_auth_token)
            if not signature or not validator.validate(
                str(request.url), form_data, signature
            ):
                raise HTTPException(status_code=403, detail="Invalid Twilio signature")

        payload = form_data
    else:
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid webhook payload") from exc

    try:
        return WhatsAppMessage.model_validate(payload), is_twilio_form
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


def whatsapp_response(payload: Dict[str, Any], is_twilio_form: bool) -> Dict[str, Any] | Response:
    """Return TwiML to Twilio while keeping JSON responses for local API tests."""
    if is_twilio_form:
        return Response(content="<Response/>", media_type="application/xml")
    return payload


@router.post("/whatsapp", response_model=None)
async def whatsapp_webhook(request: Request) -> Dict[str, Any] | Response:
    """
    Receive incoming WhatsApp messages from Twilio.

    Flow:
    1. Extract WhatsApp message details
    2. Parse reviewer response (APPROVE/FEEDBACK/REJECT)
    3. Find associated draft and thread
    4. Resume LangGraph workflow from checkpoint with reviewer action
    5. If FEEDBACK, create redraft state and restart workflow
    6. Return success

    Returns:
        Dict[str, Any]: Webhook response
    """
    try:
        message, is_twilio_form = await parse_whatsapp_message(request)
        logger.info(f"Received WhatsApp from {message.From}: {message.Body}")

        # Get services
        whatsapp_service = get_whatsapp_service()
        db = get_database()

        # Parse reviewer response
        parsed_response = whatsapp_service.parse_reviewer_response(message.Body)
        action = parsed_response["action"]
        feedback_text = parsed_response.get("feedback")

        if action == "unknown":
            # Send help message
            await whatsapp_service.send_confirmation(
                reviewer_phone=message.From.removeprefix("whatsapp:"),
                action="help",
                details="Please reply with: APPROVE, FEEDBACK: [text], or REJECT",
            )
            return whatsapp_response(
                {"success": True, "message": "Unknown action, help sent"}, is_twilio_form
            )

        # Extract reviewer phone number
        reviewer_phone = message.From.removeprefix("whatsapp:")

        # Get all active reviewers to find reviewer ID
        reviewers = await db.get_active_reviewers()
        reviewer = next(
            (
                r
                for r in reviewers
                if r["phone_number"].removeprefix("whatsapp:") == reviewer_phone
            ),
            None,
        )

        if not reviewer:
            logger.warning(f"Unknown reviewer: {reviewer_phone}")
            return whatsapp_response(
                {"success": False, "error": "Unknown reviewer"}, is_twilio_form
            )

        # Prefer Twilio's quote-reply SID; use the newest pending draft only for
        # bare replies that do not include one.
        if message.OriginalRepliedMessageSid:
            draft = await db.get_draft_by_whatsapp_sid(
                message.OriginalRepliedMessageSid
            )
        else:
            draft = await db.get_most_recent_pending_draft()

        if not draft or draft["status"] != "pending":
            logger.warning("No pending drafts found for reviewer response")
            await whatsapp_service.send_confirmation(
                reviewer_phone=reviewer_phone,
                action="help",
                details="No pending drafts found. All caught up!",
            )
            return whatsapp_response(
                {"success": False, "error": "No pending drafts"}, is_twilio_form
            )

        logger.info(
            f"Reviewer {reviewer['name']} action: {action} on draft {draft['id']}"
        )

        # Get workflow graph
        graph = get_workflow_graph()
        config = {"configurable": {"thread_id": str(draft["thread_id"])}}

        # Process based on action
        if action == "approve":
            # Resume workflow with approval action
            logger.info(f"Approving draft {draft['id']}")

            # Update state with reviewer action
            updated_state = {
                "reviewer_action": "approve",
                "draft_id": str(draft["id"]),
                "reviewer_phone": reviewer_phone,
            }

            # Resume workflow from checkpoint
            # This will trigger process_feedback_node → send_email_node
            result = await graph.ainvoke(updated_state, config)

            # Send confirmation
            await whatsapp_service.send_confirmation(
                reviewer_phone=reviewer_phone,
                action="sent",
            )

            return whatsapp_response(
                {
                    "success": True,
                    "action": "approved",
                    "draft_id": draft["id"],
                    "thread_id": draft["thread_id"],
                    "workflow_status": result.get("current_step"),
                },
                is_twilio_form,
            )

        elif action == "feedback":
            # Create redraft state and restart workflow
            logger.info(f"Requesting redraft for draft {draft['id']}")

            # Get current state from checkpoint
            state_snapshot = await graph.aget_state(config)
            existing_state = state_snapshot.values

            # Create redraft state with feedback
            redraft_state = create_redraft_state(
                existing_state=existing_state,
                reviewer_feedback=feedback_text,
            )

            # Mark old draft as rejected (replaced by new version)
            await db.update_draft_status(UUID(draft["id"]), "rejected")

            # Invoke workflow with redraft state
            # This will: draft_reply → send_to_reviewer → END (interrupt)
            result = await graph.ainvoke(redraft_state, config)

            # Send confirmation
            await whatsapp_service.send_confirmation(
                reviewer_phone=reviewer_phone,
                action="redrafting",
                details=feedback_text,
            )

            return whatsapp_response(
                {
                    "success": True,
                    "action": "feedback",
                    "old_draft_id": draft["id"],
                    "new_version": redraft_state["version_number"],
                    "thread_id": draft["thread_id"],
                    "workflow_status": result.get("current_step"),
                },
                is_twilio_form,
            )

        elif action == "reject":
            # Mark draft and thread as rejected
            logger.info(f"Rejecting draft {draft['id']}")

            # Update draft status
            await db.update_draft_status(UUID(draft["id"]), "rejected")

            # Update thread status
            await db.update_thread_status(UUID(draft["thread_id"]), "resolved")

            # Log event
            await db.log_event(
                event_type="reviewer_action",
                actor=f"reviewer:{reviewer['id']}",
                details={"draft_id": draft["id"]},
                thread_id=UUID(draft["thread_id"]),
                draft_id=UUID(draft["id"]),
            )

            # Send confirmation
            await whatsapp_service.send_confirmation(
                reviewer_phone=reviewer_phone,
                action="rejected",
            )

            return whatsapp_response(
                {
                    "success": True,
                    "action": "rejected",
                    "draft_id": draft["id"],
                    "thread_id": draft["thread_id"],
                },
                is_twilio_form,
            )

        return whatsapp_response({"success": True}, is_twilio_form)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process WhatsApp message: {str(e)}",
        )


@router.get("/whatsapp")
async def whatsapp_webhook_info() -> Dict[str, str]:
    """
    WhatsApp webhook information endpoint.

    Returns:
        Dict[str, str]: Endpoint documentation
    """
    return {
        "endpoint": "/webhooks/whatsapp",
        "method": "POST",
        "description": "Twilio WhatsApp webhook for receiving reviewer responses",
        "expected_fields": "From, To, Body, MessageSid, OriginalRepliedMessageSid",
    }
