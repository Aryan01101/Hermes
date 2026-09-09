"""LangGraph state machine for email triage workflow."""

import logging
from typing import Dict
from uuid import UUID

import asyncpg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from src.services.database import get_database
from src.services.email import get_email_service
from src.services.llm import get_llm_service
from src.services.whatsapp import get_whatsapp_service
from src.workflows.state import EmailTriageState

logger = logging.getLogger(__name__)


# =============================================================================
# Node Functions
# =============================================================================


async def extract_intent_node(state: EmailTriageState) -> Dict:
    """
    Extract intent from customer email using Claude.

    Args:
        state: Current workflow state

    Returns:
        Updated state with intent data
    """
    logger.info(f"Extracting intent for thread {state['thread_id']}")

    llm_service = get_llm_service()

    # Extract intent
    intent_result = await llm_service.extract_intent(
        email_body=state["email_body"],
        subject=state["subject"],
    )

    if not intent_result["success"]:
        return {
            "current_step": "extract_intent",
            "error": f"Intent extraction failed: {intent_result.get('error')}",
        }

    intent_data = intent_result["intent"]
    intent_confidence = intent_data.get("confidence", 0.5)

    logger.info(f"Intent extracted with confidence {intent_confidence}")

    return {
        "intent_data": intent_data,
        "intent_confidence": intent_confidence,
        "current_step": "draft_reply",
        "error": None,
    }


async def draft_reply_node(state: EmailTriageState) -> Dict:
    """
    Draft reply using Claude, optionally incorporating feedback.

    Args:
        state: Current workflow state

    Returns:
        Updated state with draft content
    """
    logger.info(
        f"Drafting reply version {state['version_number']} for thread {state['thread_id']}"
    )

    llm_service = get_llm_service()
    db = get_database()

    # Get previous drafts if this is a redraft
    previous_drafts = None
    if state["retry_count"] > 0:
        # Fetch feedback history from database
        feedback_history = await db.get_feedback_history(UUID(state["thread_id"]))
        if feedback_history:
            previous_drafts = [
                {"content": f["feedback_text"]} for f in feedback_history
            ]

    # Draft reply
    draft_result = await llm_service.draft_reply(
        email_body=state["email_body"],
        subject=state["subject"],
        intent_data=state["intent_data"],
        previous_drafts=previous_drafts,
        feedback=state.get("reviewer_feedback"),
    )

    if not draft_result["success"]:
        return {
            "current_step": "draft_reply",
            "error": f"Draft generation failed: {draft_result.get('error')}",
        }

    draft_data = draft_result["draft"]
    draft_confidence = draft_data["confidence"]

    # Calculate overall confidence
    overall_confidence = llm_service.calculate_confidence_score(
        intent_confidence=state["intent_confidence"],
        draft_confidence=draft_confidence,
        has_previous_context=(state["retry_count"] > 0),
        has_feedback=bool(state.get("reviewer_feedback")),
    )

    logger.info(f"Draft generated with confidence {overall_confidence}")

    # Store draft in database
    draft_record = await db.create_draft(
        thread_id=UUID(state["thread_id"]),
        version_number=state["version_number"],
        content=draft_data["content"],
        confidence_score=overall_confidence,
    )

    return {
        "draft_id": str(draft_record["id"]),
        "draft_content": draft_data["content"],
        "draft_confidence": draft_confidence,
        "overall_confidence": overall_confidence,
        "current_step": "send_to_reviewer",
        "error": None,
    }


async def send_to_reviewer_node(state: EmailTriageState) -> Dict:
    """
    Send draft to reviewer via WhatsApp.

    Args:
        state: Current workflow state

    Returns:
        Updated state with WhatsApp message SID
    """
    logger.info(f"Sending draft {state['draft_id']} to reviewer via WhatsApp")

    whatsapp_service = get_whatsapp_service()
    db = get_database()

    # Get active reviewers
    reviewers = await db.get_active_reviewers()
    if not reviewers:
        return {
            "current_step": "send_to_reviewer",
            "error": "No active reviewers found",
        }

    # Send to first active reviewer (can be enhanced with load balancing)
    reviewer = reviewers[0]
    reviewer_phone = reviewer["phone_number"].removeprefix("whatsapp:")

    # Send WhatsApp message
    send_result = await whatsapp_service.send_draft_for_review(
        reviewer_phone=reviewer_phone,
        customer_email=state["customer_email"],
        subject=state["subject"],
        draft_content=state["draft_content"],
        confidence_score=state["overall_confidence"],
        thread_id=state["thread_id"],
        draft_id=state["draft_id"],
    )

    if not send_result["success"]:
        return {
            "current_step": "send_to_reviewer",
            "error": f"WhatsApp send failed: {send_result.get('error')}",
        }

    # Attach the WhatsApp SID to the draft record created in draft_reply_node.
    # Creating another record would violate the (thread_id, version_number) constraint.
    await db.update_draft_whatsapp_message_sid(
        UUID(state["draft_id"]), send_result["message_sid"]
    )
    await db.update_thread_status(UUID(state["thread_id"]), "pending_review")
    await db.log_event(
        event_type="draft_sent_to_whatsapp",
        actor="system",
        details={"message_sid": send_result["message_sid"]},
        thread_id=UUID(state["thread_id"]),
        draft_id=UUID(state["draft_id"]),
    )

    logger.info(f"Draft sent via WhatsApp. SID: {send_result['message_sid']}")

    return {
        "whatsapp_message_sid": send_result["message_sid"],
        "current_step": "await_review",
        "error": None,
    }


async def process_feedback_node(state: EmailTriageState) -> Dict:
    """
    Process reviewer feedback and determine next action.

    Args:
        state: Current workflow state

    Returns:
        Updated state with next step
    """
    logger.info(f"Processing reviewer action: {state['reviewer_action']}")

    db = get_database()

    # Record reviewer action
    await db.create_reviewer_action(
        draft_id=UUID(state["draft_id"]),
        reviewer_phone=state.get("reviewer_phone") or "unknown",
        action=state["reviewer_action"],
        feedback_text=state.get("reviewer_feedback"),
    )

    if state["reviewer_action"] == "approve":
        # Mark draft as approved
        await db.update_draft_status(UUID(state["draft_id"]), "approved")

        return {
            "current_step": "send_email",
            "error": None,
        }

    elif state["reviewer_action"] == "feedback":
        # Stay in await_review - will be restarted from checkpoint with new state
        logger.info("Feedback received, will redraft on resume")

        return {
            "current_step": "await_review",
            "error": None,
        }

    elif state["reviewer_action"] == "reject":
        # Mark draft as rejected
        await db.update_draft_status(UUID(state["draft_id"]), "rejected")

        return {
            "current_step": "complete",
            "error": "Draft rejected by reviewer",
        }

    else:
        return {
            "current_step": "await_review",
            "error": f"Unknown action: {state['reviewer_action']}",
        }


async def send_email_node(state: EmailTriageState) -> Dict:
    """
    Send approved reply to customer.

    Args:
        state: Current workflow state

    Returns:
        Updated state with completion status
    """
    logger.info(f"Sending approved reply for thread {state['thread_id']}")

    email_service = get_email_service()
    db = get_database()

    # Send email
    send_result = await email_service.send_email(
        to_email=state["customer_email"],
        subject=f"Re: {state['subject']}",
        text_body=state["draft_content"],
        in_reply_to=state["in_reply_to"] or state["message_id"],
        references=state["references"],
    )

    if not send_result["success"]:
        return {
            "current_step": "send_email",
            "error": f"Email send failed: {send_result.get('error')}",
        }

    # The schema uses "approved" as the final successful draft state.
    await db.update_draft_status(UUID(state["draft_id"]), "approved")

    # Update thread status
    await db.update_thread_status(UUID(state["thread_id"]), "resolved")

    # Log event
    await db.log_event(
        event_type="email_sent_to_customer",
        actor="system",
        details={
            "to": state["customer_email"],
            "subject": state["subject"],
            "message_id": send_result.get("message_id"),
        },
        thread_id=UUID(state["thread_id"]),
        draft_id=UUID(state["draft_id"]),
    )

    logger.info("Email sent successfully")

    return {
        "current_step": "complete",
        "error": None,
    }


# =============================================================================
# Conditional Edges
# =============================================================================


def should_continue_after_feedback(state: EmailTriageState) -> str:
    """
    Determine next step after processing feedback.

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    if state["reviewer_action"] == "approve":
        return "send_email"
    elif state["reviewer_action"] == "feedback":
        # Will be handled by redraft workflow
        return "await_review"
    elif state["reviewer_action"] == "reject":
        return END
    else:
        return "await_review"


# =============================================================================
# Graph Construction
# =============================================================================


def create_email_triage_graph(checkpointer: AsyncPostgresSaver) -> StateGraph:
    """
    Create the email triage state machine.

    Flow:
    1. extract_intent: Analyze email with Claude
    2. draft_reply: Generate reply with Claude
    3. send_to_reviewer: Send to WhatsApp
    4. await_review: INTERRUPT - wait for human approval
    5. process_feedback: Handle reviewer response
    6. send_email: Send approved reply (conditional)
    7. complete: End workflow

    Args:
        checkpointer: Postgres checkpointer for state persistence

    Returns:
        Compiled StateGraph
    """
    # Create graph
    workflow = StateGraph(EmailTriageState)

    # Add nodes
    workflow.add_node("extract_intent", extract_intent_node)
    workflow.add_node("draft_reply", draft_reply_node)
    workflow.add_node("send_to_reviewer", send_to_reviewer_node)
    workflow.add_node("process_feedback", process_feedback_node)
    workflow.add_node("send_email", send_email_node)

    # Set entry point
    workflow.set_entry_point("extract_intent")

    # Add edges
    workflow.add_edge("extract_intent", "draft_reply")
    workflow.add_edge("draft_reply", "send_to_reviewer")

    # After sending to reviewer, go to process_feedback (interrupts before it)
    # Will be resumed by WhatsApp webhook with reviewer action
    workflow.add_edge("send_to_reviewer", "process_feedback")

    # Conditional edge after processing feedback
    workflow.add_conditional_edges(
        "process_feedback",
        should_continue_after_feedback,
        {
            "send_email": "send_email",
            "await_review": END,  # Stay interrupted for redraft
            END: END,  # Rejected
        },
    )

    workflow.add_edge("send_email", END)

    # Compile with checkpointer
    return workflow.compile(checkpointer=checkpointer, interrupt_before=["process_feedback"])


# =============================================================================
# Graph Singleton
# =============================================================================

_graph_instance = None
_checkpointer_instance = None


async def get_workflow_graph():
    """Get or create workflow graph instance with async checkpointer."""
    global _graph_instance, _checkpointer_instance

    if _graph_instance is None:
        from src.core.config import get_settings

        settings = get_settings()

        # Create async connection pool for checkpointer
        pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=10,
        )

        # Create async Postgres checkpointer with pool
        _checkpointer_instance = AsyncPostgresSaver(pool)

        # Setup checkpoint tables (idempotent - safe to call multiple times)
        await _checkpointer_instance.setup()

        # Create graph
        _graph_instance = create_email_triage_graph(_checkpointer_instance)

    return _graph_instance
