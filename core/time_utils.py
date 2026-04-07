from datetime import datetime, timezone


def now_utc() -> datetime:
    """Timezone-aware UTC datetime for DB defaults."""
    return datetime.now(timezone.utc)


def to_epoch_ms_utc(dt: datetime | None) -> int:
    """Convert datetime to epoch ms, treating naive values as UTC."""
    if dt is None:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

