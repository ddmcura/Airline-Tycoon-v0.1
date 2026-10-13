"""Explicit Schema 9 quarterly consumer lineage; legacy fields stay legacy."""
from copy import deepcopy
from datetime import date

from .timestamps import parse_canonical_utc, format_utc
from game.utils.quarters import parse_quarter_id

MODE = 'QUARTERLY_BACKEND_V1'
LINEAGE_FIELDS = frozenset(('weekly_plan_id', 'revision', 'service_id',
                          'slot_number', 'operating_date', 'published_at_utc'))
FLIGHT_FIELDS = frozenset(('dated_flight_id', 'occurrence_key', 'schedule_id',
    'schedule_revision', 'airline_id', 'connection_id', 'planned_aircraft_id',
    'origin_airport_id', 'destination_airport_id', 'service_type',
    'scheduled_departure_local_date', 'scheduled_off_block_utc',
    'scheduled_in_block_utc', 'capacity', 'fare_offer',
    'passenger_service_classification', 'status', 'published_at_utc',
    'superseded_by_schedule_revision', 'inventory_revision', 'operation_revision',
    'quarterly_lineage'))


def quarterly_mode(envelope):
    return envelope.get('simulation', {}).get('operational_authority') == MODE


def valid_quarterly_lineage(lineage):
    """Check canonical scalar types before any value-equality lineage join.

    Membership/ranges relative to the published plan remain the caller's proof;
    Python equality alone cannot distinguish bool/float from integer identity.
    """
    return (type(lineage) is dict and lineage.keys() == LINEAGE_FIELDS
        and type(lineage['revision']) is int and lineage['revision'] >= 1
        and type(lineage['slot_number']) is int and lineage['slot_number'] >= 1
        and all(type(lineage[key]) is str and lineage[key] for key in
            ('weekly_plan_id', 'service_id', 'operating_date', 'published_at_utc')))


def committed_slot(world, lineage):
    if not valid_quarterly_lineage(lineage):
        raise ValueError('exact quarterly publication lineage types required; revision and slot_number must be positive integers')
    plan = world['weekly_plans'][lineage['weekly_plan_id']]
    revision = plan['revisions'][str(lineage['revision'])]
    if (lineage['revision'] != plan['current_revision']
            or revision['published_at_utc'] is None
            or revision['published_at_utc'] != lineage['published_at_utc']):
        raise ValueError('current published quarterly commitment required')
    slots = [s for s in revision['slots'] if
             (s['service_id'], s['slot_number']) ==
             (lineage['service_id'], lineage['slot_number'])]
    if len(slots) != 1:
        raise ValueError('selected published frequency required')
    return plan, slots[0]


def projected_flight(world, lineage):
    """Pure Stage 3B service/date/slot projection, without a new identity."""
    from game.scheduling.quarterly_occurrences import QuarterlyOccurrenceReference, _project_times
    plan, slot = committed_slot(world, lineage)
    operating_date = lineage['operating_date']
    reference = QuarterlyOccurrenceReference(lineage['weekly_plan_id'], lineage['revision'],
        slot['service_id'], slot['slot_number'], operating_date)
    key = reference.occurrence_key
    if date.fromisoformat(operating_date).weekday() not in slot['weekdays']:
        raise ValueError('date outside published frequency')
    departure, arrival, _, _ = _project_times(world, slot, operating_date)
    quarter = parse_quarter_id(plan['quarter_id'])
    if not quarter.start_utc <= departure < quarter.end_exclusive_utc:
        raise ValueError('date outside published UTC quarter')
    return {
        'dated_flight_id': key, 'occurrence_key': key,
        'schedule_id': None, 'schedule_revision': None,
        'airline_id': plan['airline_id'],
        **{k: deepcopy(slot[k]) for k in ('connection_id', 'planned_aircraft_id',
            'origin_airport_id', 'destination_airport_id', 'service_type',
            'capacity', 'fare_offer')},
        'scheduled_departure_local_date': operating_date,
        'scheduled_off_block_utc': format_utc(departure),
        'scheduled_in_block_utc': format_utc(arrival),
        'passenger_service_classification': ('ECONOMY' if slot['service_type'] == 'PASSENGER'
                                             else 'NON_PASSENGER'),
        'status': 'PLANNED', 'published_at_utc': lineage['published_at_utc'],
        'superseded_by_schedule_revision': None,
        'inventory_revision': 0, 'operation_revision': 1,
        'quarterly_lineage': deepcopy(lineage),
    }


def validate_quarterly_flight(envelope, flight, seen):
    if not quarterly_mode(envelope) or flight.keys() != FLIGHT_FIELDS:
        raise ValueError('quarterly dated row requires explicit authority and exact fields')
    expected = projected_flight(envelope['world_state'], flight['quarterly_lineage'])
    variable = {'dated_flight_id', 'status', 'inventory_revision', 'operation_revision'}
    if any(flight[k] != v for k, v in expected.items() if k not in variable):
        raise ValueError('dated row differs from its published quarterly commitment')
    if flight['occurrence_key'] in seen:
        raise ValueError('duplicate quarterly occurrence alias')
    seen[flight['occurrence_key']] = flight['dated_flight_id']
    if (flight['status'] not in {'PLANNED', 'OPERATIONALLY_LOCKED', 'COMPLETED'}
            or type(flight['inventory_revision']) is not int or flight['inventory_revision'] < 0
            or type(flight['operation_revision']) is not int or flight['operation_revision'] < 1):
        raise ValueError('invalid quarterly flight lifecycle/revisions')


def validate_mode(envelope):
    marker = envelope['simulation'].get('operational_authority')
    if 'operational_authority' not in envelope['simulation']:
        # Called only when the marker or a dispatcher was observed during the
        # existing complete traversal. Individual quarterly rows already require
        # their marker. Legacy worlds incur no additional collection scan.
        raise ValueError('quarterly dispatch requires explicit career authority')
    if marker != MODE or envelope['metadata']['save_schema_version'] != 9:
        raise ValueError('unsupported operational authority')
    world = envelope['world_state']
    from .schema import DEFAULT_BOOKING_CONFIGURATION
    configuration = envelope['simulation']['configuration']['booking']
    if any(configuration[name] != DEFAULT_BOOKING_CONFIGURATION[name] for name in
           ('booking_horizon_days', 'lead_time_buckets', 'desired_date_tolerance_days', 'choice_policy')):
        raise ValueError('quarterly PH 1.0 requires the approved absolute booking policy')
    if world['schedule_definitions'] or any('quarterly_lineage' not in f
                                          for f in world['dated_flights'].values()):
        raise ValueError('quarterly career cannot contain legacy operational supply')
    for row in world['itineraries'].values():
        if row.get('schedule_lineage') is not None or 'quarterly_lineage' not in row:
            raise ValueError('quarterly career cannot contain legacy itinerary lineage')
        flight = world['dated_flights'][row['dated_flight_ids'][0]]
        if row['fare_offer_snapshot'] != flight['fare_offer']:
            raise ValueError('quarterly accepted fare must match the fixed publication')
    from .schema import AGGREGATE_BOOKING_CONTRACT
    for booking in world['bookings'].values():
        if booking['contract'] != AGGREGATE_BOOKING_CONTRACT:
            raise ValueError('quarterly career cannot contain legacy compatibility bookings')
        booked = parse_canonical_utc(booking['booked_at_utc']).date()
        desired = date.fromisoformat(booking['desired_travel_date'])
        itinerary = world['itineraries'][booking['itinerary_id']]
        departure = parse_canonical_utc(itinerary['scheduled_departure_utc']).date()
        if (not 0 <= (desired - booked).days <= 365
                or not 0 <= (departure - booked).days <= 365
                or abs((departure - desired).days) > 3):
            raise ValueError('quarterly booking violates absolute horizon/date flexibility')
    for table in ('active_aircraft_operations', 'flight_results'):
        for row in world[table].values():
            flight = world['dated_flights'][row['dated_flight_id']]
            if (not valid_quarterly_lineage(row.get('quarterly_lineage'))
                    or row['quarterly_lineage'] != flight['quarterly_lineage']):
                raise ValueError('operational publication lineage mismatch')
    if any(e['event_type'] == 'STAGE1_WEEKLY_PUBLICATION'
           for e in world['pending_events'].values()):
        raise ValueError('legacy recurrence writer forbidden in quarterly career')
    for event in (*world['pending_events'].values(), *world['event_history'].values()):
        if event['event_type'] != 'QUARTERLY_DISPATCH':
            continue
        payload = event['payload']
        if (payload.keys() != {'contract', 'quarterly_lineage'}
                or payload['contract'] != 'QUARTERLY_DISPATCH_V1'
                or event['owner_type'] != 'aircraft' or event['order_key'][0] != 90):
            raise ValueError('noncanonical quarterly dispatch')
        row = projected_flight(world, payload['quarterly_lineage'])
        if row['planned_aircraft_id'] != event['owner_id'] or row['scheduled_off_block_utc'] != event['due_at_utc']:
            raise ValueError('dispatch publication/assignment/time mismatch')
    # Sparse inventory must not weaken complete published aircraft chronology.
    # Draft diagnostics remain planning-only; only commitments own operations.
    from game.scheduling.quarterly_feasibility import certify_quarterly_feasibility
    published = {pid: p for pid, p in world['weekly_plans'].items()
                 if p['revisions'][str(p['current_revision'])]['published_at_utc'] is not None}
    # Publication itself defines the finite mandatory calendar. A missing event
    # may be reconstructed at/before its boundary, never erase a past flight.
    # Stream historical references; do not construct an unsold quarter table.
    from game.scheduling.quarterly_feasibility import _departures
    now = parse_canonical_utc(envelope['simulation']['time_utc'])
    aliases = {f['occurrence_key']: f for f in world['dated_flights'].values()}
    for plan in published.values():
        revision = plan['revisions'][str(plan['current_revision'])]
        start = parse_canonical_utc(revision['published_at_utc'])
        for slot in revision['slots']:
            for key, departure in _departures(world, start, plan, slot):
                if departure >= now:
                    break
                row = aliases.get(key)
                if row is None or row['status'] not in {'OPERATIONALLY_LOCKED', 'COMPLETED'}:
                    raise ValueError('published operational occurrence was skipped')
    view = {**envelope, 'world_state': {**world, 'weekly_plans': published}}
    aircraft_ids = {s['planned_aircraft_id'] for p in published.values()
                    for s in p['revisions'][str(p['current_revision'])]['slots']}
    gaps = []
    certify_quarterly_feasibility(view, aircraft_ids, _execution_blockers=gaps)
    if gaps:
        raise ValueError('published aircraft chain requires unexecuted positioning')
