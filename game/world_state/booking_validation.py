"""Strict schema-3 Booking validation helpers."""

from datetime import date

from .booking_fingerprint import calculate_booking_configuration_fingerprint

from .ids import parse_entity_id
from .money import is_minor_amount
from .schema import (
    AGGREGATE_BOOKING_CONTRACT,
    BOOKING_CHECKPOINT_STATUSES,
    BOOKING_CHOICE_POLICY_CONTRACT,
    BOOKING_CONFIGURATION_CONTRACT,
    BOOKING_CURRENCY_POLICY,
    BOOKING_DESIRED_DATE_POLICY,
    DEFAULT_BOOKING_CHOICE_POLICY,
    DIRECT_ECONOMY_ITINERARY_CONTRACT,
    SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT,
    SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT,
)
from .timestamps import is_canonical_utc


def _date(value):
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _currency(value):
    return (
        isinstance(value, str)
        and len(value) == 3
        and value.isascii()
        and value.isalpha()
        and value == value.upper()
    )


def _nonnegative_integer(value):
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _positive_integer(value):
    return not isinstance(value, bool) and isinstance(value, int) and value >= 1


def _exact(validator, record, fields, path, code, message):
    if type(record) is not dict:
        validator.add(code, path, "must be a dictionary")
        return False
    if set(record) != set(fields):
        validator.add(code, path, message)
        return False
    return True


def _reject_aliases(validator, value, path):
    seen = {}
    active = set()

    def walk(item, item_path):
        if type(item) not in (dict, list):
            return
        marker = id(item)
        if marker in active:
            return
        previous = seen.get(marker)
        if previous is not None:
            validator.add(
                "invalid_world_state",
                item_path,
                f"authoritative Booking containers must not alias {previous}",
            )
            return
        seen[marker] = item_path
        active.add(marker)
        try:
            values = item.values() if type(item) is dict else item
            for index, nested in enumerate(values):
                child = (
                    f"{item_path}.{tuple(item)[index]}"
                    if type(item) is dict
                    else f"{item_path}[{index}]"
                )
                walk(nested, child)
        finally:
            active.remove(marker)

    walk(value, path)


def validate_booking_configuration(validator, configuration):
    path = "$.simulation.configuration.booking"
    fields = {
        "contract",
        "configuration_version",
        "revision",
        "booking_horizon_days",
        "desired_date_policy",
        "lead_time_buckets",
        "desired_date_tolerance_days",
        "choice_policy",
        "configuration_fingerprint",
    }
    if not _exact(
        validator,
        configuration,
        fields,
        path,
        "invalid_booking_configuration",
        "must contain exactly the canonical V1 Booking configuration fields",
    ):
        return
    _reject_aliases(validator, configuration, path)
    if configuration.get("contract") != BOOKING_CONFIGURATION_CONTRACT:
        validator.add("invalid_booking_configuration", f"{path}.contract", "unsupported Booking configuration contract")
    version = configuration.get("configuration_version")
    if not isinstance(version, str) or not version.strip():
        validator.add("invalid_booking_configuration", f"{path}.configuration_version", "must be non-empty text")
    if not _positive_integer(configuration.get("revision")):
        validator.add("invalid_booking_configuration", f"{path}.revision", "must be a positive integer")
    horizon = configuration.get("booking_horizon_days")
    if not _nonnegative_integer(horizon) or horizon > 365:
        validator.add("invalid_booking_configuration", f"{path}.booking_horizon_days", "must be an integer from 0 through 365")
        horizon = None
    if configuration.get("desired_date_policy") != BOOKING_DESIRED_DATE_POLICY:
        validator.add("invalid_booking_configuration", f"{path}.desired_date_policy", "unsupported desired-date policy")
    tolerance = configuration.get("desired_date_tolerance_days")
    if (
        not _nonnegative_integer(tolerance)
        or horizon is None
        or tolerance > horizon
    ):
        validator.add("invalid_booking_configuration", f"{path}.desired_date_tolerance_days", "must be a non-negative integer no greater than the horizon")

    buckets = configuration.get("lead_time_buckets")
    if type(buckets) is not list or not buckets:
        validator.add("invalid_booking_configuration", f"{path}.lead_time_buckets", "must be a non-empty ordered list")
    else:
        expected_start = 0
        total_weight = 0
        valid_ranges = True
        for index, bucket in enumerate(buckets):
            bucket_path = f"{path}.lead_time_buckets[{index}]"
            if not _exact(
                validator,
                bucket,
                {"minimum_lead_days", "maximum_lead_days", "weight_bps"},
                bucket_path,
                "invalid_booking_configuration",
                "bucket must contain exactly minimum_lead_days, maximum_lead_days, and weight_bps",
            ):
                valid_ranges = False
                continue
            minimum = bucket.get("minimum_lead_days")
            maximum = bucket.get("maximum_lead_days")
            weight = bucket.get("weight_bps")
            if (
                not _nonnegative_integer(minimum)
                or not _nonnegative_integer(maximum)
                or maximum < minimum
            ):
                valid_ranges = False
                validator.add("invalid_booking_configuration", bucket_path, "bucket bounds must be ordered non-negative integers")
            elif minimum != expected_start:
                valid_ranges = False
                validator.add("invalid_booking_configuration", bucket_path, "bucket ranges must be ordered, complete, and non-overlapping")
            else:
                expected_start = maximum + 1
            if not _nonnegative_integer(weight):
                validator.add("invalid_booking_configuration", f"{bucket_path}.weight_bps", "must be a non-negative integer")
            else:
                total_weight += weight
        if valid_ranges and horizon is not None and expected_start != horizon + 1:
            validator.add("invalid_booking_configuration", f"{path}.lead_time_buckets", "bucket ranges must cover every day through the configured horizon")
        if total_weight != 10_000:
            validator.add("invalid_booking_configuration", f"{path}.lead_time_buckets", "bucket weights must total exactly 10000")

    choice = configuration.get("choice_policy")
    if not _exact(
        validator,
        choice,
        DEFAULT_BOOKING_CHOICE_POLICY,
        f"{path}.choice_policy",
        "invalid_booking_configuration",
        "choice policy must contain exactly the canonical V1 fields",
    ):
        pass
    elif (
        choice.get("contract") != BOOKING_CHOICE_POLICY_CONTRACT
        or choice.get("production_input_families") != ["FARE", "SCHEDULE"]
        or choice.get("schedule_inputs")
        != ["DATE_DEVIATION", "DEPARTURE_TIMING", "DURATION"]
        or choice.get("absent_airline_quality_signals") != "NEUTRAL"
        or choice.get("deterministic_rank_usage")
        != "INTEGER_RESIDUALS_AND_EXACT_TIES_ONLY"
        or choice.get("currency_policy") != BOOKING_CURRENCY_POLICY
    ):
        validator.add("invalid_booking_configuration", f"{path}.choice_policy", "must equal the approved V1 policy boundary")

    fingerprint = configuration.get("configuration_fingerprint")
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(character not in "0123456789abcdef" for character in fingerprint)
    ):
        validator.add("invalid_booking_configuration", f"{path}.configuration_fingerprint", "must be lowercase SHA-256 text")
    else:
        try:
            expected = calculate_booking_configuration_fingerprint(configuration)
        except (KeyError, OverflowError, RecursionError, TypeError, ValueError):
            expected = None
        if fingerprint != expected:
            validator.add("inconsistent_booking_configuration_fingerprint", f"{path}.configuration_fingerprint", "stored Booking configuration does not match its witness")


def _validate_legacy_itinerary(validator, wrapper, itinerary_id, flights, airlines):
    path = f"$.world_state.itineraries.{itinerary_id}"
    if not _exact(
        validator,
        wrapper,
        {"itinerary_id", "contract", "payload"},
        path,
        "invalid_itinerary",
        "compatibility wrapper fields are invalid",
    ):
        return
    payload = wrapper.get("payload")
    if type(payload) is not dict or payload.get("itinerary_id") != itinerary_id:
        validator.add("invalid_itinerary", f"{path}.payload", "must preserve a schema-2 itinerary payload with matching identity")
        return
    if set(payload) != {"itinerary_id", "airline_id", "dated_flight_ids"}:
        validator.add(
            "invalid_itinerary",
            f"{path}.payload",
            "must preserve exactly the canonical schema-2 itinerary fields",
        )
        return
    airline_id = payload.get("airline_id")
    if not isinstance(airline_id, str) or airline_id not in airlines:
        validator.add("invalid_itinerary", f"{path}.payload.airline_id", "must reference an airline")
    flight_ids = payload.get("dated_flight_ids")
    if type(flight_ids) is not list or not flight_ids or any(type(value) is not str for value in flight_ids) or len(set(flight_ids)) != len(flight_ids):
        validator.add("invalid_itinerary", f"{path}.payload.dated_flight_ids", "must preserve a non-empty unique list of dated-flight IDs")
        return
    for index, flight_id in enumerate(flight_ids):
        if flight_id not in flights:
            validator.add("invalid_itinerary", f"{path}.payload.dated_flight_ids[{index}]", "dated flight does not exist")
        elif flights[flight_id].get("airline_id") != airline_id:
            validator.add("invalid_itinerary", f"{path}.payload.dated_flight_ids[{index}]", "dated flight belongs to another airline")


def _validate_direct_itinerary(validator, record, itinerary_id, world):
    path = f"$.world_state.itineraries.{itinerary_id}"
    fields = {
        "itinerary_id", "contract", "market_id", "airline_id",
        "origin_airport_id", "destination_airport_id", "dated_flight_ids",
        "scheduled_departure_utc", "scheduled_arrival_utc", "cabin",
        "fare_offer_snapshot", "schedule_lineage", "status",
    }
    if not _exact(validator, record, fields, path, "invalid_itinerary", "must contain exactly the direct Economy V1 fields"):
        return
    market_id = record.get("market_id")
    airline_id = record.get("airline_id")
    markets = world.get("directional_markets")
    airlines = world.get("airlines")
    flights = world.get("dated_flights")
    market = (
        markets.get(market_id)
        if type(markets) is dict and isinstance(market_id, str)
        else None
    )
    airline = (
        airlines.get(airline_id)
        if type(airlines) is dict and isinstance(airline_id, str)
        else None
    )
    flight_ids = record.get("dated_flight_ids")
    flight = (
        flights.get(flight_ids[0])
        if type(flights) is dict
        and type(flight_ids) is list
        and len(flight_ids) == 1
        and type(flight_ids[0]) is str
        else None
    )
    if type(market) is not dict:
        validator.add("invalid_itinerary", f"{path}.market_id", "must reference a directional market")
    if type(airline) is not dict:
        validator.add("invalid_itinerary", f"{path}.airline_id", "must reference an airline")
    if type(flight) is not dict:
        validator.add("invalid_itinerary", f"{path}.dated_flight_ids", "V1 requires exactly one existing dated-flight ID")
        flight = None
    if record.get("cabin") != "ECONOMY" or record.get("status") != "CONFIRMED":
        validator.add("invalid_itinerary", path, "V1 cabin and status must be ECONOMY and CONFIRMED")
    if not is_canonical_utc(record.get("scheduled_departure_utc")) or not is_canonical_utc(record.get("scheduled_arrival_utc")):
        validator.add("invalid_itinerary", path, "scheduled times must be canonical UTC timestamps")
    snapshot = record.get("fare_offer_snapshot")
    if not _exact(validator, snapshot, {"currency", "amount_minor"}, f"{path}.fare_offer_snapshot", "invalid_itinerary", "fare snapshot fields are invalid"):
        snapshot = {}
    if not _currency(snapshot.get("currency")) or not is_minor_amount(snapshot.get("amount_minor")) or snapshot.get("amount_minor", -1) < 0:
        validator.add("invalid_itinerary", f"{path}.fare_offer_snapshot", "fare snapshot must contain currency and non-negative integer amount_minor")
    lineage = record.get("schedule_lineage")
    if not _exact(validator, lineage, {"schedule_id", "schedule_revision"}, f"{path}.schedule_lineage", "invalid_itinerary", "schedule lineage fields are invalid"):
        lineage = {}
    if not isinstance(lineage.get("schedule_id"), str) or not _positive_integer(lineage.get("schedule_revision")):
        validator.add("invalid_itinerary", f"{path}.schedule_lineage", "must identify a retained schedule revision")
    if flight is not None:
        if (
            flight.get("service_type") != "PASSENGER"
            or flight.get("passenger_service_classification") != "ECONOMY"
        ):
            validator.add(
                "invalid_itinerary",
                f"{path}.dated_flight_ids",
                "direct Economy V1 requires a passenger Economy dated flight",
            )
        comparisons = {
            "airline_id": "airline_id",
            "origin_airport_id": "origin_airport_id",
            "destination_airport_id": "destination_airport_id",
            "scheduled_departure_utc": "scheduled_off_block_utc",
            "scheduled_arrival_utc": "scheduled_in_block_utc",
        }
        for field, flight_field in comparisons.items():
            if record.get(field) != flight.get(flight_field):
                validator.add("invalid_itinerary", f"{path}.{field}", "must match the dated flight")
        if snapshot != flight.get("fare_offer"):
            validator.add("invalid_itinerary", f"{path}.fare_offer_snapshot", "must snapshot the dated-flight fare")
        if lineage != {"schedule_id": flight.get("schedule_id"), "schedule_revision": flight.get("schedule_revision")}:
            validator.add("invalid_itinerary", f"{path}.schedule_lineage", "must match dated-flight schedule lineage")
    if type(market) is dict and (record.get("origin_airport_id"), record.get("destination_airport_id")) != (market.get("origin_airport_id"), market.get("destination_airport_id")):
        validator.add("invalid_itinerary", f"{path}.market_id", "market endpoints must match the itinerary")


def validate_schema3_booking_authority(validator):
    world = validator.world
    configuration = validator.envelope.get("simulation", {}).get("configuration", {}).get("booking")
    validate_booking_configuration(validator, configuration)
    booking_state = world.get("booking_state")
    path = "$.world_state.booking_state"
    if not _exact(validator, booking_state, {"booking_revision", "booking_checkpoints"}, path, "invalid_booking_state", "must contain exactly booking_revision and booking_checkpoints"):
        return
    _reject_aliases(validator, booking_state, path)
    booking_revision = booking_state.get("booking_revision")
    if not _nonnegative_integer(booking_revision):
        validator.add("invalid_booking_state", f"{path}.booking_revision", "must be a non-negative integer")
    checkpoints = booking_state.get("booking_checkpoints")
    if type(checkpoints) is not dict:
        validator.add("invalid_booking_state", f"{path}.booking_checkpoints", "must be a dictionary")
        checkpoints = {}
    checkpoint_dates = set()
    booking_configuration = configuration if type(configuration) is dict else {}
    demand_state = world.get("demand_state", {})
    if type(demand_state) is not dict:
        demand_state = {}
    processed_cohorts = demand_state.get("processed_cohorts", {})
    if type(processed_cohorts) is not dict:
        processed_cohorts = {}
    markets = world.get("directional_markets", {})
    if type(markets) is not dict:
        markets = {}
    pack_configuration = validator.envelope.get("simulation", {}).get("configuration", {}).get("demand", {}).get("market_pack_configuration", {})
    if type(pack_configuration) is not dict:
        pack_configuration = {}
    transactions = world.get("transactions", {})
    if type(transactions) is not dict:
        transactions = {}
    transaction_checkpoint_owner = {}
    for checkpoint_id, checkpoint in checkpoints.items():
        checkpoint_path = f"{path}.booking_checkpoints.{checkpoint_id}"
        fields = {
            "booking_checkpoint_id", "checkpoint_date", "due_at_utc", "status",
            "processed_at_utc", "booking_revision", "booking_configuration_revision",
            "booking_configuration_fingerprint", "demand_model_revision",
            "market_pack_revision", "market_results", "financial_transaction_ids",
        }
        if not _exact(validator, checkpoint, fields, checkpoint_path, "invalid_booking_checkpoint", "must contain exactly the canonical checkpoint fields"):
            continue
        if checkpoint.get("booking_checkpoint_id") != checkpoint_id or parse_entity_id(checkpoint_id, "booking_checkpoint") is None:
            validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.booking_checkpoint_id", "must equal its immutable checkpoint collection key")
        checkpoint_date = checkpoint.get("checkpoint_date")
        if not _date(checkpoint_date):
            validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.checkpoint_date", "must be canonical YYYY-MM-DD")
        elif checkpoint_date in checkpoint_dates:
            validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.checkpoint_date", "checkpoint date must be unique")
        else:
            checkpoint_dates.add(checkpoint_date)
            if checkpoint.get("due_at_utc") != f"{checkpoint_date}T00:00:00Z":
                validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.due_at_utc", "must be canonical midnight for checkpoint_date")
        status = checkpoint.get("status")
        if not isinstance(status, str) or status not in BOOKING_CHECKPOINT_STATUSES:
            validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.status", "must be PENDING or COMPLETED")
        processed = checkpoint.get("processed_at_utc")
        results = checkpoint.get("market_results")
        transaction_ids = checkpoint.get("financial_transaction_ids")
        if type(results) is not dict:
            validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.market_results", "must be a dictionary")
            results = {}
        if (
            type(transaction_ids) is not list
            or any(type(value) is not str for value in transaction_ids)
            or len(set(transaction_ids)) != len(transaction_ids)
            or transaction_ids != sorted(transaction_ids)
        ):
            validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.financial_transaction_ids", "must be a sorted unique list of transaction IDs")
            transaction_ids = []
        if status == "PENDING" and (processed is not None or results or transaction_ids):
            validator.add("invalid_booking_checkpoint", checkpoint_path, "pending checkpoints require null processed time and empty result/transaction collections")
        if status == "COMPLETED" and not is_canonical_utc(processed):
            validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.processed_at_utc", "completed checkpoints require a canonical UTC timestamp")
        for market_id, result in results.items():
            result_path = f"{checkpoint_path}.market_results.{market_id}"
            result_fields = {
                "market_id",
                "cohort_key",
                "desired_passenger_count",
                "booked_passenger_count",
                "outside_option_passenger_count",
                "booking_ids",
            }
            if not _exact(
                validator,
                result,
                result_fields,
                result_path,
                "result_validation_failed",
                "must contain exactly the canonical Booking market-result fields",
            ):
                continue
            if result.get("market_id") != market_id or market_id not in markets:
                validator.add("result_validation_failed", f"{result_path}.market_id", "must equal its existing market collection key")
            cohort_key = result.get("cohort_key")
            if not isinstance(cohort_key, str) or cohort_key not in processed_cohorts:
                validator.add("result_validation_failed", f"{result_path}.cohort_key", "must reference a processed demand cohort")
            else:
                cohort_record = processed_cohorts[cohort_key]
                cohort = (
                    cohort_record.get("payload")
                    if type(cohort_record) is dict
                    and type(cohort_record.get("payload")) is dict
                    else cohort_record
                )
                if type(cohort) is not dict or cohort.get("market_id") != market_id:
                    validator.add(
                        "result_validation_failed",
                        f"{result_path}.cohort_key",
                        "processed demand cohort must belong to the result market",
                    )
            counts = tuple(
                result.get(field)
                for field in (
                    "desired_passenger_count",
                    "booked_passenger_count",
                    "outside_option_passenger_count",
                )
            )
            if any(not _nonnegative_integer(value) for value in counts):
                validator.add("result_validation_failed", result_path, "result counts must be non-negative integers")
            elif counts[0] != counts[1] + counts[2]:
                validator.add("result_validation_failed", result_path, "booked and outside-option counts must conserve desired passengers")
            result_booking_ids = result.get("booking_ids")
            if (
                type(result_booking_ids) is not list
                or any(type(value) is not str for value in result_booking_ids)
                or len(set(result_booking_ids)) != len(result_booking_ids)
                or result_booking_ids != sorted(result_booking_ids)
            ):
                validator.add("result_validation_failed", f"{result_path}.booking_ids", "must be a sorted unique list of Booking IDs")
        for transaction_id in transaction_ids:
            if transaction_id not in transactions:
                validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.financial_transaction_ids", "transaction does not exist")
            previous_checkpoint = transaction_checkpoint_owner.get(transaction_id)
            if previous_checkpoint is not None:
                validator.add(
                    "invalid_booking_checkpoint",
                    f"{checkpoint_path}.financial_transaction_ids",
                    f"transaction is already owned by {previous_checkpoint}",
                )
            else:
                transaction_checkpoint_owner[transaction_id] = checkpoint_id
        pinned_fields = (
            ("booking_configuration_revision", booking_configuration.get("revision")),
            ("booking_configuration_fingerprint", booking_configuration.get("configuration_fingerprint")),
            ("demand_model_revision", demand_state.get("demand_model_revision")),
            ("market_pack_revision", pack_configuration.get("revision")),
        )
        for field, current in pinned_fields:
            value = checkpoint.get(field)
            if field == "booking_configuration_fingerprint":
                if (
                    not isinstance(value, str)
                    or len(value) != 64
                    or any(character not in "0123456789abcdef" for character in value)
                ):
                    validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.{field}", "must be a lowercase SHA-256 witness")
                elif status == "PENDING" and value != current:
                    validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.{field}", "pending checkpoint must pin the current Booking configuration witness")
            elif not _positive_integer(value) or (
                _positive_integer(current) and value > current
            ):
                validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.{field}", "must be a positive revision no greater than current authority")
            elif status == "PENDING" and value != current:
                validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.{field}", "pending checkpoint must pin the current authoritative revision")
        if (
            status == "COMPLETED"
            and checkpoint.get("booking_configuration_revision")
            == booking_configuration.get("revision")
            and checkpoint.get("booking_configuration_fingerprint")
            != booking_configuration.get("configuration_fingerprint")
        ):
            validator.add("invalid_booking_checkpoint", f"{checkpoint_path}.booking_configuration_fingerprint", "current-revision checkpoint witness must match current Booking configuration")
        if not _nonnegative_integer(checkpoint.get("booking_revision")) or (
            _nonnegative_integer(booking_revision)
            and checkpoint.get("booking_revision") > booking_revision
        ):
            validator.add("inconsistent_booking_revision", f"{checkpoint_path}.booking_revision", "must be a non-negative revision no greater than Booking state")
        elif status == "PENDING" and checkpoint.get("booking_revision") != booking_revision:
            validator.add(
                "inconsistent_booking_revision",
                f"{checkpoint_path}.booking_revision",
                "pending checkpoint must pin the current Booking revision",
            )

    airlines = world.get("airlines", {})
    flights = world.get("dated_flights", {})
    if type(airlines) is not dict:
        airlines = {}
    if type(flights) is not dict:
        flights = {}
    for airline_id, airline in airlines.items():
        if type(airline) is not dict:
            continue
        value = airline.get("finance_revision")
        if not _nonnegative_integer(value):
            validator.add("invalid_finance_revision", f"$.world_state.airlines.{airline_id}.finance_revision", "must be a non-negative integer", "airline", airline_id)
    for flight_id, flight in flights.items():
        if type(flight) is not dict:
            continue
        value = flight.get("inventory_revision")
        if not _nonnegative_integer(value):
            validator.add("invalid_inventory", f"$.world_state.dated_flights.{flight_id}.inventory_revision", "must be a non-negative integer", "dated_flight", flight_id)
        for forbidden in ("remaining_capacity", "booked_capacity"):
            if forbidden in flight:
                validator.add("invalid_inventory", f"$.world_state.dated_flights.{flight_id}.{forbidden}", "capacity consumption is runtime-derived and must not persist", "dated_flight", flight_id)

    itineraries = world.get("itineraries", {})
    if type(itineraries) is not dict:
        itineraries = {}
    for itinerary_id, record in itineraries.items():
        if type(record) is not dict:
            continue
        contract = record.get("contract")
        if contract == SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT:
            _validate_legacy_itinerary(validator, record, itinerary_id, flights, airlines)
        elif contract == DIRECT_ECONOMY_ITINERARY_CONTRACT:
            _validate_direct_itinerary(validator, record, itinerary_id, world)
        else:
            validator.add("invalid_itinerary", f"$.world_state.itineraries.{itinerary_id}.contract", "unsupported itinerary contract")

    itinerary_booking = {}
    booked_by_flight = {}
    max_production_revision = 0
    bookings = world.get("bookings", {})
    if type(bookings) is not dict:
        bookings = {}
    for booking_id, record in bookings.items():
        if type(record) is not dict:
            continue
        booking_path = f"$.world_state.bookings.{booking_id}"
        contract = record.get("contract")
        legacy = contract == SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT
        if legacy:
            if not _exact(validator, record, {"booking_id", "contract", "payload"}, booking_path, "invalid_booking", "compatibility wrapper fields are invalid"):
                continue
            booking = record.get("payload")
            if type(booking) is not dict or booking.get("booking_id") != booking_id:
                validator.add("invalid_booking", f"{booking_path}.payload", "must preserve a schema-2 Booking payload with matching identity")
                continue
            if set(booking) != {
                "booking_id",
                "airline_id",
                "itinerary_id",
                "passenger_count",
                "booked_at_utc",
                "total_fare_minor",
                "currency",
                "status",
            }:
                validator.add(
                    "invalid_booking",
                    f"{booking_path}.payload",
                    "must preserve exactly the canonical schema-2 Booking fields",
                )
                continue
        elif contract == AGGREGATE_BOOKING_CONTRACT:
            fields = {
                "booking_id", "contract", "booking_checkpoint_id", "cohort_key",
                "desired_travel_date", "airline_id", "itinerary_id", "passenger_count",
                "booked_at_utc", "total_fare_minor", "currency",
                "inventory_revision_at_commit", "finance_transaction_id",
                "booking_revision", "status",
            }
            if not _exact(validator, record, fields, booking_path, "invalid_booking", "must contain exactly the aggregate Booking V1 fields"):
                continue
            booking = record
            checkpoint_reference = booking.get("booking_checkpoint_id")
            if not isinstance(checkpoint_reference, str) or checkpoint_reference not in checkpoints:
                validator.add("invalid_booking", f"{booking_path}.booking_checkpoint_id", "must reference a Booking checkpoint")
            cohort_reference = booking.get("cohort_key")
            if not isinstance(cohort_reference, str) or cohort_reference not in processed_cohorts:
                validator.add("invalid_booking", f"{booking_path}.cohort_key", "must reference a processed demand cohort")
            if not _date(booking.get("desired_travel_date")):
                validator.add("invalid_booking", f"{booking_path}.desired_travel_date", "must be canonical YYYY-MM-DD")
            if not _nonnegative_integer(booking.get("inventory_revision_at_commit")):
                validator.add("invalid_booking", f"{booking_path}.inventory_revision_at_commit", "must be a non-negative integer")
            transaction_id = booking.get("finance_transaction_id")
            if not isinstance(transaction_id, str) or transaction_id not in transactions:
                validator.add("invalid_booking", f"{booking_path}.finance_transaction_id", "must reference a financial transaction")
            revision = booking.get("booking_revision")
            if not _positive_integer(revision) or (_nonnegative_integer(booking_revision) and revision > booking_revision):
                validator.add("inconsistent_booking_revision", f"{booking_path}.booking_revision", "must be a positive revision no greater than Booking state")
            elif revision > max_production_revision:
                max_production_revision = revision
        else:
            validator.add("invalid_booking", f"{booking_path}.contract", "unsupported Booking contract")
            continue

        airline_id = booking.get("airline_id")
        itinerary_id = booking.get("itinerary_id")
        count = booking.get("passenger_count")
        if not isinstance(airline_id, str) or airline_id not in airlines:
            validator.add("invalid_booking", f"{booking_path}.airline_id", "must reference an airline")
        itinerary_record = itineraries.get(itinerary_id) if isinstance(itinerary_id, str) else None
        if type(itinerary_record) is not dict:
            validator.add("invalid_booking", f"{booking_path}.itinerary_id", "must reference an itinerary")
            itinerary = None
        else:
            itinerary = itinerary_record.get("payload") if itinerary_record.get("contract") == SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT else itinerary_record
            if type(itinerary) is not dict:
                validator.add(
                    "invalid_booking",
                    f"{booking_path}.itinerary_id",
                    "referenced itinerary has no valid payload",
                )
                itinerary = None
            elif itinerary.get("airline_id") != airline_id:
                validator.add("invalid_booking", f"{booking_path}.itinerary_id", "itinerary belongs to another airline")
        if not _positive_integer(count):
            validator.add("invalid_booking", f"{booking_path}.passenger_count", "must be a positive integer")
        if not is_canonical_utc(booking.get("booked_at_utc")):
            validator.add("invalid_booking", f"{booking_path}.booked_at_utc", "must be a canonical UTC timestamp")
        if not is_minor_amount(booking.get("total_fare_minor")) or booking.get("total_fare_minor", -1) < 0:
            validator.add("invalid_booking", f"{booking_path}.total_fare_minor", "must be a non-negative integer minor-unit amount")
        if not _currency(booking.get("currency")):
            validator.add("invalid_booking", f"{booking_path}.currency", "currency must be canonical")
        if legacy:
            if not isinstance(booking.get("status"), str) or not booking["status"].strip():
                validator.add("invalid_booking", f"{booking_path}.status", "schema-2 compatibility status must remain non-empty text")
        elif booking.get("status") != "CONFIRMED":
            validator.add("invalid_booking", f"{booking_path}.status", "aggregate Booking V1 status must be CONFIRMED")
        if not legacy and itinerary is not None:
            snapshot = itinerary.get("fare_offer_snapshot", {})
            if booking.get("currency") != snapshot.get("currency") or (
                _positive_integer(count)
                and is_minor_amount(snapshot.get("amount_minor"))
                and booking.get("total_fare_minor") != count * snapshot["amount_minor"]
            ):
                validator.add("invalid_booking", f"{booking_path}.total_fare_minor", "must equal passenger count times the itinerary fare snapshot")
            if isinstance(itinerary_id, str):
                previous = itinerary_booking.get(itinerary_id)
                if previous is not None:
                    validator.add("invalid_booking", f"{booking_path}.itinerary_id", f"direct V1 itinerary is already owned by {previous}")
                else:
                    itinerary_booking[itinerary_id] = booking_id
            transaction_id = booking.get("finance_transaction_id")
            transaction = (
                transactions.get(transaction_id)
                if isinstance(transaction_id, str)
                else None
            )
            if type(transaction) is dict and transaction.get("airline_id") != airline_id:
                validator.add(
                    "invalid_booking",
                    f"{booking_path}.finance_transaction_id",
                    "financial transaction belongs to another airline",
                )
            committed_inventory_revision = booking.get(
                "inventory_revision_at_commit"
            )
            itinerary_flight_ids = itinerary.get("dated_flight_ids", [])
            if (
                _nonnegative_integer(committed_inventory_revision)
                and type(itinerary_flight_ids) is list
            ):
                for flight_id in itinerary_flight_ids:
                    flight = flights.get(flight_id) if type(flight_id) is str else None
                    current_inventory_revision = (
                        flight.get("inventory_revision")
                        if type(flight) is dict
                        else None
                    )
                    if (
                        _nonnegative_integer(current_inventory_revision)
                        and committed_inventory_revision
                        > current_inventory_revision
                    ):
                        validator.add(
                            "invalid_booking",
                            f"{booking_path}.inventory_revision_at_commit",
                            "cannot exceed current dated-flight inventory revision",
                        )
        if not legacy and booking.get("status") == "CONFIRMED" and _positive_integer(count) and itinerary is not None:
            itinerary_flight_ids = itinerary.get("dated_flight_ids", [])
            if type(itinerary_flight_ids) is not list:
                itinerary_flight_ids = []
            for flight_id in itinerary_flight_ids:
                if type(flight_id) is str:
                    booked_by_flight[flight_id] = booked_by_flight.get(flight_id, 0) + count

    if max_production_revision > booking_revision:
        validator.add("inconsistent_booking_revision", f"{path}.booking_revision", "must cover all production Booking revisions")
    for itinerary_id, record in itineraries.items():
        if (
            type(record) is dict
            and record.get("contract") == DIRECT_ECONOMY_ITINERARY_CONTRACT
            and itinerary_id not in itinerary_booking
        ):
            validator.add(
                "invalid_itinerary",
                f"$.world_state.itineraries.{itinerary_id}",
                "direct V1 itinerary must belong to exactly one aggregate Booking",
            )
    result_booking_ids = set()
    result_booking_owner = {}
    for checkpoint_id, checkpoint in checkpoints.items():
        if type(checkpoint) is not dict or type(checkpoint.get("market_results")) is not dict:
            continue
        checkpoint_transactions = checkpoint.get("financial_transaction_ids", [])
        if (
            type(checkpoint_transactions) is not list
            or any(type(value) is not str for value in checkpoint_transactions)
        ):
            checkpoint_transactions = []
        referenced_transactions = set()
        for market_id, result in checkpoint["market_results"].items():
            if type(result) is not dict or type(result.get("booking_ids")) is not list:
                continue
            passenger_total = 0
            for booking_id in result["booking_ids"]:
                record = (
                    bookings.get(booking_id)
                    if isinstance(booking_id, str)
                    else None
                )
                if type(record) is not dict or record.get("contract") != AGGREGATE_BOOKING_CONTRACT:
                    validator.add("result_validation_failed", f"{path}.booking_checkpoints.{checkpoint_id}.market_results.{market_id}.booking_ids", "must reference production V1 Bookings")
                    continue
                previous_owner = result_booking_owner.get(booking_id)
                if previous_owner is not None:
                    validator.add(
                        "result_validation_failed",
                        f"{path}.booking_checkpoints.{checkpoint_id}.market_results.{market_id}.booking_ids",
                        f"Booking is already listed by {previous_owner}",
                    )
                else:
                    result_booking_owner[booking_id] = (
                        f"{checkpoint_id}/{market_id}"
                    )
                result_booking_ids.add(booking_id)
                if record.get("booking_checkpoint_id") != checkpoint_id or record.get("cohort_key") != result.get("cohort_key"):
                    validator.add("result_validation_failed", f"$.world_state.bookings.{booking_id}", "Booking checkpoint and cohort must match its market result")
                itinerary_id = record.get("itinerary_id")
                itinerary = (
                    itineraries.get(itinerary_id, {})
                    if isinstance(itinerary_id, str)
                    else {}
                )
                if type(itinerary) is not dict or itinerary.get("market_id") != market_id:
                    validator.add("result_validation_failed", f"$.world_state.bookings.{booking_id}.itinerary_id", "Booking itinerary market must match its result")
                if record.get("finance_transaction_id") not in checkpoint_transactions:
                    validator.add("result_validation_failed", f"$.world_state.bookings.{booking_id}.finance_transaction_id", "Booking transaction must be listed by its checkpoint")
                elif isinstance(record.get("finance_transaction_id"), str):
                    referenced_transactions.add(record["finance_transaction_id"])
                if record.get("booking_revision") != checkpoint.get(
                    "booking_revision"
                ):
                    validator.add(
                        "inconsistent_booking_revision",
                        f"$.world_state.bookings.{booking_id}.booking_revision",
                        "must equal the owning checkpoint Booking revision",
                    )
                if _positive_integer(record.get("passenger_count")):
                    passenger_total += record["passenger_count"]
            if result.get("booked_passenger_count") != passenger_total:
                validator.add("result_validation_failed", f"{path}.booking_checkpoints.{checkpoint_id}.market_results.{market_id}.booked_passenger_count", "must equal passengers in referenced Bookings")
        if set(checkpoint_transactions) != referenced_transactions:
            validator.add(
                "invalid_booking_checkpoint",
                f"{path}.booking_checkpoints.{checkpoint_id}.financial_transaction_ids",
                "must list exactly the transactions referenced by its result Bookings",
            )
    for booking_id, record in bookings.items():
        if type(record) is dict and record.get("contract") == AGGREGATE_BOOKING_CONTRACT and booking_id not in result_booking_ids:
            validator.add("result_validation_failed", f"$.world_state.bookings.{booking_id}", "production V1 Booking must appear in exactly one checkpoint market result")
    for flight_id, count in booked_by_flight.items():
        flight = flights.get(flight_id)
        if type(flight) is dict and type(flight.get("capacity")) is int and count > flight["capacity"]:
            validator.add("invalid_inventory", f"$.world_state.dated_flights.{flight_id}", "confirmed bookings exceed dated-flight capacity", "dated_flight", flight_id)
