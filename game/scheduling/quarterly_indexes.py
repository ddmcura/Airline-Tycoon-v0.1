"""Private reconstructible Scheduling inverse relationships, never save authority.

Only the serialized session owner uses maintained coverage. Foreign dictionaries
retain source enumeration. Immutable snapshots and staged deltas precede commit.
"""
from bisect import bisect_right
from types import MappingProxyType

from game.utils.quarters import parse_quarter_id
from game.world_state.timestamps import parse_canonical_utc
from .timing import flight_reservation

_ROOTS = ('airlines', 'aircraft', 'airports', 'connections', 'directional_markets',
          'services', 'service_numbering', 'weekly_plans', 'schedule_definitions',
          'dated_flights', 'active_aircraft_operations')
_SEAL = object()


def _plan_links(plan):
    current = plan['revisions'][str(plan['current_revision'])]
    rows = tuple((s['service_id'], s['slot_number'], s['planned_aircraft_id'],
                  s['origin_airport_id'], s['destination_airport_id'], s['connection_id'])
                 for s in current['slots'])
    return plan['airline_id'], plan['quarter_id'], plan['current_revision'], current['published_at_utc'], rows


def _edges(pid, facts):
    owner, quarter, revision, published, rows = facts
    yield 'owner_plans', owner, pid
    for sid, number, aid, origin, dest, connection in rows:
        yield 'aircraft_plans', aid, pid
        yield 'service_plans', sid, pid
        yield 'aircraft_slots', aid, (pid, sid, number)
        yield 'airport_plans', origin, pid
        yield 'airport_plans', dest, pid
        if connection is not None:
            yield 'connection_plans', connection, pid


class QuarterlyDependencyIndex:
    """Sealed immutable edge coverage bound to one validated owned world epoch."""
    __slots__ = ('_maps', '_plans', '_quarters', '_numbers', '_endpoints', '_ends', '_departures',
                 '_roots', '_time', '_turnaround', '_seal', 'epoch')

    def __setattr__(self, name, value):
        raise AttributeError('immutable dependency snapshot')

    @classmethod
    def _make(cls, envelope, maps, plans, numbers, endpoints, ends, departures, epoch):
        result = object.__new__(cls)
        for name, value in {
            '_maps': MappingProxyType({name: MappingProxyType(dict(values)) for name, values in maps.items()}),
            '_plans': MappingProxyType(dict(plans)), '_numbers': MappingProxyType(dict(numbers)),
            '_quarters': MappingProxyType({(facts[0], facts[1]): pid for pid, facts in plans.items()}),
            '_endpoints': MappingProxyType(dict(endpoints)), '_ends': MappingProxyType(dict(ends)),
            '_departures': MappingProxyType(dict(departures)),
            '_roots': tuple((envelope['world_state'][name], len(envelope['world_state'][name])) for name in _ROOTS),
            '_time': envelope['simulation']['time_utc'],
            '_turnaround': envelope['simulation']['configuration']['scheduling']['minimum_turnaround_seconds'],
            '_seal': _SEAL, 'epoch': epoch}.items():
            object.__setattr__(result, name, value)
        return result

    @classmethod
    def _build(cls, envelope):
        """Caller has already passed the complete authority trust boundary."""
        state = envelope['world_state']; maps = {}; plans = {}; endpoints = {}; numbers = {}
        def edge(name, key, value):
            maps.setdefault(name, {}).setdefault(key, set()).add(value)
        for pid, plan in sorted(state['weekly_plans'].items()):
            plans[pid] = _plan_links(plan)
            for name, key, value in _edges(pid, plans[pid]):
                edge(name, key, value)
            for revision in plan['revisions'].values():
                for slot in revision['slots']:
                    pair = slot['origin_airport_id'], slot['destination_airport_id']
                    if endpoints.setdefault(slot['service_id'], pair) != pair:
                        raise ValueError('endpoint index source is inconsistent')
        for sid, service in sorted(state['services'].items()):
            owner = service['airline_id']; edge('owner_services', owner, sid)
            numbers[sid] = (owner, service['flight_number_number'], service['retired_at_utc'])
        for sid, schedule in sorted(state['schedule_definitions'].items()):
            for revision in schedule['revisions'].values():
                edge('aircraft_schedules', revision['planned_aircraft_id'], sid)
        ends = {}; departures = {}
        minimum = envelope['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']
        from datetime import timedelta
        for fid, flight in sorted(state['dated_flights'].items()):
            if flight['status'] in {'SUPERSEDED', 'CANCELLED'}:
                continue
            aid = flight['planned_aircraft_id']; edge('aircraft_flights', aid, fid)
            end = max(flight_reservation(state, flight)[1],
                      parse_canonical_utc(flight['scheduled_in_block_utc'])+timedelta(seconds=minimum))
            ends.setdefault(aid, []).append((end, fid))
            departures.setdefault(aid, []).append((parse_canonical_utc(flight['scheduled_off_block_utc']), fid))
        for oid, operation in sorted(state['active_aircraft_operations'].items()):
            edge('aircraft_operations', operation['actual_aircraft_id'], oid)
        frozen = {name: {key: frozenset(values) for key, values in keys.items()} for name, keys in maps.items()}
        return cls._make(envelope, frozen, plans, numbers, endpoints,
                         {aid: tuple(sorted(rows)) for aid, rows in ends.items()},
                         {aid: tuple(sorted(rows)) for aid, rows in departures.items()}, 0)

    def matches(self, envelope):
        state = envelope['world_state']
        return (self._seal is _SEAL and self._time == envelope['simulation']['time_utc']
                and self._turnaround == envelope['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']
                and all(root is state[name] and count == len(state[name])
                        for name, (root, count) in zip(_ROOTS, self._roots)))

    def ids(self, relation, key):
        return tuple(sorted(self._maps.get(relation, {}).get(key, ())))

    def plan_for_quarter(self, owner, quarter):
        return self._quarters.get((owner, quarter))

    def live_plans(self, relation, key):
        now = parse_canonical_utc(self._time)
        return tuple(pid for pid in self.ids(relation, key)
                     if parse_quarter_id(self._plans[pid][1]).end_exclusive_utc > now)

    def relevant_flights(self, aircraft_id):
        rows = self._ends.get(aircraft_id, ())
        start = bisect_right(rows, (parse_canonical_utc(self._time), chr(0x10ffff)))
        return tuple(sorted(fid for _, fid in rows[start:]))

    def neighbors(self, aircraft_id, departure):
        rows = self._departures.get(aircraft_id, ())
        position = bisect_right(rows, (departure, chr(0x10ffff)))
        return (rows[position-1][1] if position else None,
                rows[position][1] if position < len(rows) else None)

    def number_holders(self, owner):
        protected = {sid for sid in self.ids('owner_services', owner) if self._numbers[sid][2] is None}
        for pid in self.live_plans('owner_plans', owner):
            facts = self._plans[pid]
            if facts[3] is not None:
                protected.update(row[0] for row in facts[4])
        holders = {}
        for sid in sorted(protected):
            holders.setdefault(self._numbers[sid][1], set()).add(sid)
        if any(len(ids) != 1 for ids in holders.values()):
            raise ValueError('protected number index collision')
        return MappingProxyType({suffix: frozenset(ids) for suffix, ids in sorted(holders.items())})

    def eligible_numbers(self, owner):
        holders = self.number_holders(owner)
        return tuple(sorted({self._numbers[sid][1] for sid in self.ids('owner_services', owner)
                             if self._numbers[sid][2] is not None and self._numbers[sid][1] not in holders}))

    def updated(self, candidate, *, plan_id, service_id):
        """Stage only accepted quarterly writer deltas; no source-wide discovery.

        Shallow map publication is O(index keys); edge changes are local. Legacy
        source maps are shared until their writer explicitly invalidates coverage.
        """
        state = candidate['world_state']; maps = {name: dict(values) for name, values in self._maps.items()}
        plans = dict(self._plans); numbers = dict(self._numbers); endpoints = dict(self._endpoints)
        old = plans.get(plan_id); new = _plan_links(state['weekly_plans'][plan_id])
        old_edges = set(_edges(plan_id, old)) if old is not None else set()
        new_edges = set(_edges(plan_id, new))
        for name, key, value in old_edges - new_edges:
            remaining = maps[name][key] - {value}
            if remaining: maps[name][key] = remaining
            else: del maps[name][key]
        for name, key, value in new_edges - old_edges:
            values = maps.setdefault(name, {})
            values[key] = values.get(key, frozenset()) | {value}
        plans[plan_id] = new
        for sid, _, _, origin, dest, _ in new[4]:
            pair = origin, dest
            if endpoints.setdefault(sid, pair) != pair:
                raise ValueError('endpoint delta contradicts retained identity')
        if service_id is not None:
            service = state['services'][service_id]; owner = service['airline_id']
            numbers[service_id] = owner, service['flight_number_number'], service['retired_at_utc']
            keys = maps.setdefault('owner_services', {})
            keys[owner] = keys.get(owner, frozenset()) | {service_id}
        return type(self)._make(candidate, maps, plans, numbers, endpoints,
                               self._ends, self._departures, self.epoch+1)

    def rebound(self, detached):
        return type(self)._make(detached, self._maps, self._plans, self._numbers,
                               self._endpoints, self._ends, self._departures, self.epoch)

    def verify_delta(self, proposed, candidate, *, plan_id, service_id):
        """Coverage fence before indexed feasibility, not a feasibility proof.

        Verify affected source facts and preservation of all other cached edges.
        Comparing immutable maps is O(index keys), not a world/history rescan.
        The independent test oracle enumerates authority without this builder.
        """
        if type(proposed) is not type(self) or not proposed.matches(candidate) or proposed.epoch != self.epoch+1:
            raise ValueError('stale or uncertified dependency delta')
        state = candidate['world_state']; expected = {name: dict(values) for name,values in self._maps.items()}
        previous = self._plans.get(plan_id); current = _plan_links(state['weekly_plans'][plan_id])
        # Remove old plan contributions then add exact resulting membership.
        for name,key,value in set(_edges(plan_id,previous)) if previous is not None else ():
            remaining = expected[name][key]-{value}
            if remaining:expected[name][key]=remaining
            else:del expected[name][key]
        for name,key,value in set(_edges(plan_id,current)):
            values=expected.setdefault(name,{})
            values[key]=values.get(key,frozenset())|{value}
        numbers=dict(self._numbers)
        if service_id is not None:
            service=state['services'][service_id];owner=service['airline_id']
            values=expected.setdefault('owner_services',{})
            values[owner]=values.get(owner,frozenset())|{service_id}
            numbers[service_id]=(owner,service['flight_number_number'],service['retired_at_utc'])
        plans=dict(self._plans);plans[plan_id]=current
        endpoints=dict(self._endpoints)
        for sid,_,_,origin,dest,_ in current[4]:
            if endpoints.setdefault(sid,(origin,dest)) != (origin,dest):
                raise ValueError('endpoint coverage conflicts with retained authority')
        if (proposed._maps != expected or proposed._plans != plans or proposed._numbers != numbers
                or proposed._endpoints != endpoints or proposed._ends != self._ends
                or proposed._departures != self._departures
                or proposed._quarters != {(facts[0],facts[1]):pid for pid,facts in plans.items()}):
            raise ValueError('incomplete inverse dependency delta')


class QuarterlyIndexOwner:
    """Session-private freshness lifetime; never returned to a frontend."""
    __slots__ = ('current',)
    def __init__(self):
        self.current = None

    def invalidate(self):
        self.current = None

    def get(self, envelope):
        if self.current is not None and type(self.current) is not QuarterlyDependencyIndex:
            raise ValueError('untrusted dependency index coverage')
        if self.current is None or not self.current.matches(envelope):
            self.current = QuarterlyDependencyIndex._build(envelope)
        return self.current

    def prepare_publication(self, prepared_index, detached):
        if (type(prepared_index) is not QuarterlyDependencyIndex
                or not prepared_index.matches(detached)
                or self.current is None or prepared_index.epoch != self.current.epoch+1):
            raise ValueError('incomplete or stale dependency publication')
        return prepared_index
