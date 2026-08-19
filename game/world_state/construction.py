"""Non-interactive construction and schema-only entity creation."""

import hashlib
import json

from .ids import allocate_id, new_allocator_state
from .money import major_to_minor
from .schema import (
    DEFAULT_GAME_VERSION,
    DEFAULT_CLOCK_RATIOS,
    DEFAULT_REFERENCE_DATA_VERSION,
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


def add_airport_reference(envelope, airport_reference):
    """Add one immutable airport reference record and return its internal ID."""
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
    airport_id = allocate_id(envelope, "airport")
    iata = airport_reference.get("iata")
    icao = airport_reference.get("icao")
    envelope["world_state"]["airports"][airport_id] = {
        "airport_id": airport_id,
        "reference_code": reference_code,
        "display_name": str(airport_reference.get("display_name") or airport_reference.get("name") or reference_code),
        "iata_code": str(iata).upper() if iata else (reference_code if len(reference_code) == 3 else None),
        "icao_code": str(icao).upper() if icao else (reference_code if len(reference_code) == 4 else None),
        "timezone": str(airport_reference.get("timezone") or "UTC"),
    }
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
        "demand_state": {"market_demand": {}, "fractional_accumulators": {}},
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
