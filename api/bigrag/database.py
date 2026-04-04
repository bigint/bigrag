from __future__ import annotations

import json
import asyncpg
import logging

logger = logging.getLogger("bigrag.database")


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT UNIQUE NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS api_keys (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        key_hash TEXT UNIQUE NOT NULL,
        prefix TEXT NOT NULL,
        permissions JSONB NOT NULL DEFAULT '{}',
        expires_at TIMESTAMPTZ,
        last_used_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS collections (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        embedding_provider TEXT NOT NULL DEFAULT 'openai',
        embedding_model TEXT NOT NULL DEFAULT 'text-embedding-3-small',
        dimension INT NOT NULL DEFAULT 1536,
        chunk_size INT NOT NULL DEFAULT 512,
        chunk_overlap INT NOT NULL DEFAULT 50,
        document_count INT NOT NULL DEFAULT 0,
        metadata JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS documents (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        file_type TEXT NOT NULL DEFAULT '',
        file_size BIGINT NOT NULL DEFAULT 0,
        file_path TEXT NOT NULL DEFAULT '',
        chunk_count INT NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
        error_message TEXT,
        metadata JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_documents_collection_id ON documents(collection_id);
    CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
    """,
    """
    CREATE TABLE IF NOT EXISTS _migrations (
        version INT PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    ALTER TABLE collections ADD COLUMN IF NOT EXISTS embedding_api_key TEXT;
    ALTER TABLE collections ADD COLUMN IF NOT EXISTS embedding_base_url TEXT;
    """,
    """
    CREATE TABLE IF NOT EXISTS webhooks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        url TEXT NOT NULL,
        secret TEXT NOT NULL,
        events TEXT[] NOT NULL,
        collections TEXT[],
        description TEXT NOT NULL DEFAULT '',
        active BOOLEAN NOT NULL DEFAULT true,
        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS webhook_deliveries (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
        event TEXT NOT NULL,
        payload JSONB NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'delivered', 'failed')),
        attempts INT NOT NULL DEFAULT 0,
        last_status_code INT,
        last_error TEXT,
        next_retry_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        completed_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id);
    CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_status ON webhook_deliveries(status);
    """,
    """
    ALTER TABLE collections ADD COLUMN IF NOT EXISTS reranking_enabled BOOLEAN NOT NULL DEFAULT false;
    ALTER TABLE collections ADD COLUMN IF NOT EXISTS reranking_model TEXT NOT NULL DEFAULT 'rerank-v3.5';
    ALTER TABLE collections ADD COLUMN IF NOT EXISTS reranking_api_key TEXT;
    """,
    """
    CREATE TABLE IF NOT EXISTS query_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        collection_name TEXT NOT NULL,
        query TEXT NOT NULL,
        top_k INT NOT NULL,
        result_count INT NOT NULL DEFAULT 0,
        avg_score DOUBLE PRECISION,
        latency_ms DOUBLE PRECISION,
        search_mode TEXT NOT NULL DEFAULT 'semantic',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_query_log_collection ON query_log(collection_name);
    CREATE INDEX IF NOT EXISTS idx_query_log_created_at ON query_log(created_at);
    """,
    """
    DROP TABLE IF EXISTS invites;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(name);
    CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
    CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
    CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at);
    CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
    """,
]


def build_update(
    table: str,
    fields: dict,
    where_col: str,
    where_val,
) -> tuple[str, list]:
    """Build a parameterized UPDATE query.

    Returns (sql, params) for use with db.fetchrow(sql, *params).
    """
    set_parts = []
    params = []
    idx = 1
    for col, val in fields.items():
        set_parts.append(f"{col} = ${idx}")
        params.append(val)
        idx += 1

    set_parts.append("updated_at = now()")
    params.append(where_val)

    sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {where_col} = ${idx} RETURNING *"
    return sql, params


class Database:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def connect(self, dsn: str, min_size: int = 5, max_size: int = 50) -> None:
        ssl = None
        if "sslmode=disable" in dsn:
            dsn = dsn.replace("?sslmode=disable", "").replace("&sslmode=disable", "")
            ssl = False
        self.pool = await asyncpg.create_pool(
            dsn, min_size=min_size, max_size=max_size, ssl=ssl,
            init=_init_connection,
            command_timeout=30,
            max_inactive_connection_lifetime=300,
        )
        logger.info(f"Postgres pool ready (min={min_size}, max={max_size})")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            logger.info("Postgres connection closed")

    async def migrate(self) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    version INT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            applied = {
                row["version"]
                for row in await conn.fetch("SELECT version FROM _migrations")
            }
            for i, sql in enumerate(MIGRATIONS):
                if i in applied:
                    continue
                logger.info(f"Applying migration {i}")
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO _migrations (version) VALUES ($1) ON CONFLICT DO NOTHING", i
                )
            logger.info("Migrations complete")

    async def fetchrow(self, query: str, *args) -> asyncpg.Record | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute(self, query: str, *args) -> str:
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)


db = Database()
