"""Terminal-only exact parsing and presentation helpers."""

from __future__ import annotations

import re

from game.world_state.timestamps import normalize_utc_timestamp


_FARE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,2}))?\Z")
_DURATION = re.compile(r"([1-9][0-9]*)([mhd])\Z")
MAX_NUMERIC_INPUT_LENGTH = 32


def parse_usd_fare(text):
    if not isinstance(text, str) or not text or len(text) > MAX_NUMERIC_INPUT_LENGTH:
        raise ValueError("fare must be a short USD amount such as 0, 99, or 99.50")
    match = _FARE.fullmatch(text)
    if match is None:
        raise ValueError("fare must be a non-negative USD amount with at most two decimals")
    whole_text, fraction_text = text.split(".", 1) if "." in text else (text, "")
    fraction = int(fraction_text.ljust(2, "0")) if fraction_text else 0
    return int(whole_text) * 100 + fraction


def parse_duration_seconds(text):
    if not isinstance(text, str) or len(text) > MAX_NUMERIC_INPUT_LENGTH:
        raise ValueError("duration must be a positive whole number followed by m, h, or d")
    match = _DURATION.fullmatch(text)
    if match is None:
        raise ValueError("duration must look like 30m, 6h, or 1d")
    amount = int(match.group(1))
    multiplier = {"m": 60, "h": 3600, "d": 86400}[match.group(2)]
    return amount * multiplier


def parse_utc_timestamp(text):
    return normalize_utc_timestamp(text, "target UTC timestamp")


def round_ratio_half_even(value, numerator, denominator):
    """Round signed ``value * numerator / denominator`` to nearest even integer."""
    if any(isinstance(item, bool) or not isinstance(item, int) for item in (
        value, numerator, denominator
    )) or numerator <= 0 or denominator <= 0:
        raise ValueError("conversion ratio requires integers and a positive ratio")
    sign = -1 if value < 0 else 1
    quotient, remainder = divmod(abs(value) * numerator, denominator)
    doubled = remainder * 2
    if doubled > denominator or (doubled == denominator and quotient % 2 == 1):
        quotient += 1
    return sign * quotient


def format_minor_units(value, *, symbol="", code=""):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("money value must be integer minor units")
    sign = "-" if value < 0 else ""
    whole, fraction = divmod(abs(value), 100)
    suffix = f" {code}" if code else ""
    return f"{sign}{symbol}{whole:,}.{fraction:02d}{suffix}"


def format_money(usd_minor, display_currency, display_rates):
    usd = format_minor_units(usd_minor, symbol="$", code="USD")
    if display_currency == "USD":
        return usd
    rate = display_rates[display_currency]
    converted = round_ratio_half_even(
        usd_minor,
        rate["minor_per_usd_minor_numerator"],
        rate["minor_per_usd_minor_denominator"],
    )
    shown = format_minor_units(
        converted, symbol=rate["symbol"], code=display_currency
    )
    return f"{usd} ({shown} display)"


def format_basis_points(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("basis points must be an integer")
    whole, fraction = divmod(abs(value), 100)
    sign = "-" if value < 0 else ""
    return f"{sign}{whole}.{fraction:02d}%"


__all__ = (
    "MAX_NUMERIC_INPUT_LENGTH", "format_basis_points", "format_minor_units",
    "format_money", "parse_duration_seconds", "parse_usd_fare",
    "parse_utc_timestamp", "round_ratio_half_even",
)
