from __future__ import annotations

from bigrag.routers.preferences import _deep_merge, _public_preferences


def test_public_preferences_redacts_playground_openai_key() -> None:
    public = _public_preferences(
        {"playground": {"openai_key": "sk-secret", "model": "gpt-4o-mini"}}
    )

    assert public == {"playground": {"has_openai_key": True, "model": "gpt-4o-mini"}}


def test_public_preferences_reports_cleared_playground_openai_key() -> None:
    public = _public_preferences({"playground": {"openai_key": ""}})

    assert public == {"playground": {"has_openai_key": False}}


def test_deep_merge_preserves_existing_nested_preferences() -> None:
    merged = _deep_merge(
        {"playground": {"openai_key": "sk-secret", "model": "gpt-4o-mini"}, "theme": "dark"},
        {"playground": {"temperature": 0.2}},
    )

    assert merged == {
        "playground": {
            "openai_key": "sk-secret",
            "model": "gpt-4o-mini",
            "temperature": 0.2,
        },
        "theme": "dark",
    }
