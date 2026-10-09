"""Diagnostic publication inspection. No commitment, allocation or supply writes.

Eligibility is calendar/lifecycle permission, not acceptance. Planning can rely
on hypothetical travel; execution cannot. Results describe one source snapshot
and are never publication certificates. All observations are runtime-only.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

from game.utils.quarters import parse_quarter_id, quarter_containing
from game.world_state.timestamps import parse_canonical_utc, format_utc
from game.aircraft_market.step5 import confirmed_contract_horizon
from .quarterly_commands import _entry, _target, _plain
from .quarterly_feasibility import certify_quarterly_feasibility, temporal_sources, _departures
from .timing import timing_bounds
from .quarterly_reads import (
    PlanReadRequest, PlanRead, ReadIssue, _ReadFailure, _freeze, _lookup, _owned,
    _positive, resolve_quarterly_reads,
)


@dataclass(frozen=True)
class PublicationReadinessRequest:
    weekly_plan_id: str | None = None
    expected_revision: int | None = None
    expected_time_utc: str | None = None
    expected_sources: Mapping | None = None


@dataclass(frozen=True)
class PublicationReadinessResult:
    inspected: bool = False
    airline_id: str | None = None
    time_utc: str | None = None
    quarter_id: str | None = None
    target_quarter_id: str | None = None
    weekly_plan_id: str | None = None
    revision: int | None = None
    operating_start_utc: str | None = None
    operating_end_exclusive_utc: str | None = None
    automatic_publication_utc: str | None = None
    next_publication_boundary_utc: str | None = None
    manual_eligible: bool = False
    automatic_due: bool = False
    publication_eligible: bool = False
    planning_feasible: bool | None = None
    execution_ready: bool | None = None
    plan: PlanRead | None = None
    baseline: PlanRead | None = None
    sources: Mapping | None = None
    eligibility_issues: tuple[ReadIssue, ...] = ()
    planning_issues: tuple[ReadIssue, ...] = ()
    execution_blockers: tuple[ReadIssue, ...] = ()
    issues: tuple[ReadIssue, ...] = ()

    @property
    def succeeded(self):
        return self.inspected


def publication_boundary(quarter):
    """The first UTC second of the calendar month preceding operating start."""
    start = quarter.start_utc
    return datetime(start.year - (start.month == 1),
                    12 if start.month == 1 else start.month - 1, 1, tzinfo=timezone.utc)


def _reject(code, path, message):
    return PublicationReadinessResult(issues=(ReadIssue(code, path, message),))


def _owner_plans(state, owner, index):
    ids = index.ids('owner_plans', owner) if index is not None else sorted(state['weekly_plans'])
    return {pid: state['weekly_plans'][pid] for pid in ids
            if state['weekly_plans'][pid]['airline_id'] == owner}


def _view(envelope, owner, plan):
    if plan is None:
        return None
    result = resolve_quarterly_reads(envelope, airline_id=owner,
        selections=(PlanReadRequest(plan['weekly_plan_id'], plan['current_revision']),))
    if not result.succeeded:
        issue = result.issues[0]
        raise _ReadFailure(issue.code, issue.path, issue.message, issue.observed_revision)
    return result.plans[0]


def _observations(envelope, owner, selected, plans, baseline, aircraft_ids, index):
    state = envelope['world_state']
    # Current owned versions determine targeting/baselines. Retained history is
    # not copied wholesale; the selected versions/dependency reads remain exact.
    facts = {'time_utc': envelope['simulation']['time_utc'], 'airline': state['airlines'][owner],
             'plans': {pid: {'quarter_id': p['quarter_id'], 'current_revision': p['current_revision'],
                            'revision': p['revisions'][str(p['current_revision'])]}
                       for pid, p in plans.items()},
             'selected': None if selected is None else selected['weekly_plan_id'],
             'baseline': None if baseline is None else baseline['weekly_plan_id'],
             'temporal': temporal_sources(envelope, aircraft_ids, index=index)}
    dependencies = set()
    for plan in (selected, baseline):
        if plan is not None:
            read = resolve_quarterly_reads(envelope, airline_id=owner,
                selections=(PlanReadRequest(plan['weekly_plan_id'], plan['current_revision']),))
            if not read.succeeded:
                issue = read.issues[0]
                raise _ReadFailure(issue.code, issue.path, issue.message)
            dependencies.update(read.dependencies)
    facts['records'] = {table + '/' + identity: state[table].get(identity)
                        for table, identity in dependencies if table != 'weekly_plans'}
    contracts = {}
    for aid in sorted(aircraft_ids):
        cid = state['aircraft'][aid].get('lifecycle', {}).get('aircraft_contract_id')
        while cid is not None:
            row = state['aircraft_contracts'][cid]
            contracts[cid] = row
            cid = row['successor_contract_id']
    facts['contracts'] = contracts
    return _freeze(facts)


def _contract_blockers(envelope, aircraft_ids, sources):
    """Reuse the existing lessor-owned arrival horizon, not a delivery forecast."""
    state = envelope['world_state']
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    issues = []
    for aid in sorted(aircraft_ids):
        if state['aircraft'][aid].get('lifecycle', {}).get('ownership_status') != 'LESSOR_OWNED':
            continue
        horizon = confirmed_contract_horizon(state, aid)
        if horizon is None:
            issues.append(ReadIssue('AIRCRAFT_UNAVAILABLE', 'aircraft.' + aid, 'no confirmed aircraft contract horizon'))
            continue
        end = parse_canonical_utc(horizon)
        for pid, facts in sorted(sources['temporal']['plans'].items()):
            for slot in facts['revision']['slots']:
                if slot['planned_aircraft_id'] != aid:
                    continue
                block = timing_bounds(slot['planning_timing'])[1][1]
                if any(departure + timedelta(seconds=block) > end
                       for _, departure in _departures(state, now, state['weekly_plans'][pid], slot)):
                    issues.append(ReadIssue('CONTRACT_HORIZON_EXCEEDED', 'weekly_plan.' + pid,
                        f'aircraft {aid} has proposed arrivals after confirmed horizon {horizon}'))
                    break
    return issues


def inspect_quarterly_publication_readiness(envelope, *, airline_id, request=None, _indexes=None):
    """Inspect a current selected plan or discover the eligible future target.

    Explicit selections require an expected current revision. Optional expected
    UTC/source facts reject stale reads. Missing automatic targets are reported,
    not constructed. Automatic due means exactly its boundary, not late recovery.
    """
    try:
        _entry(envelope)
        request = PublicationReadinessRequest() if request is None else request
        if type(request) is not PublicationReadinessRequest:
            return _reject('INVALID_REQUEST', 'request', 'canonical readiness request required')
        expected_sources = None
        if request.expected_sources is not None:
            if not isinstance(request.expected_sources, Mapping):
                return _reject('INVALID_REQUEST', 'expected_sources', 'source observations must be a mapping')
            expected_sources = _freeze(_plain(request.expected_sources))
        now_text = envelope['simulation']['time_utc']
        now = parse_canonical_utc(now_text)
        if request.expected_time_utc is not None:
            parse_canonical_utc(request.expected_time_utc)
            if request.expected_time_utc != now_text:
                return _reject('STALE_CONTEXT', 'time_utc', 'simulation UTC changed; inspect again')
        state = envelope['world_state']
        _lookup(state, 'airlines', airline_id, 'airline')
        index = _indexes.get(envelope) if _indexes is not None else None
        plans = _owner_plans(state, airline_id, index)
        target = _target(state, airline_id, now_text, index)
        if request.weekly_plan_id is not None:
            plan = _lookup(state, 'weekly_plans', request.weekly_plan_id, 'weekly_plan')
            _owned(plan, airline_id, 'weekly_plan_id')
            if not _positive(request.expected_revision):
                return _reject('INVALID_REQUEST', 'expected_revision', 'selected plan requires positive expected revision')
        else:
            plan = next((p for p in plans.values() if p['quarter_id'] == target), None)
            if request.expected_revision is not None and not (
                    type(request.expected_revision) is int and request.expected_revision >= 0):
                return _reject('INVALID_REQUEST', 'expected_revision', 'nonnegative revision/absence observation required')
        actual_revision = 0 if plan is None else plan['current_revision']
        if request.expected_revision is not None and request.expected_revision != actual_revision:
            return _reject('STALE_REVISION', 'expected_revision', 'plan revision/absence changed; inspect again')
        quarter = parse_quarter_id(target if plan is None else plan['quarter_id'])
        preceding = [p for p in plans.values() if parse_quarter_id(p['quarter_id']) < quarter
                     and p['revisions'][str(p['current_revision'])]['published_at_utc'] is not None]
        baseline = max(preceding, key=lambda p: parse_quarter_id(p['quarter_id'])) if preceding else None
        aircraft_ids = set() if plan is None else {
            slot['planned_aircraft_id'] for slot in plan['revisions'][str(actual_revision)]['slots']}
        sources = _observations(envelope, airline_id, plan, plans, baseline, aircraft_ids, index)
        if expected_sources is not None and expected_sources != sources:
            return _reject('STALE_CONTEXT', 'sources', 'relevant source observations changed; inspect again')
        committed = {p['quarter_id'] for p in plans.values()
                     if p['revisions'][str(p['current_revision'])]['published_at_utc'] is not None}
        planned = {p['quarter_id'] for p in plans.values()}
        next_quarter = quarter_containing(now).shift()
        while (publication_boundary(next_quarter) < now or next_quarter.quarter_id in committed
               or (next_quarter.quarter_id not in planned and next_quarter.quarter_id != target
                   and not any(parse_quarter_id(qid) < next_quarter for qid in committed))):
            next_quarter = next_quarter.shift()
        boundary = publication_boundary(quarter)
        published = plan is not None and plan['revisions'][str(actual_revision)]['published_at_utc'] is not None
        manual = plan is not None and not published and quarter.quarter_id == target
        automatic = plan is not None and not published and now == boundary
        eligibility = []
        if plan is None:
            eligibility.append(ReadIssue('MISSING_PLAN', 'weekly_plan', 'no selected target plan; nothing is manufactured'))
        elif published:
            eligibility.append(ReadIssue('PUBLISHED_PLAN', 'weekly_plan', 'selected plan is already committed'))
        elif not (manual or automatic):
            eligibility.append(ReadIssue('CLOSED_TARGET', 'quarter_id', 'not the current eligible future quarter or exact automatic boundary'))
        planning, execution = None, None
        planning_issues, blockers, gaps = [], [], []
        if plan is not None and quarter.end_exclusive_utc > now:
            try:
                certify_quarterly_feasibility(envelope, aircraft_ids,
                    through_utc=quarter.end_exclusive_utc, index=index, _execution_blockers=gaps)
                planning = True
                for aid, origin, destination, departure in sorted(set(gaps)):
                    blockers.append(ReadIssue('UNRESOLVED_POSITIONING', 'aircraft.' + aid,
                        f'no explicit movement from {origin} to {destination} before {format_utc(departure)}'))
                blockers.extend(_contract_blockers(envelope, aircraft_ids, sources))
                execution = not blockers
            except (ValueError, KeyError, TypeError, OverflowError) as exc:
                planning, execution = False, False
                planning_issues.append(ReadIssue('INFEASIBLE_PLAN', 'aircraft_chronology', str(exc)))
                blockers.append(ReadIssue('PLANNING_INFEASIBLE', 'aircraft_chronology', 'execution requires feasible complete chronology'))
        selected_view, baseline_view = _view(envelope, airline_id, plan), _view(envelope, airline_id, baseline)
        _entry(envelope)
        if sources != _observations(envelope, airline_id, plan, _owner_plans(state, airline_id, index),
                                     baseline, aircraft_ids, index):
            return _reject('STALE_CONTEXT', 'sources', 'sources changed during inspection')
        return PublicationReadinessResult(True, airline_id, now_text, quarter.quarter_id, target,
            None if plan is None else plan['weekly_plan_id'], None if plan is None else actual_revision,
            format_utc(quarter.start_utc), format_utc(quarter.end_exclusive_utc), format_utc(boundary),
            format_utc(publication_boundary(next_quarter)), manual, automatic, manual or automatic,
            planning, execution, selected_view, baseline_view, sources, tuple(eligibility),
            tuple(planning_issues), tuple(blockers))
    except _ReadFailure as exc:
        return PublicationReadinessResult(issues=(exc.issue,))
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError, RecursionError) as exc:
        return _reject('INVALID_REQUEST', 'publication_readiness', str(exc))
