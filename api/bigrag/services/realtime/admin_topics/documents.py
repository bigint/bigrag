from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from bigrag.services.collections.stats import collection_stats_payload
from bigrag.services.document_batch import batch_status_payload
from bigrag.services.document_progress import TERMINAL_DOCUMENT_STATUSES
from bigrag.services.documents import get_document_payload, list_documents_payload
from bigrag.services.realtime.admin_topics._session import with_session
from bigrag.services.realtime.params import boolean, document_ids, integer, string
from bigrag.services.realtime.specs import SnapshotTopic, fixed
from bigrag.services.upload_sessions import upload_session_payload


def _documents_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    q = string(params, "q", max_length=200)
    status = string(params, "status")
    sort = string(params, "sort", default="created_at") or "created_at"
    order = string(params, "order", default="desc") or "desc"
    include_total = boolean(params, "include_total") or False
    limit = integer(params, "limit", default=100, minimum=1, maximum=1000)
    offset = integer(params, "offset", default=0, minimum=0)
    snapshot_topic = f"documents:list:{collection}"

    async def load():
        return await with_session(
            lambda session: list_documents_payload(
                session,
                collection_name=collection,
                q=q,
                status=status,
                sort=sort,
                order=order,
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=include_total,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(5.0), f"collection:{collection}")


def _batch_status_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    ids = document_ids(params.get("document_ids"))
    snapshot_topic = f"documents:batch:{collection}:{','.join(ids)}"

    async def load():
        return await with_session(
            lambda session: batch_status_payload(
                session,
                user=user,
                collection_name=collection,
                document_ids=ids,
            )
        )

    return SnapshotTopic(
        snapshot_topic,
        load,
        fixed(2.0),
        f"collection:{collection}",
        lambda payload: _batch_done(payload, len(ids)),
    )


def _document_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    document_id = string(params, "document_id", required=True, max_length=120)
    snapshot_topic = f"documents:detail:{collection}:{document_id}"

    async def load():
        return await with_session(
            lambda session: get_document_payload(
                session,
                user=user,
                collection_name=collection,
                document_id=document_id,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(2.0), document_id, _document_done)


def _upload_session_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    session_id = string(params, "session_id", required=True, max_length=120)
    snapshot_topic = f"upload-session:{collection}:{session_id}"

    async def load():
        return await with_session(
            lambda session: upload_session_payload(
                session,
                user=user,
                collection_name=collection,
                session_id=session_id,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(2.0), None, _upload_session_done)


def _collection_stats_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    snapshot_topic = f"collections:stats:{collection}"

    async def load():
        return await with_session(
            lambda session: collection_stats_payload(session, name=collection, use_cache=False)
        )

    return SnapshotTopic(snapshot_topic, load, fixed(10.0), f"collection:{collection}")


def _document_done(payload: Any) -> bool:
    return getattr(payload, "status", None) in TERMINAL_DOCUMENT_STATUSES


def _batch_done(payload: Any, expected_count: int) -> bool:
    documents = getattr(payload, "documents", [])
    terminal = all(
        getattr(document, "status", None) in TERMINAL_DOCUMENT_STATUSES for document in documents
    )
    if len(documents) < expected_count:
        return terminal
    return bool(documents) and terminal


def _upload_session_done(payload: Any) -> bool:
    return getattr(payload, "status", None) in {"complete", "failed", "canceled"}
