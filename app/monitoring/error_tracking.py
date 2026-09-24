"""
Error tracking and external exception reporting setup (Phase 5 Monitoring).
Initializes Sentry if SENTRY_DSN is set; falls back to structured logging otherwise.
"""
import os
import logging

logger = logging.getLogger("ai_face_analyzer.monitoring.error_tracking")


def setup_error_tracking() -> bool:
    """
    Initialize Sentry error tracking if SENTRY_DSN is configured.
    Returns True if Sentry is active, False otherwise.
    """
    sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not sentry_dsn:
        logger.info("SENTRY_DSN not configured. Production error tracking active via local structured logging.")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from app.config import PIPELINE_VERSION

        environment = os.environ.get("ENVIRONMENT", "production")

        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            release=f"ai-face-analyzer@{PIPELINE_VERSION}",
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            send_default_pii=False,  # Privacy requirement: never send user selfie payloads to external Sentry
        )
        logger.info(f"Sentry error tracking successfully initialized (Env: {environment}, Release: {PIPELINE_VERSION})")
        return True
    except Exception as e:
        logger.warning(f"Failed to initialize Sentry error tracking: {e}")
        return False
