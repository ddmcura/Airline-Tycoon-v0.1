"""Strict parsing and validation of external aircraft catalog reference authority."""

import json
import re
from urllib.parse import urlsplit


_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")


def _text(value, path):
    if (type(value) is not str or not value or value != value.strip()
            or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value)):
        raise ValueError(f"{path}: expected nonempty stripped text without controls")


def _identifier(value, path):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError(f"{path}: invalid stable identifier")


def _fields(value, fields, path):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError(f"{path}: unexpected or missing fields")


def _integer(value, low, high, path):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{path}: expected integer in {low}..{high}")


def validate_aircraft_catalog(pack):
    """Raise ValueError on invalid reference content; never mutate or repair it."""
    _fields(pack, "contract catalog_version manufacturers models reference_prices sources", "catalog")
    if pack["contract"] != "AIRCRAFT_CATALOG_V1":
        raise ValueError("unsupported aircraft catalog contract")
    _identifier(pack["catalog_version"], "catalog_version")
    for name in ("manufacturers", "models", "reference_prices", "sources"):
        if type(pack[name]) is not dict or not pack[name]:
            raise ValueError(f"{name}: expected nonempty collection")
        for key in pack[name]:
            _identifier(key, name)

    for key, record in pack["manufacturers"].items():
        _fields(record, "manufacturer_id display_name notes", key)
        if record["manufacturer_id"] != key:
            raise ValueError(f"{key}: manufacturer identity mismatch")
        _text(record["display_name"], key)
        _text(record["notes"], key)

    for key, record in pack["sources"].items():
        _fields(record, "source_id title url", key)
        if record["source_id"] != key:
            raise ValueError(f"{key}: source identity mismatch")
        _text(record["title"], key)
        _text(record["url"], key)
        try:
            url = urlsplit(record["url"])
            valid = (url.scheme == "https" and url.hostname and not url.username
                     and not url.password and not any(c.isspace() for c in record["url"]))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError(f"{key}: expected HTTPS source URL")

    for key, record in pack["models"].items():
        _fields(record, "model_id manufacturer_id display_name family aircraft_category "
                "max_economy_seats reference_range_km cruise_speed_kph "
                "production_start_year production_end_year source_ids notes", key)
        if record["model_id"] != key:
            raise ValueError(f"{key}: model identity mismatch")
        _identifier(record["manufacturer_id"], key)
        if record["manufacturer_id"] not in pack["manufacturers"]:
            raise ValueError(f"{key}: missing manufacturer")
        for name in ("display_name", "family", "notes"):
            _text(record[name], f"{key}.{name}")
        if record["aircraft_category"] not in (
                "NARROWBODY", "WIDEBODY", "REGIONAL_JET", "TURBOPROP"):
            raise ValueError(f"{key}: unsupported aircraft category")
        for name, high in (("max_economy_seats", 1000),
                           ("reference_range_km", 30000), ("cruise_speed_kph", 2000)):
            _integer(record[name], 1, high, f"{key}.{name}")
        start, end = record["production_start_year"], record["production_end_year"]
        for year in (start, end):
            if year is not None:
                _integer(year, 1900, 9999, f"{key}.production_year")
        if start is not None and end is not None and end < start:
            raise ValueError(f"{key}: production end precedes start")
        refs = record["source_ids"]
        if type(refs) is not list or not refs:
            raise ValueError(f"{key}: expected source identifiers")
        for ref in refs:
            _identifier(ref, key)
            if ref not in pack["sources"]:
                raise ValueError(f"{key}: missing source {ref}")
        if len(refs) != len(set(refs)):
            raise ValueError(f"{key}: duplicate source identifiers")

    if set(pack["reference_prices"]) != set(pack["models"]):
        raise ValueError("reference prices must cover exactly the model identifiers")
    for key, record in pack["reference_prices"].items():
        _fields(record, "model_id currency amount_minor basis", key)
        if record["model_id"] != key:
            raise ValueError(f"{key}: price identity mismatch")
        if record["currency"] != "USD" or record["basis"] != "GAME_NEW_EQUIVALENT_V1":
            raise ValueError(f"{key}: unsupported reference price basis or currency")
        _integer(record["amount_minor"], 1, 1_000_000_000_000, key)


def parse_aircraft_catalog(text):
    """Reject duplicate keys before dictionary construction discards evidence."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate aircraft catalog key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"invalid JSON constant: {value}")

    pack = json.loads(text, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    validate_aircraft_catalog(pack)
    return pack
