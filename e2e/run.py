#!/usr/bin/env python3
"""bigRAG E2E Test Runner.

Usage:
    cd e2e && uv run python run.py

Reads configuration from .env file in this directory.
"""

import asyncio
import sys
import time
from pathlib import Path

from helpers import load_env, report

load_env(Path(__file__).parent / ".env")

from tests.test_health import test_health  # noqa: E402
from tests.test_collections import test_collections  # noqa: E402
from tests.test_documents import test_documents  # noqa: E402
from tests.test_processing import test_processing  # noqa: E402
from tests.test_batch import test_batch  # noqa: E402
from tests.test_query import test_query  # noqa: E402
from tests.test_webhooks import test_webhooks  # noqa: E402
from tests.test_vectors import test_vectors  # noqa: E402
from tests.test_sse import test_sse  # noqa: E402
from tests.test_s3 import test_s3  # noqa: E402
from tests.test_edge_cases import test_edge_cases  # noqa: E402
from tests.test_truncate import test_truncate  # noqa: E402
from tests.test_cleanup import test_cleanup  # noqa: E402


async def main():
    import httpx
    from helpers import BASE, COLLECTION, OPENAI_KEY, cleanup_collection

    print("=" * 60)
    print("bigRAG E2E Test Suite")
    print("=" * 60)

    if not OPENAI_KEY:
        print("\n  ✗ OPENAI_API_KEY not set in .env")
        sys.exit(1)

    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        await cleanup_collection(c)

        await test_health(c)
        await test_collections(c)
        await test_documents(c)
        doc_id, doc2_id = await test_processing(c)
        await test_batch(c)
        await test_query(c, doc2_id)
        await test_webhooks(c)
        await test_vectors(c)
        await test_sse(c)
        await test_s3(c)
        await test_edge_cases(c, doc_id)
        await test_truncate(c)
        await test_cleanup(c)


if __name__ == "__main__":
    start = time.time()
    asyncio.run(main())
    elapsed = time.time() - start
    report(elapsed)
