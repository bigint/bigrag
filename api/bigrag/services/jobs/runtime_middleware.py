from __future__ import annotations

from dramatiq.asyncio import get_event_loop_thread
from dramatiq.middleware import Middleware, MiddlewareError


class WorkerRuntimeMiddleware(Middleware):
    def before_worker_boot(self, broker, worker) -> None:
        event_loop_thread = get_event_loop_thread()
        if event_loop_thread is None:
            raise MiddlewareError("Worker runtime requires the Dramatiq AsyncIO middleware")
        from bigrag.services.jobs.runtime import ensure_worker_runtime

        try:
            event_loop_thread.run_coroutine(ensure_worker_runtime())
        except Exception as exc:
            raise MiddlewareError("Worker runtime initialization failed") from exc

    def after_worker_shutdown(self, broker, worker) -> None:
        event_loop_thread = get_event_loop_thread()
        if event_loop_thread is None:
            return
        from bigrag.services.jobs.runtime import stop_worker_heartbeat

        event_loop_thread.run_coroutine(stop_worker_heartbeat())
