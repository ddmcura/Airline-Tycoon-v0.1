"""Schema-6 deterministic leasing and used-aircraft marketplace authority."""

from __future__ import annotations

from calendar import monthrange
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import json

from game.economy.acquisition import purchase_accounts
from game.economy.aircraft_market import post_aircraft_market_transaction
from game.fleet_management.acquisition import delivery_locations, enter_market_aircraft
from game.simulation.kernel import DEFAULT_EVENT_HANDLERS, schedule_event
from game.world_state.ids import allocate_id
from game.world_state.schema import AIRCRAFT_MARKET_CONFIGURATION
from game.world_state.timestamps import format_utc, parse_canonical_utc
from game.world_state.validation import validate_world
from .reference_catalog import PH_AIRCRAFT_CATALOG_VERSION, load_aircraft_catalog


ROTATION_EVENT = "AIRCRAFT_MARKET_ROTATION"
PAYMENT_EVENT = "AIRCRAFT_CONTRACT_PAYMENT"
EXPIRY_EVENT = "AIRCRAFT_CONTRACT_EXPIRY"
ROTATION_PRIORITY = 10
PAYMENT_PRIORITY = 20
EXPIRY_PRIORITY = 200
def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    return sha256(encoded).hexdigest()


def _draw(seed, *parts, modulo):
    material = "|".join(map(str, ("PH_AIRCRAFT_MARKET_V1", seed, *parts)))
    return int.from_bytes(sha256(material.encode("utf-8")).digest(), "big") % modulo


def _ceil_div(value, divisor):
    return (value + divisor - 1) // divisor


def _add_months(moment, months):
    year = moment.year + (moment.month - 1 + months) // 12
    month = (moment.month - 1 + months) % 12 + 1
    day = min(moment.day, monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def _first_next_month(moment):
    return _add_months(moment.replace(day=1, hour=0, minute=0, second=0), 1)


def _configuration(view):
    return {
        "contract": "PH_MAX_ECONOMY_V1",
        "catalog_version": view["catalog_version"],
        "economy_capacity": view["model"]["max_economy_seats"],
        "performance_contract": "PH_SCALAR_RANGE_V1",
    }


def _catalog_model_ids(catalog):
    return tuple(sorted(model["model_id"] for manufacturer in catalog.manufacturers()
                        for model in catalog.models(manufacturer["manufacturer_id"])))


def _world_fingerprint(envelope):
    return _digest({key: value for key, value in envelope.items() if key != "ui_state"})


def _command(value):
    if type(value) is not str or not value or value.strip() != value or len(value) > 128:
        raise ValueError("invalid command identifier")
    return value


def _accounts(world, airline_id):
    return purchase_accounts(world, airline_id)


def _depreciated_value(new_value, manufactured_date, at_utc, config):
    made = date.fromisoformat(manufactured_date)
    now = parse_canonical_utc(at_utc).date()
    completed_years = now.year - made.year - ((now.month, now.day) < (made.month, made.day))
    age_bps = max(config["residual_value_bps"],
                  10_000 - max(0, completed_years) * config["annual_depreciation_bps"])
    return new_value * age_bps // 10_000


def _current_value(new_value, manufactured_date, at_utc, condition_bps, config):
    depreciated = _depreciated_value(new_value, manufactured_date, at_utc, config)
    condition_multiplier = config["condition_value_floor_bps"] + (
        (10_000 - config["condition_value_floor_bps"]) * condition_bps // 10_000)
    return depreciated * condition_multiplier // 10_000


def _restoration(new_value, condition_bps, config):
    return _ceil_div(new_value * (10_000 - condition_bps) * config["restoration_max_bps"],
                     100_000_000)


def initialize_market(candidate):
    """Create schema-6 marketplace roots and the first rotation."""
    world = candidate["world_state"]
    market_id = allocate_id(candidate, "aircraft_market")
    catalog = load_aircraft_catalog(catalog_version=PH_AIRCRAFT_CATALOG_VERSION)
    model_ids = _catalog_model_ids(catalog)
    lessor_specs = (
        ("Pacific Aircraft Leasing", model_ids[:8]),
        ("Island Regional Leasing", model_ids[6:14]),
        ("Archipelago Fleet Partners", model_ids[12:] + model_ids[:2]),
    )
    counterparties = {}
    for name, models in lessor_specs:
        key = allocate_id(candidate, "market_counterparty")
        counterparties[key] = {"counterparty_id": key, "counterparty_type": "LESSOR",
                               "display_name": name, "active": True,
                               "specialization_model_ids": list(models)}
    for name in ("Luzon Airframe Exchange", "Visayas Aviation Traders",
                 "Mindanao Aircraft Brokerage"):
        key = allocate_id(candidate, "market_counterparty")
        counterparties[key] = {"counterparty_id": key,
                               "counterparty_type": "BACKGROUND_AIRLINE",
                               "display_name": name, "active": True,
                               "specialization_model_ids": []}
    world["aircraft_market_counterparties"] = counterparties
    world["aircraft_lease_offers"] = {}
    world["used_aircraft_listings"] = {}
    world["aircraft_contracts"] = {}
    now = parse_canonical_utc(candidate["simulation"]["time_utc"])
    world["aircraft_market_state"] = {
        "aircraft_market_id": market_id,
        "contract": "PH_AIRCRAFT_MARKET_STATE_V1",
        "current_month": now.strftime("%Y-%m"), "rotation_revision": 0,
        "next_rotation_at_utc": format_utc(_first_next_month(now)),
        "active_lease_offer_ids": [],
    }
    candidate["simulation"]["operation_revisions"][market_id] = 0
    rotate_market(candidate, schedule_next=True)


def rotate_market(candidate, *, schedule_next=True):
    world = candidate["world_state"]
    state = world["aircraft_market_state"]
    now = parse_canonical_utc(candidate["simulation"]["time_utc"])
    month = now.strftime("%Y-%m")
    for offer in world["aircraft_lease_offers"].values():
        if offer["status"] == "ACTIVE":
            offer["status"] = "EXPIRED"
    state["rotation_revision"] += 1
    state["current_month"] = month
    revision = state["rotation_revision"]
    seed = candidate["deterministic_state"]["world_seed"]
    catalog = load_aircraft_catalog(catalog_version=PH_AIRCRAFT_CATALOG_VERSION)
    model_ids = _catalog_model_ids(catalog)
    expires = format_utc(_first_next_month(now))
    active_ids = []
    lessors = sorted((row for row in world["aircraft_market_counterparties"].values()
                      if row["counterparty_type"] == "LESSOR" and row["active"]),
                     key=lambda row: row["counterparty_id"])
    for lessor in lessors:
        models = lessor["specialization_model_ids"]
        for slot in range(AIRCRAFT_MARKET_CONFIGURATION["offers_per_lessor"]):
            model_id = models[_draw(seed, month, lessor["counterparty_id"], slot,
                                    "lease-model", modulo=len(models))]
            view = catalog.model(model_id)
            offer_id = allocate_id(candidate, "lease_offer")
            world["aircraft_lease_offers"][offer_id] = {
                "lease_offer_id": offer_id, "lessor_id": lessor["counterparty_id"],
                "generated_month": month, "expires_at_utc": expires,
                "model_id": model_id, "catalog_version": view["catalog_version"],
                "aircraft_value_minor": view["reference_price"]["amount_minor"],
                "available_quantity": 1 + _draw(seed, month, offer_id, "quantity", modulo=3),
                "configuration": _configuration(view), "status": "ACTIVE",
            }
            active_ids.append(offer_id)
    sellers = sorted((row for row in world["aircraft_market_counterparties"].values()
                      if row["counterparty_type"] == "BACKGROUND_AIRLINE" and row["active"]),
                     key=lambda row: row["counterparty_id"])
    used_registrations = {row["display_registration"] for row in world["aircraft"].values()}
    used_registrations.update(row["display_registration"]
                              for row in world["used_aircraft_listings"].values())
    for slot in range(AIRCRAFT_MARKET_CONFIGURATION["used_listings_per_month"]):
        model_id = model_ids[_draw(seed, month, slot, "used-model", modulo=len(model_ids))]
        seller = sellers[_draw(seed, month, slot, "seller", modulo=len(sellers))]
        view = catalog.model(model_id)
        age_months = 24 + _draw(seed, month, slot, "age", modulo=217)
        annual_hours = 1_200 + _draw(seed, month, slot, "util", modulo=2_401)
        flight_seconds = age_months * annual_hours * 3600 // 12
        mean_leg_minutes = 55 + _draw(seed, month, slot, "leg", modulo=246)
        cycles = max(1, flight_seconds // (mean_leg_minutes * 60))
        utilization_wear = min(3_500, flight_seconds // (18_000 * 3600))
        cycle_wear = min(2_500, cycles // 8)
        condition = max(4_000, 10_000 - utilization_wear - cycle_wear)
        made = _add_months(now, -age_months).date().isoformat()
        new_value = view["reference_price"]["amount_minor"]
        asking = _current_value(new_value, made, candidate["simulation"]["time_utc"],
                                 condition, AIRCRAFT_MARKET_CONFIGURATION)
        listing_id = allocate_id(candidate, "used_listing")
        airframe_id = allocate_id(candidate, "airframe")
        reg_draw = _draw(seed, month, listing_id, "registration", modulo=10**12)
        for attempt in range(len(used_registrations) + 1):
            registration = f"RP-U{(reg_draw + attempt) % 10**12:012d}"
            if registration not in used_registrations:
                used_registrations.add(registration)
                break
        else:
            raise ValueError("used-aircraft registration namespace exhausted")
        world["used_aircraft_listings"][listing_id] = {
            "used_listing_id": listing_id, "airframe_id": airframe_id,
            "seller_id": seller["counterparty_id"], "seller_source": "BACKGROUND_AIRLINE",
            "generated_month": month, "model_id": model_id,
            "catalog_version": view["catalog_version"], "configuration": _configuration(view),
            "display_registration": registration,
            "manufactured_date": made,
            "lifetime_flight_seconds": flight_seconds, "lifetime_cycles": cycles,
            "service_condition_bps": condition, "asking_price_minor": asking,
            "new_value_minor": new_value, "status": "ACTIVE", "sold_aircraft_id": None,
        }
    state["active_lease_offer_ids"] = sorted(active_ids)
    state["next_rotation_at_utc"] = expires
    if schedule_next:
        schedule_event(candidate, event_type=ROTATION_EVENT, due_at_utc=expires,
                       owner_type="aircraft_market", owner_id=state["aircraft_market_id"],
                       operation_revision=0, priority=ROTATION_PRIORITY,
                       payload={"contract": "PH_AIRCRAFT_MARKET_ROTATION_V1",
                                "rotation_revision": revision + 1})


@dataclass(frozen=True)
class LeasePreview:
    airline_id: str
    offer_id: str
    contract_type: str
    term_years: int
    delivery_airport_id: str
    command_id: str
    world_fingerprint: str
    monthly_rent_minor: int
    monthly_financing_minor: int
    principal_base_minor: int
    principal_remainder_installments: int


def preview_lease(envelope, *, airline_id, offer_id, contract_type, term_years,
                  delivery_airport_id, command_id=None):
    if envelope["metadata"]["save_schema_version"] not in (6, 7, 8, 9):
        raise ValueError("leasing requires schema 6")
    world = envelope["world_state"]
    if offer_id not in world["aircraft_lease_offers"]:
        raise ValueError("unknown leasing offer")
    offer = world["aircraft_lease_offers"][offer_id]
    if offer["status"] != "ACTIVE" or offer["available_quantity"] < 1:
        raise ValueError("leasing offer is no longer available")
    if airline_id not in world["airlines"] or delivery_airport_id not in delivery_locations(world, airline_id):
        raise ValueError("delivery must be an existing airline base or hub")
    if contract_type not in {"OPERATING_LEASE", "LEASE_TO_OWN"} or type(term_years) is not int or term_years not in range(1, 6):
        raise ValueError("invalid lease product or term")
    fingerprint = _world_fingerprint(envelope)
    if command_id is None:
        command_id = "lease-" + _digest([fingerprint, airline_id, offer_id, contract_type,
                                          term_years, delivery_airport_id])
    _command(command_id)
    value = offer["aircraft_value_minor"]
    months = term_years * 12
    operating = _ceil_div(value * AIRCRAFT_MARKET_CONFIGURATION[
        "operating_rate_bps_by_term_years"][str(term_years)], 10_000)
    financing = _ceil_div(value * AIRCRAFT_MARKET_CONFIGURATION[
        "lto_financing_bps_by_term_years"][str(term_years)], 10_000)
    return LeasePreview(airline_id, offer_id, contract_type, term_years,
                        delivery_airport_id, command_id, fingerprint,
                        operating if contract_type == "OPERATING_LEASE" else 0,
                        financing if contract_type == "LEASE_TO_OWN" else 0,
                        value // months if contract_type == "LEASE_TO_OWN" else 0,
                        value % months if contract_type == "LEASE_TO_OWN" else 0)


def accept_lease(envelope, preview):
    if type(preview) is not LeasePreview:
        raise ValueError("invalid lease preview")
    request = _digest(asdict(preview))
    for row in envelope["world_state"]["aircraft_contracts"].values():
        if row["command_id"] == preview.command_id:
            if row["request_fingerprint"] != request:
                raise ValueError("lease command identifier already used")
            return row["aircraft_id"]
    expected = preview_lease(envelope, airline_id=preview.airline_id, offer_id=preview.offer_id,
        contract_type=preview.contract_type, term_years=preview.term_years,
        delivery_airport_id=preview.delivery_airport_id, command_id=preview.command_id)
    if expected != preview:
        raise ValueError("stale or altered lease preview; review again")
    candidate = deepcopy(envelope)
    world = candidate["world_state"]
    offer = world["aircraft_lease_offers"][preview.offer_id]
    view = load_aircraft_catalog(catalog_version=offer["catalog_version"]).model(offer["model_id"])
    airframe_id = allocate_id(candidate, "airframe")
    lifecycle = {"airframe_id": airframe_id, "acquisition_type": preview.contract_type,
        "ownership_status": "LESSOR_OWNED", "aircraft_contract_id": None,
        "source_listing_id": None, "fixed_configuration": True,
        "manufactured_date": candidate["simulation"]["time_utc"][:10],
        "lifetime_flight_seconds": 0, "lifetime_cycles": 0,
        "service_condition_bps": 10_000}
    aircraft_id = enter_market_aircraft(candidate, preview.airline_id,
        preview.delivery_airport_id, view, lifecycle=lifecycle)
    contract_id = allocate_id(candidate, "aircraft_contract")
    now = parse_canonical_utc(candidate["simulation"]["time_utc"])
    months = preview.term_years * 12
    expires = format_utc(_add_months(now, months))
    contract = {
        "aircraft_contract_id": contract_id, "contract_type": preview.contract_type,
        "status": "ACTIVE", "airline_id": preview.airline_id, "aircraft_id": aircraft_id,
        "lessor_id": offer["lessor_id"], "offer_id": preview.offer_id,
        "predecessor_contract_id": None, "successor_contract_id": None,
        "delivery_airport_id": preview.delivery_airport_id,
        "started_at_utc": candidate["simulation"]["time_utc"], "expires_at_utc": expires,
        "term_years": preview.term_years, "total_installments": months,
        "paid_installments": 0, "aircraft_value_minor": offer["aircraft_value_minor"],
        "monthly_rent_minor": preview.monthly_rent_minor,
        "monthly_financing_minor": preview.monthly_financing_minor,
        "principal_base_minor": preview.principal_base_minor,
        "principal_remainder_installments": preview.principal_remainder_installments,
        "principal_paid_minor": 0, "financing_paid_minor": 0,
        "next_payment_at_utc": format_utc(_add_months(now, 1)),
        "command_id": preview.command_id, "request_fingerprint": request,
    }
    world["aircraft_contracts"][contract_id] = contract
    world["aircraft"][aircraft_id]["lifecycle"]["aircraft_contract_id"] = contract_id
    candidate["simulation"]["operation_revisions"][contract_id] = 0
    offer["available_quantity"] -= 1
    if offer["available_quantity"] == 0:
        offer["status"] = "EXHAUSTED"
        world["aircraft_market_state"]["active_lease_offer_ids"].remove(preview.offer_id)
    _schedule_contract_events(candidate, contract)
    _commit_valid(envelope, candidate)
    return aircraft_id


def _schedule_contract_events(candidate, contract):
    contract_id = contract["aircraft_contract_id"]
    schedule_event(candidate, event_type=PAYMENT_EVENT,
        due_at_utc=contract["next_payment_at_utc"], owner_type="aircraft_contract",
        owner_id=contract_id, operation_revision=0, priority=PAYMENT_PRIORITY,
        payload={"contract": "PH_AIRCRAFT_CONTRACT_PAYMENT_V1", "installment": 1})
    schedule_event(candidate, event_type=EXPIRY_EVENT,
        due_at_utc=contract["expires_at_utc"], owner_type="aircraft_contract",
        owner_id=contract_id, operation_revision=0, priority=EXPIRY_PRIORITY,
        payload={"contract": "PH_AIRCRAFT_CONTRACT_EXPIRY_V1"})


@dataclass(frozen=True)
class UsedPurchasePreview:
    airline_id: str
    listing_id: str
    delivery_airport_id: str
    command_id: str
    world_fingerprint: str
    asking_price_minor: int
    cash_after_minor: int


@dataclass(frozen=True)
class RenewalPreview:
    aircraft_id: str
    current_contract_id: str
    term_years: int
    starts_at_utc: str
    expires_at_utc: str
    aircraft_value_minor: int
    monthly_rent_minor: int
    world_fingerprint: str


def preview_used_purchase(envelope, *, airline_id, listing_id, delivery_airport_id,
                          command_id=None):
    world = envelope["world_state"]
    listing = world["used_aircraft_listings"].get(listing_id)
    if listing is None or listing["status"] != "ACTIVE":
        raise ValueError("used listing is not available")
    if airline_id not in world["airlines"] or delivery_airport_id not in delivery_locations(world, airline_id):
        raise ValueError("delivery must be an existing airline base or hub")
    fingerprint = _world_fingerprint(envelope)
    if command_id is None:
        command_id = "used-" + _digest([fingerprint, airline_id, listing_id, delivery_airport_id])
    _command(command_id)
    cash = _accounts(world, airline_id)["cash"]["balance_minor"]
    return UsedPurchasePreview(airline_id, listing_id, delivery_airport_id,
        command_id, fingerprint, listing["asking_price_minor"],
        cash - listing["asking_price_minor"])


def purchase_used_aircraft(envelope, preview):
    if type(preview) is not UsedPurchasePreview:
        raise ValueError("invalid used-aircraft preview")
    request = _digest(asdict(preview))
    for tx in envelope["world_state"]["transactions"].values():
        if tx.get("source_type") == "USED_AIRCRAFT_PURCHASE" and tx.get("command_id") == preview.command_id:
            if tx.get("request_fingerprint") != request:
                raise ValueError("purchase command identifier already used")
            return tx["source_id"]
    expected = preview_used_purchase(envelope, airline_id=preview.airline_id,
        listing_id=preview.listing_id, delivery_airport_id=preview.delivery_airport_id,
        command_id=preview.command_id)
    if expected != preview:
        raise ValueError("stale or altered used-aircraft preview; review again")
    if preview.cash_after_minor < 0:
        raise ValueError("insufficient cash")
    candidate = deepcopy(envelope)
    listing = candidate["world_state"]["used_aircraft_listings"][preview.listing_id]
    view = load_aircraft_catalog(catalog_version=listing["catalog_version"]).model(listing["model_id"])
    lifecycle = {"airframe_id": listing["airframe_id"], "acquisition_type": "USED_PURCHASE",
        "ownership_status": "OWNED", "aircraft_contract_id": None,
        "source_listing_id": preview.listing_id, "fixed_configuration": False,
        "manufactured_date": listing["manufactured_date"],
        "lifetime_flight_seconds": listing["lifetime_flight_seconds"],
        "lifetime_cycles": listing["lifetime_cycles"],
        "service_condition_bps": listing["service_condition_bps"]}
    aircraft_id = enter_market_aircraft(candidate, preview.airline_id,
        preview.delivery_airport_id, view, lifecycle=lifecycle,
        display_registration=listing["display_registration"])
    listing["status"] = "SOLD"
    listing["sold_aircraft_id"] = aircraft_id
    post_aircraft_market_transaction(candidate, airline_id=preview.airline_id, description="Used aircraft purchase",
          source_type="USED_AIRCRAFT_PURCHASE", source_id=aircraft_id,
          command_id=preview.command_id, request_fingerprint=request,
          delivery_airport_id=preview.delivery_airport_id,
          entries=(("aircraft_assets", preview.asking_price_minor),
                   ("cash", -preview.asking_price_minor)))
    _commit_valid(envelope, candidate)
    return aircraft_id


def _active_contract(world, aircraft_id):
    rows = [row for row in world["aircraft_contracts"].values()
            if row["aircraft_id"] == aircraft_id and row["status"] == "ACTIVE"]
    if len(rows) != 1:
        raise ValueError("aircraft must have exactly one active contract")
    return rows[0]


def preview_operating_renewal(envelope, *, aircraft_id, term_years):
    if type(term_years) is not int or term_years not in range(1, 6):
        raise ValueError("renewal term must be one through five years")
    world = envelope["world_state"]
    current = _active_contract(world, aircraft_id)
    if current["contract_type"] != "OPERATING_LEASE" or current["successor_contract_id"] is not None:
        raise ValueError("operating lease is not eligible for renewal")
    lifecycle = world["aircraft"][aircraft_id]["lifecycle"]
    value = _current_value(current["aircraft_value_minor"], lifecycle["manufactured_date"],
        current["expires_at_utc"], lifecycle["service_condition_bps"], AIRCRAFT_MARKET_CONFIGURATION)
    rent = _ceil_div(value * AIRCRAFT_MARKET_CONFIGURATION[
        "operating_rate_bps_by_term_years"][str(term_years)], 10_000)
    start = parse_canonical_utc(current["expires_at_utc"])
    return RenewalPreview(aircraft_id, current["aircraft_contract_id"], term_years,
                          current["expires_at_utc"], format_utc(_add_months(start, term_years * 12)),
                          value, rent, _world_fingerprint(envelope))


def renew_operating_lease(envelope, *, aircraft_id, term_years, command_id,
                          expected_world_fingerprint=None):
    _command(command_id)
    request = _digest([aircraft_id, term_years, command_id])
    for row in envelope["world_state"]["aircraft_contracts"].values():
        if row["command_id"] == command_id:
            if row["request_fingerprint"] != request:
                raise ValueError("renewal command identifier already used")
            return row["aircraft_contract_id"]
    quote = preview_operating_renewal(envelope, aircraft_id=aircraft_id,
                                      term_years=term_years)
    if (expected_world_fingerprint is not None
            and expected_world_fingerprint != quote.world_fingerprint):
        raise ValueError("stale renewal preview; review again")
    candidate = deepcopy(envelope)
    world = candidate["world_state"]
    current = _active_contract(world, aircraft_id)
    if current["contract_type"] != "OPERATING_LEASE" or current["successor_contract_id"] is not None:
        raise ValueError("operating lease is not eligible for renewal")
    if type(term_years) is not int or term_years not in range(1, 6):
        raise ValueError("renewal term must be one through five years")
    value = quote.aircraft_value_minor
    rent = quote.monthly_rent_minor
    contract_id = allocate_id(candidate, "aircraft_contract")
    start = parse_canonical_utc(current["expires_at_utc"])
    expires = format_utc(_add_months(start, term_years * 12))
    successor = {**current, "aircraft_contract_id": contract_id, "status": "FUTURE",
        "offer_id": None, "predecessor_contract_id": current["aircraft_contract_id"],
        "successor_contract_id": None, "started_at_utc": current["expires_at_utc"],
        "expires_at_utc": expires, "term_years": term_years,
        "total_installments": term_years * 12, "paid_installments": 0,
        "aircraft_value_minor": value, "monthly_rent_minor": rent,
        "principal_paid_minor": 0, "financing_paid_minor": 0,
        "next_payment_at_utc": format_utc(_add_months(start, 1)),
        "command_id": command_id, "request_fingerprint": request}
    world["aircraft_contracts"][contract_id] = successor
    current["successor_contract_id"] = contract_id
    candidate["simulation"]["operation_revisions"][contract_id] = 0
    _commit_valid(envelope, candidate)
    return contract_id


def terminate_contract(envelope, *, aircraft_id, command_id):
    _command(command_id)
    request = _digest([aircraft_id, command_id])
    for tx in envelope["world_state"]["transactions"].values():
        if tx.get("source_type") in {"AIRCRAFT_LEASE_TERMINATION", "AIRCRAFT_LTO_CANCELLATION"} and tx.get("command_id") == command_id:
            if tx.get("request_fingerprint") != request:
                raise ValueError("termination command identifier already used")
            accounts = envelope["world_state"]["financial_accounts"]
            return next((entry["amount_minor"] for entry in tx["entries"]
                         if accounts[entry["account_id"]]["code"] == "cash"), 0)
    candidate = deepcopy(envelope)
    world = candidate["world_state"]
    contract = _active_contract(world, aircraft_id)
    aircraft = world["aircraft"][aircraft_id]
    if aircraft["status"] != "PARKED" or any(
        flight.get("planned_aircraft_id") == aircraft_id and flight.get("status") in
        {"PLANNED", "OPERATIONALLY_LOCKED"} for flight in world["dated_flights"].values()
    ):
        raise ValueError("contract return requires a parked aircraft with no live commitments")
    remaining = contract["total_installments"] - contract["paid_installments"]
    if contract["contract_type"] == "OPERATING_LEASE":
        settlement = -(remaining * contract["monthly_rent_minor"])
        asset_remove = 0
        source_type = "AIRCRAFT_LEASE_TERMINATION"
    else:
        lifecycle = aircraft["lifecycle"]
        depreciated_value = _depreciated_value(contract["aircraft_value_minor"],
            lifecycle["manufactured_date"], candidate["simulation"]["time_utc"],
            AIRCRAFT_MARKET_CONFIGURATION)
        remaining_principal = contract["aircraft_value_minor"] - contract["principal_paid_minor"]
        equity = max(0, depreciated_value - remaining_principal)
        restoration = _restoration(contract["aircraft_value_minor"],
                                   lifecycle["service_condition_bps"],
                                   AIRCRAFT_MARKET_CONFIGURATION)
        settlement = equity - remaining * contract["monthly_financing_minor"] - restoration
        asset_remove = contract["principal_paid_minor"]
        contract["cancellation_depreciated_value_minor"] = depreciated_value
        contract["cancellation_equity_minor"] = equity
        contract["cancellation_restoration_minor"] = restoration
        source_type = "AIRCRAFT_LTO_CANCELLATION"
    expense = asset_remove - settlement
    entries = []
    if settlement:
        entries.append(("cash", settlement))
    if expense:
        entries.append(("operating_expenses", expense))
    if asset_remove:
        entries.append(("aircraft_assets", -asset_remove))
    if len(entries) < 2:
        # Operating termination always has a negative settlement; this only
        # covers an impossible zero-duration defensive boundary.
        raise ValueError("termination has no financial effect")
    post_aircraft_market_transaction(candidate, airline_id=contract["airline_id"], description="Aircraft contract cancellation",
          source_type=source_type, source_id=contract["aircraft_contract_id"], entries=entries,
          command_id=command_id, request_fingerprint=request)
    contract["status"] = "CANCELLED"
    contract["next_payment_at_utc"] = None
    aircraft["status"] = "RETURNED"
    aircraft["current_airport_id"] = None
    aircraft["lifecycle"]["ownership_status"] = "RETURNED"
    _cancel_contract_events(candidate, contract["aircraft_contract_id"])
    _commit_valid(envelope, candidate)
    return settlement


def _cancel_contract_events(candidate, contract_id):
    candidate["simulation"]["operation_revisions"][contract_id] = 1


def confirmed_contract_horizon(world, aircraft_id):
    active = [row for row in world.get("aircraft_contracts", {}).values()
              if row.get("aircraft_id") == aircraft_id and row.get("status") == "ACTIVE"]
    if not active:
        return None
    row = active[0]
    horizon = row["expires_at_utc"]
    successor_id = row.get("successor_contract_id")
    while successor_id is not None:
        successor = world["aircraft_contracts"][successor_id]
        horizon = successor["expires_at_utc"]
        successor_id = successor.get("successor_contract_id")
    return horizon


def payment_terms(contract):
    """Pure existing installment arithmetic; no rounding or economics change."""
    installment = contract["paid_installments"] + 1
    if contract["contract_type"] == "OPERATING_LEASE":
        principal = financing = 0
        amount = contract["monthly_rent_minor"]
        entries = (("operating_expenses", amount), ("cash", -amount))
        description = f"Operating lease installment {installment}"
        source_type = "AIRCRAFT_LEASE_PAYMENT"
    else:
        principal = contract["principal_base_minor"] + (
            1 if installment <= contract["principal_remainder_installments"] else 0)
        financing = contract["monthly_financing_minor"]
        entries = (("aircraft_assets", principal), ("operating_expenses", financing),
                   ("cash", -(principal + financing)))
        description = f"Lease-to-own installment {installment}"
        source_type = "AIRCRAFT_LTO_PAYMENT"
    next_due = None if installment == contract["total_installments"] else format_utc(
        _add_months(parse_canonical_utc(contract["started_at_utc"]), installment + 1))
    return dict(installment=installment, principal=principal, financing=financing,
        entries=entries, description=description, source_type=source_type, next_due=next_due)


def _payment_handler(context):
    world = context.envelope["world_state"]
    contract = world["aircraft_contracts"][context.event["owner_id"]]
    if contract["status"] not in {"ACTIVE"}:
        return
    installment = contract["paid_installments"] + 1
    if installment > contract["total_installments"]:
        return
    terms = payment_terms(contract)
    post_aircraft_market_transaction(context.envelope, airline_id=contract["airline_id"],
        description=terms["description"], source_type=terms["source_type"],
        source_id=contract["aircraft_contract_id"], entries=terms["entries"])
    contract["principal_paid_minor"] += terms["principal"]
    contract["financing_paid_minor"] += terms["financing"]
    contract["paid_installments"] = installment
    contract["next_payment_at_utc"] = terms["next_due"]
    if terms["next_due"] is not None:
        context.schedule_event(event_type=PAYMENT_EVENT, due_at_utc=terms["next_due"],
            owner_type="aircraft_contract", owner_id=contract["aircraft_contract_id"],
            operation_revision=0, priority=PAYMENT_PRIORITY,
            payload={"contract": "PH_AIRCRAFT_CONTRACT_PAYMENT_V1",
                     "installment": installment + 1})


def _expiry_handler(context):
    world = context.envelope["world_state"]
    contract = world["aircraft_contracts"][context.event["owner_id"]]
    if contract["status"] != "ACTIVE":
        return
    aircraft = world["aircraft"][contract["aircraft_id"]]
    if aircraft["status"] == "IN_FLIGHT":
        raise ValueError("contract expiry cannot remove an aircraft in flight")
    if contract["paid_installments"] != contract["total_installments"]:
        raise ValueError("contract cannot expire before final payment")
    if contract["contract_type"] == "LEASE_TO_OWN":
        contract["status"] = "COMPLETED"
        aircraft["lifecycle"]["ownership_status"] = "OWNED"
        aircraft["lifecycle"]["fixed_configuration"] = False
        return
    successor_id = contract["successor_contract_id"]
    if successor_id is not None:
        successor = world["aircraft_contracts"][successor_id]
        successor["status"] = "ACTIVE"
        aircraft["lifecycle"]["aircraft_contract_id"] = successor_id
        contract["status"] = "COMPLETED"
        _schedule_contract_events(context.envelope, successor)
        return
    contract["status"] = "RETURNED"
    aircraft["status"] = "RETURNED"
    aircraft["current_airport_id"] = None
    aircraft["lifecycle"]["ownership_status"] = "RETURNED"


def _rotation_handler(context):
    rotate_market(context.envelope, schedule_next=True)


def _commit_valid(envelope, candidate):
    result = validate_world(candidate)
    if not result.is_valid:
        issue = result.errors[0]
        raise ValueError(f"{issue.code}: {issue.path}: {issue.message}")
    envelope.clear()
    envelope.update(candidate)


DEFAULT_EVENT_HANDLERS.register(ROTATION_EVENT, _rotation_handler)
DEFAULT_EVENT_HANDLERS.register(PAYMENT_EVENT, _payment_handler)
DEFAULT_EVENT_HANDLERS.register(EXPIRY_EVENT, _expiry_handler)


__all__ = ("LeasePreview", "RenewalPreview", "UsedPurchasePreview", "accept_lease",
           "confirmed_contract_horizon", "initialize_market", "preview_lease",
           "preview_operating_renewal", "preview_used_purchase", "purchase_used_aircraft", "renew_operating_lease",
           "rotate_market", "terminate_contract")
