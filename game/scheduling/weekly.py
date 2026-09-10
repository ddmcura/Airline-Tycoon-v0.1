"""UI-independent, detached weekly drafts over canonical schedule publication."""

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
import json

from game.world_state.planning_reference import planning_snapshot
from game.world_state.timestamps import format_utc, parse_canonical_utc
from game.world_state.timezones import load_named_timezone
from game.world_state.validation import validate_world
from .publication import (create_schedule_definition, publish_occurrences_through,
                          configured_publication_horizon_utc, _expand_schedule)
from .rotation import _connection
from .timing import timing_bounds, flight_reservation


def _bytes(world):
    return json.dumps(world, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _valid(world):
    result = validate_world(world)
    if not result.is_valid:
        issue = result.errors[0]
        raise ValueError(f'{issue.code}: {issue.message}')


def _result(result):
    if not result.succeeded:
        if result.conflicts:
            issue = result.conflicts[0]
            raise ValueError(f'{issue.code}: {issue.message}')
        raise ValueError(result.status)
    return result


def monday(value):
    return value - timedelta(days=value.weekday())


def local_departure(world, airport_id, local_date, local_time):
    """PH planner inputs; underlying publisher retains general timezone support."""
    airport = world['airports'][airport_id]
    if airport['timezone'] != 'Asia/Manila':
        raise ValueError('weekly terminal planner currently requires PH airports')
    parsed_date = date.fromisoformat(local_date)
    if parsed_date.isoformat() != local_date:
        raise ValueError('use YYYY-MM-DD')
    if len(local_time) == 5:
        local_time += ':00'
    parsed_time = time.fromisoformat(local_time)
    if parsed_time.isoformat() != local_time or parsed_time.tzinfo is not None:
        raise ValueError('use HH:MM or HH:MM:SS')
    zone = load_named_timezone(airport['timezone'])
    return datetime.combine(parsed_date, parsed_time, zone).astimezone(timezone.utc)


class WeeklyDraft:
    """A draft is not authority; only save can replace the supplied world."""

    def __init__(self, envelope, *, airline_id, aircraft_id):
        _valid(envelope)
        world = envelope['world_state']
        aircraft = world['aircraft'].get(aircraft_id)
        if not aircraft or aircraft['airline_id'] != airline_id:
            raise ValueError('select an aircraft owned by the player')
        if aircraft['status'] != 'PARKED' or aircraft['current_airport_id'] is None:
            raise ValueError('select a parked aircraft')
        self._base = deepcopy(envelope)
        self._fingerprint = _bytes(envelope)
        self.airline_id = airline_id
        self.aircraft_id = aircraft_id
        self._legs = []

    @property
    def legs(self):
        return deepcopy(self._legs)

    @property
    def last_stop(self):
        return (self._legs[-1]['destination_airport_id'] if self._legs else
                self._base['world_state']['aircraft'][self.aircraft_id]['current_airport_id'])

    def _snapshot(self, origin, destination):
        if origin == destination:
            raise ValueError('origin and destination must differ')
        return planning_snapshot(self._base['world_state'], self.aircraft_id, origin, destination)

    def _candidate(self, legs, repeat_until=None):
        candidate = deepcopy(self._base)
        ids = []
        target = parse_canonical_utc(candidate['simulation']['time_utc'])
        for leg in legs:
            world = candidate['world_state']
            origin, destination = leg['origin_airport_id'], leg['destination_airport_id']
            zone = load_named_timezone(world['airports'][origin]['timezone'])
            depart = parse_canonical_utc(leg['departure_utc'])
            local = depart.astimezone(zone)
            end_date = repeat_until or local.date().isoformat()
            end = date.fromisoformat(end_date)
            if end < local.date():
                raise ValueError('repeat end precedes a draft flight')
            arrival = depart + timedelta(seconds=timing_bounds(leg['planning_timing'])[1][1])
            arrival_local = arrival.astimezone(load_named_timezone(world['airports'][destination]['timezone']))
            deadhead = leg['service_type'] == 'DEADHEAD'
            connection = None if deadhead else _connection(candidate, self.airline_id, origin, destination)
            result = _result(create_schedule_definition(
                candidate, airline_id=self.airline_id, connection_id=connection,
                planned_aircraft_id=self.aircraft_id, origin_airport_id=origin,
                destination_airport_id=destination, weekdays=[local.weekday()],
                departure_local_time=local.strftime('%H:%M:%S'),
                arrival_local_time=arrival_local.strftime('%H:%M:%S'),
                arrival_day_offset=(arrival_local.date() - local.date()).days,
                effective_from_local_date=local.date().isoformat(),
                until_local_date=end_date, planning_timing=leg['planning_timing'],
                capacity=0 if deadhead else 180,
                fare_offer={'currency': 'USD', 'amount_minor': leg['fare_minor']},
                service_type=leg['service_type'],
                passenger_service_classification='NON_PASSENGER' if deadhead else 'ECONOMY'))
            ids.append(result.schedule_id)
            last = end - timedelta(days=(end.weekday() - local.weekday()) % 7)
            target = max(target, datetime.combine(last, local.time(), zone).astimezone(timezone.utc))
        published = _result(publish_occurrences_through(candidate, format_utc(target)))
        # Check existing, not-yet-published recurrences as well. Discard this
        # preview so validation cannot extend the player's publication window.
        preview = deepcopy(candidate)
        _result(publish_occurrences_through(
            preview, configured_publication_horizon_utc(preview)))
        _valid(candidate)
        return candidate, tuple(ids), published

    def _movements(self):
        world = self._base['world_state']
        rows = []
        flights = list(world['dated_flights'].values())
        known = {flight['occurrence_key'] for flight in flights}
        now = parse_canonical_utc(self._base['simulation']['time_utc'])
        limit = now + timedelta(days=self._base['simulation']['configuration']['scheduling']['publication_horizon_days'])
        for schedule_id in sorted(world['schedule_definitions']):
            schedule = world['schedule_definitions'][schedule_id]
            if schedule['status'] == 'ACTIVE':
                virtual, conflicts = _expand_schedule(self._base, schedule, now, limit)
                if conflicts:
                    raise ValueError(conflicts[0].message)
                flights.extend(flight for key, flight in sorted(virtual.items()) if key not in known)
        for flight in flights:
            if (flight['planned_aircraft_id'] == self.aircraft_id
                    and flight['status'] not in {'SUPERSEDED', 'CANCELLED'}):
                start, end = flight_reservation(world, flight)
                rows.append((start, end, parse_canonical_utc(flight['scheduled_off_block_utc']),
                             parse_canonical_utc(flight['scheduled_in_block_utc']),
                             flight['origin_airport_id'], flight['destination_airport_id']))
        for leg in self._legs:
            pre, block, post = timing_bounds(leg['planning_timing'])[1]
            depart = parse_canonical_utc(leg['departure_utc'])
            arrival = depart + timedelta(seconds=block)
            rows.append((depart - timedelta(seconds=pre), arrival + timedelta(seconds=post),
                         depart, arrival, leg['origin_airport_id'], leg['destination_airport_id']))
        return sorted(rows)

    def earliest(self, origin, destination, *, not_before=None):
        snapshot = self._snapshot(origin, destination)
        pre, block, post = timing_bounds(snapshot)[1]
        now = parse_canonical_utc(self._base['simulation']['time_utc'])
        floor = parse_canonical_utc(not_before) if not_before else now
        cursor = max(now + timedelta(seconds=pre), floor)
        location = self._base['world_state']['aircraft'][self.aircraft_id]['current_airport_id']
        turnaround = self._base['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']
        for start, end, departure, arrival, row_origin, row_destination in self._movements():
            if end <= now:
                # Completed work still reserves its post-arrival allowance.
                continue
            if (location == origin
                    and cursor + timedelta(seconds=block + post) <= start
                    and cursor + timedelta(seconds=block + turnaround) <= departure):
                return format_utc(cursor)
            cursor = max(cursor, end + timedelta(seconds=pre),
                         arrival + timedelta(seconds=turnaround))
            location = row_destination
        if location != origin:
            raise ValueError('REPOSITIONING_REQUIRED: aircraft cannot reach the chosen origin; add an explicit positioning flight')
        limit = now + timedelta(days=self._base['simulation']['configuration']['scheduling']['publication_horizon_days'])
        if cursor > limit:
            raise ValueError('no slot within the publication horizon')
        return format_utc(cursor)

    def add(self, origin, destination, *, departure_utc=None, fare_minor=0, deadhead=False):
        if type(fare_minor) is not int or fare_minor < 0:
            raise ValueError('fare must be non-negative integer USD minor units')
        snapshot = self._snapshot(origin, destination)
        depart = parse_canonical_utc(departure_utc or self.earliest(origin, destination,
            not_before=self._legs[-1]['departure_utc'] if self._legs else None))
        now = parse_canonical_utc(self._base['simulation']['time_utc'])
        if depart - timedelta(seconds=timing_bounds(snapshot)[1][0]) < now:
            raise ValueError('pre-departure work cannot start in the past')
        leg = {'origin_airport_id': origin, 'destination_airport_id': destination,
               'departure_utc': format_utc(depart), 'planning_timing': snapshot,
               'fare_minor': 0 if deadhead else fare_minor,
               'service_type': 'DEADHEAD' if deadhead else 'PASSENGER'}
        pre, block, post = timing_bounds(snapshot)[1]
        start, end = depart - timedelta(seconds=pre), depart + timedelta(seconds=block + post)
        limit = now + timedelta(days=self._base['simulation']['configuration']['scheduling']['publication_horizon_days'])
        if depart > limit:
            raise ValueError('departure exceeds publication horizon')
        location = self._base['world_state']['aircraft'][self.aircraft_id]['current_airport_id']
        turnaround = self._base['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']
        for row_start, row_end, row_departure, arrival, row_origin, row_destination in self._movements():
            if row_end <= now:
                continue
            if start < row_end and end > row_start:
                raise ValueError('reserved ground/flight blocks overlap')
            if row_departure < depart:
                location = row_destination
                if depart < arrival + timedelta(seconds=turnaround):
                    raise ValueError('INSUFFICIENT_TURNAROUND')
            elif row_departure < depart + timedelta(seconds=block + turnaround):
                raise ValueError('INSUFFICIENT_TURNAROUND')
        if location != origin:
            raise ValueError('REPOSITIONING_REQUIRED: add an explicit positioning flight')
        # A later movement may temporarily need a bridging leg while drafting.
        # Publication validates the entire chain atomically at Save.
        self._legs = self._legs + [leg]
        return deepcopy(leg)

    def add_return(self, *, fare_minor=None):
        if not self._legs:
            raise ValueError('add an outbound flight first')
        leg = self._legs[-1]
        pre, block, post = timing_bounds(leg['planning_timing'])[1]
        floor = format_utc(parse_canonical_utc(leg['departure_utc']) + timedelta(seconds=block + post))
        departure = self.earliest(leg['destination_airport_id'], leg['origin_airport_id'], not_before=floor)
        return self.add(leg['destination_airport_id'], leg['origin_airport_id'],
                        departure_utc=departure,
                        fare_minor=leg['fare_minor'] if fare_minor is None else fare_minor)

    def copy_day(self, source_date, target_date):
        source, target = date.fromisoformat(source_date), date.fromisoformat(target_date)
        zone = load_named_timezone('Asia/Manila')
        original = deepcopy(self._legs)
        selected = sorted([leg for leg in original if parse_canonical_utc(leg['departure_utc']).astimezone(zone).date() == source],
                          key=lambda leg: leg['departure_utc'])
        if not selected or source == target:
            raise ValueError('choose different dates and a nonempty draft day')
        candidate = deepcopy(self)
        for leg in selected:
            candidate.add(leg['origin_airport_id'], leg['destination_airport_id'],
                          departure_utc=format_utc(parse_canonical_utc(leg['departure_utc']) + (target-source)),
                          fare_minor=leg['fare_minor'], deadhead=leg['service_type'] == 'DEADHEAD')
        self._legs = candidate._legs

    def undo(self):
        if self._legs:
            self._legs.pop()

    def save(self, envelope, *, repeat_until=None):
        if _bytes(envelope) != self._fingerprint:
            raise ValueError('STALE_DRAFT: world changed; reopen the planner')
        if not self._legs:
            raise ValueError('draft has no flights')
        candidate, ids, published = self._candidate(self._legs, repeat_until)
        envelope.clear()
        envelope.update(deepcopy(candidate))
        self._base = deepcopy(candidate)
        self._fingerprint = _bytes(candidate)
        self._legs = []
        return published

    def week_rows(self, week_date):
        start = monday(date.fromisoformat(week_date))
        zone = load_named_timezone('Asia/Manila')
        rows = []
        for block_start, block_end, departure, arrival, origin, destination in self._movements():
            local_start, local_end = block_start.astimezone(zone), block_end.astimezone(zone)
            if local_start.date() <= start + timedelta(days=6) and local_end.date() >= start:
                rows.append({'origin_airport_id': origin, 'destination_airport_id': destination,
                             'reserved_from': local_start.isoformat(), 'reserved_until': local_end.isoformat(),
                             'departure_local': departure.astimezone(zone).isoformat(),
                             'arrival_local': arrival.astimezone(zone).isoformat()})
        return rows
