"""Detached management reads of validated, session-owned fleet authority."""
from copy import deepcopy
from datetime import date, timedelta

from game.booking.indexes import rebuild_booking_indexes
from game.aircraft_operations.fulfilment import _build_confirmed_carriage_manifest
from game.scheduling.local_time import airport_local
from game.world_state.acquisition_validation import validate_configuration


def _week_flights(envelope, aircraft):
    world = envelope['world_state']
    today = airport_local(world, aircraft['home_airport_id'], envelope['simulation']['time_utc']).date()
    first = today - timedelta(days=today.weekday())
    last = first + timedelta(days=7)
    operations = world['active_aircraft_operations']
    results = world['flight_results']
    rows = []
    for key, flight in world['dated_flights'].items():
        owner = operations.get(key, results.get(key, {})).get('actual_aircraft_id', flight['planned_aircraft_id'])
        departure = airport_local(world, aircraft['home_airport_id'], flight['scheduled_off_block_utc'])
        if owner == aircraft['aircraft_id'] and first <= departure.date() < last:
            rows.append((key, flight))
    return first.isoformat(), sorted(rows, key=lambda row: (row[1]['scheduled_off_block_utc'], row[0]))


def _status(world, aircraft):
    if aircraft['status'] == 'PARKED':
        return 'Parked at ' + world['airports'][aircraft['current_airport_id']]['reference_code']
    if aircraft['status'] == 'IN_FLIGHT':
        op = next(row for row in world['active_aircraft_operations'].values()
                  if row['actual_aircraft_id'] == aircraft['aircraft_id'])
        return 'Airborne ' + ' -> '.join(world['airports'][op[k]]['reference_code']
                                        for k in ('origin_airport_id', 'destination_airport_id'))
    return aircraft['status'].replace('_', ' ').title()


def _model(aircraft, catalogs):
    if 'configuration' in aircraft:
        return validate_configuration(aircraft, catalogs)
    # Historical unconfigured A320-200 has no catalog-backed manufacturer identity.
    return None


def _project_management_fleet_owned(envelope, airline_id):
    world = envelope['world_state']
    indexes = rebuild_booking_indexes(envelope)
    catalogs = {}; rows = []
    for key, aircraft in sorted(world['aircraft'].items()):
        if aircraft['airline_id'] != airline_id: continue
        view = _model(aircraft, catalogs)
        week, flights = _week_flights(envelope, aircraft)
        seats = passengers = 0
        for flight_id, flight in flights:
            if flight['service_type'] != 'PASSENGER' or flight['status'] not in {'PLANNED', 'OPERATIONALLY_LOCKED', 'COMPLETED'}: continue
            seats += flight['capacity']
            result = world['flight_results'].get(flight_id)
            if result:
                passengers += result['carried_passenger_count']
            else:
                manifest = _build_confirmed_carriage_manifest(envelope, flight_id,
                    booking_ids=indexes.booking_ids_by_dated_flight_id.get(flight_id, ()))
                if not manifest.succeeded: raise ValueError('current-week carriage projection is invalid')
                passengers += manifest.carried_passenger_count
        rows.append({'aircraft_id': key, 'hub': world['airports'][aircraft['home_airport_id']]['reference_code'],
                     'name': None, 'registration': aircraft['display_registration'],
                     'model': view['model']['display_name'] if view else aircraft['model_reference'],
                     'manufacturer': view['manufacturer']['display_name'] if view else None,
                     'status': _status(world, aircraft), 'status_filter': aircraft['status'],
                     'week_start': week, 'weekly_passengers': passengers, 'weekly_seats': seats,
                     'weekly_load': passengers * 10000 // seats if seats else None})
    return deepcopy(rows)


def _project_aircraft_details_owned(envelope, airline_id, aircraft_id):
    world = envelope['world_state']; aircraft = world['aircraft'].get(aircraft_id)
    if not aircraft or aircraft['airline_id'] != airline_id: raise ValueError('aircraft is not owned by this airline')
    view = _model(aircraft, {})
    lifecycle = aircraft.get('lifecycle', {})
    week, flights = _week_flights(envelope, aircraft)
    schedule = []
    for key, flight in flights:
        origin, destination = flight['origin_airport_id'], flight['destination_airport_id']
        departure = airport_local(world, origin, flight['scheduled_off_block_utc'])
        arrival = airport_local(world, destination, flight['scheduled_in_block_utc'])
        schedule.append({'id': key, 'day': departure.strftime('%a %d %b'),
                         'departure': departure.isoformat(), 'origin': world['airports'][origin]['reference_code'],
                         'destination': world['airports'][destination]['reference_code'],
                         'arrival': arrival.isoformat(), 'state': flight['status']})
    attributes = [('Airplane Name', '— (not modeled)'), ('Registration', aircraft['display_registration']),
                  ('Manufacturer', view['manufacturer']['display_name'] if view else '—'),
                  ('Model', view['model']['display_name'] if view else aircraft['model_reference']),
                  ('Ownership', lifecycle.get('ownership_status', '—')),
                  ('Acquisition', lifecycle.get('acquisition_type', '—')),
                  ('Home base', world['airports'][aircraft['home_airport_id']]['reference_code']),
                  ('Operational status', _status(world, aircraft)),
                  ('Cabin', 'Maximum Economy' if view else 'Legacy Economy'),
                  ('Passenger capacity', aircraft.get('configuration', {}).get('economy_capacity', 180 if aircraft['model_reference'] == 'A320-200' else '—')),
                  ('Cargo', 'Not modeled'), ('Reference range (km)', view['model']['reference_range_km'] if view else '—'),
                  ('Manufactured', lifecycle.get('manufactured_date', '—')),
                  ('Age (days)', (date.fromisoformat(envelope['simulation']['time_utc'][:10]) - date.fromisoformat(lifecycle['manufactured_date'])).days if lifecycle.get('manufactured_date') else '—'),
                  ('Flight hours', f"{lifecycle['lifetime_flight_seconds'] / 3600:.1f}" if 'lifetime_flight_seconds' in lifecycle else '—'),
                  ('Cycles', lifecycle.get('lifetime_cycles', '—')),
                  ('Service condition', f"{lifecycle['service_condition_bps'] / 100:.2f}%" if 'service_condition_bps' in lifecycle else '—'),
                  ('Maintenance', 'Routine cost settled on flight completion; no repair action')]
    contract = world['aircraft_contracts'].get(lifecycle.get('aircraft_contract_id'))
    if contract:
        attributes.extend((('Contract', contract['aircraft_contract_id']), ('Contract status', contract['status'])))
    return deepcopy({'aircraft_id': aircraft_id, 'attributes': attributes, 'week_start': week, 'schedule': schedule})
