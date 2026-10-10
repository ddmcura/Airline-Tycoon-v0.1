"""Dormant quarterly domain handler; clock/queue selection belongs to Simulation."""
from copy import deepcopy

from game.utils.quarters import parse_quarter_id
from game.world_state.quarterly_boundary import (
    EVENT_TYPE, CONTRACT, boundary, obligations, enroll_candidate)
from game.world_state.validation import validate_world


def _schedule(envelope, owner, quarter_id):
    from game.simulation.kernel import schedule_event
    return schedule_event(envelope, event_type=EVENT_TYPE, due_at_utc=boundary(quarter_id),
        owner_type='airline', owner_id=owner, priority=0,
        payload={'contract': CONTRACT, 'quarter_id': quarter_id})


def reconcile_candidate(envelope):
    """Versioned bounded recovery: at most one missing current event per owner.

    Duplicates remain real budgeted lifecycle work. STALE cannot discharge a
    persisted obligation. No history enumeration or retroactive consumers.
    """
    pending = envelope['world_state']['pending_events']
    generated = []
    for owner, entry in sorted(obligations(envelope).items()):
        quarter = entry['next_quarter_id']
        revision = envelope['simulation']['operation_revisions'].get(owner, 0)
        if not any(e['event_type'] == EVENT_TYPE and e['owner_id'] == owner
                and e['payload']['quarter_id'] == quarter and e['operation_revision'] == revision
                for e in pending.values()):
            generated.append(_schedule(envelope, owner, quarter))
    return tuple(generated)


def reconcile(envelope):
    """Atomic reconstruction before processing; no mutation on normal worlds."""
    if not obligations(envelope):
        return ()
    candidate = deepcopy(envelope)
    generated = reconcile_candidate(candidate)
    if generated:
        report = validate_world(candidate)
        if not report.is_valid:
            raise ValueError('quarterly event reconciliation failed validation')
        from game.simulation.kernel import _replace_envelope
        _replace_envelope(envelope, candidate)
    return generated


def enable_quarterly_boundaries_for_testing(envelope, *, airline_id):
    """Explicit isolated-world opt-in, never called by New/Load/GUI or pacing."""
    initialize_quarterly_handler()
    report = validate_world(envelope)
    if not report.is_valid or envelope['simulation']['clock_state'] != 'PAUSED':
        raise ValueError('isolated enrollment requires a valid paused world')
    candidate = deepcopy(envelope)
    enroll_candidate(candidate, airline_id)
    reconcile_candidate(candidate)
    report = validate_world(candidate)
    if not report.is_valid:
        raise ValueError('isolated enrollment failed validation')
    from game.simulation.kernel import _replace_envelope
    _replace_envelope(envelope, candidate)


def initialize_quarterly_handler():
    """Explicit dormant-world dispatch; ordinary runtime initialization stays unchanged."""
    from game.simulation.kernel import DEFAULT_EVENT_HANDLERS
    from game.simulation.execution_contracts import ExecutionMode, HandlerExecutionContract
    registry = DEFAULT_EVENT_HANDLERS
    existing = registry.handler_for(EVENT_TYPE)
    if existing is not None and existing is not _publication_handler:
        raise ValueError('conflicting quarterly publication handler')
    if existing is None:
        registry.register(EVENT_TYPE, _publication_handler)
    registry._execution_contracts[EVENT_TYPE] = HandlerExecutionContract(
        _publication_handler, ExecutionMode.FENCE, 'quarterly-boundary-strict-v1')


def _publication_handler(context):
    from .quarterly_publication import PublishQuarterlyPlan
    from .quarterly_commands import prepare_quarterly_command, apply_quarterly_command
    from game.simulation.kernel import HandlerFailure, EventFailure
    envelope = context.envelope
    owner = context.event['owner_id']; quarter = context.payload['quarter_id']
    entry = obligations(envelope)[owner]
    if quarter != entry['next_quarter_id']:
        # Duplicate/obsolete lifecycle only. It never advances the obligation.
        return
    plans = [p for p in envelope['world_state']['weekly_plans'].values()
             if p['airline_id'] == owner and p['quarter_id'] == quarter]
    plan = plans[0] if plans else None
    request = PublishQuarterlyPlan('AUTOMATIC', quarter,
        None if plan is None else plan['weekly_plan_id'],
        0 if plan is None else plan['current_revision'], envelope['simulation']['time_utc'])
    prepared = prepare_quarterly_command(envelope, airline_id=owner, request=request)
    result = (apply_quarterly_command(envelope, airline_id=owner, prepared=prepared.prepared)
              if prepared.succeeded else prepared)
    if not result.succeeded:
        details = tuple({'code': i.code, 'path': i.path, 'message': i.message} for i in result.issues)
        raise HandlerFailure(EventFailure('QUARTERLY_PUBLICATION_FAILED',
            f'{owner} {quarter}: correct the unpublished candidate and retry',
            context.event['event_id'], details))
    committed = envelope['world_state']['weekly_plans'].get(result.weekly_plan_id)
    if (committed is None or committed['airline_id'] != owner or committed['quarter_id'] != quarter
            or committed['current_revision'] != result.revision
            or committed['revisions'][str(result.revision)]['published_at_utc'] is None):
        raise HandlerFailure(EventFailure('QUARTERLY_PUBLICATION_FAILED',
            f'{owner} {quarter}: publication did not establish a committed target',
            context.event['event_id'], ({'code':'INVALID_PUBLICATION_RESULT',
                'path':'weekly_plan.published_at_utc', 'message':'committed target required'},)))
    # Stage 3C detached publication replaced the envelope; reacquire its entry.
    entry = obligations(envelope)[owner]
    entry['next_quarter_id'] = parse_quarter_id(quarter).shift().quarter_id
    entry['failure'] = None
    reconcile_candidate(envelope)
