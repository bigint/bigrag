from __future__ import annotations

import re


def tokenize_query(query: str) -> list[str]:
    return [w.lower() for w in re.split(r"\s+", query.strip()) if len(w) >= 2]


def keyword_score(text: str, query_terms: list[str]) -> float:
    text_lower = text.lower()
    if not query_terms:
        return 0.0
    patterns = [re.compile(r"\b" + re.escape(term) + r"\b") for term in query_terms]
    matches = sum(1 for pat in patterns if pat.search(text_lower))
    return matches / len(query_terms)


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list):
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
            if item_id not in items:
                items[item_id] = item

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    result = []
    for item_id in sorted_ids:
        item = items[item_id].copy()
        item["score"] = round(scores[item_id], 6)
        result.append(item)

    return result
