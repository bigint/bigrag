# SQLAlchemy 2 Async Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hand-rolled `asyncpg` raw-SQL layer with SQLAlchemy 2.x async ORM + asyncpg driver + Alembic migrations while preserving runtime behavior and performance.

**Architecture:** Introduce a new `bigrag.db` package housing the async engine, session factory, declarative base, and 14 ORM models. Replace the `Database` class with a thin `engine`/`session_factory` pair wired through FastAPI dependencies. Replace the `MIGRATIONS` list with Alembic, bootstrapping existing production DBs via `alembic stamp`. Migrate each router/service to session-based queries. Keep asyncpg for performance; keep advisory-lock semantics during migration run.

**Tech Stack:** SQLAlchemy 2.0 (async) · asyncpg · Alembic · FastAPI · Pydantic v2 · Python 3.11+

---

## File Structure

```
api/
├── alembic.ini                    # Alembic config (sync URL for offline, async for online)
├── alembic/
│   ├── env.py                     # async env.py with advisory-lock
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py # Full current schema as of 2026-04-12
└── bigrag/
    ├── db/
    │   ├── __init__.py            # re-exports: Base, all models, session, engine, get_session
    │   ├── base.py                # DeclarativeBase, type annotations (UUIDpk, TSTZ, JSONB dict)
    │   ├── engine.py              # configure/close async engine + session_factory
    │   ├── session.py             # FastAPI dependency: get_session
    │   ├── bootstrap.py           # alembic stamp/upgrade logic on startup
    │   └── models.py              # ALL 14 tables as ORM models (single file, cohesive)
    ├── database.py                # DELETE once migration complete
    ├── deps.py                    # MODIFIED: expose get_session
    ├── main.py                    # MODIFIED: wire engine.configure + bootstrap
    ├── routers/*.py               # MODIFIED: each uses `session: AsyncSession = Depends(get_session)`
    ├── services/*.py              # MODIFIED: services accept session or use session_factory()
    └── middleware/auth.py         # MODIFIED: uses session
```

**Why one `models.py`:** 14 related tables with FKs across each other. Splitting into per-entity files creates painful circular-import dances and scatters foreign-key references. A single 400-line models file stays readable, aligns with langflow/phoenix conventions, and keeps the schema diffable.

**Why no repository layer:** Every surveyed comparable project (Phoenix, langflow, mlflow, OpenHands) inlines ORM calls into route handlers. A repository layer would add ceremony without hiding the ORM that's already the abstraction. Keep query sites next to the route logic that owns the business rule.

---

## Task 1: Dependencies and scaffold

**Files:**
- Modify: `api/pyproject.toml`
- Create: `api/bigrag/db/__init__.py`
- Create: `api/bigrag/db/base.py`
- Create: `api/bigrag/db/engine.py`
- Create: `api/bigrag/db/session.py`

- [ ] **Step 1.1: Add dependencies**

Modify `api/pyproject.toml` dependencies block — add:
```toml
"sqlalchemy[asyncio]>=2.0.36",
"alembic>=1.14.0",
```

- [ ] **Step 1.2: Install**

Run: `cd api && uv sync`

- [ ] **Step 1.3: Create `api/bigrag/db/base.py`**

```python
"""Declarative base and reusable column type annotations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    """All ORM models inherit from this."""

    type_annotation_map = {dict: JSONB, list: JSONB}


UUIDpk = Annotated[
    UUID,
    mapped_column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
]
TS = Annotated[
    datetime,
    mapped_column(sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
]
TSupd = Annotated[
    datetime,
    mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        onupdate=sa.text("now()"),
        nullable=False,
    ),
]
```

- [ ] **Step 1.4: Create `api/bigrag/db/engine.py`**

```python
"""Async engine + session factory lifecycle."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from bigrag.logging import get_logger

logger = get_logger("bigrag.db")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _normalize_url(dsn: str) -> tuple[str, dict]:
    connect_args: dict = {}
    if "sslmode=disable" in dsn:
        dsn = dsn.replace("?sslmode=disable", "").replace("&sslmode=disable", "")
        connect_args["ssl"] = False
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql+asyncpg://", 1)
    return dsn, connect_args


async def configure(database_url: str, pool_min: int = 5, pool_max: int = 50) -> None:
    global _engine, _session_factory
    url, connect_args = _normalize_url(database_url)
    _engine = create_async_engine(
        url,
        pool_size=pool_max,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
        future=True,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    logger.info(f"SQLAlchemy engine ready (pool_size={pool_max})")


def engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("db.engine not configured — call configure() first")
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("db.session_factory not configured — call configure() first")
    return _session_factory


async def close() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    logger.info("SQLAlchemy engine closed")
```

- [ ] **Step 1.5: Create `api/bigrag/db/session.py`**

```python
"""FastAPI session dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.engine import session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session
```

- [ ] **Step 1.6: Create `api/bigrag/db/__init__.py`**

```python
"""bigRAG database layer — SQLAlchemy 2 async."""

from bigrag.db.base import TS, TSupd, UUIDpk, Base
from bigrag.db.engine import close, configure, engine, session_factory
from bigrag.db.session import get_session

__all__ = [
    "Base",
    "TS",
    "TSupd",
    "UUIDpk",
    "close",
    "configure",
    "engine",
    "get_session",
    "session_factory",
]
```

- [ ] **Step 1.7: Commit**

```bash
git add api/pyproject.toml api/uv.lock api/bigrag/db/
git commit -m "feat: scaffold SQLAlchemy async engine and session factory"
```

---

## Task 2: Define all 14 ORM models

**Files:**
- Create: `api/bigrag/db/models.py`

Single file, all models. Column names, types, defaults, constraints, and indexes must exactly mirror the current schema in `api/bigrag/database.py` MIGRATIONS array.

- [ ] **Step 2.1: Write `api/bigrag/db/models.py`**

Full content (every table the MIGRATIONS array built):

```python
"""All ORM models for the bigRAG metadata database.

Mirrors the schema built by the legacy MIGRATIONS array. Any structural
change must go through Alembic; do not edit this file without generating
a migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bigrag.db.base import TS, TSupd, Base, UUIDpk


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUIDpk]
    email: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    role: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint("role IN ('admin', 'member')", name="users_role_check"),
        nullable=False,
        server_default="member",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        sa.Index("idx_sessions_user_id", "user_id"),
        sa.Index("idx_sessions_expires_at", "expires_at"),
    )

    id: Mapped[UUIDpk]
    user_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_at: Mapped[TS]


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        sa.Index("idx_api_keys_user_id", "user_id"),
        sa.Index("idx_api_keys_expires_at", "expires_at"),
        sa.Index("idx_api_keys_active", "active"),
        sa.Index("idx_api_keys_prefix", "prefix"),
    )

    id: Mapped[UUIDpk]
    user_id: Mapped[Optional[UUID]] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    prefix: Mapped[str] = mapped_column(sa.Text, nullable=False)
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    rate_limits: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    expires_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (sa.Index("idx_collections_name", "name"),)

    id: Mapped[UUIDpk]
    name: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    embedding_provider: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="openai")
    embedding_model: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="text-embedding-3-small")
    embedding_api_key: Mapped[Optional[str]] = mapped_column(sa.Text)
    embedding_base_url: Mapped[Optional[str]] = mapped_column(sa.Text)
    dimension: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("1536"))
    chunk_size: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("512"))
    chunk_overlap: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("50"))
    chunk_strategy: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="paragraph")
    document_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    default_top_k: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("10"))
    default_min_score: Mapped[Optional[float]] = mapped_column(sa.Double)
    default_search_mode: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="semantic")
    reranking_enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    reranking_model: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="rerank-v3.5")
    reranking_api_key: Mapped[Optional[str]] = mapped_column(sa.Text)
    index_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="IVF_FLAT")
    tenant_field: Mapped[Optional[str]] = mapped_column(sa.Text)
    metadata_schema: Mapped[Optional[dict]] = mapped_column(JSONB)
    redact_pii: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    moderation_enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        sa.Index("idx_documents_collection_id", "collection_id"),
        sa.Index("idx_documents_status", "status"),
        sa.Index("idx_documents_created_at", "created_at"),
        sa.Index("idx_documents_collection_hash", "collection_id", "content_hash"),
    )

    id: Mapped[UUIDpk]
    collection_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(sa.Text, nullable=False)
    file_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    file_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, server_default=sa.text("0"))
    file_path: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    chunk_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    token_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    content_hash: Mapped[Optional[str]] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="documents_status_check",
        ),
        nullable=False,
        server_default="pending",
    )
    error_message: Mapped[Optional[str]] = mapped_column(sa.Text)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[UUIDpk]
    url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    secret: Mapped[str] = mapped_column(sa.Text, nullable=False)
    events: Mapped[list[str]] = mapped_column(ARRAY(sa.Text), nullable=False)
    collections: Mapped[Optional[list[str]]] = mapped_column(ARRAY(sa.Text))
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    created_by: Mapped[Optional[UUID]] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        sa.Index("idx_webhook_deliveries_webhook_id", "webhook_id"),
        sa.Index("idx_webhook_deliveries_status", "status"),
    )

    id: Mapped[UUIDpk]
    webhook_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[str] = mapped_column(sa.Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name="webhook_deliveries_status_check",
        ),
        nullable=False,
        server_default="pending",
    )
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    last_status_code: Mapped[Optional[int]] = mapped_column(sa.Integer)
    last_error: Mapped[Optional[str]] = mapped_column(sa.Text)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[TS]
    completed_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))


class QueryLog(Base):
    __tablename__ = "query_log"
    __table_args__ = (
        sa.Index("idx_query_log_collection", "collection_name"),
        sa.Index("idx_query_log_created_at", "created_at"),
    )

    id: Mapped[UUIDpk]
    collection_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    query: Mapped[str] = mapped_column(sa.Text, nullable=False)
    top_k: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    result_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    avg_score: Mapped[Optional[float]] = mapped_column(sa.Double)
    latency_ms: Mapped[Optional[float]] = mapped_column(sa.Double)
    search_mode: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="semantic")
    created_at: Mapped[TS]


class S3IngestJob(Base):
    __tablename__ = "s3_ingest_jobs"
    __table_args__ = (sa.Index("idx_s3_ingest_jobs_status", "status"),)

    id: Mapped[UUIDpk]
    collection_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    collection_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    bucket: Mapped[str] = mapped_column(sa.Text, nullable=False)
    prefix: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="")
    region: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="us-east-1")
    endpoint_url: Mapped[Optional[str]] = mapped_column(sa.Text)
    access_key: Mapped[Optional[str]] = mapped_column(sa.Text)
    secret_key: Mapped[Optional[str]] = mapped_column(sa.Text)
    no_sign_request: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    file_types: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    status: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint(
            "status IN ('pending', 'listing', 'ingesting', 'complete', 'failed')",
            name="s3_ingest_jobs_status_check",
        ),
        nullable=False,
        server_default="pending",
    )
    total_found: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    total_ingested: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    total_skipped: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    error_message: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class EmbeddingPreset(Base):
    __tablename__ = "embedding_presets"
    __table_args__ = (sa.Index("idx_embedding_presets_name", "name"),)

    id: Mapped[UUIDpk]
    name: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(
        sa.Text,
        sa.CheckConstraint(
            "provider IN ('openai', 'cohere')",
            name="embedding_presets_provider_check",
        ),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(sa.Text, nullable=False)
    api_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(sa.Text)
    dimension: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[TS]
    updated_at: Mapped[TSupd]


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    updated_at: Mapped[TSupd]


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        sa.Index("idx_audit_actor", "actor_id"),
        sa.Index("idx_audit_action", "action"),
        sa.Index("idx_audit_created_at", "created_at", postgresql_using="btree"),
    )

    id: Mapped[UUIDpk]
    actor_id: Mapped[Optional[UUID]] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_email: Mapped[Optional[str]] = mapped_column(sa.Text)
    api_key_id: Mapped[Optional[UUID]] = mapped_column(
        sa.ForeignKey("api_keys.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(sa.Text)
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    ip: Mapped[Optional[str]] = mapped_column(sa.Text)
    user_agent: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[TS]


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"
    __table_args__ = (sa.Index("idx_embedding_cache_last_hit", "last_hit_at"),)

    content_hash: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    model_key: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    vector: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    dimension: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[TS]
    last_hit_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )
```

- [ ] **Step 2.2: Smoke-test model import**

Run: `cd api && uv run python -c "from bigrag.db.models import *; from bigrag.db.base import Base; print(sorted(Base.metadata.tables.keys()))"`
Expected: prints 13 table names alphabetically.

- [ ] **Step 2.3: Commit**

```bash
git add api/bigrag/db/models.py
git commit -m "feat: add SQLAlchemy ORM models for all 13 metadata tables"
```

---

## Task 3: Alembic setup + initial migration

**Files:**
- Create: `api/alembic.ini`
- Create: `api/alembic/env.py`
- Create: `api/alembic/script.py.mako`
- Create: `api/alembic/versions/0001_initial_schema.py`
- Create: `api/bigrag/db/bootstrap.py`

- [ ] **Step 3.1: Create `api/alembic.ini`**

```ini
[alembic]
script_location = alembic
file_template = %%(rev)s_%%(slug)s
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3.2: Create `api/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 3.3: Create `api/alembic/env.py`**

```python
"""Alembic env — async, reads database URL from bigrag settings,
holds an advisory lock during migrations so multi-instance rollouts
don't race the DDL."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from bigrag.config import settings
from bigrag.db.base import Base
from bigrag.db import models  # noqa: F401  — register all tables on metadata

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

ADVISORY_LOCK_KEY = 8675309


def _build_url() -> str:
    dsn = settings.database_url
    if "sslmode=disable" in dsn:
        dsn = dsn.replace("?sslmode=disable", "").replace("&sslmode=disable", "")
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql+asyncpg://", 1)
    return dsn


def run_migrations_offline() -> None:
    context.configure(
        url=_build_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    connection.execute(text("SELECT pg_advisory_lock(:k)").bindparams(k=ADVISORY_LOCK_KEY))
    try:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.execute(text("SELECT pg_advisory_unlock(:k)").bindparams(k=ADVISORY_LOCK_KEY))


async def run_async_migrations() -> None:
    config_section = config.get_section(config.config_ini_section, {})
    config_section["sqlalchemy.url"] = _build_url()
    connectable = async_engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3.4: Generate initial migration**

Temporarily point Alembic at an empty test DB and autogenerate to verify models. For the commit, write the initial migration by hand so it is reviewable and matches the legacy schema exactly.

Run: `cd api && mkdir -p alembic/versions`

- [ ] **Step 3.5: Create `api/alembic/versions/0001_initial_schema.py`**

Write a single upgrade() that creates the 13 tables, every index, every check constraint, every FK — identical to what MIGRATIONS produced at HEAD. Use `op.create_table(...)`, `op.create_index(...)`. Full content is mechanically translatable from `api/bigrag/database.py` — reference that file and the ORM models.

Downgrade drops all 13 tables in reverse FK order.

- [ ] **Step 3.6: Create `api/bigrag/db/bootstrap.py`**

```python
"""On-startup migration bootstrap.

- If alembic_version table exists → run `alembic upgrade head` normally.
- Else if legacy `_migrations` table exists with >= 21 rows → stamp head
  (existing production DB adoption; schema is already at HEAD).
- Else (fresh DB) → run `alembic upgrade head`.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from bigrag.db.engine import engine
from bigrag.logging import get_logger

logger = get_logger("bigrag.db.bootstrap")

LEGACY_MIGRATION_COUNT = 21  # count of entries in the old MIGRATIONS list at adoption time


def _alembic_config() -> Config:
    here = Path(__file__).resolve().parent.parent.parent  # api/
    cfg = Config(str(here / "alembic.ini"))
    cfg.set_main_option("script_location", str(here / "alembic"))
    return cfg


async def _legacy_migration_count(conn) -> int | None:
    result = await conn.execute(
        text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = '_migrations'"
        )
    )
    if result.scalar_one() == 0:
        return None
    result = await conn.execute(text("SELECT count(*) FROM _migrations"))
    return int(result.scalar_one())


async def _alembic_version_exists(conn) -> bool:
    result = await conn.execute(
        text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = 'alembic_version'"
        )
    )
    return result.scalar_one() > 0


async def run_migrations() -> None:
    cfg = _alembic_config()
    async with engine().connect() as conn:
        have_alembic = await _alembic_version_exists(conn)
        legacy_count = await _legacy_migration_count(conn)

    if not have_alembic and legacy_count is not None and legacy_count >= LEGACY_MIGRATION_COUNT:
        logger.info("adopting existing schema — stamping alembic head")
        await _run_alembic_sync(lambda: command.stamp(cfg, "head"))
    else:
        logger.info("running alembic upgrade head")
        await _run_alembic_sync(lambda: command.upgrade(cfg, "head"))
    logger.info("migrations complete")


async def _run_alembic_sync(fn) -> None:
    import asyncio

    await asyncio.get_running_loop().run_in_executor(None, fn)
```

- [ ] **Step 3.7: Commit**

```bash
git add api/alembic.ini api/alembic/ api/bigrag/db/bootstrap.py
git commit -m "feat: add alembic async env and initial schema migration"
```

---

## Task 4: Wire engine/bootstrap into lifespan

**Files:**
- Modify: `api/bigrag/main.py`
- Modify: `api/bigrag/deps.py`

- [ ] **Step 4.1: Update lifespan**

In `api/bigrag/main.py`:
- Import: `from bigrag import db as db_module` (avoid shadowing legacy `database.db`)
- Replace `await db.connect(s.database_url, ...)` / `await db.migrate()` with:
  ```python
  await db_module.configure(s.database_url, pool_min=s.db_pool_min, pool_max=s.db_pool_max)
  from bigrag.db.bootstrap import run_migrations
  await run_migrations()
  ```
- Replace `await db.close()` with `await db_module.close()`
- Keep `app.state.db = db` for legacy routers during rolling migration (routers migrated task-by-task).

- [ ] **Step 4.2: Expose session in `api/bigrag/deps.py`**

Add:
```python
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session as _get_session

async def get_session(request: Request):
    async for s in _get_session():
        yield s
```

Actually simpler — re-export:
```python
from bigrag.db.session import get_session  # noqa: F401
```

- [ ] **Step 4.3: Smoke test**

Run: `cd api && uv run python -c "from bigrag.main import create_app; app = create_app()"`
Expected: no import errors.

- [ ] **Step 4.4: Commit**

```bash
git add api/bigrag/main.py api/bigrag/deps.py
git commit -m "feat: wire SQLAlchemy engine into app lifespan with alembic bootstrap"
```

---

## Task 5: Migrate routers (one commit per router)

**Pattern** — every router swap follows this template:

1. Remove `from bigrag.database import db`.
2. Add `from sqlalchemy.ext.asyncio import AsyncSession` and `from bigrag.db.session import get_session` and the models you need.
3. Each endpoint adds `session: AsyncSession = Depends(get_session)` to its signature.
4. Replace raw SQL with `session.execute(select(...))` / `session.add(Model(...))` / `session.delete(obj)` / `await session.commit()`.
5. For JSONB merge upserts, use `pg_insert(Model).values(...).on_conflict_do_update(...)` from `sqlalchemy.dialects.postgresql`.
6. For SELECT ... FROM `table` WHERE x = ANY($1::text[]) bulk lookups, use `select(Model).where(Model.col.in_(values))`.
7. `session.commit()` is required for writes — adopt `async with session.begin():` for multi-statement atomic blocks.

**Reference implementation** — `preferences.py` (simplest JSONB upsert):

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import UserPreference
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_session

router = APIRouter(prefix="/v1/auth/preferences", tags=["auth"])


@router.get("")
async def get_preferences(
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await session.scalar(
        select(UserPreference).where(UserPreference.user_id == user["id"])
    )
    return {"data": dict(row.data) if row else {}}


@router.put("")
async def update_preferences(
    body: dict,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict:
    incoming = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(incoming, dict):
        incoming = {}

    stmt = (
        pg_insert(UserPreference)
        .values(user_id=user["id"], data=incoming)
        .on_conflict_do_update(
            index_elements=[UserPreference.user_id],
            set_={
                "data": UserPreference.__table__.c.data.op("||")(pg_insert(UserPreference).excluded.data),
                "updated_at": sa.func.now(),
            },
        )
        .returning(UserPreference.data)
    )
    result = await session.execute(stmt)
    await session.commit()
    return {"data": dict(result.scalar_one())}
```

**Migration tasks (in dependency order — auth deps first):**

- [ ] **Step 5.1:** `api/bigrag/middleware/auth.py` → session-based (blocking — everything depends on this). Commit.
- [ ] **Step 5.2:** `api/bigrag/routers/preferences.py`. Commit.
- [ ] **Step 5.3:** `api/bigrag/routers/auth.py`. Commit.
- [ ] **Step 5.4:** `api/bigrag/routers/admin_users.py`. Commit.
- [ ] **Step 5.5:** `api/bigrag/routers/admin_api_keys.py`. Commit.
- [ ] **Step 5.6:** `api/bigrag/routers/admin_audit.py`. Commit.
- [ ] **Step 5.7:** `api/bigrag/routers/embedding_presets.py`. Commit.
- [ ] **Step 5.8:** `api/bigrag/routers/collections.py`. Commit.
- [ ] **Step 5.9:** `api/bigrag/routers/documents.py`. Commit.
- [ ] **Step 5.10:** `api/bigrag/routers/s3_jobs.py`. Commit.
- [ ] **Step 5.11:** `api/bigrag/routers/webhooks.py`. Commit.
- [ ] **Step 5.12:** `api/bigrag/routers/usage.py`. Commit.
- [ ] **Step 5.13:** `api/bigrag/routers/query.py` (if it still uses db). Commit.

---

## Task 6: Migrate services (one commit per service)

Services don't have a FastAPI request context, so they acquire sessions explicitly via `session_factory()`. Pattern:

```python
from bigrag.db.engine import session_factory

async def do_work():
    async with session_factory()() as session:
        async with session.begin():
            ...
```

Or accept a session as an argument when the caller already has one (preferred — avoids nested transactions).

- [ ] **Step 6.1:** `api/bigrag/services/embedding_cache.py` — BYTEA bulk upsert stays as Core via `session.execute(pg_insert(...).on_conflict_do_update(...))`. Commit.
- [ ] **Step 6.2:** `api/bigrag/services/queue.py`. Commit.
- [ ] **Step 6.3:** `api/bigrag/services/webhook.py`. Commit.
- [ ] **Step 6.4:** `api/bigrag/services/audit.py`. Commit.
- [ ] **Step 6.5:** `api/bigrag/services/s3_ingest.py`. Commit.
- [ ] **Step 6.6:** `api/bigrag/services/retrieval.py`. Commit.
- [ ] **Step 6.7:** `api/bigrag/services/collection_cache.py`. Commit.
- [ ] **Step 6.8:** `api/bigrag/services/cleanup.py` — takes `db` arg today; change signature to not need db. Commit.

---

## Task 7: Remove legacy Database class

**Files:**
- Delete: `api/bigrag/database.py`
- Modify: `api/bigrag/deps.py` (remove `get_db`)
- Modify: `api/bigrag/main.py` (remove `app.state.db`, remove `db.connect`/`db.migrate`/`db.close`)

- [ ] **Step 7.1: Grep for stragglers**

Run: `cd api && rg "from bigrag.database" bigrag/`
Expected: empty output.

Run: `cd api && rg "\bdb\.(fetch|execute|fetchrow|fetchval)" bigrag/`
Expected: empty output.

If either produces matches, migrate those call sites before continuing.

- [ ] **Step 7.2: Delete `api/bigrag/database.py`**

- [ ] **Step 7.3: Remove `get_db` from `api/bigrag/deps.py`**

- [ ] **Step 7.4: Remove `Database` wiring from `api/bigrag/main.py`**

- [ ] **Step 7.5: Smoke-test**

Run: `cd api && uv run python -c "from bigrag.main import create_app; create_app()"`
Expected: no error.

Run: `cd api && uv run ruff check bigrag/`
Expected: clean.

- [ ] **Step 7.6: Commit**

```bash
git add -A
git commit -m "feat: remove legacy asyncpg Database class"
```

---

## Task 8: Verify end-to-end

- [ ] **Step 8.1: Spin up services**

Run: `./dev.sh`
Expected: backend boots, migrations stamped or upgraded cleanly.

- [ ] **Step 8.2: Run E2E tests**

Run: `cd e2e && uv run --with httpx python run.py`
Expected: all passing.

- [ ] **Step 8.3: Studio UI smoke**

Hit `http://localhost:3100` — log in, list collections, upload a doc, run a query. Watch the backend logs for SQLAlchemy errors.

- [ ] **Step 8.4: Docs update**

Modify `website/content/docs/` any page that referenced the old migration runner or the `Database` class. Verify none of the public API surface changed — SDK and endpoints are unchanged.

- [ ] **Step 8.5: Final commit**

```bash
git add website/
git commit -m "docs: note SQLAlchemy/alembic migration in backend notes"
```

---

## Notes

- **JSONB "metadata" column collision:** SQLAlchemy's `DeclarativeBase` reserves `metadata`. We use `meta` as the Python attr mapped to the `metadata` column via positional mapping: `meta: Mapped[dict] = mapped_column("metadata", JSONB, ...)`. Routers/serializers must translate accordingly (`row.meta` → API response key `metadata`).
- **asyncpg JSONB codec:** SQLAlchemy's `JSONB` type handles Python dict ↔ JSONB round-trip without the custom `set_type_codec` — we can drop that callback.
- **Cursor-of-rows patterns:** `fetch(...)` → `scalars(...).all()`. `fetchrow(...)` → `scalar(...)` or `scalar_one_or_none()`. `execute(...)` returning a status string → `session.execute(...)` + `result.rowcount`.
- **Transactions:** wrap multi-statement writes with `async with session.begin():`. For single-statement writes, a plain `await session.commit()` at the end of the handler is fine.
- **build_update helper:** delete. Each route writes its update inline via ORM.
