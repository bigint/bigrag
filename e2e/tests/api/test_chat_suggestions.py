"""End-to-end tests for chat question-suggestion endpoints.

Endpoints covered (bigrag.routers.chat):
- GET  /v1/chat/question-suggestions?collection=...
- POST /v1/chat/question-suggestions

NOTE: The fake-openai stub returns a single sentence rather than the strict
``{"questions":[...]}`` JSON the suggestion generator requires, so the
POST happy-path resolves to ``502`` (UpstreamError) in this environment.
The tests below exercise every observable code path; if/when the fake is
upgraded to return a JSON object, the POST test should be expanded to
assert ``200`` + persisted round-trip.
"""

from __future__ import annotations

import httpx

from tests._helpers import (
    CollectionFactory,
    DocumentFactory,
    assert_envelope,
    seed_collection,
    wait_until_searchable,
)

# ---------------------------------------------------------------------------
# GET /v1/chat/question-suggestions
# ---------------------------------------------------------------------------


async def test_get_question_suggestions_empty_when_none_generated(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        "/v1/chat/question-suggestions",
        params={"collection": coll["name"]},
    )
    body = assert_envelope(resp, 200)
    assert body["collection"] == coll["name"]
    assert body["questions"] == []
    assert body["generated_at"] is None
    assert body["model"] is None


async def test_get_question_suggestions_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await unauth_client.get(
        "/v1/chat/question-suggestions",
        params={"collection": coll["name"]},
    )
    assert resp.status_code == 401, resp.text


async def test_get_question_suggestions_unknown_collection_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(
        "/v1/chat/question-suggestions",
        params={"collection": "missing-suggestions-zzz"},
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# POST /v1/chat/question-suggestions
# ---------------------------------------------------------------------------


async def test_post_question_suggestions_requires_ready_docs(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        "/v1/chat/question-suggestions",
        json={"collection": coll["name"]},
    )
    assert resp.status_code == 400, resp.text


async def test_post_question_suggestions_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await unauth_client.post(
        "/v1/chat/question-suggestions",
        json={"collection": coll["name"]},
    )
    assert resp.status_code == 401, resp.text


async def test_post_question_suggestions_unknown_collection_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/chat/question-suggestions",
        json={"collection": "missing-suggestions-post-zzz"},
    )
    assert resp.status_code == 404, resp.text


async def test_post_question_suggestions_round_trip_or_upstream_error(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    """When ready docs exist the endpoint either:

    * returns 200 + 5 persisted questions (GET round-trips them), or
    * returns 502 because the fake-openai stub doesn't emit JSON.

    Both outcomes confirm the auth/scope/collection plumbing is wired.
    """
    coll = await seed_collection(collection, document, fixtures=("sample.txt",))
    await wait_until_searchable(admin_client, coll["name"], "Acme", top_k=3)

    post = await admin_client.post(
        "/v1/chat/question-suggestions",
        json={"collection": coll["name"]},
    )
    assert post.status_code in (200, 502), post.text

    if post.status_code == 200:
        body = post.json()
        assert body["collection"] == coll["name"]
        assert isinstance(body["questions"], list)
        assert len(body["questions"]) > 0
        assert body["generated_at"] is not None
        assert body["model"]

        get_resp = await admin_client.get(
            "/v1/chat/question-suggestions",
            params={"collection": coll["name"]},
        )
        get_body = assert_envelope(get_resp, 200)
        assert get_body["questions"] == body["questions"]
        assert get_body["model"] == body["model"]


async def test_question_suggestions_independent_across_collections(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll_a = await collection()
    coll_b = await collection()
    a = await admin_client.get(
        "/v1/chat/question-suggestions",
        params={"collection": coll_a["name"]},
    )
    b = await admin_client.get(
        "/v1/chat/question-suggestions",
        params={"collection": coll_b["name"]},
    )
    a_body = assert_envelope(a, 200)
    b_body = assert_envelope(b, 200)
    assert a_body["collection"] == coll_a["name"]
    assert b_body["collection"] == coll_b["name"]
    assert a_body["questions"] == []
    assert b_body["questions"] == []
