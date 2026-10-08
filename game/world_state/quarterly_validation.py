"""Strict quarterly authority validation, never operational expansion."""
import re
from game.utils.quarters import parse_quarter_id
from .timestamps import parse_canonical_utc
from .ids import parse_entity_id
from .planning_validation import validate_timing

SLOT_FIELDS = frozenset({'service_id', 'slot_number', 'weekdays',
    'departure_local_time', 'departure_local_fold', 'origin_airport_id',
    'destination_airport_id', 'planned_aircraft_id', 'connection_id',
    'service_type', 'capacity', 'fare_offer', 'planning_timing'})


def exact(record, fields):
    if type(record) is not dict or set(record) != set(fields):
        raise ValueError('noncanonical quarterly record fields')


def positive(value):
    if type(value) is not int or value < 1:
        raise ValueError('quarterly cursor/identity number must be positive integer')


def validate_slots(world, airline_id, slots, *, new=False):
    if type(slots) is not list:
        raise ValueError('weekly slots must be a list')
    previous = None
    catalogs = {}
    for slot in slots:
        exact(slot, SLOT_FIELDS)
        sid = slot['service_id']; number = slot['slot_number']
        service = world['services'].get(sid)
        if not service or service['airline_id'] != airline_id:
            raise ValueError('slot service belongs to another airline or is absent')
        positive(number)
        if number >= service['next_slot_number']:
            raise ValueError('slot identity has not been allocated')
        if new and service['retired_at_utc'] is not None:
            raise ValueError('retired service cannot enter a new plan revision')
        identity = (sid, number)
        if previous is not None and identity <= previous:
            raise ValueError('slots must be unique and sorted by service/slot identity')
        previous = identity
        days = slot['weekdays']
        if (type(days) is not list or not days or any(type(d) is not int or not 0 <= d <= 6 for d in days)
                or days != sorted(set(days))):
            raise ValueError('weekdays must be sorted unique 0..6')
        if type(slot['departure_local_time']) is not str or re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]', slot['departure_local_time']) is None:
            raise ValueError('departure time must be HH:MM:SS')
        if type(slot['departure_local_fold']) is not int or slot['departure_local_fold'] not in (0, 1):
            raise ValueError('departure fold must be 0 or 1')
        origin = slot['origin_airport_id']; dest = slot['destination_airport_id']
        if origin not in world['airports'] or dest not in world['airports'] or origin == dest:
            raise ValueError('invalid slot endpoints')
        aircraft = world['aircraft'].get(slot['planned_aircraft_id'])
        if not aircraft or aircraft['airline_id'] != airline_id:
            raise ValueError('invalid slot aircraft ownership')
        if type(slot['capacity']) is not int or slot['capacity'] < 0:
            raise ValueError('slot capacity must be nonnegative integer')
        exact(slot['fare_offer'], {'currency', 'amount_minor'})
        fare = slot['fare_offer']
        if fare['currency'] != world['airlines'][airline_id]['base_currency'] or type(fare['amount_minor']) is not int or fare['amount_minor'] < 0:
            raise ValueError('invalid slot fare/currency')
        if slot['service_type'] == 'PASSENGER':
            connection = world['connections'].get(slot['connection_id'])
            market = world['directional_markets'].get(connection['market_id']) if connection else None
            if (not connection or connection['airline_id'] != airline_id or not market
                    or market['origin_airport_id'] != origin or market['destination_airport_id'] != dest
                    or slot['capacity'] < 1):
                raise ValueError('invalid passenger slot connection/capacity')
        elif slot['service_type'] == 'DEADHEAD':
            if slot['connection_id'] is not None or slot['capacity'] != 0 or fare['amount_minor'] != 0:
                raise ValueError('deadhead slot has commercial facts')
        else:
            raise ValueError('unsupported slot service type')
        timing = slot['planning_timing']
        validate_timing(timing, catalogs)
        if timing['model_reference'] != aircraft['model_reference']:
            raise ValueError('timing model mismatch')
        from game.utils.geo_distance import distance_km
        num, den = distance_km(world['airports'][origin], world['airports'][dest]).as_integer_ratio()
        if timing['distance_m'] != (num * 1000 + den - 1) // den:
            raise ValueError('timing distance mismatch')
        config = aircraft.get('configuration')
        if config:
            if (timing.get('contract') != 'PH_SCHEDULING_TIMING_V2'
                    or timing.get('catalog_version') != config['catalog_version']
                    or timing.get('performance_contract') != config['performance_contract']
                    or slot['capacity'] != (0 if slot['service_type'] == 'DEADHEAD' else config['economy_capacity'])):
                raise ValueError('configured aircraft timing/capacity mismatch')
        elif timing['contract'] == 'PH_SCHEDULING_TIMING_V2':
            raise ValueError('configured timing requires configured aircraft')


def validate_service_endpoints(world, slots):
    """Reject endpoint reinterpretation before a low-level candidate write.

    Only incoming services need comparison; retained revisions remain authority.
    Maintained inverse relationships are intentionally deferred to Stage 2D.
    """
    endpoints = {}
    for slot in slots:
        pair = (slot['origin_airport_id'], slot['destination_airport_id'])
        if endpoints.setdefault(slot['service_id'], pair) != pair:
            raise ValueError('service endpoint identity cannot change')
    if not endpoints:
        return
    for plan in world['weekly_plans'].values():
        for row in plan['revisions'].values():
            for slot in row['slots']:
                sid = slot['service_id']
                if sid in endpoints and endpoints[sid] != (slot['origin_airport_id'], slot['destination_airport_id']):
                    raise ValueError('service endpoint identity cannot change')


def validate_quarterly(envelope):
    world = envelope['world_state']; now = parse_canonical_utc(envelope['simulation']['time_utc'])
    numbering = world['service_numbering']
    if type(numbering) is not dict:
        raise ValueError('service numbering must be a mapping')
    for owner, record in numbering.items():
        if owner not in world['airlines']:
            raise ValueError('numbering airline is absent')
        exact(record, {'flight_number_prefix', 'next_number'})
        if type(record['flight_number_prefix']) is not str or re.fullmatch(r'[A-Z]{2,8}', record['flight_number_prefix']) is None:
            raise ValueError('invalid flight number prefix')
        positive(record['next_number'])
    used = set()
    for sid, service in world['services'].items():
        exact(service, {'service_id', 'airline_id', 'flight_number_number', 'next_slot_number', 'retired_at_utc'})
        if sid != service['service_id'] or parse_entity_id(sid, 'service') is None:
            raise ValueError('invalid service identity')
        owner = service['airline_id']
        if owner not in numbering:
            raise ValueError('service number allocation is absent')
        number = service['flight_number_number']; positive(number); positive(service['next_slot_number'])
        if number >= numbering[owner]['next_number'] or (
                envelope['metadata']['save_schema_version'] == 8 and (owner, number) in used):
            raise ValueError('duplicate/unallocated flight number')
        used.add((owner, number))
        if service['retired_at_utc'] is not None and parse_canonical_utc(service['retired_at_utc']) > now:
            raise ValueError('retirement cannot be in the future')
    periods = set()
    endpoints = {}
    for pid, plan in world['weekly_plans'].items():
        exact(plan, {'weekly_plan_id', 'airline_id', 'quarter_id', 'current_revision', 'revisions'})
        if pid != plan['weekly_plan_id'] or parse_entity_id(pid, 'weekly_plan') is None:
            raise ValueError('invalid weekly plan identity')
        quarter = parse_quarter_id(plan['quarter_id']); owner = plan['airline_id']
        if owner not in world['airlines'] or (owner, plan['quarter_id']) in periods:
            raise ValueError('absent owner or duplicate airline quarter plan')
        periods.add((owner, plan['quarter_id']))
        revision = plan['current_revision']; positive(revision)
        rows = plan['revisions']
        if type(rows) is not dict or len(rows) != revision:
            raise ValueError('invalid plan revision coverage')
        for number in range(1, revision + 1):
            row = rows.get(str(number)); exact(row, {'revision', 'published_at_utc', 'slots'})
            if type(row['revision']) is not int or row['revision'] != number:
                raise ValueError('noncanonical plan revision')
            stamp = row['published_at_utc']
            if stamp is not None:
                instant = parse_canonical_utc(stamp)
                if number != revision or instant > now or instant > quarter.start_utc:
                    raise ValueError('inconsistent plan publication commitment')
            validate_slots(world, owner, row['slots'])
            if envelope['metadata']['save_schema_version'] == 9:
                for slot in row['slots']:
                    pair = (slot['origin_airport_id'], slot['destination_airport_id'])
                    if endpoints.setdefault(slot['service_id'], pair) != pair:
                        raise ValueError('service endpoint identity cannot change')
    if envelope['metadata']['save_schema_version'] == 9:
        from .service_numbers import protected_number_holders
        protected_number_holders(envelope)
