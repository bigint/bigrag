"""Shared helpers for E2E tests."""

from __future__ import annotations

import asyncio
import os

import httpx

# --- Config (populated by load_env) ---
BASE = ""
COLLECTION = "e2e_test_collection"
OPENAI_KEY = ""
S3_BUCKET = ""
S3_ENDPOINT = ""
S3_ACCESS_KEY = ""
S3_SECRET_KEY = ""

# --- Results ---
passed = 0
failed = 0
errors: list[str] = []


def load_env(path) -> None:
    """Load .env file and populate module-level config."""
    global BASE, OPENAI_KEY, S3_BUCKET, S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY

    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

    BASE = os.environ.get("BIGRAG_URL", "http://localhost:6100")
    OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
    S3_BUCKET = os.environ.get("E2E_S3_BUCKET", "")
    S3_ENDPOINT = os.environ.get("E2E_S3_ENDPOINT", "")
    S3_ACCESS_KEY = os.environ.get("E2E_S3_ACCESS_KEY", "")
    S3_SECRET_KEY = os.environ.get("E2E_S3_SECRET_KEY", "")


def ok(name: str) -> None:
    global passed
    passed += 1
    print(f"  ✓ {name}")


def fail(name: str, detail: str) -> None:
    global failed
    failed += 1
    errors.append(f"{name}: {detail}")
    print(f"  ✗ {name}: {detail}")


def skip(reason: str) -> None:
    print(f"  ⊘ Skipped ({reason})")


async def wait_doc(c: httpx.AsyncClient, doc_id: str, max_wait: int = 60) -> str:
    """Poll until document reaches ready or failed."""
    status = "unknown"
    for _ in range(max_wait // 2):
        r = await c.get(f"/v1/collections/{COLLECTION}/documents/{doc_id}")
        status = r.json()["status"]
        if status in ("ready", "failed"):
            return status
        await asyncio.sleep(2)
    return status


async def cleanup_collection(c: httpx.AsyncClient) -> None:
    """Delete the test collection if it exists from a previous run."""
    await c.delete(f"/v1/collections/{COLLECTION}")


def report(elapsed: float) -> None:
    import sys

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed ({elapsed:.1f}s)")
    if errors:
        print("\nFailures:")
        for e in errors:
            print(f"  ✗ {e}")
    print("=" * 60)
    sys.exit(1 if failed > 0 else 0)
