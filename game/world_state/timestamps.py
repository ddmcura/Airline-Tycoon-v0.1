"""Canonical whole-second UTC timestamp helpers for authoritative state."""

from datetime import datetime, timezone


def is_canonical_utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.microsecond == 0 and parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def parse_canonical_utc(value, field_name="timestamp"):
    if not is_canonical_utc(value):
        raise ValueError(
            f"{field_name} must be canonical UTC YYYY-MM-DDTHH:MM:SSZ"
        )
    return datetime.fromisoformat(value[:-1] + "+00:00")


def format_utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    value = value.astimezone(timezone.utc)
    if value.microsecond:
        raise ValueError("timestamp must use whole-second precision")
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_utc_timestamp(value, field_name="timestamp"):
    if isinstance(value, str):
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            value = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be an ISO-8601 UTC timestamp"
            ) from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    try:
        return format_utc(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use whole-second precision") from exc
