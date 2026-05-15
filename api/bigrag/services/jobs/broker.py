from __future__ import annotations

import asyncio

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AsyncIO

from bigrag import config as config_module

INGESTION_QUEUE = "ingestion"
CONNECTORS_QUEUE = "connectors"
WEBHOOKS_QUEUE = "webhooks"
BACKUPS_QUEUE = "backups"
MAINTENANCE_QUEUE = "maintenance"
NAMESPACE = "bigrag:dramatiq"
WORKER_HEARTBEAT_KEY = "bigrag:dramatiq:worker:heartbeat"

broker = RedisBroker(url=config_module.settings.redis_url, namespace=NAMESPACE)
broker.add_middleware(AsyncIO())
dramatiq.set_broker(broker)


async def queue_size(queue_name: str) -> int:
    return int(await asyncio.to_thread(broker.do_qsize, queue_name))


def delayed_messages_key(queue_name: str) -> str:
    return f"{NAMESPACE}:{queue_name}.DQ.msgs"


def dead_letter_key(queue_name: str) -> str:
    return f"{NAMESPACE}:{queue_name}.XQ"
