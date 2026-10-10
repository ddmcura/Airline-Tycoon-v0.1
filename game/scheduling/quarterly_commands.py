"""Dormant 2B/2C commands. Full candidates/gates are transitional.

Private derived indexes narrow discovery; no publication or operational consumers.
Only the serialized application owner may prepare/apply against live authority.
"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping

from game.utils.quarters import normal_target_quarter, parse_quarter_id
from game.world_state import validate_world
from game.world_state.planning_reference import planning_snapshot
from game.world_state.quarterly_construction import (
    create_service, allocate_service_slot, create_weekly_plan, append_weekly_plan_revision,
    commit_weekly_plan_publication)
from .quarterly_publication import (
    PublishQuarterlyPlan, publication_intent, resolve_publication, publication_sources,
    require_execution, carry_forward_selection)
from game.world_state.quarterly_validation import SLOT_FIELDS
from .quarterly_reads import (
    PlanReadRequest, QuarterlyReadResult, ReadIssue, _freeze, _lookup, _owned,
    _ReadFailure, _positive, resolve_quarterly_reads)
from .quarterly_edits import (
    ReviseQuarterlySlot, AddQuarterlyFrequency, RemoveQuarterlySlots,
    ContinueQuarterlySlot, RetireQuarterlyService, ReplaceQuarterlyService,
    edit_intent, resolve_edit, source_slot, proposed_edit_rows)
from .quarterly_feasibility import temporal_sources, certify_quarterly_feasibility


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
    skipped: bool = False
    planning_quarter_id: str | None = None


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


def _target(state, owner, now, index=None):
    """Editability query only; no workflow activation or target mutation."""
    quarter = normal_target_quarter(now)
    plans = (state['weekly_plans'][pid] for pid in index.ids('owner_plans', owner)) if index is not None else state['weekly_plans'].values()
    committed = {p['quarter_id'] for p in plans
        if p['airline_id'] == owner
        and p['revisions'][str(p['current_revision'])]['published_at_utc'] is not None}
    while quarter.quarter_id in committed:
        quarter = quarter.shift()
    return quarter.quarter_id


def _resolve(envelope, owner, intent, index=None):
    if intent['kind'] == 'PUBLISH':
        plan, read, _, _, _ = resolve_publication(envelope, owner, intent, index)
        return plan, read
    state = envelope['world_state']
    _lookup(state, 'airlines', owner, 'airline')
    pid = intent['weekly_plan_id']; expected = intent['expected_revision']
    if pid is None:
        if intent['kind'] not in {'CREATE', 'CONTINUE'}:
            _fail('INVALID_REQUEST', 'weekly_plan_id', 'operation requires an existing target plan')
        if type(expected) is not int or expected != 0:
            _fail('INVALID_REQUEST', 'expected_revision', 'creation requires explicit absence (0)')
        parse_quarter_id(intent['quarter_id'])
        exists = (index.plan_for_quarter(owner, intent['quarter_id']) is not None if index is not None else
                  any(p['airline_id'] == owner and p['quarter_id'] == intent['quarter_id'] for p in state['weekly_plans'].values()))
        if exists:
            _fail('STALE_REVISION', 'weekly_plan_id', 'quarter plan now exists; refresh')
        plan = None; quarter = intent['quarter_id']
        _, old, _ = carry_forward_selection(envelope, owner, quarter, index)
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
    from game.world_state.quarterly_boundary import correction_target
    if (quarter != _target(state, owner, envelope['simulation']['time_utc'], index)
            and not correction_target(envelope, owner, quarter)):
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
    elif intent['kind'] == 'CREATE':
        slot = intent['slot']
        aircraft = _lookup(state, 'aircraft', slot['planned_aircraft_id'], 'aircraft')
        _owned(aircraft, owner, 'planned_aircraft_id')
        for field in ('origin_airport_id', 'destination_airport_id'):
            _lookup(state, 'airports', slot[field], 'airport')
        if slot['connection_id'] is not None:
            connection = _lookup(state, 'connections', slot['connection_id'], 'connection')
            _owned(connection, owner, 'connection_id')
    else:
        resolve_edit(state, owner, intent)
    return plan, old


def _sources(envelope, owner, intent, index=None):
    """Exact typed observations via owned indexes or authoritative enumeration."""
    if intent['kind'] == 'PUBLISH':
        return publication_sources(envelope, owner, intent, index)
    state = envelope['world_state']; plan, old = _resolve(envelope, owner, intent, index)
    refs = set(old.dependencies) | {('airlines', owner)}
    slot = intent.get('slot', intent.get('changes', {}))
    if intent['kind'] == 'CONTINUE':
        source_aircraft = source_slot(state, owner, intent)['planned_aircraft_id']
        refs.add(('aircraft', source_aircraft))
        slot = dict(source_slot(state, owner, intent), **_plain(slot))
    if 'planned_aircraft_id' in slot:
        _owned(_lookup(state, 'aircraft', slot['planned_aircraft_id'], 'aircraft'), owner, 'planned_aircraft_id')
        refs.add(('aircraft', slot['planned_aircraft_id']))
    for field in ('origin_airport_id', 'destination_airport_id'):
        if field in slot:
            _lookup(state, 'airports', slot[field], 'airport'); refs.add(('airports', slot[field]))
    if slot.get('connection_id') is not None:
        connection = _lookup(state, 'connections', slot['connection_id'], 'connection')
        _owned(connection, owner, 'connection_id')
        refs.add(('connections', slot['connection_id']))
        refs.add(('directional_markets', connection['market_id']))
    records = {table + '/' + identity: state[table].get(identity)
        for table, identity in refs if table != 'weekly_plans'}
    for view in old.plans:
        selected = state['weekly_plans'][view.weekly_plan_id]; current = selected['current_revision']
        records['weekly_plans/' + view.weekly_plan_id] = {
            'weekly_plan_id': view.weekly_plan_id, 'airline_id': selected['airline_id'],
            'quarter_id': selected['quarter_id'], 'current_revision': current,
            'revisions': {str(current): selected['revisions'][str(current)]}}
    # Current memberships/retirements protect numbering and editability. No old revisions scanned.
    plans = ((pid, state['weekly_plans'][pid]) for pid in index.ids('owner_plans', owner)) if index is not None else state['weekly_plans'].items()
    owner_plans = {pid: {'quarter_id': p['quarter_id'], 'current_revision': p['current_revision'],
        'published_at_utc': p['revisions'][str(p['current_revision'])]['published_at_utc'],
        'services': sorted({s['service_id'] for s in p['revisions'][str(p['current_revision'])]['slots']})}
        for pid, p in plans if p['airline_id'] == owner}
    facts = {'time_utc': envelope['simulation']['time_utc'], 'records': records,
        'plans': owner_plans}
    aircraft_ids = {identity for table, identity in refs if table == 'aircraft'}
    facts['temporal'] = temporal_sources(envelope, aircraft_ids, index=index)
    if intent['kind'] == 'CONTINUE':
        facts['source_slot'] = source_slot(state, owner, intent)
    if intent['kind'] in {'CREATE', 'REPLACE', 'RETIRE', 'ADD', 'CONTINUE'}:
        facts['numbering'] = state['service_numbering'].get(owner)
        services = ((sid, state['services'][sid]) for sid in index.ids('owner_services', owner)) if index is not None else state['services'].items()
        facts['services'] = {sid: s for sid, s in services if s['airline_id'] == owner}
    return _freeze(facts)


def prepare_quarterly_command(envelope, *, airline_id, request, _indexes=None):
    try:
        _entry(envelope)
        index = _indexes.get(envelope) if _indexes is not None else None
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
            intent = publication_intent(request) if type(request) is PublishQuarterlyPlan else edit_intent(request)
            if intent is None:
                _fail('INVALID_REQUEST', 'request', 'unsupported quarterly planning operation')
        frozen = _freeze(intent)
        sources = _sources(envelope, airline_id, frozen, index)
        return QuarterlyCommandResult(succeeded=True,
            prepared=PreparedQuarterlyCommand(airline_id, frozen, sources))
    except _ReadFailure as exc:
        return QuarterlyCommandResult(issues=(exc.issue,))
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return rejected('INVALID_REQUEST', 'quarterly_command', str(exc))


def apply_quarterly_command(envelope, *, airline_id, prepared, _indexes=None):
    """Owner-authenticated preparation required. No candidate or writable result escapes."""
    try:
        _entry(envelope)
        index = _indexes.get(envelope) if _indexes is not None else None
        if type(prepared) is not PreparedQuarterlyCommand or prepared.airline_id != airline_id:
            _fail('OWNERSHIP_MISMATCH', 'prepared', 'command belongs to another owner')
        intent = prepared.intent
        if _sources(envelope, airline_id, intent, index) != prepared.sources:
            _fail('STALE_CONTEXT', 'prepared', 'dependency facts or simulation UTC changed; refresh')
        if intent['kind'] == 'PUBLISH':
            plan, old_read, publication_rows, baseline, skipped = resolve_publication(envelope, airline_id, intent, index)
            if skipped:
                result = QuarterlyCommandResult(True, weekly_plan_id=plan['weekly_plan_id'],
                    revision=plan['current_revision'], read=old_read, dependencies=old_read.dependencies,
                    skipped=True, planning_quarter_id=_target(envelope['world_state'], airline_id,
                                                             envelope['simulation']['time_utc'], index))
                if _sources(envelope, airline_id, intent, index) != prepared.sources:
                    _fail('STALE_CONTEXT', 'prepared', 'dependencies changed before skip')
                return result
        candidate = deepcopy(envelope)
        state = candidate['world_state']; pid = intent['weekly_plan_id']
        seed_rows = []
        if pid is None and intent['kind'] in {'CREATE', 'CONTINUE'}:
            _, _, seed_rows = carry_forward_selection(candidate, airline_id, intent['quarter_id'], index)
        if intent['kind'] == 'PUBLISH':
            rows = deepcopy(publication_rows); sid = number = None
        elif intent['kind'] in {'CREATE', 'REPLACE'}:
            sid = create_service(candidate, airline_id, flight_number_prefix=intent['flight_number_prefix'])
            number = allocate_service_slot(candidate, sid)
            slot = _plain(intent['slot'])
            slot.update(service_id=sid, slot_number=number, planning_timing=planning_snapshot(state,
                slot['planned_aircraft_id'], slot['origin_airport_id'], slot['destination_airport_id']))
            rows = deepcopy(seed_rows) if pid is None else deepcopy(state['weekly_plans'][pid]['revisions'][str(intent['expected_revision'])]['slots'])
            if intent['kind'] == 'REPLACE':
                rows = [s for s in rows if s['service_id'] != intent['service_id']]
            rows.append(slot); rows.sort(key=lambda s: (s['service_id'], s['slot_number']))
        elif intent['kind'] == 'FARE':
            sid = intent['service_id']; number = intent['slot_number']
            rows = deepcopy(state['weekly_plans'][pid]['revisions'][str(intent['expected_revision'])]['slots'])
            for slot in rows:
                if slot['service_id'] == sid and slot['slot_number'] == number:
                    slot['fare_offer'] = _plain(intent['fare_offer'])
        else:
            rows, sid, number = proposed_edit_rows(candidate, airline_id, intent, _plain, index=index)
            if pid is None and intent['kind'] == 'CONTINUE':
                # Explicit continuation may amend its inherited frequency;
                # all other continuing frequencies survive the first edit.
                merged = {(s['service_id'], s['slot_number']): s for s in deepcopy(seed_rows)}
                merged.update({(s['service_id'], s['slot_number']): s for s in rows})
                rows = [merged[key] for key in sorted(merged)]
        if pid is None:
            pid = create_weekly_plan(candidate, airline_id, intent['quarter_id'], slots=rows); revision = 1
        elif intent['kind'] in {'RETIRE', 'PUBLISH'}:
            revision = intent['expected_revision']
        else:
            revision = append_weekly_plan_revision(candidate, pid,
                expected_revision=intent['expected_revision'], slots=rows)
        if intent['kind'] == 'PUBLISH':
            commit_weekly_plan_publication(candidate, pid, expected_revision=revision)
        _entry(candidate)
        candidate_index = index.updated(candidate, plan_id=pid, service_id=sid) if index is not None else None
        if index is not None:
            index.verify_delta(candidate_index, candidate, plan_id=pid, service_id=sid)
        old_rows = [] if intent['weekly_plan_id'] is None else envelope['world_state']['weekly_plans'][
            intent['weekly_plan_id']]['revisions'][str(intent['expected_revision'])]['slots']
        old_by_key = {(s['service_id'], s['slot_number']): s for s in old_rows}
        new_by_key = {(s['service_id'], s['slot_number']): s for s in rows}
        changed = {key for key in old_by_key.keys() | new_by_key.keys()
                   if old_by_key.get(key) != new_by_key.get(key)}
        if intent['kind'] == 'PUBLISH':
            changed = old_by_key.keys() | new_by_key.keys()
        aircraft_ids = {s['planned_aircraft_id'] for key in changed
                       for s in (old_by_key.get(key), new_by_key.get(key)) if s is not None}
        try:
            gaps = []
            proof_arguments = {'_execution_blockers': gaps} if intent['kind'] == 'PUBLISH' else {}
            certify_quarterly_feasibility(candidate, aircraft_ids,
                through_utc=parse_quarter_id(state['weekly_plans'][pid]['quarter_id']).end_exclusive_utc,
                index=candidate_index, **proof_arguments)
        except ValueError as exc:
            _fail('INFEASIBLE_PLAN', 'weekly_plan.aircraft_chronology', str(exc))
        if intent['kind'] == 'PUBLISH':
            require_execution(candidate, airline_id, pid, aircraft_ids, gaps, candidate_index)
        detached = deepcopy(candidate)
        _entry(detached)
        read = resolve_quarterly_reads(detached, airline_id=airline_id,
            selections=(PlanReadRequest(pid, revision),))
        if not read.succeeded:
            _fail('INVALID_RESULT', 'read', 'candidate read failed')
        old_plan, old_read = _resolve(envelope, airline_id, intent, index)
        closure = set()
        if sid is not None:
            closure.add(('services', sid))
        tables = {'plans': 'weekly_plans', 'lineage': 'weekly_plans', 'schedules': 'schedule_definitions',
                  'flights': 'dated_flights', 'operations': 'active_aircraft_operations',
                  'aircraft': 'aircraft', 'airports': 'airports'}
        for observed in (temporal_sources(envelope, aircraft_ids, index=index), temporal_sources(candidate, aircraft_ids, index=candidate_index)):
            closure.update((table, identity) for category, table in tables.items() for identity in observed[category])
        result = QuarterlyCommandResult(True, service_id=sid, slot_number=number,
            weekly_plan_id=pid, revision=revision, read=read,
            dependencies=tuple(sorted(set(old_read.dependencies) | set(read.dependencies) | closure)),
            planning_quarter_id=(_target(state, airline_id, candidate['simulation']['time_utc'], candidate_index)
                                 if intent['kind'] == 'PUBLISH' else None))
        published_index = candidate_index.rebound(detached) if candidate_index is not None else None
        if _indexes is not None:
            published_index = _indexes.prepare_publication(published_index, detached)
        if _sources(envelope, airline_id, intent, index) != prepared.sources:
            _fail('STALE_CONTEXT', 'prepared', 'dependencies changed before commit')
        # Both copies/gates and detached response are ready before exposure. No yields.
        envelope.clear(); envelope.update(detached)
        if _indexes is not None:
            # All fallible delta/publication work precedes authority exposure.
            # The serialized owner publishes one prepared immutable reference.
            object.__setattr__(_indexes, 'current', published_index)
        return result
    except _ReadFailure as exc:
        return QuarterlyCommandResult(issues=(exc.issue,))
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return rejected('INVALID_REQUEST', 'quarterly_command', str(exc))
