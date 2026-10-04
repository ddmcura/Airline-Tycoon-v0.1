"""Frozen Stage 3E graph predicates: independent exact diagnostic oracle."""
import math
from game.world_state.money import is_minor_amount
from game.world_state.timestamps import is_canonical_utc as _canonical_utc

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

def _container_alias_error(value):
    """Return the first repeated mutable-container path in schema-3 authority."""
    seen = {}
    stack = [(value, "$")]
    while stack:
        item, path = stack.pop()
        if type(item) not in (dict, list):
            continue
        marker = id(item)
        previous = seen.get(marker)
        if previous is not None:
            return path, previous
        seen[marker] = path
        if type(item) is dict:
            for key, nested in item.items():
                stack.append((nested, f"{path}.{key}"))
        else:
            for index, nested in enumerate(item):
                stack.append((nested, f"{path}[{index}]"))
    return None

def validate_no_name_references_or_float_money(self):
    forbidden = {
        "airline_name",
        "aircraft_registration",
        "assigned_aircraft_registration",
        "assigned_aircraft",
        "current_focus",
        "origin_iata",
        "destination_iata",
        "route_id",
    }

    stack = [(self.world, "$.world_state")]
    seen_containers = set()
    while stack:
        value, path = stack.pop()
        if type(value) is dict:
            marker = id(value)
            if marker in seen_containers:
                continue
            seen_containers.add(marker)
            for key, nested in value.items():
                invalid_name = key in forbidden
                invalid_money = isinstance(key, str) and key.endswith("_minor") and not is_minor_amount(nested)
                invalid_time = (isinstance(key, str) and key.endswith("_utc")
                                and nested is not None and not _canonical_utc(nested))
                container = type(nested) in (dict, list)
                # Primitive leaves have already been checked at their owning
                # field. They cannot contain another authoritative field.
                if invalid_name or invalid_money or invalid_time or container:
                    child_path = f"{path}.{key}"
                    if invalid_name:
                        self.add("name_based_authoritative_reference", child_path, "legacy/name-based authoritative field is forbidden")
                    if invalid_money:
                        self.add("invalid_money", child_path, "authoritative money must be integer minor units")
                    if invalid_time:
                        self.add("invalid_timestamp", child_path, "authoritative timestamp must be canonical UTC YYYY-MM-DDTHH:MM:SSZ")
                    if container:
                        stack.append((nested, child_path))
        elif type(value) is list:
            marker = id(value)
            if marker in seen_containers:
                continue
            seen_containers.add(marker)
            for index, nested in enumerate(value):
                if type(nested) in (dict, list):
                    stack.append((nested, f"{path}[{index}]"))
