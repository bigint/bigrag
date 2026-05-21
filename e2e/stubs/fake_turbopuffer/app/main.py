from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="fake-turbopuffer", version="0.1.0")

_namespaces: dict[str, dict[str, dict[str, Any]]] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/namespaces")
async def list_namespaces() -> dict[str, list[dict[str, str]]]:
    return {"namespaces": [{"id": name, "name": name} for name in sorted(_namespaces)]}


@app.delete("/v2/namespaces/{namespace}")
async def delete_namespace(namespace: str) -> JSONResponse:
    if namespace not in _namespaces:
        return JSONResponse({"error": "not found"}, status_code=404)
    del _namespaces[namespace]
    return JSONResponse({"status": "ok"})


@app.post("/v2/namespaces/{namespace}")
async def write_namespace(namespace: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    rows = _namespaces.setdefault(namespace, {})
    affected = 0
    for row in body.get("upsert_rows") or []:
        row_id = str(row["id"])
        rows[row_id] = deepcopy(row)
        affected += 1
    for row_id in body.get("deletes") or []:
        if rows.pop(str(row_id), None) is not None:
            affected += 1
    delete_filter = body.get("delete_by_filter")
    if delete_filter is not None:
        delete_ids = [row_id for row_id, row in rows.items() if _matches(row, delete_filter)]
        for row_id in delete_ids:
            rows.pop(row_id, None)
        affected += len(delete_ids)
    return {"status": "ok", "rows_affected": affected}


@app.post("/v2/namespaces/{namespace}/query")
async def query_namespace(namespace: str, request: Request) -> dict[str, list[dict[str, Any]]]:
    body = await request.json()
    rows = [
        deepcopy(row)
        for row in _namespaces.get(namespace, {}).values()
        if _matches(row, body.get("filters"))
    ]
    ranked = _rank(rows, body.get("rank_by"))
    total = _limit(body, default=len(ranked))
    return {"rows": [_project(row, body) for row in ranked[:total]]}


def _rank(rows: list[dict[str, Any]], rank_by: Any) -> list[dict[str, Any]]:
    if not isinstance(rank_by, list) or len(rank_by) < 2:
        return sorted(rows, key=lambda row: str(row.get("id", "")))
    mode = str(rank_by[1]).lower()
    field = str(rank_by[0])
    if field == "id" and mode == "asc":
        return sorted(rows, key=lambda row: str(row.get("id", "")))
    if mode == "ann":
        query_vector = rank_by[2] if len(rank_by) > 2 else []
        for row in rows:
            score = _cosine(row.get(field) or [], query_vector)
            row["$dist"] = max(0.0, 1.0 - score)
            row["$score"] = score
        return sorted(rows, key=lambda row: float(row.get("$dist", 1.0)))
    if mode in {"bm25", "hybrid"}:
        query = str(rank_by[2] if len(rank_by) > 2 else "")
        for row in rows:
            score = _text_score(str(row.get(field, "")), query)
            if mode == "hybrid":
                score += max(0.0, _cosine(row.get("vector") or [], _vector_hint(rank_by))) * 0.25
            row["$score"] = score
            row["$dist"] = max(0.0, 1.0 - min(score, 1.0))
        return sorted(rows, key=lambda row: float(row.get("$score", 0.0)), reverse=True)
    return sorted(rows, key=lambda row: str(row.get("id", "")))


def _vector_hint(rank_by: list[Any]) -> list[float]:
    for item in rank_by:
        if isinstance(item, list) and all(isinstance(value, (int, float)) for value in item):
            return [float(value) for value in item]
    return []


def _text_score(text: str, query: str) -> float:
    words = re.findall(r"[a-z0-9]+", text.lower())
    terms = re.findall(r"[a-z0-9]+", query.lower())
    if not words or not terms:
        return 0.0
    counts = {word: words.count(word) for word in set(words)}
    hits = sum(counts.get(term, 0) for term in terms)
    coverage = len({term for term in terms if term in counts}) / max(1, len(set(terms)))
    return round(hits / len(words) + coverage, 6)


def _cosine(left: list[Any], right: list[Any]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    a = [float(value) for value in left[:size]]
    b = [float(value) for value in right[:size]]
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _limit(body: dict[str, Any], *, default: int) -> int:
    if isinstance(body.get("top_k"), int):
        return max(0, int(body["top_k"]))
    limit = body.get("limit")
    if isinstance(limit, dict) and isinstance(limit.get("total"), int):
        return max(0, int(limit["total"]))
    if isinstance(limit, int):
        return max(0, int(limit))
    return default


def _project(row: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    include = body.get("include_attributes")
    exclude = set(body.get("exclude_attributes") or [])
    if include is True or include is None:
        projected = deepcopy(row)
    elif isinstance(include, list):
        projected = {"id": row.get("id")}
        for key in include:
            if key in row:
                projected[str(key)] = deepcopy(row[key])
    else:
        projected = deepcopy(row)
    for key in exclude:
        projected.pop(str(key), None)
    return projected


def _matches(row: dict[str, Any], filter_expr: Any) -> bool:
    if filter_expr is None:
        return True
    if not isinstance(filter_expr, list) or not filter_expr:
        return True
    head = filter_expr[0]
    if head == "And":
        clauses = filter_expr[1] if len(filter_expr) > 1 else []
        return all(_matches(row, clause) for clause in clauses)
    if head == "Or":
        clauses = filter_expr[1] if len(filter_expr) > 1 else []
        return any(_matches(row, clause) for clause in clauses)
    if len(filter_expr) < 3:
        return True
    field, operator, expected = filter_expr[0], str(filter_expr[1]), filter_expr[2]
    actual = row.get(str(field))
    if operator == "Eq":
        return actual == expected
    if operator == "NotEq":
        return actual != expected
    if operator == "In":
        return actual in set(expected if isinstance(expected, list) else [expected])
    if operator == "Gt":
        return actual is not None and actual > expected
    if operator == "Gte":
        return actual is not None and actual >= expected
    if operator == "Lt":
        return actual is not None and actual < expected
    if operator == "Lte":
        return actual is not None and actual <= expected
    return True
