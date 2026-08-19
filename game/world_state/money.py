"""Exact money conversion at the authoritative-state boundary."""

from decimal import Decimal, InvalidOperation


MINOR_UNITS_PER_MAJOR = 100


def major_to_minor(value, field_name="amount"):
    """Convert a two-decimal major-unit input to an integer minor-unit value.

    Floats are deliberately rejected because their binary representation cannot
    be treated as an authoritative amount.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{field_name} must not use binary floating-point")
    if not isinstance(value, (int, str, Decimal)):
        raise ValueError(f"{field_name} must be an int, decimal string, or Decimal")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} is not a valid decimal amount") from exc
    if not amount.is_finite():
        raise ValueError(f"{field_name} must be finite")
    scaled = amount * MINOR_UNITS_PER_MAJOR
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{field_name} has more than two decimal places")
    return int(scaled)


def is_minor_amount(value):
    return isinstance(value, int) and not isinstance(value, bool)


def minor_to_decimal(value):
    """Return an exact display/reporting Decimal without changing authority."""
    if not is_minor_amount(value):
        raise ValueError("minor-unit amount must be an integer")
    return Decimal(value) / MINOR_UNITS_PER_MAJOR
