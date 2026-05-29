from __future__ import annotations

import re

KeywordPattern = re.Pattern[str]
_QUERY_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]*")


def tokenize_query(query: str) -> list[str]:
    return [
        match.group(0).lower()
        for match in _QUERY_TOKEN_RE.finditer(query)
        if len(match.group(0)) >= 2
    ]


def keyword_patterns(query_terms: list[str]) -> list[KeywordPattern]:
    return [re.compile(r"\b" + re.escape(term) + r"\b") for term in query_terms]


def keyword_score(text: str, patterns: list[KeywordPattern]) -> float:
    text_lower = text.lower()
    if not patterns:
        return 0.0
    matches = sum(1 for pat in patterns if pat.search(text_lower))
    return matches / len(patterns)


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    max_score = len(ranked_lists) / (k + 1) if ranked_lists else 1.0

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
        item["score"] = round(scores[item_id] / max_score, 6)
        result.append(item)

    return result
