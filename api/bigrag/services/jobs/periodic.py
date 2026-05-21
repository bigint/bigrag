from __future__ import annotations

from dramatiq.middleware import Middleware


class PeriodicSeedMiddleware(Middleware):
    def __init__(self, enabled_queues: set[str] | None, seed_key: str) -> None:
        self.enabled_queues = enabled_queues
        self.seed_key = seed_key

    def after_worker_boot(self, broker, _worker) -> None:
        if not self._claim_seed(broker):
            return
        from bigrag.services.jobs.actors import seed_periodic_jobs

        seed_periodic_jobs(self.enabled_queues)

    def _claim_seed(self, broker) -> bool:
        try:
            return bool(broker.client.set(self.seed_key, b"1", ex=30, nx=True))
        except Exception:
            return True
