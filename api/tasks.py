from __future__ import annotations

import logging

from api.celery_app import get_celery_app
from api.indexing_service import run_reindex_job_loop

logger = logging.getLogger("ai_knowledge_assistant.tasks")

_celery_app = get_celery_app()


if _celery_app is not None:

    @_celery_app.task(name="ai_knowledge_assistant.reindex_task", bind=True, max_retries=0)
    def reindex_task(self, trigger: str, started_at: str | None) -> None:
        # Runs the exact same reindex loop as the in-process background task
        # path, just on a Celery worker process instead of inside the web
        # process's event loop.
        try:
            run_reindex_job_loop(trigger, started_at)
        except Exception:
            logger.exception(
                "Celery reindex task failed.",
                extra={
                    "event": "celery_reindex_task_failed",
                    "context": {"trigger": trigger},
                },
            )
            raise
