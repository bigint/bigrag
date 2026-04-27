from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from bigrag.middleware.auth import require_admin_session, require_session


def _run(coro):
    return asyncio.run(coro)


def test_member_session_passes_session_dependency() -> None:
    user = {"auth_method": "session", "role": "member"}

    assert _run(require_session(user)) is user


def test_member_session_fails_admin_session_dependency() -> None:
    user = {"auth_method": "session", "role": "member"}

    with pytest.raises(HTTPException) as exc:
        _run(require_admin_session(user))

    assert exc.value.status_code == 403
    assert exc.value.detail == "Admin access required"


def test_api_key_fails_session_dependency() -> None:
    user = {"auth_method": "api_key", "role": "admin"}

    with pytest.raises(HTTPException) as exc:
        _run(require_session(user))

    assert exc.value.status_code == 403
    assert exc.value.detail == "Session authentication required"
