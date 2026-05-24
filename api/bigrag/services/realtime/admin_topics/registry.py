from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from bigrag.services.realtime.admin_topics._session import TopicBuilder
from bigrag.services.realtime.admin_topics.access import (
    _access_logs_topic,
    _access_overview_topic,
    _audit_topic,
    _usage_topic,
)
from bigrag.services.realtime.admin_topics.connectors import (
    _connector_jobs_topic,
    _connector_sources_topic,
)
from bigrag.services.realtime.admin_topics.documents import (
    _batch_status_topic,
    _collection_stats_topic,
    _document_topic,
    _documents_topic,
    _upload_session_topic,
)
from bigrag.services.realtime.admin_topics.platform import (
    _backups_topic,
    _platform_readiness_topic,
    _platform_stats_topic,
)
from bigrag.services.realtime.specs import TopicError

_TOPIC_BUILDERS: dict[str, TopicBuilder] = {
    "admin.collections.documents": _documents_topic,
    "admin.collections.documents.batch_status": _batch_status_topic,
    "admin.collections.documents.detail": _document_topic,
    "admin.collections.upload_session": _upload_session_topic,
    "admin.collections.stats": _collection_stats_topic,
    "admin.connectors.sources": _connector_sources_topic,
    "admin.connectors.sync_jobs": _connector_jobs_topic,
    "admin.backups": _backups_topic,
    "admin.access.overview": _access_overview_topic,
    "admin.access.logs": _access_logs_topic,
    "admin.audit": _audit_topic,
    "admin.usage": _usage_topic,
    "admin.platform.stats": _platform_stats_topic,
    "admin.platform.readiness": _platform_readiness_topic,
}


def admin_topic(websocket: WebSocket, user: dict, topic: str, params: dict[str, Any]):
    builder = _TOPIC_BUILDERS.get(topic)
    if builder is None:
        raise TopicError("Unknown realtime topic")
    return builder(websocket, user, params)
