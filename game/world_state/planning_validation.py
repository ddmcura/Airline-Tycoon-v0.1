"""Persistent weekly planning snapshot and reservation validation."""

from datetime import date
from game.scheduling.timing import timing_bounds, flight_reservation
from .timestamps import parse_canonical_utc

ACTIVITIES = {'baggage_loading', 'catering', 'refueling', 'cleaning',
              'boarding', 'disembarking', 'baggage_unloading'}


def validate_timing(snapshot):
    fields = {'contract', 'profile_version', 'model_reference', 'distance_m',
              'cruise_speed_kph', 'max_speed_kph', 'activities',
              'taxi_to_stand_seconds', 'taxi_out_seconds', 'taxi_in_seconds'}
    if type(snapshot) is not dict or set(snapshot) != fields:
        raise ValueError('invalid planning timing fields')
    if snapshot['contract'] != 'PH_SCHEDULING_TIMING_V1':
        raise ValueError('unsupported planning timing contract')
    for field in ('profile_version', 'model_reference'):
        if type(snapshot[field]) is not str or not snapshot[field].strip():
            raise ValueError('invalid timing identity')
    for field in ('distance_m', 'cruise_speed_kph', 'max_speed_kph'):
        if type(snapshot[field]) is not int or not 0 <= snapshot[field] <= 100_000_000:
            raise ValueError('invalid timing numeric input')
    if not 0 < snapshot['cruise_speed_kph'] <= snapshot['max_speed_kph']:
        raise ValueError('invalid aircraft speeds')
    activities = snapshot['activities']
    if type(activities) is not dict or set(activities) != ACTIVITIES:
        raise ValueError('invalid handling activities')
    ranges = list(activities.values()) + [snapshot[k] for k in (
        'taxi_to_stand_seconds', 'taxi_out_seconds', 'taxi_in_seconds')]
    for value in ranges:
        if (type(value) is not list or len(value) != 2
                or any(type(n) is not int for n in value)
                or not 0 <= value[0] <= value[1] <= 86400):
            raise ValueError('invalid timing range')


def validate_planning(envelope):
    """Called only after baseline structure validation succeeds."""
    world = envelope['world_state']
    for schedule in world['schedule_definitions'].values():
        for revision in schedule['revisions'].values():
            until = revision['recurrence'].get('until_local_date')
            if until is not None:
                if envelope['metadata']['save_schema_version'] != 4:
                    raise ValueError('bounded planner recurrence requires schema 4')
                if (type(until) is not str or date.fromisoformat(until).isoformat() != until
                        or until < revision['effective_from_local_date']):
                    raise ValueError('invalid recurrence end date')
            elif 'until_local_date' in revision['recurrence']:
                raise ValueError('recurrence end date cannot be null')
            if 'planning_timing' in revision:
                validate_timing(revision['planning_timing'])
                if envelope['metadata']['save_schema_version'] != 4:
                    raise ValueError('timed planning requires schema 4')
                model = world['aircraft'][revision['planned_aircraft_id']]['model_reference']
                if revision['planning_timing']['model_reference'] != model:
                    raise ValueError('planning timing model mismatch')
    by_aircraft = {}
    for flight in world['dated_flights'].values():
        revision = world['schedule_definitions'][flight['schedule_id']]['revisions'][
            str(flight['schedule_revision'])]
        until = revision['recurrence'].get('until_local_date')
        if until is not None and flight['scheduled_departure_local_date'] > until:
            raise ValueError('dated flight exceeds retained revision recurrence end date')
        snapshot = revision.get('planning_timing')
        if snapshot:
            duration = (parse_canonical_utc(flight['scheduled_in_block_utc'])
                        - parse_canonical_utc(flight['scheduled_off_block_utc'])).total_seconds()
            if duration != timing_bounds(snapshot)[1][1]:
                raise ValueError('planned gate-to-gate duration differs from timing snapshot')
        if flight['status'] not in {'SUPERSEDED', 'CANCELLED'}:
            by_aircraft.setdefault(flight['planned_aircraft_id'], []).append(flight)
    for flights in by_aircraft.values():
        flights.sort(key=lambda f: (f['scheduled_off_block_utc'], f['dated_flight_id']))
        for previous, following in zip(flights, flights[1:]):
            revisions = [world['schedule_definitions'][f['schedule_id']]['revisions'][
                str(f['schedule_revision'])] for f in (previous, following)]
            if not any('planning_timing' in r for r in revisions):
                continue
            if flight_reservation(world, previous)[1] > flight_reservation(world, following)[0]:
                raise ValueError('reserved ground/flight blocks overlap')
