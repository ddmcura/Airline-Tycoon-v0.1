"""Canonical whole-second UTC timestamp helpers for authoritative state."""

from datetime import datetime, timezone
from functools import lru_cache


def _uncached_canonical_utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.microsecond == 0 and parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


# Immutable, pure UTC syntax predicates dominate repeated historical validation.
# Bounded scalar memoization has no world/reference inputs or mutable results.
_canonical_utc_text = lru_cache(maxsize=4096)(_uncached_canonical_utc)


def is_canonical_utc(value):
    return (_canonical_utc_text(value) if type(value) is str
            else _uncached_canonical_utc(value))


def parse_canonical_utc(value, field_name="timestamp"):
    if not is_canonical_utc(value):
        raise ValueError(
            f"{field_name} must be canonical UTC YYYY-MM-DDTHH:MM:SSZ"
        )
    return datetime.fromisoformat(value[:-1] + "+00:00")


def format_utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    try:
        value = value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValueError("timestamp is outside the canonical UTC range") from exc
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
    if value.microsecond:
        raise ValueError(f"{field_name} must use whole-second precision")
    return format_utc(value)
