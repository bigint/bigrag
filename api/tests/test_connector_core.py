from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from conftest import FakeSession

from bigrag.services import connector_core


def _config(**overrides):
    base = {
        "provider": "google",
        "enabled": True,
        "client_id": "cid",
        "client_secret": "secret",
        "redirect_uri": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _account(**overrides):
    base = {
        "id": uuid.uuid4(),
        "provider": "google",
        "user_id": uuid.uuid4(),
        "status": "connected",
        "account_email": "u@x.com",
        "refresh_token": "rt",
        "access_token": "at",
        "token_expires_at": datetime.now(UTC),
        "last_connected_at": datetime.now(UTC),
        "scopes": ["read"],
        "oauth_state": None,
        "meta": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _source(**overrides):
    base = {
        "id": uuid.uuid4(),
        "account_id": uuid.uuid4(),
        "collection_id": uuid.uuid4(),
        "collection_name": "docs",
        "provider": "google",
        "root_id": "root-1",
        "root_name": "Folder",
        "root_mime_type": "folder",
        "source_type": "folder",
        "status": "idle",
        "schedule_enabled": True,
        "sync_interval_hours": 24,
        "last_sync_at": None,
        "next_sync_at": None,
        "last_error": None,
        "meta": {},
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _job(**overrides):
    base = {
        "id": uuid.uuid4(),
        "provider": "google",
        "source_id": uuid.uuid4(),
        "trigger": "manual",
        "status": "pending",
        "total_found": 0,
        "total_created": 0,
        "total_updated": 0,
        "total_skipped": 0,
        "total_deleted": 0,
        "total_failed": 0,
        "error_message": None,
        "details": None,
        "started_at": None,
        "completed_at": None,
        "started_by": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_sync_progress_percent_fixed_phases() -> None:
    assert connector_core.sync_progress_percent("queued") == 0
    assert connector_core.sync_progress_percent("complete") == 100
    assert connector_core.sync_progress_percent("failed") == 100


def test_sync_progress_percent_dynamic_range() -> None:
    pct = connector_core.sync_progress_percent("syncing", 5, 10)
    assert pct == round(15 + ((85 - 15) * 0.5))


def test_sync_progress_percent_unknown_phase_returns_zero() -> None:
    assert connector_core.sync_progress_percent("garbage") == 0


def test_sync_progress_percent_clamps_ratios() -> None:
    assert connector_core.sync_progress_percent("syncing", 100, 0) == 15
    assert connector_core.sync_progress_percent("syncing", 1000, 1) == 85


def test_sync_counter_details_includes_all_counters() -> None:
    counters = connector_core.ConnectorSyncCounters(
        found=2, created=1, updated=1, skipped=2, deleted=3, failed=1
    )
    counters.add_error("rid", "name", "boom")
    assert counters.failed == 2
    assert counters.errors[-1]["error"] == "boom"
    details = connector_core.sync_counter_details(counters)
    assert details == {
        "created": 1,
        "updated": 1,
        "skipped": 2,
        "deleted": 3,
        "failed": 2,
    }


def test_add_error_capped_at_50() -> None:
    counters = connector_core.ConnectorSyncCounters()
    for i in range(60):
        counters.add_error(f"rid-{i}", f"name-{i}", "err")
    assert counters.failed == 60
    assert len(counters.errors) == 50


def test_sync_progress_details_uses_current_item() -> None:
    item = connector_core.RemoteConnectorFile(id="rid", name="file.txt", mime_type="text/plain")
    details = connector_core.sync_progress_details(
        phase="syncing",
        message="working",
        current_item=item,
        processed_items=1,
        total_items=4,
    )
    assert details["current_item_id"] == "rid"
    assert details["current_item_name"] == "file.txt"
    assert details["progress_percent"] > 0


def test_parse_dt_round_trip() -> None:
    iso = "2026-05-09T00:00:00Z"
    parsed = connector_core.parse_dt(iso)
    assert parsed is not None
    assert parsed.tzinfo is not None


def test_parse_dt_none_and_invalid() -> None:
    assert connector_core.parse_dt(None) is None
    assert connector_core.parse_dt("not a date") is None


def test_next_sync_at_disabled_returns_none() -> None:
    source = _source(schedule_enabled=False)
    assert connector_core.next_sync_at(source) is None


def test_next_sync_at_enabled_returns_future() -> None:
    source = _source(schedule_enabled=True, sync_interval_hours=2)
    now = datetime.now(UTC)
    result = connector_core.next_sync_at(source, from_time=now)
    assert result == now + timedelta(hours=2)


def test_next_sync_at_handles_invalid_interval() -> None:
    source = _source(schedule_enabled=True, sync_interval_hours=0)
    result = connector_core.next_sync_at(source)
    assert result is not None


def test_utcnow_returns_aware_datetime() -> None:
    now = connector_core.utcnow()
    assert now.tzinfo is not None


def test_configured_true_when_complete() -> None:
    config = _config()
    assert connector_core.configured(config) is True


def test_configured_false_when_disabled_or_missing() -> None:
    assert connector_core.configured(None) is False
    assert connector_core.configured(_config(enabled=False)) is False
    assert connector_core.configured(_config(client_secret=None)) is False


def test_config_public_shows_fields() -> None:
    config = _config()
    public = connector_core.config_public(config, provider="google", callback_url="https://app/cb")
    assert public["provider"] == "google"
    assert public["configured"] is True
    assert public["client_id"] == "cid"


def test_config_public_handles_missing_config() -> None:
    public = connector_core.config_public(None, provider="google", callback_url="cb")
    assert public["configured"] is False
    assert public["enabled"] is False


def test_account_public_connected_and_scope_ok() -> None:
    account = _account()
    public = connector_core.account_public(
        provider="google",
        config=_config(),
        account=account,
        has_required_scope=lambda _a: True,
    )
    assert public["connected"] is True
    assert public["status"] == "connected"


def test_account_public_scope_missing_marks_reauth() -> None:
    account = _account()
    public = connector_core.account_public(
        provider="google",
        config=_config(),
        account=account,
        has_required_scope=lambda _a: False,
    )
    assert public["connected"] is False
    assert public["status"] == "needs_reauth"


def test_account_public_handles_missing_account() -> None:
    public = connector_core.account_public(
        provider="google",
        config=None,
        account=None,
        has_required_scope=lambda _a: True,
    )
    assert public["status"] is None
    assert public["email"] is None
    assert public["scopes"] == []


def test_source_public_includes_account_email() -> None:
    source = _source()
    account = _account()
    public = connector_core.source_public("google", (source, account))
    assert public["account_email"] == account.account_email
    assert public["metadata"] == {}


def test_sync_job_public_serializes_all_counts() -> None:
    job = _job(total_found=2, total_created=1)
    public = connector_core.sync_job_public("google", job)
    assert public["total_found"] == 2
    assert public["total_created"] == 1
    assert public["details"] == {}


@pytest.mark.anyio
async def test_oauth_redirect_url_with_origin(monkeypatch) -> None:
    async def fake_get_value(_key: str) -> list[str]:
        return ["https://app"]

    monkeypatch.setattr("bigrag.services.runtime_settings.get_value", fake_get_value)
    account = _account(meta={"redirect_origin": "https://app/"})
    assert await connector_core.oauth_redirect_url(account, "/done") == "https://app/done"


@pytest.mark.anyio
async def test_oauth_redirect_url_without_origin() -> None:
    account = _account(meta={})
    assert await connector_core.oauth_redirect_url(account, "/done") == "/done"


@pytest.mark.anyio
async def test_oauth_redirect_url_rejects_unallowed_origin(monkeypatch) -> None:
    async def fake_get_value(_key: str) -> list[str]:
        return ["https://allowed"]

    monkeypatch.setattr("bigrag.services.runtime_settings.get_value", fake_get_value)
    account = _account(meta={"redirect_origin": "https://attacker"})
    assert await connector_core.oauth_redirect_url(account, "/done") == "/done"


@pytest.mark.anyio
async def test_get_provider_config_uses_scalar() -> None:
    config = _config()
    session = FakeSession(scalar_values=[config])

    result = await connector_core.get_provider_config(session, "google")

    assert result is config


@pytest.mark.anyio
async def test_get_connector_account_filters_by_user() -> None:
    account = _account()
    session = FakeSession(scalar_values=[account])

    result = await connector_core.get_connector_account(
        session, provider="google", user_id=str(account.user_id)
    )

    assert result is account


@pytest.mark.anyio
async def test_oauth_error_redirect_url_returns_path_without_state() -> None:
    session = FakeSession()
    url = await connector_core.oauth_error_redirect_url(
        session, provider="google", user_id=str(uuid.uuid4()), state=None, path="/err"
    )
    assert url == "/err"


@pytest.mark.anyio
async def test_oauth_error_redirect_url_falls_back_when_state_mismatch() -> None:
    account = _account(oauth_state="other", meta={"redirect_origin": "https://app"})
    session = FakeSession(scalar_values=[account])
    url = await connector_core.oauth_error_redirect_url(
        session,
        provider="google",
        user_id=str(account.user_id),
        state="not-matching",
        path="/err",
    )
    assert url == "/err"


@pytest.mark.anyio
async def test_oauth_error_redirect_url_returns_app_origin_on_match(monkeypatch) -> None:
    async def fake_get_value(_key: str) -> list[str]:
        return ["https://app"]

    monkeypatch.setattr("bigrag.services.runtime_settings.get_value", fake_get_value)
    account = _account(oauth_state="matching", meta={"redirect_origin": "https://app"})
    session = FakeSession(scalar_values=[account])
    url = await connector_core.oauth_error_redirect_url(
        session,
        provider="google",
        user_id=str(account.user_id),
        state="matching",
        path="/err",
    )
    assert url == "https://app/err"


@pytest.mark.anyio
async def test_disconnect_account_is_noop_when_no_account() -> None:
    session = FakeSession(scalar_values=[None])
    await connector_core.disconnect_account(
        session, provider="google", user_id=str(uuid.uuid4()), source_error="x"
    )


@pytest.mark.anyio
async def test_disconnect_account_revokes_and_updates_sources() -> None:
    account = _account()
    session = FakeSession(scalar_values=[account])

    await connector_core.disconnect_account(
        session,
        provider="google",
        user_id=str(account.user_id),
        source_error="re-auth needed",
    )

    assert account.status == "revoked"
    assert account.access_token is None
    assert account.refresh_token is None
    assert session.commits == 1


@pytest.mark.anyio
async def test_run_due_syncs_logged_swallows_errors(monkeypatch) -> None:
    async def boom(*_args, **_kwargs):
        raise RuntimeError("scheduler tick failed")

    monkeypatch.setattr(connector_core, "run_due_syncs", boom)

    await connector_core.run_due_syncs_logged(provider="google", start_sync_job=lambda _j: None)


@pytest.mark.anyio
async def test_update_sync_progress_writes_counters() -> None:
    job = _job()
    counters = connector_core.ConnectorSyncCounters(found=3, created=1)
    session = FakeSession()

    await connector_core.update_sync_progress(
        session,
        job=job,
        counters=counters,
        phase="syncing",
        message="working",
        processed_items=1,
        total_items=3,
    )

    assert job.total_found == 3
    assert job.total_created == 1
    assert job.details["progress"]["phase"] == "syncing"
    assert session.commits == 1


@pytest.mark.anyio
async def test_create_sync_job_returns_existing_when_in_progress(monkeypatch) -> None:
    async def writes_allowed() -> None:
        return None

    monkeypatch.setattr("bigrag.services.maintenance.ensure_writes_allowed", writes_allowed)
    source = _source()
    existing = _job(status="pending", source_id=source.id)
    session = FakeSession(scalar_values=[existing])

    result = await connector_core.create_sync_job(
        session,
        provider="google",
        source=source,
        trigger="manual",
        user_id=None,
        commit=False,
    )

    assert result is existing


@pytest.mark.anyio
async def test_source_for_user_raises_when_missing() -> None:
    class ExecResult:
        def scalar_one_or_none(self):
            return None

    class S(FakeSession):
        async def execute(self, _stmt):
            return ExecResult()

    session = S()
    with pytest.raises(ValueError, match="not found"):
        await connector_core.source_for_user(
            session,
            provider="google",
            source_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            not_found_message="not found",
        )


@pytest.mark.anyio
async def test_list_sources_returns_serialized_rows() -> None:
    source = _source()
    account = _account()

    class ExecResult:
        def all(self):
            return [(source, account)]

    class S(FakeSession):
        async def execute(self, _stmt):
            return ExecResult()

    session = S()
    rows, total = await connector_core.list_sources(
        session,
        provider="google",
        user_id=str(account.user_id),
    )
    assert total == 1
    assert rows[0]["account_email"] == account.account_email


@pytest.mark.anyio
async def test_list_sync_jobs_returns_counts() -> None:
    job = _job()
    session = FakeSession(scalars_values=[[job]], scalar_values=[1])

    jobs, total = await connector_core.list_sync_jobs(
        session,
        provider="google",
        user_id=str(uuid.uuid4()),
        collection_name="docs",
        source_id=str(job.source_id),
        limit=10,
    )

    assert total == 1
    assert jobs[0]["id"] == str(job.id)
