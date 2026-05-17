from __future__ import annotations

import time
from collections import deque
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="webhook-sink", version="0.1.0")

_DELIVERIES: deque[dict[str, Any]] = deque(maxlen=1000)
_FAIL_QUEUE: dict[str, int] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/{label}")
async def receive_webhook(label: str, request: Request):
    raw = await request.body()
    try:
        parsed = await request.json()
    except Exception:
        parsed = None
    delivery = {
        "label": label,
        "headers": {k: v for k, v in request.headers.items()},
        "body": parsed if parsed is not None else raw.decode("utf-8", errors="replace"),
        "received_at": time.time(),
    }
    _DELIVERIES.append(delivery)

    if _FAIL_QUEUE.get(label, 0) > 0:
        _FAIL_QUEUE[label] -= 1
        return JSONResponse(content={"received": False, "forced_failure": True}, status_code=500)

    return {"received": True}


@app.get("/received")
async def list_received(
    label: str | None = Query(default=None),
    since: float | None = Query(default=None),
) -> dict[str, Any]:
    items = list(_DELIVERIES)
    if label is not None:
        items = [d for d in items if d["label"] == label]
    if since is not None:
        items = [d for d in items if d["received_at"] >= since]
    return {"count": len(items), "deliveries": items}


@app.post("/reset")
async def reset_received() -> dict[str, str]:
    _DELIVERIES.clear()
    _FAIL_QUEUE.clear()
    return {"status": "ok"}


@app.post("/fail/{label}")
async def configure_failures(label: str, count: int = Query(default=1, ge=1, le=100)) -> dict:
    _FAIL_QUEUE[label] = count
    return {"status": "ok", "label": label, "fail_next": count}
