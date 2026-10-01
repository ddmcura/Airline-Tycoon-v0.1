"""Terminal-only exact parsing and presentation helpers."""

from __future__ import annotations

from app.inputs import parse_duration_seconds, parse_usd_fare

from game.world_state.timestamps import normalize_utc_timestamp


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
