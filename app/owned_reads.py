"""Private read context for the application's exclusive validated world owner.

Not an arbitrary-envelope projection API. Session construction/load/validated
commands establish this context; foreign world bindings require a full gate.
All derived state is disposable and bounded, never passed to event handlers.
"""
import json
from collections import OrderedDict

from game.aircraft_operations.projections import (
    _build_operations_lookup, _page_options, _project_airline_fleet_owned,
    _project_airline_flights_owned, _project_recent_flight_results_owned,
)


def _source_parts(world):
    # Strong references prevent identity reuse. Observe subtree replacement and
    # collection size changes even when an external validated command preserves
    # the top-level envelope. In-place writes to borrowed rows are NOT supported:
    # the session exclusively owns mutations; external input must be rebound.
    sim = world['simulation']
    values = (world, *world.values(), *world['world_state'].values(), *sim.values())
    containers = tuple((value, len(value)) for value in values
                       if type(value) in (dict, list))
    clock = (sim['time_utc'], sim['clock_state'],
             sim['fast_forward']['target_time_utc'],
             sim['configuration']['clock_ratios']['NORMAL'])
    return containers, clock


class _OwnedReadViews:
    """One source/revision epoch; no cache or index escapes this owner."""

    def __init__(self, world, revision):
        self.world = world
        self.revision = revision
        self._parts = _source_parts(world)
        self._lookup = None
        self._lookup_ready = False
        self._pages = OrderedDict()

    def matches(self, world, revision):
        if world is not self.world or revision != self.revision:
            return False
        try:
            parts, clock = _source_parts(world)
        except (KeyError, TypeError, AttributeError):
            return False  # Malformed foreign replacement must reacquire the gate.
        old, old_clock = self._parts
        return (clock == old_clock and len(parts) == len(old)
                and all(a is b and size == old_size
                        for (a,size),(b,old_size) in zip(parts,old)))

    def _operations(self):
        if not self._lookup_ready:
            self._lookup = _build_operations_lookup(self.world)
            self._lookup_ready = True
        return self._lookup

    def _page(self, key, render):
        # Immutable encoded values, detached decode on EVERY return. Bound memory
        # to eight bounded pages, rather than retaining full worlds per query.
        if key not in self._pages:
            self._pages[key] = json.dumps(render(), separators=(',', ':'), allow_nan=False)
            if len(self._pages) > 8:
                self._pages.popitem(last=False)
        self._pages.move_to_end(key)
        return json.loads(self._pages[key])

    def fleet(self, airline_id, *, offset, limit):
        _page_options(limit, offset)
        return self._page(('fleet',airline_id,offset,limit), lambda:
            _project_airline_fleet_owned(self.world,airline_id,offset=offset,limit=limit))

    def flights(self, airline_id, *, offset, limit):
        _page_options(limit, offset)
        return self._page(('flights',airline_id,offset,limit), lambda:
            _project_airline_flights_owned(self.world,airline_id,offset=offset,limit=limit,
                                          lookup=self._operations()))

    def finances(self, airline_id):
        return self._page(('finance',airline_id), lambda:
            _project_recent_flight_results_owned(self.world,airline_id,
                                                 lookup=self._operations()))
