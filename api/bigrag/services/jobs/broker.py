from __future__ import annotations

import asyncio
import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AsyncIO, Middleware

from bigrag import config as config_module
from bigrag.services.jobs.runtime_middleware import WorkerRuntimeMiddleware

INGESTION_QUEUE = "ingestion"
CONNECTORS_QUEUE = "connectors"
WEBHOOKS_QUEUE = "webhooks"
MAINTENANCE_QUEUE = "maintenance"
NAMESPACE = "bigrag:dramatiq"
WORKER_HEARTBEAT_KEY = "bigrag:dramatiq:worker:heartbeat"
WORKER_HEARTBEAT_KEY_PREFIX = "bigrag:dramatiq:worker:heartbeat:"
PERIODIC_SEED_KEY = "bigrag:dramatiq:periodic:startup_seed"


class _ConversionPoolMiddleware(Middleware):
    def after_worker_shutdown(self, _broker, _worker):
        from bigrag.services import conversion as conversion_module

        executor = conversion_module._executor
        if executor is None:
            return
        conversion_module._executor = None
        executor.shutdown(wait=True, cancel_futures=True)


broker = RedisBroker(url=config_module.settings.redis_url, namespace=NAMESPACE)
broker.add_middleware(AsyncIO())
broker.add_middleware(WorkerRuntimeMiddleware())
broker.add_middleware(_ConversionPoolMiddleware())

if os.environ.get("BIGRAG_WORKER_SEED_PERIODIC") == "1":
    from bigrag.services.jobs.periodic import PeriodicSeedMiddleware

    raw_queues = os.environ.get("BIGRAG_WORKER_PERIODIC_QUEUES")
    enabled_queues = (
        {queue for queue in raw_queues.split(",") if queue} if raw_queues is not None else None
    )
    broker.add_middleware(PeriodicSeedMiddleware(enabled_queues, PERIODIC_SEED_KEY))

dramatiq.set_broker(broker)


async def queue_size(queue_name: str) -> int:
    return int(await asyncio.to_thread(broker.do_qsize, queue_name))


def delayed_messages_key(queue_name: str) -> str:
    return f"{NAMESPACE}:{queue_name}.DQ.msgs"


def dead_letter_key(queue_name: str) -> str:
    return f"{NAMESPACE}:{queue_name}.XQ"


def worker_heartbeat_key(queue_name: str) -> str:
    return f"{WORKER_HEARTBEAT_KEY_PREFIX}{queue_name}"
