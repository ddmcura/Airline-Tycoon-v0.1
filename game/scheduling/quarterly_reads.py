"""Dormant Schema-8 direct dependency reads, never mutation certificates.

The application owner supplies validated authority; foreign session bindings keep
the existing full gate. Reads inspect only explicitly selected plan versions and
their direct references. Endpoint consistency covers that selection only, not
unrequested quarterly history. No inverse index, allocation or event publication.
"""
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Mapping

from game.world_state.ids import parse_entity_id
from game.world_state.quarterly_validation import validate_slots
from game.world_state.timestamps import parse_canonical_utc
from .service_identity import flight_number, plan_lifecycle


@dataclass(frozen=True)
class PlanReadRequest:
    weekly_plan_id: str
    expected_revision: int
    revision: int | None = None
    slot_keys: tuple[tuple[str, int], ...] | None = None


@dataclass(frozen=True)
class ReadIssue:
    code: str
    path: str
    message: str
    observed_revision: int | None = None


@dataclass(frozen=True)
class SlotRead:
    service_id: str
    slot_number: int
    flight_number: str
    retired_at_utc: str | None
    market_id: str | None
    facts: Mapping


@dataclass(frozen=True)
class PlanRead:
    weekly_plan_id: str
    airline_id: str
    quarter_id: str
    current_revision: int
    revision: int
    published_at_utc: str | None
    current_lifecycle: str
    slots: tuple[SlotRead, ...]


@dataclass(frozen=True)
class QuarterlyReadResult:
    plans: tuple[PlanRead, ...] = ()
    dependencies: tuple[tuple[str, str], ...] = ()
    source_time_utc: str | None = None
    issues: tuple[ReadIssue, ...] = ()

    @property
    def succeeded(self):
        return bool(self.plans) and not self.issues


class _ReadFailure(ValueError):
    def __init__(self, code, path, message, observed_revision=None):
        self.issue = ReadIssue(code, path, message, observed_revision)


def _positive(value):
    return type(value) is int and value > 0


def _freeze(value):
    """Copy JSON facts recursively into immutable, disposable read values."""
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in sorted(value.items())})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and isfinite(value):
        return value
    raise ValueError('noncanonical JSON read fact')


def _lookup(state, table, identity, entity_type):
    path = f'world_state.{table}.{identity}'
    if parse_entity_id(identity, entity_type) is None:
        raise _ReadFailure('INVALID_REFERENCE', path, 'canonical internal ID required')
    record = state[table].get(identity)
    if type(record) is not dict or record.get(f'{entity_type}_id') != identity:
        raise _ReadFailure('INVALID_REFERENCE', path, 'entity is absent or identity mismatched')
    return record


def _owned(record, airline_id, path):
    if record.get('airline_id') != airline_id:
        raise _ReadFailure('OWNERSHIP_MISMATCH', path, 'entity belongs to another airline')


def _selection(slots, slot_keys):
    if slot_keys is None:
        return slots
    if type(slot_keys) is not tuple:
        raise _ReadFailure('INVALID_REQUEST', 'slot_keys', 'immutable explicit slot keys required')
    wanted = set()
    for key in slot_keys:
        if (type(key) is not tuple or len(key) != 2
                or parse_entity_id(key[0], 'service') is None or not _positive(key[1])):
            raise _ReadFailure('INVALID_REQUEST', 'slot_keys', 'invalid service/slot key')
        if key in wanted:
            raise _ReadFailure('INVALID_REQUEST', 'slot_keys', 'duplicate requested slot')
        wanted.add(key)
    chosen = [row for row in slots if (row['service_id'], row['slot_number']) in wanted]
    if {(row['service_id'], row['slot_number']) for row in chosen} != wanted:
        raise _ReadFailure('INVALID_REFERENCE', 'slot_keys', 'slot absent from selected version')
    return chosen


def resolve_quarterly_reads(envelope, *, airline_id, selections):
    """Resolve one or more explicit retained versions in one read snapshot.

    expected_revision observes the current pointer; revision optionally selects
    immutable older facts. Comparisons are explicit additional requests, avoiding
    global history discovery. No result grants editability, bookability or complete
    feasibility. Rejected reads return no partial views and consume nothing.
    """
    try:
        if envelope['metadata']['save_schema_version'] not in (8, 9):
            raise _ReadFailure('INVALID_SCHEMA', 'metadata.save_schema_version', 'Schema 8 or 9 required')
        if type(selections) is not tuple or not selections:
            raise _ReadFailure('INVALID_REQUEST', 'selections', 'nonempty immutable request sequence required')
        for request in selections:
            if (type(request) is not PlanReadRequest
                    or parse_entity_id(request.weekly_plan_id, 'weekly_plan') is None
                    or not _positive(request.expected_revision)
                    or (request.revision is not None and not _positive(request.revision))):
                raise _ReadFailure('INVALID_REQUEST', 'selections', 'invalid plan/version request')
        state = envelope['world_state']
        _lookup(state, 'airlines', airline_id, 'airline')
        now = envelope['simulation']['time_utc']
        parse_canonical_utc(now)
        dependencies = {('airlines', airline_id)}
        views, seen, endpoints = [], set(), {}
        ordered = sorted(selections, key=lambda r: (r.weekly_plan_id, r.revision or 0))
        for request in ordered:
            pid = request.weekly_plan_id
            plan = _lookup(state, 'weekly_plans', pid, 'weekly_plan')
            _owned(plan, airline_id, f'world_state.weekly_plans.{pid}')
            current = plan['current_revision']
            if not _positive(current):
                raise _ReadFailure('INVALID_REFERENCE', f'world_state.weekly_plans.{pid}',
                                   'invalid current revision')
            if request.expected_revision != current:
                raise _ReadFailure('STALE_REVISION', f'world_state.weekly_plans.{pid}',
                                   'current revision changed; refresh', current)
            revision = current if request.revision is None else request.revision
            row = plan['revisions'].get(str(revision))
            if revision > current or type(row) is not dict or row.get('revision') != revision:
                raise _ReadFailure('INVALID_REFERENCE', f'world_state.weekly_plans.{pid}.revisions',
                                   'retained revision absent')
            if (pid, revision) in seen:
                raise _ReadFailure('INVALID_REQUEST', 'selections', 'duplicate selected plan/version')
            seen.add((pid, revision))
            dependencies.add(('weekly_plans', pid))
            slots = _selection(row['slots'], request.slot_keys)
            resolved = []
            for slot in slots:
                sid = slot['service_id']
                service = _lookup(state, 'services', sid, 'service')
                _owned(service, airline_id, f'world_state.services.{sid}')
                aid = slot['planned_aircraft_id']
                aircraft = _lookup(state, 'aircraft', aid, 'aircraft')
                _owned(aircraft, airline_id, f'world_state.aircraft.{aid}')
                origin, dest = slot['origin_airport_id'], slot['destination_airport_id']
                for airport in (origin, dest):
                    _lookup(state, 'airports', airport, 'airport')
                    dependencies.add(('airports', airport))
                pair = (origin, dest)
                if endpoints.setdefault(sid, pair) != pair:
                    raise _ReadFailure('ENDPOINT_INCONSISTENCY', f'world_state.services.{sid}',
                                       'selected versions change service endpoints; new identity required')
                market_id = None
                if slot['service_type'] == 'PASSENGER':
                    cid = slot['connection_id']
                    connection = _lookup(state, 'connections', cid, 'connection')
                    _owned(connection, airline_id, f'world_state.connections.{cid}')
                    market_id = connection['market_id']
                    _lookup(state, 'directional_markets', market_id, 'market')
                    dependencies.update((('connections', cid), ('directional_markets', market_id)))
                dependencies.update((('services', sid), ('aircraft', aid),
                                     ('service_numbering', airline_id)))
                # Display numbers come from service identity; historical duplicates are permitted in Schema 9.
                number = service['flight_number_number']
                if not _positive(number) or number >= state['service_numbering'][airline_id]['next_number']:
                    raise _ReadFailure('INVALID_REFERENCE', f'world_state.services.{sid}',
                                       'unallocated display number')
                resolved.append(SlotRead(sid, slot['slot_number'], flight_number(state, sid),
                                         service['retired_at_utc'], market_id, _freeze(slot)))
            # Reuse existing local fact rules; do not weaken or replace validate_world.
            validate_slots(state, airline_id, slots)
            views.append(PlanRead(pid, airline_id, plan['quarter_id'], current, revision,
                                  row['published_at_utc'], plan_lifecycle(plan, now), tuple(resolved)))
        views.sort(key=lambda view: (view.weekly_plan_id, view.revision))
        return QuarterlyReadResult(tuple(views), tuple(sorted(dependencies)), now)
    except _ReadFailure as exc:
        return QuarterlyReadResult(issues=(exc.issue,))
    except (KeyError, TypeError, ValueError) as exc:
        return QuarterlyReadResult(issues=(ReadIssue('INVALID_REFERENCE', 'quarterly_read', str(exc)),))
