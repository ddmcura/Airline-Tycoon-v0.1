"""Detached, one-way read projection for selected legacy UI shapes."""

from copy import deepcopy
from datetime import datetime

from .money import minor_to_decimal


def _legacy_key(display_value, entity_id, used):
    candidates = (display_value, f"{display_value} [{entity_id}]", f"[{entity_id}]")
    for value in candidates:
        if value not in used:
            used.add(value)
            return value
    suffix = 2
    while f"[{entity_id}] {suffix}" in used:
        suffix += 1
    value = f"[{entity_id}] {suffix}"
    used.add(value)
    return value


def build_legacy_read_projection(envelope):
    """Build a detached compatibility dictionary; write-back is unsupported."""
    world = envelope["world_state"]
    accounts = world["financial_accounts"]
    airlines = world["airlines"]
    aircraft = world["aircraft"]
    player = world["player"]
    used_airline_keys = set()
    airline_keys = {}
    for airline_id in sorted(airlines):
        record = airlines[airline_id]
        airline_keys[airline_id] = _legacy_key(
            record["display_name"], airline_id, used_airline_keys
        )
    airline_list = {}
    for airline_id in sorted(airlines):
        airline = airlines[airline_id]
        airline_accounts = [accounts[account_id] for account_id in airline["financial_account_ids"]]
        by_code = {account["code"]: account for account in airline_accounts}
        used_registrations = set()
        fleet = {}
        for aircraft_id in sorted(aircraft):
            record = aircraft[aircraft_id]
            if record["airline_id"] != airline_id:
                continue
            registration = _legacy_key(record["display_registration"], aircraft_id, used_registrations)
            fleet[registration] = {
                "aircraft_id": aircraft_id,
                "model": record["model_reference"],
                "hub": world["airports"][record["home_airport_id"]].get("iata_code"),
                "status": record["status"].lower(),
                "delivery_status": "delivered",
                "schedule": {},
            }
        currency = airline["base_currency"]
        airline_list[airline_keys[airline_id]] = {
            "airline_id": airline_id,
            "hubs": {},
            "routes": {},
            "fleet": fleet,
            "finances": {
                "cash_on_hand": float(minor_to_decimal(by_code["cash"]["balance_minor"])),
                "debt": float(minor_to_decimal(by_code["debt"]["balance_minor"])),
                "currency": currency,
            },
            "subsidiaries": {},
            "ai_mode": "player_controlled" if airline["control_type"] == "PLAYER" else "ai_controlled",
        }
    focus_id = envelope["ui_state"].get("current_focus_airline_id")
    primary_id = player["primary_airline_id"]
    projection_currency = airlines[primary_id]["base_currency"]
    timestamp = datetime.fromisoformat(envelope["simulation"]["time_utc"][:-1] + "+00:00")
    projection = {
        "player_info": {
            "ceo_name": player["ceo_display_name"],
            "airline_name": airlines[primary_id]["display_name"],
            "level": 1,
            "current_focus": airline_keys.get(focus_id, ""),
        },
        "airline_list": airline_list,
        "settings": {
            "difficulty": envelope["simulation"]["configuration"]["difficulty"],
            "base_currency": projection_currency,
            "display_currency": projection_currency,
        },
        "game_time": {"current_date": timestamp.strftime("%Y-%m-%d %H:%M")},
    }
    return deepcopy(projection)
