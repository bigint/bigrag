from __future__ import annotations

import asyncpg
import logging

logger = logging.getLogger("bigrag.database")

MIGRATIONS = [
    # 001: core auth tables
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

    CREATE TABLE IF NOT EXISTS invites (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        code TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
        used_by UUID REFERENCES users(id) ON DELETE SET NULL,
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
    # 002: collections and documents
    """
    CREATE TABLE IF NOT EXISTS collections (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        embedding_provider TEXT NOT NULL DEFAULT 'sentence-transformers',
        embedding_model TEXT NOT NULL DEFAULT 'all-MiniLM-L6-v2',
        dimension INT NOT NULL DEFAULT 384,
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
    # 003: migration tracking
    """
    CREATE TABLE IF NOT EXISTS _migrations (
        version INT PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
]


class Database:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def connect(self, dsn: str) -> None:
        self.pool = await asyncpg.create_pool(dsn, min_size=2, max_size=20)
        logger.info("Connected to Postgres")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            logger.info("Postgres connection closed")

    async def migrate(self) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            # Ensure migration tracking exists
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
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute(self, query: str, *args) -> str:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)


db = Database()
