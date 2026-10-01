"""Frontend-independent parsing for application control inputs."""

import re


_DURATION = re.compile(r"([1-9][0-9]*)([mhd])\Z")
MAX_NUMERIC_INPUT_LENGTH = 32


def parse_duration_seconds(text):
    if not isinstance(text, str) or len(text) > MAX_NUMERIC_INPUT_LENGTH:
        raise ValueError("duration must be a positive whole number followed by m, h, or d")
    match = _DURATION.fullmatch(text)
    if match is None:
        raise ValueError("duration must look like 30m, 6h, or 1d")
    amount = int(match.group(1))
    multiplier = {"m": 60, "h": 3600, "d": 86400}[match.group(2)]
    return amount * multiplier
