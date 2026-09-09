"""Hermes v2 - AI Communications Agent FastAPI Application."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.health import router as health_router
from src.api.webhooks import router as webhooks_router
from src.core.config import get_settings
from src.services.gmail import GmailMailService
from src.services.outlook import OutlookMailService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_database_migrations() -> None:
    """Ensure integration_tokens table exists before application starts."""
    settings = get_settings()

    try:
        logger.info("🔧 Running database migrations...")
        conn = await asyncpg.connect(settings.database_url)

        # Check if integration_tokens table exists
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'integration_tokens'
            )
            """
        )

        if exists:
            logger.info("✅ integration_tokens table already exists")
        else:
            logger.info("📝 Creating integration_tokens table...")

            # Create the table
            await conn.execute(
                """
                CREATE TABLE integration_tokens (
                    provider TEXT PRIMARY KEY,
                    token_cache TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            # Create the updated_at trigger function
            await conn.execute(
                """
                CREATE OR REPLACE FUNCTION update_integration_tokens_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )

            # Create the trigger
            await conn.execute(
                """
                DROP TRIGGER IF EXISTS update_integration_tokens_updated_at ON integration_tokens;
                CREATE TRIGGER update_integration_tokens_updated_at
                    BEFORE UPDATE ON integration_tokens
                    FOR EACH ROW
                    EXECUTE FUNCTION update_integration_tokens_updated_at();
                """
            )

            # Enable RLS
            await conn.execute(
                """
                ALTER TABLE integration_tokens ENABLE ROW LEVEL SECURITY;
                """
            )

            logger.info("✅ integration_tokens table created successfully")

        await conn.close()
        logger.info("✅ Database migrations complete")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Log level: {settings.log_level}")

    # Run database migrations before anything else
    await run_database_migrations()

    outlook_task: asyncio.Task | None = None
    gmail_task: asyncio.Task | None = None

    # Startup tasks
    if settings.outlook_polling_enabled:
        if not settings.outlook_client_id:
            raise RuntimeError("OUTLOOK_CLIENT_ID is required when Outlook polling is enabled")

        outlook_task = asyncio.create_task(OutlookMailService().run())
        logger.info("Outlook Inbox polling enabled")

    if settings.gmail_polling_enabled:
        gmail_task = asyncio.create_task(GmailMailService().run())
        logger.info("Gmail Inbox polling enabled")

    logger.info("Application startup complete")

    yield

    # Shutdown tasks
    if outlook_task:
        outlook_task.cancel()
        with suppress(asyncio.CancelledError):
            await outlook_task

    if gmail_task:
        gmail_task.cancel()
        with suppress(asyncio.CancelledError):
            await gmail_task

    logger.info("Application shutdown")


# Create FastAPI app
app = FastAPI(
    title="Hermes v2",
    description="AI Communications Agent (Email-to-WhatsApp Triage)",
    version="2.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
        },
    )


@app.get("/")
async def root():
    """Root endpoint."""
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
