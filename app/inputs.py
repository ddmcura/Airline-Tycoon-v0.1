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


_FARE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,2}))?\Z")


def parse_usd_fare(text):
    """Parse exact non-negative USD input for either frontend."""
    if not isinstance(text, str) or not text or len(text) > MAX_NUMERIC_INPUT_LENGTH:
        raise ValueError("fare must be a short USD amount such as 0, 99, or 99.50")
    if _FARE.fullmatch(text) is None:
        raise ValueError("fare must be a non-negative USD amount with at most two decimals")
    whole_text, fraction_text = text.split(".", 1) if "." in text else (text, "")
    fraction = int(fraction_text.ljust(2, "0")) if fraction_text else 0
    return int(whole_text) * 100 + fraction
