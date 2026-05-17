from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bigrag.db.models import ConnectorSource


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def next_sync_at(source: ConnectorSource, *, from_time: datetime | None = None) -> datetime | None:
    if not source.schedule_enabled:
        return None
    interval = max(1, int(source.sync_interval_hours or 24))
    if from_time is None and source.next_sync_at is not None and source.next_sync_at < utcnow():
        from_time = source.next_sync_at
    return (from_time or utcnow()) + timedelta(hours=interval)
