"""Validation of the JSON-compatible authoritative persistence boundary."""

import math


def json_compatibility_error(value):
    """Return ``(path, message)`` for the first invalid value, or ``None``."""
    active = set()

    def walk(item, path):
        if item is None or type(item) in (str, bool, int):
            return None
        if type(item) is float:
            if math.isfinite(item):
                return None
            return path, "floating-point values must be finite"
        if type(item) is dict:
            marker = id(item)
            if marker in active:
                return path, "cyclic data is not JSON-compatible"
            active.add(marker)
            try:
                for key, nested in item.items():
                    if not isinstance(key, str):
                        return path, "dictionary keys must be strings"
                    error = walk(nested, f"{path}.{key}")
                    if error:
                        return error
            finally:
                active.remove(marker)
            return None
        if type(item) is list:
            marker = id(item)
            if marker in active:
                return path, "cyclic data is not JSON-compatible"
            active.add(marker)
            try:
                for index, nested in enumerate(item):
                    error = walk(nested, f"{path}[{index}]")
                    if error:
                        return error
            finally:
                active.remove(marker)
            return None
        return path, f"{type(item).__name__} is not JSON-compatible"

    try:
        return walk(value, "$")
    except RecursionError:
        return "$", "nesting exceeds the supported JSON validation depth"


def require_json_compatible(value, field_name="value"):
    error = json_compatibility_error(value)
    if error:
        path, message = error
        raise ValueError(f"{field_name} at {path}: {message}")
