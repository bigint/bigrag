from __future__ import annotations

import time

import orjson

from bigrag.services.semantic_cache import _best_match, _scope_hash


def test_semantic_cache_scope_separates_query_options() -> None:
    vec = [1.0, 0.0, 0.0]
    now = time.time()
    payload = {"total": 3, "results": [{"id": "cached"}]}
    raw_entries = [
        orjson.dumps(
            {
                "vec": vec,
                "payload": payload,
                "scope_hash": _scope_hash({"top_k": 3, "filters": None}),
                "ts": now,
            }
        )
    ]

    _, miss = _best_match(
        vec,
        raw_entries,
        0.97,
        now,
        _scope_hash({"top_k": 100, "filters": None}),
    )
    _, hit = _best_match(
        vec,
        raw_entries,
        0.97,
        now,
        _scope_hash({"top_k": 3, "filters": None}),
    )

    assert miss is None
    assert hit == payload
