"""Deterministic named-timezone loading for authoritative scheduling."""

from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@lru_cache(maxsize=None)
def load_named_timezone(timezone_name):
    """Load named rules exclusively from the project-pinned ``tzdata`` package."""
    if not isinstance(timezone_name, str) or not timezone_name:
        raise ValueError("timezone name must be a non-empty string")
    parts = timezone_name.split("/")
    if any(part in {"", ".", ".."} or "\\" in part for part in parts):
        raise ValueError("timezone name must be a canonical IANA key")
    try:
        resource = files("tzdata.zoneinfo")
        for part in parts:
            resource = resource.joinpath(part)
        with resource.open("rb") as stream:
            return ZoneInfo.from_file(stream, key=timezone_name)
    except (OSError, ModuleNotFoundError) as exc:
        raise ZoneInfoNotFoundError(
            f"pinned tzdata does not contain timezone {timezone_name!r}"
        ) from exc
