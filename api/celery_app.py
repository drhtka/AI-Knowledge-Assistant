from __future__ import annotations

import logging
from functools import lru_cache

from api.settings import (
    CELERY_BROKER_URL,
    CELERY_ENABLED,
    CELERY_REINDEX_QUEUE,
    CELERY_RESULT_BACKEND,
)

logger = logging.getLogger("ai_knowledge_assistant.celery_app")


@lru_cache(maxsize=1)
def get_celery_app() -> object | None:
    # Celery is an optional dependency: reindex must keep working through the
    # in-process FastAPI background task path when Celery is disabled or the
    # `celery` package/broker is unavailable.
    if not CELERY_ENABLED:
        return None

    try:
        from celery import Celery
    except ImportError:
        logger.warning(
            "CELERY_ENABLED is set but the celery package is not installed; "
            "falling back to in-process background reindex.",
            extra={"event": "celery_package_unavailable"},
        )
        return None

    app = Celery(
        "ai_knowledge_assistant",
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND,
        include=["api.tasks"],
    )
    app.conf.update(
        task_default_queue=CELERY_REINDEX_QUEUE,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = get_celery_app()
