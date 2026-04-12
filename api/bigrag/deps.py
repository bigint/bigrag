"""FastAPI dependency injection for service singletons.

Services are stored on app.state during lifespan and retrieved here via the
Request object. This eliminates the need for module-level singleton imports
in routers and simplifies test setup.
"""

from __future__ import annotations

from fastapi import Request

from bigrag.config import Settings
from bigrag.database import Database
from bigrag.db.session import get_session  # noqa: F401  — re-exported
from bigrag.services.queue import IngestionQueue
from bigrag.services.storage import StorageBackend
from bigrag.services.vector_store import VectorStore
from bigrag.services.webhook import WebhookDispatcher


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


def get_queue(request: Request) -> IngestionQueue:
    return request.app.state.queue


def get_storage(request: Request) -> StorageBackend:
    return request.app.state.storage


def get_webhook_dispatcher(request: Request) -> WebhookDispatcher:
    return request.app.state.webhook_dispatcher
