"""Application configuration and environment management."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    environment: str = Field(default="development", description="Runtime environment")
    log_level: str = Field(default="INFO", description="Logging level")
    app_name: str = Field(default="Hermes v2", description="Application name")
    app_version: str = Field(default="2.0.0", description="Application version")

    # Database (Supabase Postgres)
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_service_role_key: str = Field(..., description="Supabase service role key")
    database_url: str = Field(..., description="Direct Postgres connection string")

    # LLM Configuration
    llm_provider: str = Field(
        default="gemini",
        description="LLM provider to use (anthropic or gemini)",
    )

    # Anthropic Claude (optional if using Gemini)
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key (required if llm_provider=anthropic)",
    )
    claude_model: str = Field(
        default="claude-3-haiku-20240307",
        description="Claude model for extraction and drafting",
    )

    # Google Gemini
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key (required if llm_provider=gemini)",
    )
    gemini_model: str = Field(
        default="gemini-3.6-flash",
        description="Gemini model for extraction and drafting",
    )

    # Email (SendGrid)
    sendgrid_api_key: str = Field(..., description="SendGrid API key")
    intake_email_address: str = Field(..., description="Dedicated intake email address")
    from_email: str = Field(
        ..., description="From email for outbound replies (must be verified in SendGrid)"
    )
    from_name: str = Field(default="Support Team", description="From name for outbound replies")

    # Outlook inbox (Microsoft Graph, delegated access for personal accounts)
    outlook_polling_enabled: bool = Field(
        default=False, description="Poll the configured Outlook Inbox through Microsoft Graph"
    )
    outlook_client_id: Optional[str] = Field(
        default=None, description="Microsoft Entra application (client) ID"
    )
    outlook_token_cache: Optional[str] = Field(
        default=None,
        description="Initial base64-encoded MSAL token cache used to seed Supabase",
    )
    outlook_poll_interval_seconds: int = Field(
        default=60, ge=30, description="Seconds between Outlook Inbox polls"
    )

    # Gmail inbox (Gmail API, delegated OAuth access for personal accounts)
    gmail_polling_enabled: bool = Field(
        default=False, description="Poll the configured Gmail Inbox through the Gmail API"
    )
    gmail_token_cache: Optional[str] = Field(
        default=None,
        description="Initial base64-encoded Gmail OAuth credentials used to seed Supabase",
    )
    gmail_poll_interval_seconds: int = Field(
        default=60, ge=30, description="Seconds between Gmail Inbox polls"
    )

    # WhatsApp (Twilio)
    twilio_account_sid: str = Field(..., description="Twilio account SID")
    twilio_auth_token: str = Field(..., description="Twilio auth token")
    twilio_whatsapp_number: str = Field(
        ..., description="Twilio WhatsApp number (format: whatsapp:+1234567890)"
    )

    # LangGraph
    langgraph_checkpoint_namespace: str = Field(
        default="hermes_checkpoints", description="LangGraph checkpoint namespace"
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of the allowed values."""
        allowed = {"development", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v_upper


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
