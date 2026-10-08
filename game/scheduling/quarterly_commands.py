"""Restricted dormant 2B commands. Full candidates/gates are transitional.

No executable feasibility certificate, inverse indexes, publication or consumers.
Only the serialized application owner may prepare/apply against live authority.
"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping

from game.utils.quarters import normal_target_quarter, parse_quarter_id
from game.world_state import validate_world
from game.world_state.planning_reference import planning_snapshot
from game.world_state.quarterly_construction import (
    create_service, allocate_service_slot, create_weekly_plan, append_weekly_plan_revision)
from game.world_state.quarterly_validation import SLOT_FIELDS
from .quarterly_reads import (
    PlanReadRequest, QuarterlyReadResult, ReadIssue, _freeze, _lookup, _owned,
    _ReadFailure, _positive, resolve_quarterly_reads)


@dataclass(frozen=True)
class CreateQuarterlyService:
    quarter_id: str
    flight_number_prefix: str
    slot: Mapping
    weekly_plan_id: str | None = None
    expected_revision: int = 0  # explicit absence expectation


@dataclass(frozen=True)
class ReviseQuarterlyFare:
    weekly_plan_id: str
    expected_revision: int
    service_id: str
    slot_number: int
    fare_offer: Mapping


@dataclass(frozen=True)
class PreparedQuarterlyCommand:
    airline_id: str
    intent: Mapping
    sources: Mapping


@dataclass(frozen=True)
class QuarterlyCommandResult:
    succeeded: bool = False
    prepared: PreparedQuarterlyCommand | None = None
    service_id: str | None = None
    slot_number: int | None = None
    weekly_plan_id: str | None = None
    revision: int | None = None
    read: QuarterlyReadResult | None = None
    dependencies: tuple[tuple[str, str], ...] = ()
    issues: tuple[ReadIssue, ...] = ()


def rejected(code, path, message, observed_revision=None):
    return QuarterlyCommandResult(issues=(ReadIssue(code, path, message, observed_revision),))


def _fail(code, path, message, observed=None):
    raise _ReadFailure(code, path, message, observed)


def _plain(value):
    """Thaw only internally frozen JSON observations, never accept arbitrary objects."""
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_plain(item) for item in value]
    return value


def _entry(envelope):
    metadata = envelope.get('metadata') if type(envelope) is dict else None
    if type(metadata) is not dict or metadata.get('save_schema_version') != 9:
        _fail('INVALID_SCHEMA', 'metadata.save_schema_version', 'Schema 9 required')
    result = validate_world(envelope)
    if not result.is_valid:
        issue = result.errors[0]
        _fail('INVALID_WORLD', issue.path, issue.message)


def _target(state, owner, now):
    """Editability query only; no workflow activation or target mutation."""
    quarter = normal_target_quarter(now)
    committed = {p['quarter_id'] for p in state['weekly_plans'].values()
        if p['airline_id'] == owner
        and p['revisions'][str(p['current_revision'])]['published_at_utc'] is not None}
    while quarter.quarter_id in committed:
        quarter = quarter.shift()
    return quarter.quarter_id


def _resolve(envelope, owner, intent):
    state = envelope['world_state']
    _lookup(state, 'airlines', owner, 'airline')
    pid = intent['weekly_plan_id']; expected = intent['expected_revision']
    if pid is None:
        if type(expected) is not int or expected != 0:
            _fail('INVALID_REQUEST', 'expected_revision', 'creation requires explicit absence (0)')
        parse_quarter_id(intent['quarter_id'])
        if any(p['airline_id'] == owner and p['quarter_id'] == intent['quarter_id']
               for p in state['weekly_plans'].values()):
            _fail('STALE_REVISION', 'weekly_plan_id', 'quarter plan now exists; refresh')
        plan = None; quarter = intent['quarter_id']; old = QuarterlyReadResult()
    else:
        plan = _lookup(state, 'weekly_plans', pid, 'weekly_plan')
        _owned(plan, owner, 'weekly_plan_id')
        if not _positive(expected):
            _fail('INVALID_REQUEST', 'expected_revision', 'positive expected revision required')
        if expected != plan['current_revision']:
            _fail('STALE_REVISION', 'expected_revision', 'refresh current plan', plan['current_revision'])
        quarter = plan['quarter_id']
        if intent['kind'] == 'CREATE' and intent['quarter_id'] != quarter:
            _fail('INVALID_REQUEST', 'quarter_id', 'plan quarter mismatch')
        if plan['revisions'][str(expected)]['published_at_utc'] is not None:
            _fail('PUBLISHED_PLAN', 'weekly_plan_id', 'ordinary published edits are locked')
        old = resolve_quarterly_reads(envelope, airline_id=owner,
            selections=(PlanReadRequest(pid, expected),))
        if not old.succeeded:
            raise _ReadFailure(old.issues[0].code, old.issues[0].path, old.issues[0].message)
    if quarter != _target(state, owner, envelope['simulation']['time_utc']):
        _fail('CLOSED_TARGET', 'quarter_id', 'use the eligible unpublished future quarter')
    if intent['kind'] == 'FARE':
        sid = intent['service_id']; service = _lookup(state, 'services', sid, 'service')
        _owned(service, owner, 'service_id')
        if service['retired_at_utc'] is not None:
            _fail('RETIRED_SERVICE', 'service_id', 'retired services cannot be revised')
        if not _positive(intent['slot_number']) or not any(
                s['service_id'] == sid and s['slot_number'] == intent['slot_number']
                for s in plan['revisions'][str(expected)]['slots']):
            _fail('INVALID_REFERENCE', 'slot_number', 'frequency is absent from current plan')
    else:
        slot = intent['slot']
        aircraft = _lookup(state, 'aircraft', slot['planned_aircraft_id'], 'aircraft')
        _owned(aircraft, owner, 'planned_aircraft_id')
        for field in ('origin_airport_id', 'destination_airport_id'):
            _lookup(state, 'airports', slot[field], 'airport')
        if slot['connection_id'] is not None:
            connection = _lookup(state, 'connections', slot['connection_id'], 'connection')
            _owned(connection, owner, 'connection_id')
    return plan, old


def _sources(envelope, owner, intent):
    """Exact relevant observations, not a complete-world fingerprint or 2D index."""
    state = envelope['world_state']; plan, old = _resolve(envelope, owner, intent)
    refs = set(old.dependencies) | {('airlines', owner)}
    if intent['kind'] == 'CREATE':
        slot = intent['slot']
        refs.add(('aircraft', slot['planned_aircraft_id']))
        refs.update(('airports', slot[k]) for k in ('origin_airport_id', 'destination_airport_id'))
        if slot['connection_id'] is not None:
            refs.add(('connections', slot['connection_id']))
            refs.add(('directional_markets', state['connections'][slot['connection_id']]['market_id']))
    records = {table + '/' + identity: state[table].get(identity)
        for table, identity in refs if table != 'weekly_plans'}
    if plan is not None:
        current = plan['current_revision']
        records['weekly_plans/' + plan['weekly_plan_id']] = {
            'weekly_plan_id': plan['weekly_plan_id'], 'airline_id': plan['airline_id'],
            'quarter_id': plan['quarter_id'], 'current_revision': current,
            'revisions': {str(current): plan['revisions'][str(current)]}}
    # Current memberships/retirements protect numbering and editability. No old revisions scanned.
    owner_plans = {pid: {'quarter_id': p['quarter_id'], 'current_revision': p['current_revision'],
        'published_at_utc': p['revisions'][str(p['current_revision'])]['published_at_utc'],
        'services': sorted({s['service_id'] for s in p['revisions'][str(p['current_revision'])]['slots']})}
        for pid, p in state['weekly_plans'].items() if p['airline_id'] == owner}
    facts = {'time_utc': envelope['simulation']['time_utc'], 'records': records,
        'plans': owner_plans}
    if intent['kind'] == 'CREATE':
        facts['numbering'] = state['service_numbering'].get(owner)
        facts['services'] = {sid: s for sid, s in state['services'].items() if s['airline_id'] == owner}
    return _freeze(facts)


def prepare_quarterly_command(envelope, *, airline_id, request):
    try:
        _entry(envelope)
        if type(request) is CreateQuarterlyService:
            if type(request.slot) is not dict or set(request.slot) != SLOT_FIELDS - {
                    'service_id', 'slot_number', 'planning_timing'}:
                _fail('INVALID_REQUEST', 'slot', 'canonical initial facts required; IDs/timing are allocated/derived')
            intent = {'kind': 'CREATE', 'quarter_id': request.quarter_id,
                'weekly_plan_id': request.weekly_plan_id, 'expected_revision': request.expected_revision,
                'flight_number_prefix': request.flight_number_prefix, 'slot': request.slot}
        elif type(request) is ReviseQuarterlyFare:
            if type(request.fare_offer) is not dict or set(request.fare_offer) != {'currency', 'amount_minor'}:
                _fail('INVALID_REQUEST', 'fare_offer', 'canonical fare offer required')
            intent = {'kind': 'FARE', 'weekly_plan_id': request.weekly_plan_id,
                'expected_revision': request.expected_revision, 'service_id': request.service_id,
                'slot_number': request.slot_number, 'fare_offer': request.fare_offer}
        else:
            _fail('INVALID_REQUEST', 'request', 'only service creation and fare revision are exposed in 2B')
        frozen = _freeze(intent)
        sources = _sources(envelope, airline_id, frozen)
        return QuarterlyCommandResult(succeeded=True,
            prepared=PreparedQuarterlyCommand(airline_id, frozen, sources))
    except _ReadFailure as exc:
        return QuarterlyCommandResult(issues=(exc.issue,))
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return rejected('INVALID_REQUEST', 'quarterly_command', str(exc))


def apply_quarterly_command(envelope, *, airline_id, prepared):
    """Owner-authenticated preparation required. No candidate or writable result escapes."""
    try:
        _entry(envelope)
        if type(prepared) is not PreparedQuarterlyCommand or prepared.airline_id != airline_id:
            _fail('OWNERSHIP_MISMATCH', 'prepared', 'command belongs to another owner')
        intent = prepared.intent
        if _sources(envelope, airline_id, intent) != prepared.sources:
            _fail('STALE_CONTEXT', 'prepared', 'dependency facts or simulation UTC changed; refresh')
        candidate = deepcopy(envelope)
        state = candidate['world_state']; pid = intent['weekly_plan_id']
        if intent['kind'] == 'CREATE':
            sid = create_service(candidate, airline_id, flight_number_prefix=intent['flight_number_prefix'])
            number = allocate_service_slot(candidate, sid)
            slot = _plain(intent['slot'])
            slot.update(service_id=sid, slot_number=number, planning_timing=planning_snapshot(state,
                slot['planned_aircraft_id'], slot['origin_airport_id'], slot['destination_airport_id']))
            rows = [] if pid is None else deepcopy(state['weekly_plans'][pid]['revisions'][str(intent['expected_revision'])]['slots'])
            rows.append(slot); rows.sort(key=lambda s: (s['service_id'], s['slot_number']))
        else:
            sid = intent['service_id']; number = intent['slot_number']
            rows = deepcopy(state['weekly_plans'][pid]['revisions'][str(intent['expected_revision'])]['slots'])
            for slot in rows:
                if slot['service_id'] == sid and slot['slot_number'] == number:
                    slot['fare_offer'] = _plain(intent['fare_offer'])
        if pid is None:
            pid = create_weekly_plan(candidate, airline_id, intent['quarter_id'], slots=rows); revision = 1
        else:
            revision = append_weekly_plan_revision(candidate, pid,
                expected_revision=intent['expected_revision'], slots=rows)
        _entry(candidate)
        detached = deepcopy(candidate)
        _entry(detached)
        read = resolve_quarterly_reads(detached, airline_id=airline_id,
            selections=(PlanReadRequest(pid, revision),))
        if not read.succeeded:
            _fail('INVALID_RESULT', 'read', 'candidate read failed')
        old_plan, old_read = _resolve(envelope, airline_id, intent)
        result = QuarterlyCommandResult(True, service_id=sid, slot_number=number,
            weekly_plan_id=pid, revision=revision, read=read,
            dependencies=tuple(sorted(set(old_read.dependencies) | set(read.dependencies))))
        if _sources(envelope, airline_id, intent) != prepared.sources:
            _fail('STALE_CONTEXT', 'prepared', 'dependencies changed before commit')
        # Both copies/gates and detached response are ready before exposure. No yields.
        envelope.clear(); envelope.update(detached)
        return result
    except _ReadFailure as exc:
        return QuarterlyCommandResult(issues=(exc.issue,))
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return rejected('INVALID_REQUEST', 'quarterly_command', str(exc))
