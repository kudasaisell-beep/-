import logging
from config import SENTRY_DSN

logger = logging.getLogger(__name__)

if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[AsyncioIntegration()],
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            # Таймауты и ретраи для регионов с ограничениями
            transport_options={
                "timeout": 5,
                "max_retries": 2,
            },
        )
        logger.info("Sentry initialized")
    except Exception as e:
        logger.warning(f"Sentry init failed (возможно 403 из вашего региона): {e}")
        logger.warning("Бот продолжает работу без Sentry.")
else:
    logger.info("SENTRY_DSN not set, skipping Sentry")
