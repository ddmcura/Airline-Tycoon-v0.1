"""Shared dormant publication intent and proof. No operational supply/events."""
from dataclasses import dataclass

from game.utils.quarters import parse_quarter_id, quarter_containing
from game.world_state.timestamps import parse_canonical_utc
from .quarterly_reads import (
    PlanReadRequest, QuarterlyReadResult, _ReadFailure, _lookup, _owned, resolve_quarterly_reads,
)


@dataclass(frozen=True)
class PublishQuarterlyPlan:
    mode: str
    quarter_id: str
    weekly_plan_id: str | None = None
    expected_revision: int = 0
    expected_time_utc: str | None = None


def publication_intent(request):
    if type(request) is not PublishQuarterlyPlan:
        return None
    return {'kind': 'PUBLISH', 'mode': request.mode, 'quarter_id': request.quarter_id,
            'weekly_plan_id': request.weekly_plan_id, 'expected_revision': request.expected_revision,
            'expected_time_utc': request.expected_time_utc}


def _baseline(plans, quarter):
    previous = [p for p in plans if parse_quarter_id(p['quarter_id']) < quarter
                and p['revisions'][str(p['current_revision'])]['published_at_utc'] is not None]
    return max(previous,key=lambda p:parse_quarter_id(p['quarter_id'])) if previous else None


def carry_forward_selection(envelope, owner, quarter_id, index=None):
    """Default first-edit snapshot; no allocation and no implicit retirement revival."""
    from .quarterly_readiness import _owner_plans
    state=envelope['world_state']
    baseline=_baseline(_owner_plans(state,owner,index).values(),parse_quarter_id(quarter_id))
    if baseline is None:
        return None,QuarterlyReadResult(),[]
    read=resolve_quarterly_reads(envelope,airline_id=owner,
        selections=(PlanReadRequest(baseline['weekly_plan_id'],baseline['current_revision']),))
    if not read.succeeded:
        issue=read.issues[0]; raise _ReadFailure(issue.code,issue.path,issue.message)
    rows=[s for s in baseline['revisions'][str(baseline['current_revision'])]['slots']
          if state['services'][s['service_id']]['retired_at_utc'] is None]
    return baseline,read,rows


def resolve_publication(envelope, owner, intent, index=None):
    from .quarterly_commands import _target
    from .quarterly_readiness import _owner_plans, publication_boundary
    state = envelope['world_state']
    _lookup(state, 'airlines', owner, 'airline')
    mode = intent['mode']
    if mode not in ('MANUAL', 'AUTOMATIC'):
        raise _ReadFailure('INVALID_REQUEST', 'mode', 'MANUAL or AUTOMATIC required')
    quarter = parse_quarter_id(intent['quarter_id'])
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    if intent['expected_time_utc'] is not None:
        parse_canonical_utc(intent['expected_time_utc'])
        if intent['expected_time_utc'] != envelope['simulation']['time_utc']:
            raise _ReadFailure('STALE_CONTEXT', 'time_utc', 'simulation UTC changed')
    plans = _owner_plans(state, owner, index)
    actual = next((p for p in plans.values() if p['quarter_id'] == quarter.quarter_id), None)
    pid = intent['weekly_plan_id']; expected = intent['expected_revision']
    if pid is None:
        if type(expected) is not int or expected != 0:
            raise _ReadFailure('INVALID_REQUEST', 'expected_revision', 'missing target requires absence observation 0')
        if actual is not None:
            raise _ReadFailure('STALE_REVISION', 'weekly_plan_id', 'target now exists; observe its ID/revision')
        plan = None
    else:
        plan = _lookup(state, 'weekly_plans', pid, 'weekly_plan')
        _owned(plan, owner, 'weekly_plan_id')
        if plan['quarter_id'] != quarter.quarter_id:
            raise _ReadFailure('INVALID_REQUEST', 'quarter_id', 'selected plan belongs to another quarter')
        if type(expected) is not int or expected < 1:
            raise _ReadFailure('INVALID_REQUEST', 'expected_revision', 'positive current observation required')
        if plan['current_revision'] != expected:
            raise _ReadFailure('STALE_REVISION', 'expected_revision', 'refresh current plan', plan['current_revision'])
    committed = plan is not None and plan['revisions'][str(expected)]['published_at_utc'] is not None
    if mode == 'AUTOMATIC':
        if quarter != quarter_containing(now).shift() or now != publication_boundary(quarter):
            raise _ReadFailure('CLOSED_TARGET', 'time_utc', 'automatic publication requires the exact UTC boundary')
    elif committed:
        raise _ReadFailure('PUBLISHED_PLAN', 'weekly_plan_id', 'manual recommit is not permitted')
    elif quarter.quarter_id != _target(state, owner, envelope['simulation']['time_utc'], index):
        raise _ReadFailure('CLOSED_TARGET', 'quarter_id', 'use the eligible unpublished future quarter')
    baseline = _baseline(plans.values(),quarter)
    selected = plan if plan is not None else baseline
    if selected is None:
        raise _ReadFailure('MISSING_PLAN', 'weekly_plan', 'no target or published carry-forward baseline')
    read = resolve_quarterly_reads(envelope, airline_id=owner,
        selections=(PlanReadRequest(selected['weekly_plan_id'], selected['current_revision']),))
    if not read.succeeded:
        raise _ReadFailure(read.issues[0].code, read.issues[0].path, read.issues[0].message)
    rows = selected['revisions'][str(selected['current_revision'])]['slots']
    if plan is None:
        rows = [s for s in rows if state['services'][s['service_id']]['retired_at_utc'] is None]
    elif not committed and any(state['services'][s['service_id']]['retired_at_utc'] is not None for s in rows):
        raise _ReadFailure('RETIRED_SERVICE', 'slots', 'remove retired draft references explicitly before publication')
    return plan, read, rows, baseline, committed


def publication_sources(envelope, owner, intent, index=None):
    from .quarterly_readiness import _owner_plans, _observations
    plan, read, rows, baseline, skipped = resolve_publication(envelope, owner, intent, index)
    return _observations(envelope, owner, plan, _owner_plans(envelope['world_state'], owner, index),
                         baseline, {s['planned_aircraft_id'] for s in rows}, index)


def require_execution(envelope, owner, plan_id, aircraft_ids, gaps, index=None):
    """Use 3A's literal positioning and lease facts after the complete 2C proof."""
    from .quarterly_readiness import _contract_blockers, _owner_plans, _observations
    from game.world_state.timestamps import format_utc
    if gaps:
        aid, origin, destination, departure = sorted(set(gaps))[0]
        raise _ReadFailure('UNRESOLVED_POSITIONING', 'aircraft.' + aid,
            f'no explicit movement from {origin} to {destination} before {format_utc(departure)}')
    state = envelope['world_state']; plan = state['weekly_plans'][plan_id]
    sources = _observations(envelope, owner, plan, _owner_plans(state, owner, index), None, aircraft_ids, index)
    blockers = _contract_blockers(envelope, aircraft_ids, sources)
    if blockers:
        issue = blockers[0]
        raise _ReadFailure(issue.code, issue.path, issue.message)
