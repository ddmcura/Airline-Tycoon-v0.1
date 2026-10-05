"""UI-independent, detached weekly drafts over canonical schedule publication."""

from copy import deepcopy
from contextlib import contextmanager
from datetime import date, timedelta
import json

from game.world_state.planning_reference import planning_snapshot, _PlanningReferences
from game.world_state.timestamps import format_utc, parse_canonical_utc
from game.world_state.validation import validate_world
from .publication import (
    configured_publication_horizon_utc, _expand_schedule,
    _revision_for_date, _occurrence_record,
    _stage_schedule_definition, _stage_schedule_revision, _publish_detached,
    _initial_partial_activation,
)
from .local_time import local_departure, airport_zone, airport_local
from .recurrence import POLICY, rolling_horizon, rolling_schedules, pattern_edit_date, ensure_publication_event
from .rotation import _connection
from .timing import timing_bounds, flight_reservation
from .eligibility import installed_capacity


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


class WeeklyDraft:
    """A draft is not authority; only save can replace the supplied world."""

    def __init__(self, envelope, *, airline_id, aircraft_id):
        _valid(envelope)
        world = envelope['world_state']
        aircraft = world['aircraft'].get(aircraft_id)
        if not aircraft or aircraft['airline_id'] != airline_id:
            raise ValueError('select an aircraft owned by the player')
        if aircraft['status'] not in {'PARKED', 'IN_FLIGHT'}:
            raise ValueError('aircraft is not available for future planning')
        self._base = deepcopy(envelope)
        self._fingerprint = _bytes(envelope)
        self.airline_id = airline_id
        self.aircraft_id = aircraft_id
        self._legs = []
        self._undo_stack = []
        self._replacement_ids = ()
        self._revision_from = None

    @property
    def legs(self):
        return deepcopy(self._legs)

    @property
    def last_stop(self):
        return (self._legs[-1]['destination_airport_id'] if self._legs else
                self.projected_location)

    def _snapshot(self, origin, destination):
        if origin == destination:
            raise ValueError('origin and destination must differ')
        return planning_snapshot(self._base['world_state'], self.aircraft_id, origin, destination,
                                 _references=getattr(self, '_operation_references', None))

    @contextmanager
    def _planning_operation(self):
        """Reuse immutable base movements/reference inputs only for this batch.

        Draft legs are merged afresh on every check. These inputs never survive
        the operation, enter saves, or hide subsequent world/reference changes.
        """
        self._operation_references = _PlanningReferences()
        try:
            self._operation_movements = self._base_movements()
            yield
        finally:
            self.__dict__.pop('_operation_movements', None)
            self.__dict__.pop('_operation_references', None)

    @property
    def context_airport_id(self):
        return self._base['world_state']['aircraft'][self.aircraft_id]['home_airport_id']

    @property
    def context_timezone(self):
        return self._base['world_state']['airports'][self.context_airport_id]['timezone']

    @property
    def current_local_date(self):
        return airport_local(self._base['world_state'], self.context_airport_id,
                             self._base['simulation']['time_utc']).date()

    @property
    def revision_from(self):
        return self._revision_from

    @property
    def publication_defaults(self):
        if not self._replacement_ids:
            return {'mode': 'This week / one-off', 'repeat': ''}
        ends = {self._base['world_state']['schedule_definitions'][key]['revisions'][str(
            self._base['world_state']['schedule_definitions'][key]['current_revision'])]['recurrence'].get(
                'until_local_date') for key in self._replacement_ids}
        if ends == {None}:
            return {'mode': 'Continuous recurring', 'repeat': ''}
        if len(ends) == 1 and None not in ends:
            return {'mode': 'Repeat until date', 'repeat': next(iter(ends))}
        return {'mode': 'This week / one-off', 'repeat': ''}

    @property
    def projected_location(self):
        world = self._base['world_state']
        aircraft = world['aircraft'][self.aircraft_id]
        if aircraft['status'] == 'IN_FLIGHT':
            active = [row for row in world['active_aircraft_operations'].values()
                      if row['actual_aircraft_id'] == self.aircraft_id
                      and row['state'] == 'OPERATIONALLY_LOCKED']
            if len(active) != 1:
                raise ValueError('aircraft active operation is unavailable')
            return active[0]['destination_airport_id']
        return aircraft['current_airport_id']

    @classmethod
    def edit_recurring(cls, envelope, *, airline_id, aircraft_id):
        draft = cls(envelope, airline_id=airline_id, aircraft_id=aircraft_id)
        schedules = rolling_schedules(envelope, airline_id, aircraft_id)
        if not schedules:
            raise ValueError('no active recurring aircraft pattern')
        draft._replacement_ids = tuple(row['schedule_id'] for row in schedules)
        draft._revision_from = pattern_edit_date(envelope, airline_id, aircraft_id)
        first = date.fromisoformat(draft._revision_from)
        start = local_departure(envelope['world_state'], draft.context_airport_id,
                                first.isoformat(), '00:00')
        end = local_departure(envelope['world_state'], draft.context_airport_id,
                              (first + timedelta(days=7)).isoformat(), '00:00')
        legs = []
        for schedule in schedules:
            prototype = schedule['revisions'][str(schedule['current_revision'])]
            origin_zone = airport_zone(envelope['world_state'], prototype['origin_airport_id'])
            local_date = start.astimezone(origin_zone).date()
            while local_date <= end.astimezone(origin_zone).date():
                revision = _revision_for_date(schedule, local_date)
                if (revision is not None and revision['recurrence'].get('enabled', True)
                        and local_date.weekday() in revision['recurrence']['weekdays']):
                    # The editable pattern is independent of its old finite end.
                    flight = _occurrence_record(envelope, schedule, revision, local_date)
                    departure = parse_canonical_utc(flight['scheduled_off_block_utc'])
                    if start <= departure < end:
                        legs.append({'origin_airport_id': flight['origin_airport_id'],
                            'destination_airport_id': flight['destination_airport_id'],
                            'departure_utc': flight['scheduled_off_block_utc'],
                            'planning_timing': deepcopy(revision['planning_timing']),
                            'fare_minor': flight['fare_offer']['amount_minor'],
                            'service_type': flight['service_type']})
                local_date += timedelta(days=1)
        draft._legs = sorted(legs, key=lambda row: row['departure_utc'])
        return draft

    def _revision_origin_date(self, world, origin_id):
        boundary = local_departure(world, self.context_airport_id, self._revision_from, '00:00')
        return boundary.astimezone(airport_zone(world, origin_id)).date().isoformat()

    def _candidate(self, legs, repeat_until=None, *, continuous=False):
        candidate = deepcopy(self._base)
        ids = []
        now = parse_canonical_utc(candidate['simulation']['time_utc'])
        target = now
        capacity = (installed_capacity(candidate['world_state']['aircraft'][self.aircraft_id])
                    if any(leg['service_type'] != 'DEADHEAD' for leg in legs) else 0)
        ordered = sorted(legs, key=lambda row: row['departure_utc'])
        for index, leg in enumerate(ordered):
            world = candidate['world_state']
            origin, destination = leg['origin_airport_id'], leg['destination_airport_id']
            zone = airport_zone(world, origin)
            depart = parse_canonical_utc(leg['departure_utc'])
            local = depart.astimezone(zone)
            end_date = None if continuous else (repeat_until or local.date().isoformat())
            if end_date is not None and date.fromisoformat(end_date) < local.date():
                raise ValueError('repeat end precedes a draft flight')
            arrival = depart + timedelta(seconds=timing_bounds(leg['planning_timing'])[1][1])
            arrival_local = arrival.astimezone(airport_zone(world, destination))
            deadhead = leg['service_type'] == 'DEADHEAD'
            connection = None if deadhead else _connection(candidate, self.airline_id, origin, destination)
            common = dict(connection_id=connection, planned_aircraft_id=self.aircraft_id,
                origin_airport_id=origin, destination_airport_id=destination,
                planning_timing=leg['planning_timing'],
                capacity=0 if deadhead else capacity,
                fare_offer={'currency': 'USD', 'amount_minor': leg['fare_minor']},
                service_type=leg['service_type'],
                passenger_service_classification='NON_PASSENGER' if deadhead else 'ECONOMY')
            recurrence = dict(frequency='WEEKLY', weekdays=[local.weekday()],
                departure_local_time=local.strftime('%H:%M:%S'), departure_local_fold=local.fold,
                arrival_local_time=arrival_local.strftime('%H:%M:%S'), arrival_local_fold=arrival_local.fold,
                arrival_day_offset=(arrival_local.date() - local.date()).days)
            if end_date is not None:
                recurrence['until_local_date'] = end_date
            if candidate['metadata']['save_schema_version'] == 7:
                recurrence['publication_policy'] = POLICY
            if index < len(self._replacement_ids):
                schedule_id = self._replacement_ids[index]
                result = _result(_stage_schedule_revision(candidate, schedule_id,
                    effective_from_local_date=self._revision_origin_date(world, origin),
                    expected_revision=world['schedule_definitions'][schedule_id]['current_revision'],
                    recurrence=recurrence, **common))
            else:
                result = _result(_stage_schedule_definition(candidate,
                    airline_id=self.airline_id, effective_from_local_date=local.date().isoformat(),
                    weekdays=recurrence['weekdays'],
                    departure_local_time=recurrence['departure_local_time'],
                    arrival_local_time=recurrence['arrival_local_time'],
                    departure_local_fold=local.fold, arrival_local_fold=arrival_local.fold,
                    arrival_day_offset=recurrence['arrival_day_offset'],
                    until_local_date=end_date, publication_policy=recurrence.get('publication_policy'),
                    **common))
            ids.append(result.schedule_id)
            target = max(target, depart)
        for schedule_id in self._replacement_ids[len(ordered):]:
            current = candidate['world_state']['schedule_definitions'][schedule_id]
            recurrence = deepcopy(current['revisions'][str(current['current_revision'])]['recurrence'])
            recurrence.pop('until_local_date', None)
            recurrence['enabled'] = False
            _result(_stage_schedule_revision(candidate, schedule_id,
                effective_from_local_date=self._revision_origin_date(candidate['world_state'],
                    current['revisions'][str(current['current_revision'])]['origin_airport_id']),
                expected_revision=current['current_revision'], recurrence=recurrence))
        ensure_publication_event(candidate, self.airline_id)
        if continuous or repeat_until:
            target = parse_canonical_utc(rolling_horizon(candidate, self.airline_id))
        # Validate the complete proposed definition batch once, then reconcile
        # inside this isolated candidate. No live authority changes until Save.
        _valid(candidate)
        published = _result(_publish_detached(candidate, format_utc(target)))
        _valid(candidate)
        # Revisions and cyclic continuity are checked beyond the initial rolling
        # horizon on a discarded candidate, never materialized in live authority.
        preview = deepcopy(candidate)
        _result(_publish_detached(preview, configured_publication_horizon_utc(preview)))
        _valid(preview)
        return candidate, tuple(ids), published

    def _base_movements(self):
        world = self._base['world_state']
        rows = []
        flights = list(world['dated_flights'].values())
        known = {flight['occurrence_key'] for flight in flights}
        now = parse_canonical_utc(self._base['simulation']['time_utc'])
        limit = now + timedelta(days=self._base['simulation']['configuration']['scheduling']['publication_horizon_days'])
        replacement_boundary = (local_departure(world, self.context_airport_id, self._revision_from, '00:00')
                                if self._revision_from else None)
        desired = {}
        for schedule_id in sorted(world['schedule_definitions']):
            schedule = world['schedule_definitions'][schedule_id]
            if schedule['status'] == 'ACTIVE':
                virtual, conflicts = _expand_schedule(self._base, schedule, now, limit,
                                                      known_occurrences=known)
                if conflicts:
                    raise ValueError(conflicts[0].message)
                desired.update(virtual)
        _initial_partial_activation(self._base, desired)
        flights.extend(flight for key, flight in sorted(desired.items())
                               if key not in known and not (
                                   flight['schedule_id'] in self._replacement_ids
                                   and parse_canonical_utc(flight['scheduled_off_block_utc']) >= replacement_boundary))
        for flight in flights:
            if (flight['planned_aircraft_id'] == self.aircraft_id
                    and flight['status'] not in {'SUPERSEDED', 'CANCELLED'}):
                start, end = flight_reservation(world, flight)
                rows.append((start, end, parse_canonical_utc(flight['scheduled_off_block_utc']),
                             parse_canonical_utc(flight['scheduled_in_block_utc']),
                             flight['origin_airport_id'], flight['destination_airport_id']))
        return rows

    def _movements(self, *, operational=False, extra=None):
        base = getattr(self, '_operation_movements', None)
        rows = list(self._base_movements() if base is None else base)
        eligible = set()
        for leg in self._legs + ([extra] if extra is not None else []):
            pre, block, post = timing_bounds(leg['planning_timing'])[1]
            depart = parse_canonical_utc(leg['departure_utc'])
            arrival = depart + timedelta(seconds=block)
            row = (depart - timedelta(seconds=pre), arrival + timedelta(seconds=post),
                   depart, arrival, leg['origin_airport_id'], leg['destination_airport_id'])
            rows.append(row)
            eligible.add(row)
        if operational:
            from .activation import initial_week_end, initial_week_window, operational_sequence
            end = initial_week_end(self._base, self.aircraft_id, ((row[0], row[2]) for row in eligible))
            beginning, boundary = initial_week_window(self._base, self.aircraft_id)
            activated = []
            world = self._base['world_state']
            for flight in world['dated_flights'].values():
                if flight['planned_aircraft_id'] != self.aircraft_id or flight['status'] in {'SUPERSEDED', 'CANCELLED'}:
                    continue
                revision = world['schedule_definitions'][flight['schedule_id']]['revisions'][str(flight['schedule_revision'])]
                departure = parse_canonical_utc(flight['scheduled_off_block_utc'])
                if (revision['recurrence'].get('publication_policy') == POLICY
                        and beginning <= departure < boundary):
                    activated.append(departure)
            rows = operational_sequence(self._base, self.aircraft_id, rows, eligible, end,
                                        activated_at=min(activated) if activated else None)
        return sorted(rows)

    def earliest(self, origin, destination, *, not_before=None, _pattern_only=False):
        snapshot = self._snapshot(origin, destination)
        pre, block, post = timing_bounds(snapshot)[1]
        now = parse_canonical_utc(self._base['simulation']['time_utc'])
        floor = parse_canonical_utc(not_before) if not_before else now
        pattern = _pattern_only or (floor - timedelta(seconds=pre) < now and not_before is not None)
        cursor = floor if pattern else max(now + timedelta(seconds=pre), floor)
        location = origin if pattern else self.projected_location
        turnaround = self._base['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']
        for start, end, departure, arrival, row_origin, row_destination in self._movements(operational=not pattern):
            if pattern:
                if (not _pattern_only and departure >= now) or (format_utc(departure), row_origin, row_destination) not in {
                    (leg['departure_utc'], leg['origin_airport_id'], leg['destination_airport_id'])
                    for leg in self._legs}:
                    continue
            elif end <= now:
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
        pattern = depart - timedelta(seconds=timing_bounds(snapshot)[1][0]) < now
        local_date = depart.astimezone(airport_zone(self._base['world_state'], origin)).date()
        current_date = now.astimezone(airport_zone(self._base['world_state'], origin)).date()
        if pattern and local_date < monday(current_date):
            raise ValueError('pattern slots before the current local week are unavailable')
        leg = {'origin_airport_id': origin, 'destination_airport_id': destination,
               'departure_utc': format_utc(depart), 'planning_timing': snapshot,
               'fare_minor': 0 if deadhead else fare_minor,
               'service_type': 'DEADHEAD' if deadhead else 'PASSENGER'}
        pre, block, post = timing_bounds(snapshot)[1]
        start, end = depart - timedelta(seconds=pre), depart + timedelta(seconds=block + post)
        limit = now + timedelta(days=self._base['simulation']['configuration']['scheduling']['publication_horizon_days'])
        if depart > limit:
            raise ValueError('departure exceeds publication horizon')
        location = origin if pattern else self.projected_location
        turnaround = self._base['simulation']['configuration']['scheduling']['minimum_turnaround_seconds']
        movements = self._movements() if pattern else self._movements(operational=True, extra=leg)
        proposed = (start, end, depart, depart + timedelta(seconds=block), origin, destination)
        if not pattern and proposed not in movements:
            # Initial incompatible prefix remains intent only; publication
            # proves the complete recurrence and strict post-activation chain.
            self._undo_stack.append(deepcopy(self._legs))
            self._legs = self._legs + [leg]
            return deepcopy(leg)
        if not pattern:
            movements.remove(proposed)
        for row_start, row_end, row_departure, arrival, row_origin, row_destination in movements:
            if pattern:
                if (format_utc(row_departure), row_origin, row_destination) not in {
                    (item['departure_utc'], item['origin_airport_id'], item['destination_airport_id'])
                    for item in self._legs}:
                    continue
            elif row_end <= now:
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
        self._undo_stack.append(deepcopy(self._legs))
        self._legs = self._legs + [leg]
        return deepcopy(leg)

    def add_return(self, *, fare_minor=None):
        if not self._legs:
            raise ValueError('add an outbound flight first')
        leg = self._legs[-1]
        pre, block, post = timing_bounds(leg['planning_timing'])[1]
        floor = format_utc(parse_canonical_utc(leg['departure_utc']) + timedelta(seconds=block + post))
        depart = parse_canonical_utc(leg['departure_utc'])
        row = (depart - timedelta(seconds=pre), depart + timedelta(seconds=block + post),
               depart, depart + timedelta(seconds=block),
               leg['origin_airport_id'], leg['destination_airport_id'])
        departure = self.earliest(leg['destination_airport_id'], leg['origin_airport_id'],
                                 not_before=floor,
                                 _pattern_only=row not in self._movements(operational=True))
        return self.add(leg['destination_airport_id'], leg['origin_airport_id'],
                        departure_utc=departure,
                        fare_minor=leg['fare_minor'] if fare_minor is None else fare_minor)

    def copy_day(self, source_date, target_date):
        source, target = date.fromisoformat(source_date), date.fromisoformat(target_date)
        zone = airport_zone(self._base['world_state'], self.context_airport_id)
        original = deepcopy(self._legs)
        selected = sorted([leg for leg in original if parse_canonical_utc(leg['departure_utc']).astimezone(zone).date() == source],
                          key=lambda leg: leg['departure_utc'])
        if not selected or source == target:
            raise ValueError('choose different dates and a nonempty draft day')
        candidate = deepcopy(self)
        anchor = parse_canonical_utc(selected[0]['departure_utc'])
        anchor_local = anchor.astimezone(airport_zone(self._base['world_state'], selected[0]['origin_airport_id']))
        translated = local_departure(self._base['world_state'], selected[0]['origin_airport_id'],
                                     target.isoformat(), anchor_local.strftime('%H:%M:%S'))
        for leg in selected:
            departure = translated + (parse_canonical_utc(leg['departure_utc']) - anchor)
            candidate.add(leg['origin_airport_id'], leg['destination_airport_id'],
                          departure_utc=format_utc(departure), fare_minor=leg['fare_minor'],
                          deadhead=leg['service_type'] == 'DEADHEAD')
        self._undo_stack.append(original)
        self._legs = candidate._legs

    def copy_selection(self, indices):
        """Return detached relative offsets; this clipboard is never world state."""
        if not indices or any(type(index) is not int or index < 0 or index >= len(self._legs)
                              for index in indices) or len(set(indices)) != len(indices):
            raise ValueError("select one or more draft flights")
        selected = sorted((self._legs[index] for index in indices),
                          key=lambda leg: leg["departure_utc"])
        anchor = parse_canonical_utc(selected[0]["departure_utc"])
        return {"contract": "WEEKLY_DRAFT_CLIPBOARD_V1",
                "aircraft_id": self.aircraft_id,
                "anchor_local_time": anchor.astimezone(
                    airport_zone(self._base['world_state'], selected[0]['origin_airport_id'])).strftime('%H:%M'),
                "legs": tuple({
                    "origin_airport_id": leg["origin_airport_id"],
                    "destination_airport_id": leg["destination_airport_id"],
                    "offset_seconds": int((parse_canonical_utc(leg["departure_utc"]) - anchor).total_seconds()),
                    "fare_minor": leg["fare_minor"],
                    "service_type": leg["service_type"],
                } for leg in selected)}

    def paste_sequence(self, clipboard, target_date, target_time):
        """Revalidate a translated sequence atomically against draft authority."""
        if (type(clipboard) is not dict
                or clipboard.get("contract") != "WEEKLY_DRAFT_CLIPBOARD_V1"
                or clipboard.get("aircraft_id") != self.aircraft_id
                or type(clipboard.get("legs")) not in (tuple, list)
                or not clipboard["legs"]):
            raise ValueError("clipboard does not belong to this aircraft draft")
        legs = clipboard["legs"]
        if (any(type(leg) is not dict or set(leg) != {
                "origin_airport_id", "destination_airport_id", "offset_seconds",
                "fare_minor", "service_type"} for leg in legs)
                or any(type(leg["offset_seconds"]) is not int or leg["offset_seconds"] < 0
                       or type(leg["fare_minor"]) is not int or leg["fare_minor"] < 0
                       or leg["service_type"] not in {"PASSENGER", "DEADHEAD"}
                       or type(leg["origin_airport_id"]) is not str
                       or type(leg["destination_airport_id"]) is not str
                       for leg in legs)
                or legs[0]["offset_seconds"] != 0
                or any(left["offset_seconds"] > right["offset_seconds"]
                       for left, right in zip(legs, legs[1:]))):
            raise ValueError("invalid weekly draft clipboard")
        start = local_departure(self._base["world_state"],
                                legs[0]["origin_airport_id"], target_date, target_time)
        candidate = deepcopy(self)
        for index, leg in enumerate(legs):
            departure = format_utc(start + timedelta(seconds=leg["offset_seconds"]))
            try:
                candidate.add(leg["origin_airport_id"], leg["destination_airport_id"],
                              departure_utc=departure, fare_minor=leg["fare_minor"],
                              deadhead=leg["service_type"] == "DEADHEAD")
            except (ValueError, KeyError) as exc:
                detail = str(exc)
                if index == 0:
                    try:
                        alternative = self.earliest(leg["origin_airport_id"],
                            leg["destination_airport_id"], not_before=departure)
                        if alternative != departure:
                            zone = airport_zone(self._base["world_state"], leg["origin_airport_id"])
                            local = parse_canonical_utc(alternative).astimezone(zone)
                            detail += f"; earliest available start: {local:%Y-%m-%d %H:%M}"
                    except (ValueError, KeyError):
                        pass
                raise ValueError(f"Pasted flight {index + 1} rejected: {detail}") from exc
        self._undo_stack.append(deepcopy(self._legs))
        self._legs = candidate._legs
        return len(legs)

    def _commit_edited_sequence(self, candidate):
        """Validate a detached edit and record one undo step, never world state."""
        if candidate._legs:
            candidate._candidate(candidate._legs)
        self._undo_stack.append(deepcopy(self._legs))
        self._legs = deepcopy(candidate._legs)

    def add_weekdays(self, origin, destination, local_dates, local_time,
                     *, earliest=False, return_flight=False, fare_minor=0):
        """Add selected local dates atomically through the normal planner."""
        if not local_dates or len(set(local_dates)) != len(local_dates):
            raise ValueError('select one or more distinct weekdays')
        candidate = deepcopy(self)
        zone = airport_zone(self._base['world_state'], origin)
        with candidate._planning_operation():
            for local_date in sorted(local_dates):
                try:
                    requested = local_departure(candidate._base['world_state'],
                                                origin, local_date, local_time)
                    departure = (candidate.earliest(origin, destination,
                                 not_before=format_utc(requested)) if earliest
                                 else format_utc(requested))
                    if parse_canonical_utc(departure).astimezone(zone).date().isoformat() != local_date:
                        raise ValueError('no available departure on the selected local day')
                    candidate.add(origin, destination, departure_utc=departure,
                                  fare_minor=fare_minor)
                    if return_flight:
                        candidate.add_return(fare_minor=fare_minor)
                except (ValueError, KeyError) as exc:
                    raise ValueError(f'{local_date}: {exc}') from exc
        count = len(candidate._legs) - len(self._legs)
        self._commit_edited_sequence(candidate)
        return count

    def paste_weekdays(self, clipboard, local_dates, local_time):
        """Apply every target through paste_sequence; all or none become draft."""
        if not local_dates or len(set(local_dates)) != len(local_dates):
            raise ValueError('select one or more distinct paste weekdays')
        candidate = deepcopy(self)
        total = 0
        for local_date in sorted(local_dates):
            try:
                total += candidate.paste_sequence(clipboard, local_date, local_time)
            except (ValueError, KeyError) as exc:
                raise ValueError(f'{local_date}: {exc}') from exc
        self._commit_edited_sequence(candidate)
        return total

    def delete_selection(self, indices):
        """Delete draft indices only; published reservations are not addressable."""
        if not indices or any(type(index) is not int or index < 0 or index >= len(self._legs)
                              for index in indices) or len(set(indices)) != len(indices):
            raise ValueError('select one or more unpublished draft flights')
        remaining = [leg for index, leg in enumerate(self._legs)
                     if index not in set(indices)]
        candidate = WeeklyDraft(self._base, airline_id=self.airline_id,
                                aircraft_id=self.aircraft_id)
        candidate._replacement_ids, candidate._revision_from = self._replacement_ids, self._revision_from
        for leg in sorted(remaining, key=lambda row: row['departure_utc']):
            candidate.add(leg['origin_airport_id'], leg['destination_airport_id'],
                          departure_utc=leg['departure_utc'], fare_minor=leg['fare_minor'],
                          deadhead=leg['service_type'] == 'DEADHEAD')
        self._commit_edited_sequence(candidate)
        return len(indices)

    def reschedule(self, index, local_date, local_time):
        """Move one unpublished leg to an exact local slot through validation."""
        if type(index) is not int or index < 0 or index >= len(self._legs):
            raise ValueError('select an unpublished draft flight')
        intents = deepcopy(self._legs)
        moved = intents[index]
        moved['departure_utc'] = format_utc(local_departure(
            self._base['world_state'], moved['origin_airport_id'],
            local_date, local_time))
        candidate = WeeklyDraft(self._base, airline_id=self.airline_id,
                                aircraft_id=self.aircraft_id)
        candidate._replacement_ids, candidate._revision_from = self._replacement_ids, self._revision_from
        for leg in sorted(intents, key=lambda row: row['departure_utc']):
            candidate.add(leg['origin_airport_id'], leg['destination_airport_id'],
                          departure_utc=leg['departure_utc'], fare_minor=leg['fare_minor'],
                          deadhead=leg['service_type'] == 'DEADHEAD')
        self._commit_edited_sequence(candidate)
        return deepcopy(moved)

    def reschedule_in_context(self, index, local_date, local_time):
        """Translate the home-local timeline proposal to the origin's local slot."""
        leg = self._legs[index]
        utc = local_departure(self._base['world_state'], self.context_airport_id,
                              local_date, local_time)
        local = utc.astimezone(airport_zone(self._base['world_state'], leg['origin_airport_id']))
        return self.reschedule(index, local.date().isoformat(), local.strftime('%H:%M:%S'))

    def undo(self):
        if self._undo_stack:
            self._legs = self._undo_stack.pop()
        elif self._legs and not self._replacement_ids:
            self._legs.pop()

    def save(self, envelope, *, repeat_until=None, continuous=False):
        if _bytes(envelope) != self._fingerprint:
            raise ValueError('STALE_DRAFT: world changed; reopen the planner')
        if not self._legs and not self._replacement_ids:
            raise ValueError('draft has no flights')
        candidate, ids, published = self._candidate(self._legs, repeat_until, continuous=continuous)
        envelope.clear()
        envelope.update(deepcopy(candidate))
        self._base = deepcopy(candidate)
        self._fingerprint = _bytes(candidate)
        self._legs = []
        self._undo_stack = []
        self._replacement_ids = ()
        self._revision_from = None
        return published

    def validate_current(self, envelope):
        """Check draft legs against current authority without publishing."""
        current = WeeklyDraft(envelope, airline_id=self.airline_id,
                              aircraft_id=self.aircraft_id)
        current._replacement_ids, current._revision_from = self._replacement_ids, self._revision_from
        with current._planning_operation():
            for leg in sorted(self._legs, key=lambda row: row['departure_utc']):
                current.add(leg['origin_airport_id'], leg['destination_airport_id'],
                            departure_utc=leg['departure_utc'], fare_minor=leg['fare_minor'],
                            deadhead=leg['service_type'] == 'DEADHEAD')
                if current._legs[-1]['planning_timing'] != leg['planning_timing']:
                    raise ValueError('STALE_DRAFT: aircraft timing changed; reopen the planner')
        return current

    def save_current(self, envelope, *, repeat_until=None, continuous=False):
        """Revalidate explicit draft legs against current authority, atomically.

        Runtime navigation may advance the world. Never overwrite it with the
        old draft snapshot, shift departures, or silently add positioning.
        """
        current = self.validate_current(envelope)
        result = current.save(envelope, repeat_until=repeat_until, continuous=continuous)
        self._base = current._base
        self._fingerprint = current._fingerprint
        self._legs = []
        self._undo_stack = []
        self._replacement_ids = ()
        self._revision_from = None
        return result

    def week_rows(self, week_date):
        start = monday(date.fromisoformat(week_date))
        zone = airport_zone(self._base['world_state'], self.context_airport_id)
        rows = []
        published_keys = {(flight['scheduled_off_block_utc'], flight['origin_airport_id'],
                           flight['destination_airport_id'])
                          for flight in self._base['world_state']['dated_flights'].values()
                          if flight['planned_aircraft_id'] == self.aircraft_id
                          and flight['status'] not in {'SUPERSEDED', 'CANCELLED'}}
        draft_indices = {(leg["departure_utc"], leg["origin_airport_id"],
                          leg["destination_airport_id"]): index
                         for index, leg in enumerate(self._legs)}
        for block_start, block_end, departure, arrival, origin, destination in self._movements():
            local_start, local_end = block_start.astimezone(zone), block_end.astimezone(zone)
            if local_start.date() <= start + timedelta(days=6) and local_end.date() >= start:
                rows.append({'origin_airport_id': origin, 'destination_airport_id': destination,
                             'reserved_from': local_start.isoformat(), 'reserved_until': local_end.isoformat(),
                             'timeline_departure_local': departure.astimezone(zone).isoformat(),
                             'timeline_arrival_local': arrival.astimezone(zone).isoformat(),
                             'departure_local': departure.astimezone(airport_zone(self._base['world_state'], origin)).isoformat(),
                             'arrival_local': arrival.astimezone(airport_zone(self._base['world_state'], destination)).isoformat(),
                             'departure_timezone': self._base['world_state']['airports'][origin]['timezone'],
                             'arrival_timezone': self._base['world_state']['airports'][destination]['timezone'],
                             'pattern_only': block_start < parse_canonical_utc(self._base['simulation']['time_utc']),
                             'published': (format_utc(departure), origin, destination) in published_keys,
                             'draft_index': draft_indices.get((format_utc(departure), origin, destination))})
        return rows
