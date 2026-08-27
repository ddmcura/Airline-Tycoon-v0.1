"""Non-interactive construction and schema-only entity creation."""

import hashlib
import json
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN

from .ids import allocate_id, new_allocator_state
from .demand_fingerprint import calculate_demand_input_fingerprint
from .money import major_to_minor
from .schema import (
    DEFAULT_GAME_VERSION,
    DEFAULT_CLOCK_RATIOS,
    DEFAULT_DEMAND_CONFIGURATION,
    DEFAULT_MINIMUM_TURNAROUND_SECONDS,
    DEFAULT_PUBLICATION_HORIZON_DAYS,
    DEFAULT_REFERENCE_DATA_VERSION,
    DEMAND_DESTINATION_TYPES,
    DEMAND_ROUNDING_POLICY,
    MODEL4_DEMAND_MODEL_VERSION,
    SAVE_SCHEMA_VERSION,
)
from .timestamps import normalize_utc_timestamp


def _required_text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _currency_code(value):
    value = _required_text(value, "currency").upper()
    if len(value) != 3 or not value.isascii() or not value.isalpha():
        raise ValueError("currency must be a three-letter code")
    return value


def _optional_local_date(value, field_name):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be null or canonical YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be null or canonical YYYY-MM-DD"
        ) from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} must be null or canonical YYYY-MM-DD")
    return value


def _microdegrees(value, field_name, minimum, maximum):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite coordinate")
    try:
        coordinate = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite coordinate") from exc
    if not coordinate.is_finite() or coordinate < minimum or coordinate > maximum:
        raise ValueError(f"{field_name} is outside the supported range")
    return int((coordinate * 1_000_000).to_integral_value(rounding=ROUND_HALF_EVEN))


def _destination_type(airport_reference):
    explicit = airport_reference.get("demand_destination_type")
    if explicit is not None:
        return str(explicit).strip().upper() or None
    importance = str(airport_reference.get("regional_importance") or "").lower()
    size = str(airport_reference.get("airport_size") or "").lower()
    if importance == "global" or size == "mega":
        return "MEGA_GLOBAL_CITY"
    if importance == "major":
        return "CAPITAL_MAJOR_CITY"
    if importance == "regional" and size == "large":
        return "MAJOR_REGIONAL_CITY"
    if importance == "regional" and size == "medium":
        return "NORMAL_CITY"
    if importance == "regional" and size == "small":
        return "SMALL_REGIONAL_CITY"
    if importance == "minor":
        return "MINOR_CITY"
    return None


def _add_account(envelope, airline_id, code, category, currency, balance_minor):
    account_id = allocate_id(envelope, "account")
    envelope["world_state"]["financial_accounts"][account_id] = {
        "account_id": account_id,
        "airline_id": airline_id,
        "code": code,
        "category": category,
        "currency": currency,
        "balance_minor": balance_minor,
    }
    return account_id


def _add_airport_reference_in_place(envelope, airport_reference):
    if isinstance(airport_reference, str):
        airport_reference = {"reference_code": airport_reference}
    if not isinstance(airport_reference, dict):
        raise ValueError("starting_airport must be a reference code or dictionary")
    reference_code = _required_text(
        airport_reference.get("reference_code")
        or airport_reference.get("iata")
        or airport_reference.get("icao"),
        "starting_airport.reference_code",
    ).upper()
    if any(
        airport.get("reference_code") == reference_code
        for airport in envelope["world_state"]["airports"].values()
    ):
        raise ValueError("airport reference_code must be unique")

    population = airport_reference.get("population")
    if population is not None:
        if isinstance(population, bool) or not isinstance(population, int):
            raise ValueError("starting_airport.population must be an integer or null")
        if population < 0:
            raise ValueError("starting_airport.population must be non-negative")
    coordinates = airport_reference.get("coordinates")
    if coordinates is not None and not isinstance(coordinates, dict):
        raise ValueError("starting_airport.coordinates must be a dictionary or null")
    coordinates = coordinates or {}
    latitude = _microdegrees(
        airport_reference.get("latitude", coordinates.get("lat")),
        "starting_airport.latitude",
        Decimal("-90"),
        Decimal("90"),
    )
    longitude = _microdegrees(
        airport_reference.get("longitude", coordinates.get("lon")),
        "starting_airport.longitude",
        Decimal("-180"),
        Decimal("180"),
    )
    country_reference = airport_reference.get("country_reference")
    if country_reference is None:
        country_reference = airport_reference.get("country_code")
    if country_reference is None and airport_reference.get("country"):
        country_reference = str(airport_reference["country"]).strip().upper()
    if country_reference is not None:
        country_reference = _required_text(
            country_reference, "starting_airport.country_reference"
        ).upper()
    schema_version = envelope.get("metadata", {}).get("save_schema_version")
    country_id = airport_reference.get("country_id")
    if schema_version == 2:
        countries = envelope.get("world_state", {}).get("countries", {})
        if not isinstance(country_id, str) or country_id not in countries:
            raise ValueError(
                "schema-2 airport additions require an existing immutable country_id"
            )
        if (
            country_reference is not None
            and countries[country_id].get("external_reference_code")
            != country_reference
        ):
            raise ValueError(
                "country_id and country_reference must identify the same country"
            )
    destination_type = _destination_type(airport_reference)
    if destination_type is not None and destination_type not in DEMAND_DESTINATION_TYPES:
        raise ValueError("starting_airport.demand_destination_type is unsupported")
    active_from = _optional_local_date(
        airport_reference.get("active_from_date", airport_reference.get("date_opened")),
        "starting_airport.active_from_date",
    )
    active_until = _optional_local_date(
        airport_reference.get("active_until_date", airport_reference.get("date_closed")),
        "starting_airport.active_until_date",
    )
    if active_from and active_until and active_until <= active_from:
        raise ValueError("airport active_until_date must follow active_from_date")
    complete_demand_inputs = (
        isinstance(population, int)
        and population > 0
        and latitude is not None
        and longitude is not None
        and country_reference is not None
        and destination_type is not None
    )
    requested_eligibility = airport_reference.get("passenger_demand_eligible")
    if requested_eligibility is None:
        demand_eligible = complete_demand_inputs
    elif type(requested_eligibility) is not bool:
        raise ValueError("passenger_demand_eligible must be a boolean")
    else:
        demand_eligible = requested_eligibility
    if demand_eligible and not complete_demand_inputs:
        raise ValueError(
            "passenger-demand-eligible airports require positive population, "
            "coordinates, country_reference, and demand_destination_type"
        )
    demand_allocation_member = airport_reference.get("demand_allocation_member")
    if schema_version == 2 and type(demand_allocation_member) is not bool:
        raise ValueError(
            "schema-2 airport additions require an explicit boolean "
            "demand_allocation_member"
        )

    demand_configuration = envelope.get("simulation", {}).get(
        "configuration", {}
    ).get("demand", {})
    demand_state = envelope.get("world_state", {}).get("demand_state", {})
    demand_revision = demand_configuration.get("revision", 1)
    should_increment_demand_revision = demand_eligible and any(
        airport.get("passenger_demand_eligible")
        for airport in envelope["world_state"]["airports"].values()
    )
    if should_increment_demand_revision:
        demand_revision += 1
    airport_id = allocate_id(envelope, "airport")
    if should_increment_demand_revision:
        demand_configuration["revision"] = demand_revision
        if isinstance(demand_state, dict):
            demand_state["demand_model_revision"] = demand_revision
    iata = airport_reference.get("iata")
    icao = airport_reference.get("icao")
    record = {
        "airport_id": airport_id,
        "reference_code": reference_code,
        "display_name": str(airport_reference.get("display_name") or airport_reference.get("name") or reference_code),
        "iata_code": str(iata).upper() if iata else (reference_code if len(reference_code) == 3 else None),
        "icao_code": str(icao).upper() if icao else (reference_code if len(reference_code) == 4 else None),
        "timezone": str(airport_reference.get("timezone") or "UTC"),
        "passenger_demand_eligible": demand_eligible,
        "population": population,
        "latitude_microdegrees": latitude,
        "longitude_microdegrees": longitude,
        "country_reference": country_reference,
        "demand_destination_type": destination_type,
        "active_from_date": active_from,
        "active_until_date": active_until,
        "demand_input_revision": demand_revision,
    }
    if schema_version == 2:
        record["country_id"] = country_id
        record["demand_allocation_member"] = demand_allocation_member
    envelope["world_state"]["airports"][airport_id] = record
    demand_state["input_fingerprint"] = calculate_demand_input_fingerprint(envelope)
    return airport_id


def add_airport_reference(envelope, airport_reference):
    """Atomically add one immutable airport reference record."""
    if (
        envelope.get("metadata", {}).get("save_schema_version") == 2
        and envelope.get("simulation", {})
        .get("configuration", {})
        .get("demand", {})
        .get("model_version")
        == MODEL4_DEMAND_MODEL_VERSION
    ):
        raise ValueError(
            "active Model 4 airport additions require atomic country-pack materialization"
        )
    candidate = deepcopy(envelope)
    airport_id = _add_airport_reference_in_place(candidate, airport_reference)

    candidate_demand = candidate["simulation"]["configuration"]["demand"]
    candidate_state = candidate["world_state"]["demand_state"]
    envelope["world_state"]["airports"][airport_id] = deepcopy(
        candidate["world_state"]["airports"][airport_id]
    )
    envelope["deterministic_state"]["id_allocator"]["next_by_type"][
        "airport"
    ] = candidate["deterministic_state"]["id_allocator"]["next_by_type"][
        "airport"
    ]
    envelope["simulation"]["configuration"]["demand"][
        "revision"
    ] = candidate_demand["revision"]
    envelope["world_state"]["demand_state"][
        "demand_model_revision"
    ] = candidate_state["demand_model_revision"]
    envelope["world_state"]["demand_state"][
        "input_fingerprint"
    ] = candidate_state["input_fingerprint"]
    return airport_id


def add_airline(
    envelope,
    display_name,
    *,
    control_type="AI",
    owner_type="INDEPENDENT",
    owner_id=None,
    base_airport_id=None,
    base_kind="OPERATING_BASE",
    starting_money=0,
    starting_debt=0,
    currency="USD",
):
    """Add an airline plus the minimal explicit Stage 1 account foundation."""
    display_name = _required_text(display_name, "display_name")
    control_type = str(control_type).upper()
    owner_type = str(owner_type).upper()
    if control_type not in {"PLAYER", "AI"}:
        raise ValueError("control_type must be PLAYER or AI")
    if owner_type not in {"PLAYER", "INDEPENDENT", "AIRLINE"}:
        raise ValueError("owner_type must be PLAYER, INDEPENDENT, or AIRLINE")
    if owner_type == "PLAYER":
        owner_id = "player"
    elif owner_type == "INDEPENDENT":
        owner_id = None
    elif not isinstance(owner_id, str) or owner_id not in envelope["world_state"]["airlines"]:
        raise ValueError("owner_id must reference an existing airline")
    if base_airport_id is not None and (
        not isinstance(base_airport_id, str)
        or base_airport_id not in envelope["world_state"]["airports"]
    ):
        raise ValueError("base_airport_id must reference an existing airport")
    base_kind = str(base_kind).upper()
    if base_kind not in {"OPERATING_BASE", "HUB"}:
        raise ValueError("base_kind must be OPERATING_BASE or HUB")
    starting_money_minor = major_to_minor(starting_money, "starting_money")
    starting_debt_minor = major_to_minor(starting_debt, "starting_debt")
    if starting_money_minor < 0 or starting_debt_minor < 0:
        raise ValueError("starting money and debt must be non-negative")
    currency = _currency_code(currency)

    airline_id = allocate_id(envelope, "airline")
    base_ids = [base_airport_id] if base_airport_id else []
    hub_ids = list(base_ids) if base_kind == "HUB" else []
    airline = {
        "airline_id": airline_id,
        "display_name": display_name,
        "base_currency": currency,
        "control_type": control_type,
        "owner_type": owner_type,
        "owner_id": owner_id,
        "base_airport_ids": base_ids,
        "hub_airport_ids": hub_ids,
        "financial_account_ids": [],
    }
    envelope["world_state"]["airlines"][airline_id] = airline

    accounts = (
        ("cash", "CASH", starting_money_minor),
        ("aircraft_assets", "ASSET", 0),
        ("debt", "LIABILITY", starting_debt_minor),
        ("unflown_tickets", "LIABILITY", 0),
        ("passenger_revenue", "REVENUE", 0),
        ("operating_expenses", "EXPENSE", 0),
    )
    airline["financial_account_ids"] = [
        _add_account(envelope, airline_id, code, category, currency, balance)
        for code, category, balance in accounts
    ]
    return airline_id


def add_aircraft(
    envelope,
    airline_id,
    display_registration,
    model_reference,
    *,
    home_airport_id,
    current_airport_id=None,
    status="PARKED",
):
    """Add schema state only; no purchase, delivery, or operations behavior."""
    if not isinstance(airline_id, str) or airline_id not in envelope["world_state"]["airlines"]:
        raise ValueError("airline_id must reference an existing airline")
    airports = envelope["world_state"]["airports"]
    if not isinstance(home_airport_id, str) or home_airport_id not in airports:
        raise ValueError("home_airport_id must reference an existing airport")
    current_airport_id = current_airport_id or home_airport_id
    if not isinstance(current_airport_id, str) or current_airport_id not in airports:
        raise ValueError("current_airport_id must reference an existing airport")
    aircraft_id = allocate_id(envelope, "aircraft")
    envelope["world_state"]["aircraft"][aircraft_id] = {
        "aircraft_id": aircraft_id,
        "airline_id": airline_id,
        "display_registration": _required_text(display_registration, "display_registration"),
        "model_reference": _required_text(model_reference, "model_reference"),
        "home_airport_id": home_airport_id,
        "current_airport_id": current_airport_id,
        "status": _required_text(status, "status").upper(),
    }
    return aircraft_id


def add_directional_market(envelope, origin_airport_id, destination_airport_id):
    airports = envelope["world_state"]["airports"]
    if (
        not isinstance(origin_airport_id, str)
        or origin_airport_id not in airports
        or not isinstance(destination_airport_id, str)
        or destination_airport_id not in airports
    ):
        raise ValueError("market endpoints must reference existing airports")
    if origin_airport_id == destination_airport_id:
        raise ValueError("directional market endpoints must differ")
    if any(
        market.get("origin_airport_id") == origin_airport_id
        and market.get("destination_airport_id") == destination_airport_id
        for market in envelope["world_state"]["directional_markets"].values()
    ):
        raise ValueError("directional market already exists")
    market_id = allocate_id(envelope, "market")
    envelope["world_state"]["directional_markets"][market_id] = {
        "market_id": market_id,
        "origin_airport_id": origin_airport_id,
        "destination_airport_id": destination_airport_id,
    }
    return market_id


def add_connection(envelope, airline_id, market_id, status="PLANNED"):
    world = envelope["world_state"]
    if (
        not isinstance(airline_id, str)
        or airline_id not in world["airlines"]
        or not isinstance(market_id, str)
        or market_id not in world["directional_markets"]
    ):
        raise ValueError("connection references must exist")
    if any(
        connection.get("airline_id") == airline_id
        and connection.get("market_id") == market_id
        for connection in world["connections"].values()
    ):
        raise ValueError("airline connection to market already exists")
    connection_id = allocate_id(envelope, "connection")
    world["connections"][connection_id] = {
        "connection_id": connection_id,
        "airline_id": airline_id,
        "market_id": market_id,
        "status": _required_text(status, "status").upper(),
    }
    return connection_id


def _empty_world_state():
    return {
        "player": {},
        "airports": {},
        "airlines": {},
        "aircraft": {},
        "directional_markets": {},
        "connections": {},
        "schedule_definitions": {},
        "dated_flights": {},
        "demand_state": {
            "demand_model_revision": 1,
            "universe_date": None,
            "input_fingerprint": "",
            "rounding_policy": DEMAND_ROUNDING_POLICY,
            "processed_cohorts": {},
        },
        "bookings": {},
        "itineraries": {},
        "active_aircraft_operations": {},
        "pending_events": {},
        "event_history": {},
        "financial_accounts": {},
        "transactions": {},
        "history": {"operations": [], "financial": [], "world_events": []},
    }


def create_new_world(
    *,
    ceo_display_name,
    airline_display_name,
    starting_airport,
    difficulty,
    simulation_time_utc,
    simulation_seed,
    starting_money,
    starting_debt=0,
    base_kind="HUB",
    currency="USD",
    game_version=DEFAULT_GAME_VERSION,
    reference_data_version=DEFAULT_REFERENCE_DATA_VERSION,
):
    """Construct a deterministic valid world without importing UI/legacy code."""
    ceo_display_name = _required_text(ceo_display_name, "ceo_display_name")
    airline_display_name = _required_text(airline_display_name, "airline_display_name")
    difficulty = _required_text(difficulty, "difficulty")
    simulation_time = normalize_utc_timestamp(simulation_time_utc, "simulation_time_utc")
    if isinstance(simulation_seed, bool) or not isinstance(simulation_seed, int) or simulation_seed < 0:
        raise ValueError("simulation_seed must be a non-negative integer")
    game_version = _required_text(game_version, "game_version")
    reference_data_version = _required_text(reference_data_version, "reference_data_version")

    money_minor = major_to_minor(starting_money, "starting_money")
    debt_minor = major_to_minor(starting_debt, "starting_debt")
    if money_minor < 0 or debt_minor < 0:
        raise ValueError("starting money and debt must be non-negative")
    if isinstance(starting_airport, dict):
        airport_lineage_input = (
            starting_airport.get("reference_code")
            or starting_airport.get("iata")
            or starting_airport.get("icao")
        )
    else:
        airport_lineage_input = str(starting_airport)
    lineage_material = json.dumps(
        {
            "airport": airport_lineage_input,
            "base_kind": str(base_kind).upper(),
            "currency": str(currency).upper(),
            "debt_minor": debt_minor,
            "difficulty": difficulty,
            "game_version": game_version,
            "money_minor": money_minor,
            "reference_data_version": reference_data_version,
            "seed": simulation_seed,
            "time": simulation_time,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    lineage_id = "lineage-" + hashlib.sha256(lineage_material).hexdigest()[:24]

    envelope = {
        "metadata": {
            "save_schema_version": SAVE_SCHEMA_VERSION,
            "game_version": game_version,
            "reference_data_version": reference_data_version,
            "lineage_id": lineage_id,
            "world_created_at_utc": simulation_time,
        },
        "simulation": {
            "time_utc": simulation_time,
            "clock_state": "PAUSED",
            "event_order_cursor": 0,
            "fast_forward": {"target_time_utc": None},
            "operation_revisions": {},
            "configuration": {
                "difficulty": difficulty,
                "clock_ratios": dict(DEFAULT_CLOCK_RATIOS),
                "scheduling": {
                    "publication_horizon_days": DEFAULT_PUBLICATION_HORIZON_DAYS,
                    "minimum_turnaround_seconds": DEFAULT_MINIMUM_TURNAROUND_SECONDS,
                },
                "demand": deepcopy(DEFAULT_DEMAND_CONFIGURATION),
            },
        },
        "deterministic_state": {
            "world_seed": simulation_seed,
            "streams": {},
            "id_allocator": new_allocator_state(),
        },
        "world_state": _empty_world_state(),
        "ui_state": {
            "current_focus_airline_id": None,
            "selected_screen": None,
            "filters": {},
        },
    }
    envelope["world_state"]["demand_state"]["universe_date"] = simulation_time[:10]
    airport_id = add_airport_reference(envelope, starting_airport)
    airline_id = add_airline(
        envelope,
        airline_display_name,
        control_type="PLAYER",
        owner_type="PLAYER",
        base_airport_id=airport_id,
        base_kind=base_kind,
        starting_money=starting_money,
        starting_debt=starting_debt,
        currency=currency,
    )
    envelope["world_state"]["player"] = {
        "player_id": "player",
        "ceo_display_name": ceo_display_name,
        "primary_airline_id": airline_id,
    }
    envelope["ui_state"]["current_focus_airline_id"] = airline_id
    return envelope
