"""Private candidate-local IDs for the existing confirmed carriage predicate.

Booking/itinerary authority is protected by the certified write capsules. This is
not a Stage 2 index, persisted state, manifest cache, or validation bypass.
"""
from types import MappingProxyType
from game.simulation.candidate_ownership import is_read_dict
from game.world_state.schema import (
    AGGREGATE_BOOKING_CONTRACT, DIRECT_ECONOMY_ITINERARY_CONTRACT,
)


def _flight_relation(world, booking):
    # Match the canonical manifest preselection; all lineage checks remain there.
    if (not is_read_dict(booking)
            or booking.get('contract') != AGGREGATE_BOOKING_CONTRACT
            or booking.get('status') != 'CONFIRMED'):
        return None
    itinerary = world['itineraries'].get(booking.get('itinerary_id'))
    if (not is_read_dict(itinerary)
            or itinerary.get('contract') != DIRECT_ECONOMY_ITINERARY_CONTRACT
            or itinerary.get('status') != 'CONFIRMED'):
        return None
    ids = itinerary.get('dated_flight_ids')
    if ids is None or len(ids) != 1:
        return None
    return ids[0]


def _build_groups(world):
    groups = {}
    for booking_id, booking in world['bookings'].items():
        flight_id = _flight_relation(world, booking)
        if flight_id is not None:
            groups.setdefault(flight_id, []).append(booking_id)
    return {key: tuple(sorted(ids)) for key, ids in groups.items()}


def _verify_groups(world, groups):
    # Independent coverage check before making the mapping immutable. Detect
    # omission, duplicate/surplus IDs and wrong association, not just row counts.
    reverse = {}
    for flight_id, ids in groups.items():
        if type(flight_id) is not str or flight_id not in world['dated_flights']:
            raise ValueError('invalid candidate manifest flight association')
        if type(ids) is not tuple or ids != tuple(sorted(set(ids))):
            raise ValueError('invalid candidate manifest ID ordering/duplicates')
        for booking_id in ids:
            if type(booking_id) is not str or booking_id in reverse:
                raise ValueError('duplicate candidate manifest Booking')
            reverse[booking_id] = flight_id
    expected = 0
    for booking_id, booking in world['bookings'].items():
        flight_id = _flight_relation(world, booking)
        if flight_id is None:
            if booking_id in reverse:
                raise ValueError('unconfirmed candidate manifest Booking')
            continue
        expected += 1
        if (booking.get('booking_id') != booking_id
                or reverse.get(booking_id) != flight_id):
            raise ValueError('candidate manifest lookup disagrees with authority')
    if len(reverse) != expected:
        raise ValueError('missing/surplus candidate manifest Booking')


class CandidateManifestLookup:
    """Derived immutable IDs, current-authority resolution, explicit disposal."""
    protected_collections = frozenset(('bookings', 'itineraries'))

    def __init__(self, candidate):
        if candidate['metadata']['save_schema_version'] not in (7, 8):
            raise ValueError('candidate manifest lookup requires Schema 7')
        self._world = candidate['world_state']
        self._sources = {name: self._world[name] for name in self.protected_collections}
        self._sizes = {name: len(rows) for name, rows in self._sources.items()}
        groups = _build_groups(self._world)
        _verify_groups(self._world, groups)
        self._groups = MappingProxyType(groups)

    def lookup(self, envelope, flight_id):
        if self._world is None:
            raise ValueError('candidate manifest lookup expired')
        if any(self._world[name] is not source or len(source) != self._sizes[name]
               for name, source in self._sources.items()):
            raise ValueError('candidate manifest lookup source changed')
        ids = self._groups.get(flight_id, ())
        # IDs resolve against the CURRENT capsule/predecessor, never cloned rows.
        world = envelope['world_state']
        for booking_id in ids:
            booking = world['bookings'].get(booking_id)
            if (not is_read_dict(booking) or booking.get('booking_id') != booking_id
                    or _flight_relation(world, booking) != flight_id):
                raise ValueError('candidate manifest lookup disagrees with authority')
        return ids

    def close(self):
        self._groups = MappingProxyType({})
        self._sources.clear()
        self._sizes.clear()
        self._world = None
