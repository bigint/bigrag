from types import SimpleNamespace

from starlette.datastructures import URL, Headers

from bigrag.middleware.csrf import _allowed_origin


def make_request(url: str, host: str):
    return SimpleNamespace(url=URL(url), headers=Headers({"host": host}))


def test_allowed_origin_accepts_configured_admin_ui() -> None:
    request = make_request("https://api.example.com/v1/auth/logout", "api.example.com")

    assert _allowed_origin("https://admin.example.com", request, ["https://admin.example.com"])


def test_allowed_origin_accepts_same_origin_api() -> None:
    request = make_request("https://api.example.com/v1/auth/logout", "api.example.com")

    assert _allowed_origin("https://api.example.com", request, [])


def test_allowed_origin_rejects_other_origins() -> None:
    request = make_request("https://api.example.com/v1/auth/logout", "api.example.com")

    assert not _allowed_origin("https://evil.example.com", request, ["https://admin.example.com"])
