from __future__ import annotations

from dramatiq.asyncio import get_event_loop_thread
from dramatiq.middleware import Middleware


class WorkerRuntimeMiddleware(Middleware):
    def before_worker_boot(self, broker, worker) -> None:
        event_loop_thread = get_event_loop_thread()
        if event_loop_thread is None:
            return
        from bigrag.services.jobs.runtime import ensure_worker_runtime

        event_loop_thread.run_coroutine(ensure_worker_runtime())
