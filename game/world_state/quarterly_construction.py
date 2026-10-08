"""Schema-9 low-level constructors for caller-owned isolated candidates.

No GUI workflow, publication, recurrence expansion or legacy save conversion.
"""
from copy import deepcopy
import re
from game.utils.quarters import parse_quarter_id
from .ids import allocate_id
from .quarterly_validation import validate_slots, validate_service_endpoints
from .service_numbers import eligible_retired_numbers


def _initialize_quarterly_foundation(candidate):
    """New-game bootstrap only; never called by Load or old-save migration."""
    if candidate['metadata']['save_schema_version'] != 7:
        raise ValueError('fresh bootstrap must finish schema-7 construction first')
    if any(name in candidate['world_state'] for name in ('services', 'service_numbering', 'weekly_plans')):
        raise ValueError('quarterly foundation already exists')
    if candidate['simulation']['time_utc'] != candidate['metadata']['world_created_at_utc'] or any(
            candidate['world_state'].get(name) for name in ('schedule_definitions', 'dated_flights',
            'bookings', 'itineraries', 'active_aircraft_operations', 'flight_results', 'event_history', 'transactions')):
        raise ValueError('quarterly initialization is restricted to a fresh new-game bootstrap')
    candidate['metadata']['save_schema_version'] = 9
    candidate['world_state'].update(services={}, service_numbering={}, weekly_plans={})
    candidate['deterministic_state']['id_allocator']['next_by_type'].update(service=1, weekly_plan=1)


def _world(candidate):
    if candidate['metadata']['save_schema_version'] != 9:
        raise ValueError('quarterly construction requires schema 9')
    return candidate['world_state']


def create_service(candidate, airline_id, *, flight_number_prefix):
    world = _world(candidate)
    if airline_id not in world['airlines']:
        raise ValueError('unknown service airline')
    if type(flight_number_prefix) is not str or re.fullmatch(r'[A-Z]{2,8}', flight_number_prefix) is None:
        raise ValueError('prefix must be 2..8 uppercase ASCII letters')
    numbering = world['service_numbering'].get(airline_id)
    if numbering is not None and numbering['flight_number_prefix'] != flight_number_prefix:
        raise ValueError('existing airline prefix cannot change')
    cursor = numbering['next_number'] if numbering else 1
    if type(cursor) is not int or cursor < 1:
        raise ValueError('invalid flight number cursor')
    if numbering is None and any(s['airline_id'] == airline_id for s in world['services'].values()):
        raise ValueError('service numbering authority is absent')
    eligible = eligible_retired_numbers(candidate, airline_id) if numbering else ()
    number = eligible[0] if eligible else cursor
    sid = allocate_id(candidate, 'service')
    if numbering is None:
        numbering = {'flight_number_prefix': flight_number_prefix, 'next_number': 1}
        world['service_numbering'][airline_id] = numbering
    world['services'][sid] = {'service_id': sid, 'airline_id': airline_id,
        'flight_number_number': number, 'next_slot_number': 1, 'retired_at_utc': None}
    if not eligible:
        numbering['next_number'] = cursor + 1
    return sid


def allocate_service_slot(candidate, service_id):
    service = _world(candidate)['services'][service_id]
    if service['retired_at_utc'] is not None:
        raise ValueError('retired service cannot allocate slots')
    number = service['next_slot_number']
    if type(number) is not int or number < 1:
        raise ValueError('invalid slot cursor')
    service['next_slot_number'] = number + 1
    return number


def retire_service(candidate, service_id):
    service = _world(candidate)['services'][service_id]
    if service['retired_at_utc'] is None:
        service['retired_at_utc'] = candidate['simulation']['time_utc']


def create_weekly_plan(candidate, airline_id, quarter_id, *, slots=()):
    world = _world(candidate); parse_quarter_id(quarter_id)
    if airline_id not in world['airlines']:
        raise ValueError('unknown plan airline')
    if any(p['airline_id'] == airline_id and p['quarter_id'] == quarter_id for p in world['weekly_plans'].values()):
        raise ValueError('airline quarter already has a weekly plan')
    rows = deepcopy(list(slots)); validate_slots(world, airline_id, rows, new=True)
    validate_service_endpoints(world, rows)
    pid = allocate_id(candidate, 'weekly_plan')
    world['weekly_plans'][pid] = {'weekly_plan_id': pid, 'airline_id': airline_id,
        'quarter_id': quarter_id, 'current_revision': 1,
        'revisions': {'1': {'revision': 1, 'published_at_utc': None, 'slots': rows}}}
    return pid


def append_weekly_plan_revision(candidate, weekly_plan_id, *, expected_revision, slots):
    world = _world(candidate); plan = world['weekly_plans'][weekly_plan_id]
    if type(expected_revision) is not int or expected_revision != plan['current_revision']:
        raise ValueError('stale weekly plan revision')
    if plan['revisions'][str(expected_revision)]['published_at_utc'] is not None:
        raise ValueError('published plan cannot append ordinary revisions')
    rows = deepcopy(list(slots)); validate_slots(world, plan['airline_id'], rows, new=True)
    validate_service_endpoints(world, rows)
    number = expected_revision + 1
    plan['revisions'][str(number)] = {'revision': number, 'published_at_utc': None, 'slots': rows}
    plan['current_revision'] = number
    return number
