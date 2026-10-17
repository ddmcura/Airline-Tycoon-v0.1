"""Application ownership admission and detached runtime status (runtime-only)."""
from copy import deepcopy
from dataclasses import dataclass

from game.world_state import validate_world


@dataclass(frozen=True)
class RuntimeView:
    state: str
    draining: bool
    processing: bool
    running: bool
    blocked: bool
    closed: bool
    diagnostic: str | None
    earned_target_utc: str
    credit_ns: int


def detach_foreign_world(value):
    """Reject compatibility callbacks/aliases before copying foreign authority."""
    def plain(item):
        if type(item) is dict:
            return all(type(key) is str and plain(child) for key, child in item.items())
        if type(item) is list:
            return all(plain(child) for child in item)
        return item is None or type(item) in (str, int, float, bool)

    # Full validity includes the canonical alias/cycle and JSON predicates.
    result = validate_world(value)
    if not result.is_valid:
        raise ValueError('invalid closed-owner world: ' + result.errors[0].message)
    if not plain(value):
        raise ValueError('closed-owner acquisition requires plain state; use legacy mode')
    return deepcopy(value)
