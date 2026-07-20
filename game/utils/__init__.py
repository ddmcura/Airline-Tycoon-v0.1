from importlib import import_module

from .dev import enable_dev_mode
from .formatting import country_flag
from .ui import paginate


__all__ = [
    "country_flag",
    "enable_dev_mode",
    "paginate",
    "render_airports",
    "render_country_names",
]


def __getattr__(name):
    if name in {"render_airports", "render_country_names"}:
        return getattr(import_module("game.utils.render"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
