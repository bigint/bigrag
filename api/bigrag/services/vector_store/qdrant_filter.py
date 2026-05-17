from __future__ import annotations

from qdrant_client import models

from bigrag.services._retrieval_filters import FilterExpression


def to_qdrant_filter(filters: FilterExpression | None) -> models.Filter | None:
    if filters is None:
        return None
    must: list[models.Condition] = []
    must_not: list[models.Condition] = []
    for condition in filters.conditions:
        if condition.operator == "eq":
            must.append(
                models.FieldCondition(
                    key=condition.field,
                    match=models.MatchValue(value=condition.value),
                )
            )
        elif condition.operator == "ne":
            must_not.append(
                models.FieldCondition(
                    key=condition.field,
                    match=models.MatchValue(value=condition.value),
                )
            )
        elif condition.operator == "in":
            must.append(
                models.FieldCondition(
                    key=condition.field,
                    match=models.MatchAny(any=condition.value),
                )
            )
        else:
            must.append(
                models.FieldCondition(
                    key=condition.field,
                    range=models.Range(
                        gt=condition.value if condition.operator == "gt" else None,
                        gte=condition.value if condition.operator == "gte" else None,
                        lt=condition.value if condition.operator == "lt" else None,
                        lte=condition.value if condition.operator == "lte" else None,
                    ),
                )
            )
    if not must and not must_not:
        return None
    return models.Filter(must=must or None, must_not=must_not or None)


def combine_filters(
    *filters: models.Filter | None,
) -> models.Filter | None:
    active = [f for f in filters if f is not None]
    if not active:
        return None
    if len(active) == 1:
        return active[0]
    return models.Filter(must=active)
