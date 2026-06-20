import logging

import structlog

from app.core.config import settings

_QUIET_LOGGER_NAMES = (
    "watchfiles",
    "watchfiles.main",
    "uvicorn.access",
    "sqlalchemy.engine",
    "httpx",
    "httpcore",
)


def configure_logging() -> None:
    root_level = getattr(logging, settings.app_log_level.upper(), logging.WARNING)
    logging.basicConfig(level=root_level, format="%(message)s")

    for name in _QUIET_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Start/Stop-Meldungen von Uvicorn behalten, ohne jeden HTTP-Request
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
