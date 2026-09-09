"""Shared processing for inbound mail from SendGrid and Microsoft Graph."""

import logging
from typing import Any, Dict
from uuid import UUID

from src.services.database import get_database
from src.services.email import get_email_service
from src.workflows.graph import get_workflow_graph
from src.workflows.state import create_initial_state

logger = logging.getLogger(__name__)


async def process_inbound_email(parsed_email: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update a thread, then run it until human review is required."""
    email_service = get_email_service()
    db = get_database()
    reply_content = email_service.extract_reply_content(parsed_email["text_body"])

    thread = None
    if parsed_email["message_id"]:
        thread = await db.get_thread_by_message_id(parsed_email["message_id"])
    if not thread and parsed_email["references"]:
        thread = await db.get_thread_by_references(parsed_email["references"])
    if not thread and parsed_email["in_reply_to"]:
        thread = await db.get_thread_by_message_id(parsed_email["in_reply_to"])

    if not thread:
        logger.info("Creating new thread for %s", parsed_email["from_email"])
        thread = await db.create_thread(
            customer_email=parsed_email["from_email"],
            subject=parsed_email["subject"],
            message_id=parsed_email["message_id"],
            in_reply_to=parsed_email["in_reply_to"],
            references=parsed_email["references"],
        )
    else:
        logger.info("Found existing thread %s", thread["id"])
        stale_count = await db.mark_drafts_stale(UUID(thread["id"]))
        if stale_count > 0:
            logger.info("Marked %s pending drafts as stale", stale_count)

    await db.log_event(
        event_type="email_received",
        actor="system",
        details={"from": parsed_email["from_email"], "subject": parsed_email["subject"]},
        thread_id=UUID(thread["id"]),
    )

    initial_state = create_initial_state(
        thread_id=str(thread["id"]),
        customer_email=parsed_email["from_email"],
        subject=parsed_email["subject"],
        email_body=reply_content,
        message_id=parsed_email["message_id"],
        in_reply_to=parsed_email["in_reply_to"],
        references=parsed_email["references"],
    )
    graph = await get_workflow_graph()
    config = {"configurable": {"thread_id": str(thread["id"])}}

    logger.info("Starting workflow for thread %s", thread["id"])
    result = await graph.ainvoke(initial_state, config)
    logger.info("Email processed successfully. Thread: %s", thread["id"])

    return {
        "success": True,
        "thread_id": thread["id"],
        "workflow_status": "started",
        "current_step": result.get("current_step"),
    }
