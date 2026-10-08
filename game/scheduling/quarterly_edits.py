"""Explicit dormant 2C intents; no broad CRUD, publication or carry-forward."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping

from game.utils.quarters import parse_quarter_id
from game.world_state.timestamps import parse_canonical_utc
from game.world_state.quarterly_construction import allocate_service_slot, retire_service
from game.world_state.quarterly_validation import SLOT_FIELDS
from game.world_state.planning_reference import planning_snapshot
from .quarterly_reads import _lookup, _owned, _ReadFailure, _positive


@dataclass(frozen=True)
class ReviseQuarterlySlot:
    weekly_plan_id: str
    expected_revision: int
    service_id: str
    slot_number: int
    changes: Mapping


@dataclass(frozen=True)
class AddQuarterlyFrequency:
    weekly_plan_id: str
    expected_revision: int
    service_id: str
    slot: Mapping


@dataclass(frozen=True)
class RemoveQuarterlySlots:
    weekly_plan_id: str
    expected_revision: int
    slot_keys: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ContinueQuarterlySlot:
    weekly_plan_id: str | None
    expected_revision: int
    source_plan_id: str
    source_expected_revision: int
    source_revision: int
    service_id: str
    slot_number: int
    changes: Mapping
    quarter_id: str | None = None  # explicit destination absence is revision 0


@dataclass(frozen=True)
class RetireQuarterlyService:
    weekly_plan_id: str
    expected_revision: int
    service_id: str


@dataclass(frozen=True)
class ReplaceQuarterlyService:
    weekly_plan_id: str
    expected_revision: int
    service_id: str
    flight_number_prefix: str
    slot: Mapping


def fail(code, path, message):
    raise _ReadFailure(code, path, message)


def edit_intent(request):
    kinds = {ReviseQuarterlySlot: 'REVISE', AddQuarterlyFrequency: 'ADD',
             RemoveQuarterlySlots: 'REMOVE', ContinueQuarterlySlot: 'CONTINUE',
             RetireQuarterlyService: 'RETIRE', ReplaceQuarterlyService: 'REPLACE'}
    kind = kinds.get(type(request))
    if kind is None:
        return None
    intent = dict(request.__dict__, kind=kind)
    if kind in {'REVISE', 'CONTINUE'}:
        if type(request.changes) is not dict or not request.changes:
            # Continuation can explicitly retain unchanged source facts.
            if kind != 'CONTINUE' or request.changes != {}:
                fail('INVALID_REQUEST', 'changes', 'explicit nonempty canonical changes required')
        if set(request.changes) & {'origin_airport_id', 'destination_airport_id'}:
            fail('ENDPOINT_REPLACEMENT_REQUIRED', 'changes', 'endpoint replacement requires a new service')
        allowed = SLOT_FIELDS - {'service_id', 'slot_number', 'planning_timing',
                                'origin_airport_id', 'destination_airport_id'}
        if not set(request.changes) <= allowed:
            fail('INVALID_REQUEST', 'changes', 'only non-endpoint planned facts may change')
    if kind in {'ADD', 'REPLACE'} and (type(request.slot) is not dict or set(request.slot) != SLOT_FIELDS - {
            'service_id', 'slot_number', 'planning_timing'}):
        fail('INVALID_REQUEST', 'slot', 'canonical frequency facts required')
    if kind == 'REMOVE' and (type(request.slot_keys) is not tuple or not request.slot_keys
                            or len(set(request.slot_keys)) != len(request.slot_keys)):
        fail('INVALID_REQUEST', 'slot_keys', 'distinct explicit service/slot keys required')
    if kind == 'REMOVE':
        if any(type(k) is not tuple or len(k) != 2 for k in request.slot_keys):
            fail('INVALID_REQUEST', 'slot_keys', 'canonical service/slot pairs required')
        intent['slot_keys'] = [list(k) for k in request.slot_keys]
    return intent


def selected_rows(state, intent):
    if intent['weekly_plan_id'] is None:
        return []
    return state['weekly_plans'][intent['weekly_plan_id']]['revisions'][str(intent['expected_revision'])]['slots']


def source_slot(state, owner, intent):
    plan = _lookup(state, 'weekly_plans', intent['source_plan_id'], 'weekly_plan')
    _owned(plan, owner, 'source_plan_id')
    if not _positive(intent['source_expected_revision']) or intent['source_expected_revision'] != plan['current_revision']:
        fail('STALE_REVISION', 'source_expected_revision', 'refresh source plan')
    revision = intent['source_revision']
    if not _positive(revision) or str(revision) not in plan['revisions']:
        fail('INVALID_REFERENCE', 'source_revision', 'source revision is absent')
    target_quarter = (intent['quarter_id'] if intent['weekly_plan_id'] is None
                      else state['weekly_plans'][intent['weekly_plan_id']]['quarter_id'])
    if parse_quarter_id(plan['quarter_id']) >= parse_quarter_id(target_quarter):
        fail('INVALID_REFERENCE', 'source_plan_id', 'continuation requires an earlier quarter source')
    matches = [s for s in plan['revisions'][str(revision)]['slots']
               if (s['service_id'], s['slot_number']) == (intent['service_id'], intent['slot_number'])]
    if len(matches) != 1:
        fail('INVALID_REFERENCE', 'source_slot', 'explicit source lineage is absent')
    return matches[0]


def resolve_edit(state, owner, intent):
    rows = selected_rows(state, intent); kind = intent['kind']
    keys = intent['slot_keys'] if kind == 'REMOVE' else ((intent['service_id'], intent.get('slot_number')),)
    for sid, number in keys:
        service = _lookup(state, 'services', sid, 'service'); _owned(service, owner, 'service_id')
        if service['retired_at_utc'] is not None and kind != 'REMOVE':
            fail('RETIRED_SERVICE', 'service_id', 'retired identity cannot continue or be edited')
        if kind in {'REVISE', 'REMOVE'} and (not _positive(number) or not any(
                (s['service_id'], s['slot_number']) == (sid, number) for s in rows)):
            fail('INVALID_REFERENCE', 'slot_number', 'frequency is absent from current plan')
    if kind == 'CONTINUE':
        source_slot(state, owner, intent)
        if any((s['service_id'], s['slot_number']) == (intent['service_id'], intent['slot_number']) for s in rows):
            fail('DUPLICATE_REFERENCE', 'slot_number', 'continuing frequency already exists in target')
    if kind == 'REPLACE' and not any(s['service_id'] == intent['service_id'] for s in rows):
        fail('INVALID_REFERENCE', 'service_id', 'replacement service is absent from target')


def proposed_edit_rows(candidate, owner, intent, thaw):
    state = candidate['world_state']; rows = deepcopy(selected_rows(state, intent)); kind = intent['kind']
    sid = intent.get('service_id'); number = intent.get('slot_number')
    if kind == 'RETIRE':
        now = parse_canonical_utc(candidate['simulation']['time_utc'])
        for plan in state['weekly_plans'].values():
            if plan['airline_id'] != owner or parse_quarter_id(plan['quarter_id']).end_exclusive_utc <= now:
                continue
            current = plan['revisions'][str(plan['current_revision'])]
            if current['published_at_utc'] is None and any(s['service_id'] == sid for s in current['slots']):
                fail('SERVICE_IN_USE', 'service_id', 'remove editable continuation first; committed use remains protected')
        retire_service(candidate, sid)
    elif kind == 'REMOVE':
        keys = {tuple(k) for k in intent['slot_keys']}
        rows = [s for s in rows if (s['service_id'], s['slot_number']) not in keys]
    else:
        if kind == 'ADD':
            number = allocate_service_slot(candidate, sid)
            row = thaw(intent['slot']); row.update(service_id=sid, slot_number=number); rows.append(row)
        elif kind == 'CONTINUE':
            row = deepcopy(source_slot(state, owner, intent)); row.update(thaw(intent['changes'])); rows.append(row)
        else:
            row = next(s for s in rows if (s['service_id'], s['slot_number']) == (sid, number))
            row.update(thaw(intent['changes']))
        row['planning_timing'] = planning_snapshot(state, row['planned_aircraft_id'],
            row['origin_airport_id'], row['destination_airport_id'])
    rows.sort(key=lambda s: (s['service_id'], s['slot_number']))
    return rows, sid, number
