from __future__ import annotations

from fastapi import FastAPI


def include_all_routers(app: FastAPI) -> None:
    from bigrag.routers._upload_sessions_file import (
        upload_session_file as _upload_session_file,  # noqa: F401
    )
    from bigrag.routers.admin_access import router as admin_access_router
    from bigrag.routers.admin_api_keys import router as admin_api_keys_router
    from bigrag.routers.admin_audit import router as admin_audit_router
    from bigrag.routers.admin_backups import router as admin_backups_router
    from bigrag.routers.admin_connectors import router as admin_connectors_router
    from bigrag.routers.admin_realtime import router as admin_realtime_router
    from bigrag.routers.admin_settings import router as admin_settings_router
    from bigrag.routers.admin_users import router as admin_users_router
    from bigrag.routers.admin_vector_storage import router as admin_vector_storage_router
    from bigrag.routers.analytics import router as analytics_router
    from bigrag.routers.auth import router as auth_router
    from bigrag.routers.chat import router as chat_router
    from bigrag.routers.collection_events import router as _collection_events_router  # noqa: F401
    from bigrag.routers.collections import router as collections_router
    from bigrag.routers.collections_embedding import (
        reembed_collection as _reembed_collection,  # noqa: F401
    )
    from bigrag.routers.connectors import router as connectors_router
    from bigrag.routers.connectors_oauth import router as connectors_oauth_router
    from bigrag.routers.documents import router as documents_router
    from bigrag.routers.documents_batch import router as documents_batch_router  # noqa: F401
    from bigrag.routers.documents_global import global_router as documents_global_router
    from bigrag.routers.embedding_presets import router as embedding_presets_router
    from bigrag.routers.evaluation import router as evaluation_router
    from bigrag.routers.health import router as health_router
    from bigrag.routers.mcp_servers import router as mcp_servers_router
    from bigrag.routers.preferences import router as preferences_router
    from bigrag.routers.query import router as query_router
    from bigrag.routers.upload_sessions import router as upload_sessions_router
    from bigrag.routers.usage import router as usage_router
    from bigrag.routers.vectors import router as vectors_router
    from bigrag.routers.webhooks import router as webhooks_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(preferences_router)
    app.include_router(admin_users_router)
    app.include_router(admin_api_keys_router)
    app.include_router(admin_connectors_router)
    app.include_router(admin_backups_router)
    app.include_router(admin_settings_router)
    app.include_router(admin_access_router)
    app.include_router(admin_vector_storage_router)
    app.include_router(admin_realtime_router)
    app.include_router(mcp_servers_router)
    app.include_router(admin_audit_router)
    app.include_router(embedding_presets_router)
    app.include_router(collections_router)
    app.include_router(connectors_router)
    app.include_router(connectors_oauth_router)
    app.include_router(documents_router)
    app.include_router(documents_global_router)
    app.include_router(upload_sessions_router)
    app.include_router(chat_router)
    app.include_router(query_router)
    app.include_router(vectors_router)
    app.include_router(analytics_router)
    app.include_router(evaluation_router)
    app.include_router(usage_router)
    app.include_router(webhooks_router)
