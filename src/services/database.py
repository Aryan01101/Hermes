"""Supabase database client and connection management."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from supabase import Client, create_client

from src.core.config import get_settings


class DatabaseService:
    """Service for interacting with Supabase Postgres database."""

    def __init__(self) -> None:
        """Initialize database service with Supabase client."""
        settings = get_settings()
        self.client: Client = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_role_key,
        )

    # =========================================================================
    # Threads
    # =========================================================================

    async def create_thread(
        self,
        customer_email: str,
        subject: str,
        message_id: str,
        in_reply_to: Optional[str] = None,
        references: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new email thread."""
        data = {
            "customer_email": customer_email,
            "subject": subject,
            "message_id": message_id,
            "in_reply_to": in_reply_to,
            "references": references or [],
        }
        response = self.client.table("threads").insert(data).execute()
        return response.data[0] if response.data else {}

    async def get_thread_by_message_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get thread by Message-ID."""
        response = self.client.table("threads").select("*").eq("message_id", message_id).execute()
        return response.data[0] if response.data else None

    async def get_thread_by_references(self, references: List[str]) -> Optional[Dict[str, Any]]:
        """Find thread by checking if any reference matches existing message_id."""
        if not references:
            return None

        response = (
            self.client.table("threads").select("*").in_("message_id", references).execute()
        )
        return response.data[0] if response.data else None

    async def update_thread_status(self, thread_id: UUID, status: str) -> Dict[str, Any]:
        """Update thread status."""
        response = (
            self.client.table("threads")
            .update({"status": status})
            .eq("id", str(thread_id))
            .execute()
        )
        return response.data[0] if response.data else {}

    # =========================================================================
    # Drafts
    # =========================================================================

    async def create_draft(
        self,
        thread_id: UUID,
        version_number: int,
        content: str,
        confidence_score: float,
        whatsapp_message_sid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new draft version."""
        data = {
            "thread_id": str(thread_id),
            "version_number": version_number,
            "content": content,
            "confidence_score": confidence_score,
            "whatsapp_message_sid": whatsapp_message_sid,
        }
        response = self.client.table("drafts").insert(data).execute()
        return response.data[0] if response.data else {}

    async def get_draft_by_whatsapp_sid(self, whatsapp_sid: str) -> Optional[Dict[str, Any]]:
        """Get draft by WhatsApp message SID for reply-to-quote."""
        response = (
            self.client.table("drafts")
            .select("*")
            .eq("whatsapp_message_sid", whatsapp_sid)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_latest_draft(self, thread_id: UUID) -> Optional[Dict[str, Any]]:
        """Get the latest active draft for a thread."""
        response = (
            self.client.table("drafts")
            .select("*")
            .eq("thread_id", str(thread_id))
            .in_("status", ["pending", "approved"])
            .order("version_number", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_most_recent_pending_draft(self) -> Optional[Dict[str, Any]]:
        """Return the newest draft that is awaiting reviewer action."""
        response = (
            self.client.table("drafts")
            .select("*")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def mark_drafts_stale(self, thread_id: UUID) -> int:
        """Mark all pending drafts as stale (trailing email edge case)."""
        response = (
            self.client.table("drafts")
            .update({"status": "stale"})
            .eq("thread_id", str(thread_id))
            .eq("status", "pending")
            .execute()
        )
        return len(response.data) if response.data else 0

    async def update_draft_status(self, draft_id: UUID, status: str) -> Dict[str, Any]:
        """Update draft status."""
        response = (
            self.client.table("drafts").update({"status": status}).eq("id", str(draft_id)).execute()
        )
        return response.data[0] if response.data else {}

    async def update_draft_whatsapp_message_sid(
        self, draft_id: UUID, whatsapp_message_sid: str
    ) -> Dict[str, Any]:
        """Attach the Twilio SID to an existing draft for quote-reply matching."""
        response = (
            self.client.table("drafts")
            .update({"whatsapp_message_sid": whatsapp_message_sid})
            .eq("id", str(draft_id))
            .execute()
        )
        return response.data[0] if response.data else {}

    # =========================================================================
    # Reviewer Actions
    # =========================================================================

    async def create_reviewer_action(
        self,
        draft_id: UUID,
        reviewer_phone: str,
        action: str,
        feedback_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a reviewer action."""
        data = {
            "draft_id": str(draft_id),
            "reviewer_phone": reviewer_phone,
            "action": action,
            "feedback_text": feedback_text,
        }
        response = self.client.table("reviewer_actions").insert(data).execute()
        return response.data[0] if response.data else {}

    async def get_feedback_history(self, thread_id: UUID) -> List[Dict[str, Any]]:
        """Get all feedback for a thread (for redraft context)."""
        response = (
            self.client.table("reviewer_actions")
            .select("*, drafts!inner(thread_id)")
            .eq("drafts.thread_id", str(thread_id))
            .eq("action", "feedback")
            .order("created_at", desc=False)
            .execute()
        )
        return response.data if response.data else []

    # =========================================================================
    # Reviewers
    # =========================================================================

    async def get_active_reviewers(self) -> List[Dict[str, Any]]:
        """Get all active reviewers."""
        response = self.client.table("reviewers").select("*").eq("active", True).execute()
        return response.data if response.data else []

    # =========================================================================
    # Integration Tokens
    # =========================================================================

    async def get_integration_token(self, provider: str) -> Optional[str]:
        """Return the persisted OAuth token cache for an integration."""
        response = (
            self.client.table("integration_tokens")
            .select("token_cache")
            .eq("provider", provider)
            .limit(1)
            .execute()
        )
        return response.data[0]["token_cache"] if response.data else None

    async def upsert_integration_token(self, provider: str, token_cache: str) -> None:
        """Persist a refreshed OAuth token cache for an integration."""
        self.client.table("integration_tokens").upsert(
            {"provider": provider, "token_cache": token_cache},
            on_conflict="provider",
        ).execute()

    async def add_reviewer(self, phone_number: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Add a new reviewer."""
        data = {"phone_number": phone_number, "name": name}
        response = self.client.table("reviewers").insert(data).execute()
        return response.data[0] if response.data else {}

    # =========================================================================
    # Audit Log
    # =========================================================================

    async def log_event(
        self,
        event_type: str,
        actor: str,
        details: Dict[str, Any],
        thread_id: Optional[UUID] = None,
        draft_id: Optional[UUID] = None,
        reviewer_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Write an event to the audit log."""
        data = {
            "event_type": event_type,
            "actor": actor,
            "details": details,
            "thread_id": str(thread_id) if thread_id else None,
            "draft_id": str(draft_id) if draft_id else None,
            "reviewer_id": str(reviewer_id) if reviewer_id else None,
        }
        response = self.client.table("audit_log").insert(data).execute()
        return response.data[0] if response.data else {}


# Singleton instance
_db_service: Optional[DatabaseService] = None


def get_database() -> DatabaseService:
    """Get or create database service instance."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
