"""Schema 9 optional dormant publication obligation construction/validation."""
from copy import deepcopy

from game.utils.quarters import parse_quarter_id, quarter_containing
from .timestamps import format_utc, parse_canonical_utc

EVENT_TYPE = 'QUARTERLY_PUBLICATION'
CONTRACT = 'QUARTERLY_BOUNDARY_V1'


def boundary(quarter_id):
    quarter = parse_quarter_id(quarter_id)
    preceding = quarter.shift(-1)
    return format_utc(preceding.start_utc.replace(month=preceding.number * 3))


def obligations(envelope):
    return envelope['simulation'].get('quarterly_publication', {})


def validate_boundaries(envelope):
    entries = obligations(envelope)
    if type(entries) is not dict:
        raise ValueError('quarterly publication obligations must be an airline-ID map')
    if 'quarterly_publication' in envelope['simulation'] and envelope['metadata']['save_schema_version'] != 9:
        raise ValueError('quarterly boundary enrollment requires Schema 9')
    now = envelope['simulation']['time_utc']
    for owner, entry in entries.items():
        if owner not in envelope['world_state']['airlines']:
            raise ValueError('quarterly publication owner is absent')
        if type(entry) is not dict or set(entry) != {'next_quarter_id', 'failure'}:
            raise ValueError('noncanonical quarterly obligation fields')
        due = boundary(entry['next_quarter_id'])
        if due < now:
            raise ValueError('quarterly obligation precedes saved UTC; historical repair is forbidden')
        failure = entry['failure']
        if failure is not None:
            if (type(failure) is not dict or set(failure) != {'code', 'message', 'details'}
                    or any(type(failure[k]) is not str or not failure[k] for k in ('code', 'message'))
                    or type(failure['details']) is not list or any(type(d) is not dict for d in failure['details'])
                    or due != now):
                raise ValueError('noncanonical quarterly failure fence')
    records = (envelope['world_state']['pending_events'], envelope['world_state']['event_history'])
    for event in (e for collection in records for e in collection.values()):
        if event['event_type'] != EVENT_TYPE:
            continue
        payload = event['payload']
        if (event['owner_type'] != 'airline' or event['owner_id'] not in entries
                or event['order_key'][0] != 0 or type(payload) is not dict
                or set(payload) != {'contract', 'quarter_id'} or payload['contract'] != CONTRACT
                or boundary(payload['quarter_id']) != event['due_at_utc']):
            raise ValueError('noncanonical quarterly publication event')


def enroll_candidate(envelope, owner):
    """Explicit test-world opt-in; caller validates and publishes a detached candidate."""
    if envelope['metadata']['save_schema_version'] != 9:
        raise ValueError('Schema 9 required')
    if owner not in envelope['world_state']['airlines']:
        raise ValueError('airline is absent')
    if owner in obligations(envelope):
        raise ValueError('quarterly boundary owner already enrolled')
    now = envelope['simulation']['time_utc']
    quarter = quarter_containing(now).shift()
    if boundary(quarter.quarter_id) < now:
        quarter = quarter.shift()
    # No invented initial current-quarter plan: enrollment starts only with
    # a real upcoming draft or a real preceding committed carry-forward baseline.
    plans = [p for p in envelope['world_state']['weekly_plans'].values() if p['airline_id'] == owner]
    applicable = lambda q: any(p['quarter_id'] == q.quarter_id or (
            p['quarter_id'] < q.quarter_id and
            p['revisions'][str(p['current_revision'])]['published_at_utc'] is not None) for p in plans)
    if not applicable(quarter) and boundary(quarter.quarter_id) == now:
        quarter = quarter.shift()  # Brand-new month-three airline's first future target.
    if not applicable(quarter):
        raise ValueError('isolated enrollment needs an upcoming plan or published baseline')
    envelope['simulation'].setdefault('quarterly_publication', {})[owner] = {
        'next_quarter_id': quarter.quarter_id, 'failure': None}


def correction_target(envelope, owner, quarter_id):
    entry = obligations(envelope).get(owner)
    return bool(entry and entry['failure'] is not None
                and entry['next_quarter_id'] == quarter_id
                and boundary(quarter_id) == envelope['simulation']['time_utc'])


def record_failure_candidate(envelope, event, failure):
    entry = obligations(envelope)[event['owner_id']]
    if entry['next_quarter_id'] != event['payload']['quarter_id']:
        raise ValueError('failure does not belong to the outstanding obligation')
    envelope['simulation']['time_utc'] = event['due_at_utc']
    envelope['simulation']['clock_state'] = 'PAUSED'
    envelope['simulation']['fast_forward']['target_time_utc'] = None
    entry['failure'] = {'code': failure.code, 'message': failure.message,
                        'details': deepcopy(list(failure.validation_errors))}
