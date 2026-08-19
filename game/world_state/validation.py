"""Strict, side-effect-free validation for Stage 1 authoritative worlds."""

from dataclasses import dataclass
from typing import Mapping

from .ids import parse_entity_id
from .money import is_minor_amount
from .schema import (
    ACCOUNT_CATEGORIES,
    AIRLINE_CONTROL_TYPES,
    AIRLINE_OWNER_TYPES,
    CLOCK_STATES,
    ENVELOPE_ROOTS,
    ENTITY_COLLECTIONS,
    ENTITY_TYPES,
    MAX_ENTITY_ID_NUMBER,
    PENDING_EVENT_STATUS,
    REQUIRED_ACCOUNT_CODES,
    SAVE_SCHEMA_VERSION,
    TERMINAL_EVENT_STATUSES,
    WORLD_ROOTS,
)
from .serialization import json_compatibility_error
from .timestamps import is_canonical_utc


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    recoverable: bool = False

    def as_dict(self):
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "recoverable": self.recoverable,
        }


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[ValidationIssue, ...]

    @property
    def is_valid(self):
        return not self.errors

    def as_dict(self):
        return {"is_valid": self.is_valid, "errors": [error.as_dict() for error in self.errors]}

    def __bool__(self):
        return self.is_valid


def _canonical_utc(value):
    return is_canonical_utc(value)


def _currency_code(value):
    return (
        isinstance(value, str)
        and len(value) == 3
        and value.isascii()
        and value.isalpha()
        and value == value.upper()
    )


class _Validator:
    def __init__(self, envelope):
        self.envelope = envelope
        self.errors = []
        self.world = {}

    def add(self, code, path, message, entity_type=None, entity_id=None):
        self.errors.append(ValidationIssue(code, path, message, entity_type, entity_id))

    def require_mapping(self, value, path):
        if not isinstance(value, Mapping):
            self.add("invalid_type", path, "must be a dictionary")
            return {}
        return value

    def require_text(self, record, field, path, entity_type=None, entity_id=None):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            self.add("malformed_required_field", f"{path}.{field}", "must be a non-empty string", entity_type, entity_id)
            return None
        return value

    def require_ref(self, record, field, targets, path, entity_type, entity_id, optional=False):
        value = record.get(field)
        if optional and value is None:
            return None
        if not isinstance(value, str) or value not in targets:
            self.add("dangling_reference", f"{path}.{field}", f"must reference an existing {field.removesuffix('_id')}", entity_type, entity_id)
            return None
        return value

    def require_timestamp(self, record, field, path, entity_type=None, entity_id=None, optional=False):
        value = record.get(field)
        if optional and value is None:
            return None
        if not _canonical_utc(value):
            self.add("invalid_timestamp", f"{path}.{field}", "must be canonical UTC YYYY-MM-DDTHH:MM:SSZ", entity_type, entity_id)
            return None
        return value

    def validate_root(self):
        if not isinstance(self.envelope, Mapping):
            self.add("invalid_envelope", "$", "world envelope must be a dictionary")
            return False
        serialization_error = json_compatibility_error(self.envelope)
        if serialization_error:
            path, message = serialization_error
            self.add("not_json_compatible", path, message)
        for key in ENVELOPE_ROOTS:
            if key not in self.envelope:
                self.add("missing_root", f"$.{key}", "required root is missing")
        for key in sorted(set(self.envelope) - ENVELOPE_ROOTS, key=repr):
            self.add("unknown_root", f"$.{key}", "field is not part of schema version 1")
        metadata = self.require_mapping(self.envelope.get("metadata"), "$.metadata")
        schema_version = metadata.get("save_schema_version")
        if isinstance(schema_version, bool) or schema_version != SAVE_SCHEMA_VERSION:
            self.add("unsupported_schema_version", "$.metadata.save_schema_version", f"must equal {SAVE_SCHEMA_VERSION}")
        for field in ("game_version", "reference_data_version", "lineage_id"):
            self.require_text(metadata, field, "$.metadata")
        self.require_timestamp(metadata, "world_created_at_utc", "$.metadata")

        simulation = self.require_mapping(self.envelope.get("simulation"), "$.simulation")
        self.require_timestamp(simulation, "time_utc", "$.simulation")
        clock_state = simulation.get("clock_state")
        if not isinstance(clock_state, str) or clock_state not in CLOCK_STATES:
            self.add("invalid_clock_state", "$.simulation.clock_state", "must be a canonical clock mode")
        cursor = simulation.get("event_order_cursor")
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
            self.add("invalid_event_cursor", "$.simulation.event_order_cursor", "must be a non-negative integer")
        configuration = self.require_mapping(simulation.get("configuration"), "$.simulation.configuration")
        self.require_text(configuration, "difficulty", "$.simulation.configuration")
        ratios = self.require_mapping(configuration.get("clock_ratios"), "$.simulation.configuration.clock_ratios")
        for mode in ("NORMAL", "FAST"):
            ratio = ratios.get(mode)
            if isinstance(ratio, bool) or not isinstance(ratio, int) or ratio < 1:
                self.add("invalid_clock_ratio", f"$.simulation.configuration.clock_ratios.{mode}", "must be a positive integer")
        for mode in sorted(set(ratios) - {"NORMAL", "FAST"}, key=repr):
            self.add("unknown_clock_ratio", f"$.simulation.configuration.clock_ratios.{mode}", "ratio is not part of the Stage 1 clock")
        fast_forward = self.require_mapping(simulation.get("fast_forward"), "$.simulation.fast_forward")
        target = fast_forward.get("target_time_utc")
        if clock_state == "FAST_FORWARD":
            if not _canonical_utc(target):
                self.add("invalid_fast_forward_target", "$.simulation.fast_forward.target_time_utc", "FAST_FORWARD requires a canonical UTC target")
            elif _canonical_utc(simulation.get("time_utc")) and target < simulation["time_utc"]:
                self.add("invalid_fast_forward_target", "$.simulation.fast_forward.target_time_utc", "target cannot precede simulation time")
        elif target is not None:
            self.add("invalid_fast_forward_target", "$.simulation.fast_forward.target_time_utc", "target must be null outside FAST_FORWARD")
        revisions = self.require_mapping(simulation.get("operation_revisions"), "$.simulation.operation_revisions")
        for owner_id, revision in revisions.items():
            if not isinstance(owner_id, str):
                self.add("invalid_revision_owner", "$.simulation.operation_revisions", "owner IDs must be strings")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                self.add("invalid_revision", f"$.simulation.operation_revisions.{owner_id}", "must be a non-negative integer")

        deterministic = self.require_mapping(self.envelope.get("deterministic_state"), "$.deterministic_state")
        seed = deterministic.get("world_seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            self.add("invalid_seed", "$.deterministic_state.world_seed", "must be a non-negative integer")
        self.require_mapping(deterministic.get("streams"), "$.deterministic_state.streams")
        self.world = self.require_mapping(self.envelope.get("world_state"), "$.world_state")
        for key in WORLD_ROOTS:
            if key not in self.world:
                self.add("missing_world_root", f"$.world_state.{key}", "required world root is missing")
        for key in sorted(set(self.world) - WORLD_ROOTS, key=repr):
            self.add("unknown_world_root", f"$.world_state.{key}", "field is not part of schema version 1")
        self.require_mapping(self.envelope.get("ui_state"), "$.ui_state")
        return True

    def validate_collections_and_ids(self):
        seen_primary_ids = {}
        max_issued = {entity_type: 0 for entity_type in ENTITY_TYPES}
        for entity_type, (collection_name, id_field) in ENTITY_COLLECTIONS.items():
            path = f"$.world_state.{collection_name}"
            if collection_name not in self.world:
                self.add("missing_collection", path, "required authoritative collection is missing")
                continue
            collection = self.require_mapping(self.world.get(collection_name), path)
            seen_in_collection = set()
            for key, record in collection.items():
                record_path = f"{path}.{key}"
                if not isinstance(key, str):
                    self.add("invalid_collection_key", record_path, "entity collection keys must be strings", entity_type)
                    continue
                if not isinstance(record, Mapping):
                    self.add("invalid_entity", record_path, "entity record must be a dictionary", entity_type, key)
                    continue
                record_id = record.get(id_field)
                if isinstance(record_id, str):
                    if record_id in seen_in_collection:
                        self.add("duplicate_id", f"{record_path}.{id_field}", "duplicate primary ID in collection", entity_type, record_id)
                    else:
                        seen_in_collection.add(record_id)
                if record_id != key:
                    self.add("id_key_mismatch", f"{record_path}.{id_field}", "record ID must equal its collection key", entity_type, str(record_id))
                parsed = parse_entity_id(record_id, entity_type)
                if parsed is None:
                    self.add("malformed_id", f"{record_path}.{id_field}", f"must be a valid {entity_type} ID", entity_type, str(record_id))
                else:
                    max_issued[entity_type] = max(max_issued[entity_type], parsed[1])
                if isinstance(record_id, str):
                    previous = seen_primary_ids.get(record_id)
                    if previous is not None:
                        self.add("duplicate_id", f"{record_path}.{id_field}", f"ID is already used by {previous}", entity_type, record_id)
                    else:
                        seen_primary_ids[record_id] = entity_type

        event_history = self.require_mapping(
            self.world.get("event_history"), "$.world_state.event_history"
        )
        for key, record in event_history.items():
            path = f"$.world_state.event_history.{key}"
            if not isinstance(key, str) or not isinstance(record, Mapping):
                self.add("invalid_entity", path, "resolved event must be a keyed dictionary", "event", str(key))
                continue
            event_id = record.get("event_id")
            if event_id != key:
                self.add("id_key_mismatch", f"{path}.event_id", "record ID must equal its collection key", "event", str(event_id))
            parsed = parse_entity_id(event_id, "event")
            if parsed is None:
                self.add("malformed_id", f"{path}.event_id", "must be a valid event ID", "event", str(event_id))
            else:
                max_issued["event"] = max(max_issued["event"], parsed[1])
            if isinstance(event_id, str):
                previous = seen_primary_ids.get(event_id)
                if previous is not None:
                    self.add("duplicate_id", f"{path}.event_id", f"ID is already used by {previous}", "event", event_id)
                else:
                    seen_primary_ids[event_id] = "event_history"

        deterministic = self.envelope.get("deterministic_state", {})
        allocator = self.require_mapping(deterministic.get("id_allocator"), "$.deterministic_state.id_allocator")
        next_by_type = self.require_mapping(allocator.get("next_by_type"), "$.deterministic_state.id_allocator.next_by_type")
        for entity_type in ENTITY_TYPES:
            value = next_by_type.get(entity_type)
            path = f"$.deterministic_state.id_allocator.next_by_type.{entity_type}"
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
                or value > MAX_ENTITY_ID_NUMBER + 1
            ):
                self.add("invalid_id_allocator", path, "next value must be a positive integer")
            elif value <= max_issued[entity_type]:
                self.add("id_allocator_collision", path, "next value would collide with an issued ID")
        unknown = set(next_by_type) - set(ENTITY_TYPES)
        for entity_type in sorted(unknown, key=repr):
            self.add("unknown_id_namespace", f"$.deterministic_state.id_allocator.next_by_type.{entity_type}", "namespace is not part of schema version 1")

    def validate_structure(self):
        world = self.world
        player = self.require_mapping(world.get("player"), "$.world_state.player")
        if player.get("player_id") != "player":
            self.add("invalid_player", "$.world_state.player.player_id", "must equal 'player'")
        self.require_text(player, "ceo_display_name", "$.world_state.player")

        def valid_records(value, path):
            collection = self.require_mapping(value, path)
            return {key: record for key, record in collection.items() if isinstance(key, str) and isinstance(record, Mapping)}

        airports = valid_records(world.get("airports"), "$.world_state.airports")
        airlines = valid_records(world.get("airlines"), "$.world_state.airlines")
        aircraft = valid_records(world.get("aircraft"), "$.world_state.aircraft")
        markets = valid_records(world.get("directional_markets"), "$.world_state.directional_markets")
        connections = valid_records(world.get("connections"), "$.world_state.connections")
        schedules = valid_records(world.get("schedule_definitions"), "$.world_state.schedule_definitions")
        flights = valid_records(world.get("dated_flights"), "$.world_state.dated_flights")
        itineraries = valid_records(world.get("itineraries"), "$.world_state.itineraries")
        bookings = valid_records(world.get("bookings"), "$.world_state.bookings")
        accounts = valid_records(world.get("financial_accounts"), "$.world_state.financial_accounts")
        transactions = valid_records(world.get("transactions"), "$.world_state.transactions")
        events = valid_records(world.get("pending_events"), "$.world_state.pending_events")
        event_history = valid_records(world.get("event_history"), "$.world_state.event_history")
        operations = self.require_mapping(world.get("active_aircraft_operations"), "$.world_state.active_aircraft_operations")

        primary = self.require_ref(player, "primary_airline_id", airlines, "$.world_state.player", "player", "player")
        if primary and airlines.get(primary, {}).get("control_type") != "PLAYER":
            self.add("invalid_ownership", "$.world_state.player.primary_airline_id", "primary airline must be player-controlled", "airline", primary)
        if primary and (
            airlines.get(primary, {}).get("owner_type") != "PLAYER"
            or airlines.get(primary, {}).get("owner_id") != "player"
        ):
            self.add(
                "invalid_ownership",
                "$.world_state.player.primary_airline_id",
                "primary airline must be owned directly by the player",
                "airline",
                primary,
            )

        airport_reference_codes = {}
        for airport_id, record in airports.items():
            path = f"$.world_state.airports.{airport_id}"
            reference_code = self.require_text(record, "reference_code", path, "airport", airport_id)
            self.require_text(record, "display_name", path, "airport", airport_id)
            self.require_text(record, "timezone", path, "airport", airport_id)
            if reference_code:
                if reference_code != reference_code.upper():
                    self.add("malformed_required_field", f"{path}.reference_code", "must be uppercase", "airport", airport_id)
                previous = airport_reference_codes.get(reference_code)
                if previous is not None:
                    self.add("duplicate_airport_reference", f"{path}.reference_code", f"reference code is already used by {previous}", "airport", airport_id)
                else:
                    airport_reference_codes[reference_code] = airport_id
            for field in ("iata_code", "icao_code"):
                if record.get(field) is not None and (not isinstance(record.get(field), str) or not record[field]):
                    self.add("malformed_required_field", f"{path}.{field}", "must be null or a non-empty string", "airport", airport_id)
                elif isinstance(record.get(field), str):
                    expected_length = 3 if field == "iata_code" else 4
                    if len(record[field]) != expected_length or record[field] != record[field].upper():
                        self.add("malformed_required_field", f"{path}.{field}", f"must be an uppercase {expected_length}-character code", "airport", airport_id)

        for airline_id, record in airlines.items():
            path = f"$.world_state.airlines.{airline_id}"
            self.require_text(record, "display_name", path, "airline", airline_id)
            if not _currency_code(record.get("base_currency")):
                self.add("invalid_currency", f"{path}.base_currency", "must be a three-letter uppercase currency code", "airline", airline_id)
            control = record.get("control_type")
            if not isinstance(control, str) or control not in AIRLINE_CONTROL_TYPES:
                self.add("invalid_control", f"{path}.control_type", "must be PLAYER or AI", "airline", airline_id)
            owner_type = record.get("owner_type")
            owner_id = record.get("owner_id")
            if not isinstance(owner_type, str) or owner_type not in AIRLINE_OWNER_TYPES:
                self.add("invalid_ownership", f"{path}.owner_type", "invalid owner type", "airline", airline_id)
            elif owner_type == "PLAYER" and owner_id != "player":
                self.add("invalid_ownership", f"{path}.owner_id", "PLAYER ownership must reference player", "airline", airline_id)
            elif owner_type == "INDEPENDENT" and owner_id is not None:
                self.add("invalid_ownership", f"{path}.owner_id", "INDEPENDENT ownership must have null owner_id", "airline", airline_id)
            elif owner_type == "AIRLINE" and (
                not isinstance(owner_id, str)
                or owner_id not in airlines
                or owner_id == airline_id
            ):
                self.add("invalid_ownership", f"{path}.owner_id", "AIRLINE ownership must reference another airline", "airline", airline_id)
            for field in ("base_airport_ids", "hub_airport_ids", "financial_account_ids"):
                values = record.get(field)
                if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                    self.add("malformed_required_field", f"{path}.{field}", "must be a list of IDs", "airline", airline_id)
                    continue
                if len(values) != len(set(values)):
                    self.add("duplicate_reference", f"{path}.{field}", "must not contain duplicate IDs", "airline", airline_id)
                targets = accounts if field == "financial_account_ids" else airports
                for index, value in enumerate(values):
                    if value not in targets:
                        self.add("dangling_reference", f"{path}.{field}[{index}]", "referenced entity does not exist", "airline", airline_id)
                    elif field == "financial_account_ids" and targets[value].get("airline_id") != airline_id:
                        self.add("invalid_ownership", f"{path}.{field}[{index}]", "account belongs to another airline", "airline", airline_id)
            hubs = record.get("hub_airport_ids", [])
            bases = record.get("base_airport_ids", [])
            if (
                isinstance(hubs, list)
                and all(isinstance(value, str) for value in hubs)
                and isinstance(bases, list)
                and all(isinstance(value, str) for value in bases)
                and not set(hubs).issubset(set(bases))
            ):
                self.add("invalid_ownership", f"{path}.hub_airport_ids", "every hub must also be an operating base", "airline", airline_id)

        reported_cycles = set()
        for airline_id in airlines:
            chain = []
            current = airline_id
            while (
                isinstance(current, str)
                and current in airlines
                and airlines[current].get("owner_type") == "AIRLINE"
            ):
                if current in chain:
                    cycle = frozenset(chain[chain.index(current):])
                    if cycle not in reported_cycles:
                        reported_cycles.add(cycle)
                        self.add(
                            "ownership_cycle",
                            f"$.world_state.airlines.{airline_id}.owner_id",
                            "airline ownership must be acyclic",
                            "airline",
                            airline_id,
                        )
                    break
                chain.append(current)
                current = airlines[current].get("owner_id")

        for aircraft_id, record in aircraft.items():
            path = f"$.world_state.aircraft.{aircraft_id}"
            owner = self.require_ref(record, "airline_id", airlines, path, "aircraft", aircraft_id)
            self.require_ref(record, "home_airport_id", airports, path, "aircraft", aircraft_id)
            self.require_ref(record, "current_airport_id", airports, path, "aircraft", aircraft_id, optional=True)
            self.require_text(record, "display_registration", path, "aircraft", aircraft_id)
            self.require_text(record, "model_reference", path, "aircraft", aircraft_id)
            self.require_text(record, "status", path, "aircraft", aircraft_id)
            if owner is None:
                continue

        market_pairs = {}
        for market_id, record in markets.items():
            path = f"$.world_state.directional_markets.{market_id}"
            origin = self.require_ref(record, "origin_airport_id", airports, path, "market", market_id)
            destination = self.require_ref(record, "destination_airport_id", airports, path, "market", market_id)
            if origin is not None and origin == destination:
                self.add("invalid_market", path, "origin and destination must differ", "market", market_id)
            elif origin is not None and destination is not None:
                pair = (origin, destination)
                previous = market_pairs.get(pair)
                if previous is not None:
                    self.add("duplicate_market", path, f"directional pair is already represented by {previous}", "market", market_id)
                else:
                    market_pairs[pair] = market_id

        airline_markets = {}
        for connection_id, record in connections.items():
            path = f"$.world_state.connections.{connection_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "connection", connection_id)
            market_id = self.require_ref(record, "market_id", markets, path, "connection", connection_id)
            self.require_text(record, "status", path, "connection", connection_id)
            if airline_id and market_id:
                pair = (airline_id, market_id)
                previous = airline_markets.get(pair)
                if previous is not None:
                    self.add("duplicate_connection", path, f"airline market connection already exists as {previous}", "connection", connection_id)
                else:
                    airline_markets[pair] = connection_id

        for schedule_id, record in schedules.items():
            path = f"$.world_state.schedule_definitions.{schedule_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "schedule", schedule_id)
            connection_id = self.require_ref(record, "connection_id", connections, path, "schedule", schedule_id)
            planned = self.require_ref(record, "planned_aircraft_id", aircraft, path, "schedule", schedule_id, optional=True)
            self.require_text(record, "status", path, "schedule", schedule_id)
            self.require_mapping(record.get("recurrence"), f"{path}.recurrence")
            self.require_timestamp(record, "effective_from_utc", path, "schedule", schedule_id)
            self.require_timestamp(record, "effective_until_utc", path, "schedule", schedule_id, optional=True)
            start = record.get("effective_from_utc")
            end = record.get("effective_until_utc")
            if _canonical_utc(start) and _canonical_utc(end) and start >= end:
                self.add("invalid_timestamp_order", path, "effective_until_utc must be after effective_from_utc", "schedule", schedule_id)
            if connection_id and airline_id and connections[connection_id].get("airline_id") != airline_id:
                self.add("invalid_ownership", f"{path}.connection_id", "connection belongs to another airline", "schedule", schedule_id)
            if planned and airline_id and aircraft[planned].get("airline_id") != airline_id:
                self.add("invalid_ownership", f"{path}.planned_aircraft_id", "aircraft belongs to another airline", "schedule", schedule_id)

        for flight_id, record in flights.items():
            path = f"$.world_state.dated_flights.{flight_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "dated_flight", flight_id)
            schedule_id = self.require_ref(record, "schedule_id", schedules, path, "dated_flight", flight_id)
            connection_id = self.require_ref(record, "connection_id", connections, path, "dated_flight", flight_id)
            planned = self.require_ref(record, "planned_aircraft_id", aircraft, path, "dated_flight", flight_id, optional=True)
            start = self.require_timestamp(record, "scheduled_off_block_utc", path, "dated_flight", flight_id)
            end = self.require_timestamp(record, "scheduled_in_block_utc", path, "dated_flight", flight_id)
            self.require_text(record, "status", path, "dated_flight", flight_id)
            if start and end and start >= end:
                self.add("invalid_timestamp_order", path, "scheduled arrival must be after departure", "dated_flight", flight_id)
            for related, related_id, label in ((schedules, schedule_id, "schedule"), (connections, connection_id, "connection"), (aircraft, planned, "aircraft")):
                if related_id and airline_id and related[related_id].get("airline_id") != airline_id:
                    self.add("invalid_ownership", f"{path}.{label}_id", f"{label} belongs to another airline", "dated_flight", flight_id)
            if (
                schedule_id
                and connection_id
                and schedules[schedule_id].get("connection_id") != connection_id
            ):
                self.add("inconsistent_reference", f"{path}.connection_id", "must match the schedule's connection", "dated_flight", flight_id)

        for itinerary_id, record in itineraries.items():
            path = f"$.world_state.itineraries.{itinerary_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "itinerary", itinerary_id)
            flight_ids = record.get("dated_flight_ids")
            if not isinstance(flight_ids, list) or not flight_ids:
                self.add("malformed_required_field", f"{path}.dated_flight_ids", "must be a non-empty list", "itinerary", itinerary_id)
            else:
                valid_flight_ids = [flight_id for flight_id in flight_ids if isinstance(flight_id, str)]
                if len(valid_flight_ids) != len(flight_ids):
                    self.add("malformed_required_field", f"{path}.dated_flight_ids", "must contain only string IDs", "itinerary", itinerary_id)
                if len(valid_flight_ids) != len(set(valid_flight_ids)):
                    self.add("duplicate_reference", f"{path}.dated_flight_ids", "itinerary must not repeat a dated flight", "itinerary", itinerary_id)
                for index, flight_id in enumerate(valid_flight_ids):
                    if flight_id not in flights:
                        self.add("dangling_reference", f"{path}.dated_flight_ids[{index}]", "dated flight does not exist", "itinerary", itinerary_id)
                    elif airline_id and flights[flight_id].get("airline_id") != airline_id:
                        self.add("invalid_ownership", f"{path}.dated_flight_ids[{index}]", "dated flight belongs to another airline", "itinerary", itinerary_id)

        for booking_id, record in bookings.items():
            path = f"$.world_state.bookings.{booking_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "booking", booking_id)
            itinerary_id = self.require_ref(record, "itinerary_id", itineraries, path, "booking", booking_id)
            self.require_timestamp(record, "booked_at_utc", path, "booking", booking_id)
            count = record.get("passenger_count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                self.add("invalid_passenger_count", f"{path}.passenger_count", "must be a positive integer", "booking", booking_id)
            if not is_minor_amount(record.get("total_fare_minor")) or record.get("total_fare_minor", -1) < 0:
                self.add("invalid_money", f"{path}.total_fare_minor", "must be a non-negative integer minor-unit amount", "booking", booking_id)
            if not _currency_code(record.get("currency")):
                self.add("invalid_currency", f"{path}.currency", "must be a three-letter uppercase currency code", "booking", booking_id)
            self.require_text(record, "status", path, "booking", booking_id)
            if itinerary_id and airline_id and itineraries[itinerary_id].get("airline_id") != airline_id:
                self.add("invalid_ownership", f"{path}.itinerary_id", "itinerary belongs to another airline", "booking", booking_id)

        account_ids_by_airline = {airline_id: set() for airline_id in airlines}
        account_codes_by_airline = {airline_id: {} for airline_id in airlines}
        for account_id, record in accounts.items():
            path = f"$.world_state.financial_accounts.{account_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "account", account_id)
            code = self.require_text(record, "code", path, "account", account_id)
            currency = record.get("currency")
            if not _currency_code(currency):
                self.add("invalid_currency", f"{path}.currency", "must be a three-letter uppercase currency code", "account", account_id)
            category = record.get("category")
            if not isinstance(category, str) or category not in ACCOUNT_CATEGORIES:
                self.add("invalid_account_category", f"{path}.category", "unknown account category", "account", account_id)
            if not is_minor_amount(record.get("balance_minor")):
                self.add("invalid_money", f"{path}.balance_minor", "must be an integer minor-unit amount", "account", account_id)
            if airline_id:
                account_ids_by_airline[airline_id].add(account_id)
                if currency != airlines[airline_id].get("base_currency"):
                    self.add("invalid_currency", f"{path}.currency", "must match the owning airline's base currency", "account", account_id)
                if code:
                    previous = account_codes_by_airline[airline_id].get(code)
                    if previous is not None:
                        self.add("duplicate_account_code", f"{path}.code", f"account code is already used by {previous}", "account", account_id)
                    else:
                        account_codes_by_airline[airline_id][code] = account_id
        for airline_id, actual in account_ids_by_airline.items():
            listed = airlines.get(airline_id, {}).get("financial_account_ids", [])
            if (
                isinstance(listed, list)
                and all(isinstance(value, str) for value in listed)
                and set(listed) != actual
            ):
                self.add("account_index_mismatch", f"$.world_state.airlines.{airline_id}.financial_account_ids", "must list exactly the airline's accounts", "airline", airline_id)
            codes = account_codes_by_airline[airline_id]
            for code, category in REQUIRED_ACCOUNT_CODES.items():
                account_id = codes.get(code)
                if account_id is None:
                    self.add("missing_financial_account", f"$.world_state.airlines.{airline_id}.financial_account_ids", f"required account code '{code}' is missing", "airline", airline_id)
                elif accounts[account_id].get("category") != category:
                    self.add("invalid_account_category", f"$.world_state.financial_accounts.{account_id}.category", f"account '{code}' must use category {category}", "account", account_id)

        for transaction_id, record in transactions.items():
            path = f"$.world_state.transactions.{transaction_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "transaction", transaction_id)
            self.require_timestamp(record, "occurred_at_utc", path, "transaction", transaction_id)
            self.require_text(record, "description", path, "transaction", transaction_id)
            entries = record.get("entries")
            if not isinstance(entries, list) or len(entries) < 2:
                self.add("invalid_transaction", f"{path}.entries", "must contain at least two entries", "transaction", transaction_id)
                continue
            total = 0
            amounts_valid = True
            for index, entry in enumerate(entries):
                entry_path = f"{path}.entries[{index}]"
                if not isinstance(entry, Mapping):
                    self.add("invalid_transaction", entry_path, "entry must be a dictionary", "transaction", transaction_id)
                    amounts_valid = False
                    continue
                account_id = entry.get("account_id")
                if not isinstance(account_id, str) or account_id not in accounts:
                    self.add("dangling_reference", f"{entry_path}.account_id", "account does not exist", "transaction", transaction_id)
                elif airline_id and accounts[account_id].get("airline_id") != airline_id:
                    self.add("invalid_ownership", f"{entry_path}.account_id", "account belongs to another airline", "transaction", transaction_id)
                amount = entry.get("amount_minor")
                if not is_minor_amount(amount):
                    self.add("invalid_money", f"{entry_path}.amount_minor", "must be an integer minor-unit amount", "transaction", transaction_id)
                    amounts_valid = False
                else:
                    total += amount
            if amounts_valid and total != 0:
                self.add("unbalanced_transaction", f"{path}.entries", "entry amounts must sum to zero", "transaction", transaction_id)

        owner_targets = {
            "airline": airlines,
            "aircraft": aircraft,
            "connection": connections,
            "dated_flight": flights,
            "booking": bookings,
        }
        revisions = self.envelope.get("simulation", {}).get("operation_revisions", {})
        simulation_time = self.envelope.get("simulation", {}).get("time_utc")
        cursor = self.envelope.get("simulation", {}).get("event_order_cursor")
        seen_sequences = {}

        def validate_event(event_id, record, path, pending):
            self.require_text(record, "event_type", path, "event", event_id)
            due = self.require_timestamp(record, "due_at_utc", path, "event", event_id)
            if pending and due and _canonical_utc(simulation_time) and due < simulation_time:
                self.add("event_scheduled_in_past", f"{path}.due_at_utc", "pending event cannot precede simulation time", "event", event_id)
            owner_type = record.get("owner_type")
            owner_id = record.get("owner_id")
            if (
                not isinstance(owner_type, str)
                or owner_type not in owner_targets
                or not isinstance(owner_id, str)
                or owner_id not in owner_targets.get(owner_type, {})
            ):
                self.add("dangling_reference", f"{path}.owner_id", "event owner does not exist", "event", event_id)
            revision = record.get("operation_revision")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                self.add("invalid_revision", f"{path}.operation_revision", "must be a non-negative integer", "event", event_id)
            elif isinstance(owner_id, str):
                current_revision = revisions.get(owner_id) if isinstance(revisions, Mapping) else None
                if current_revision is None:
                    self.add("missing_operation_revision", f"$.simulation.operation_revisions.{owner_id}", "event owner must have a persisted revision", "event", event_id)
                elif isinstance(current_revision, int) and revision > current_revision:
                    self.add("invalid_revision", f"{path}.operation_revision", "cannot exceed the owner's current revision", "event", event_id)
            order_key = record.get("order_key")
            if (
                not isinstance(order_key, list)
                or len(order_key) != 2
                or any(
                    isinstance(value, bool) or not isinstance(value, int) or value < 0
                    for value in order_key
                )
            ):
                self.add("invalid_event_order", f"{path}.order_key", "must be [non-negative priority, non-negative sequence]", "event", event_id)
            else:
                sequence = order_key[1]
                previous = seen_sequences.get(sequence)
                if previous is not None:
                    self.add("duplicate_event_order", f"{path}.order_key", f"sequence is already used by {previous}", "event", event_id)
                else:
                    seen_sequences[sequence] = event_id
                if isinstance(cursor, int) and sequence >= cursor:
                    self.add("invalid_event_cursor", f"{path}.order_key", "sequence must be below the next ordering cursor", "event", event_id)
            payload = self.require_mapping(record.get("payload"), f"{path}.payload")
            payload_error = json_compatibility_error(payload)
            if payload_error:
                _payload_path, message = payload_error
                self.add("not_json_compatible", f"{path}.payload", message, "event", event_id)
            expected_statuses = {PENDING_EVENT_STATUS} if pending else TERMINAL_EVENT_STATUSES
            status = record.get("status")
            if not isinstance(status, str) or status not in expected_statuses:
                self.add("invalid_event_status", f"{path}.status", f"must be one of {sorted(expected_statuses)}", "event", event_id)
            if pending:
                if "resolved_at_utc" in record:
                    self.add("invalid_event_status", f"{path}.resolved_at_utc", "pending event cannot have a resolution timestamp", "event", event_id)
            else:
                resolved_at = self.require_timestamp(record, "resolved_at_utc", path, "event", event_id)
                if resolved_at and _canonical_utc(simulation_time) and resolved_at > simulation_time:
                    self.add("invalid_event_resolution", f"{path}.resolved_at_utc", "cannot be later than simulation time", "event", event_id)
                if (
                    resolved_at
                    and due
                    and isinstance(status, str)
                    and status in {"COMPLETED", "STALE"}
                    and resolved_at != due
                ):
                    self.add("invalid_event_resolution", f"{path}.resolved_at_utc", "completed and stale events resolve at their due timestamp", "event", event_id)

        for event_id, record in events.items():
            validate_event(event_id, record, f"$.world_state.pending_events.{event_id}", True)
        for event_id, record in event_history.items():
            validate_event(event_id, record, f"$.world_state.event_history.{event_id}", False)

        valid_owner_ids = set().union(*(set(target) for target in owner_targets.values()))
        if isinstance(revisions, Mapping):
            for owner_id in revisions:
                if isinstance(owner_id, str) and owner_id not in valid_owner_ids:
                    self.add("dangling_reference", f"$.simulation.operation_revisions.{owner_id}", "revision owner does not exist")

        for key, record in operations.items():
            path = f"$.world_state.active_aircraft_operations.{key}"
            if not isinstance(record, Mapping):
                self.add("invalid_entity", path, "operation must be a dictionary", "operation", str(key))
                continue
            if key not in flights or record.get("dated_flight_id") != key:
                self.add("dangling_reference", f"{path}.dated_flight_id", "operation key and dated flight reference must match", "operation", str(key))
            aircraft_id = record.get("aircraft_id")
            if not isinstance(aircraft_id, str) or aircraft_id not in aircraft:
                self.add("dangling_reference", f"{path}.aircraft_id", "aircraft does not exist", "operation", str(key))
            elif key in flights and aircraft[aircraft_id].get("airline_id") != flights[key].get("airline_id"):
                self.add("invalid_ownership", f"{path}.aircraft_id", "operation aircraft belongs to another airline", "operation", str(key))
            self.require_text(record, "state", path, "operation", str(key))
            revision = record.get("revision")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                self.add("invalid_revision", f"{path}.revision", "must be a non-negative integer", "operation", str(key))

        demand = self.require_mapping(world.get("demand_state"), "$.world_state.demand_state")
        for field in ("market_demand", "fractional_accumulators"):
            values = self.require_mapping(demand.get(field), f"$.world_state.demand_state.{field}")
            for market_id in values:
                if market_id not in markets:
                    self.add("dangling_reference", f"$.world_state.demand_state.{field}.{market_id}", "market does not exist")
        history = self.require_mapping(world.get("history"), "$.world_state.history")
        for field in ("operations", "financial", "world_events"):
            if not isinstance(history.get(field), list):
                self.add("invalid_type", f"$.world_state.history.{field}", "must be a list")

        ui = self.require_mapping(self.envelope.get("ui_state"), "$.ui_state")
        focus = ui.get("current_focus_airline_id")
        if focus is not None and (not isinstance(focus, str) or focus not in airlines):
            self.add("dangling_reference", "$.ui_state.current_focus_airline_id", "focused airline does not exist")
        selected_screen = ui.get("selected_screen")
        if selected_screen is not None and not isinstance(selected_screen, str):
            self.add("invalid_type", "$.ui_state.selected_screen", "must be null or a string")
        if not isinstance(ui.get("filters"), Mapping):
            self.add("invalid_type", "$.ui_state.filters", "must be a dictionary")

    def validate_no_name_references_or_float_money(self):
        forbidden = {
            "airline_name",
            "aircraft_registration",
            "assigned_aircraft_registration",
            "assigned_aircraft",
            "current_focus",
            "origin_iata",
            "destination_iata",
            "route_id",
        }

        stack = [(self.world, "$.world_state")]
        seen_containers = set()
        while stack:
            value, path = stack.pop()
            if isinstance(value, Mapping):
                marker = id(value)
                if marker in seen_containers:
                    continue
                seen_containers.add(marker)
                for key, nested in value.items():
                    child_path = f"{path}.{key}"
                    if key in forbidden:
                        self.add("name_based_authoritative_reference", child_path, "legacy/name-based authoritative field is forbidden")
                    if isinstance(key, str) and key.endswith("_minor") and not is_minor_amount(nested):
                        self.add("invalid_money", child_path, "authoritative money must be integer minor units")
                    if (
                        isinstance(key, str)
                        and key.endswith("_utc")
                        and nested is not None
                        and not _canonical_utc(nested)
                    ):
                        self.add("invalid_timestamp", child_path, "authoritative timestamp must be canonical UTC YYYY-MM-DDTHH:MM:SSZ")
                    stack.append((nested, child_path))
            elif isinstance(value, list):
                marker = id(value)
                if marker in seen_containers:
                    continue
                seen_containers.add(marker)
                for index, nested in enumerate(value):
                    stack.append((nested, f"{path}[{index}]"))

    def run(self):
        if self.validate_root():
            self.validate_collections_and_ids()
            self.validate_structure()
            self.validate_no_name_references_or_float_money()
        return ValidationResult(tuple(self.errors))


def validate_world(envelope):
    """Return structured errors without repairing or mutating ``envelope``."""
    return _Validator(envelope).run()
