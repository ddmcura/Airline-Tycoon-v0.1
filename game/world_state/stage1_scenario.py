"""Atomic construction for the curated, temporary Stage 1 playable scenario."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re

from .air_suitability_validation import (
    validate_air_suitability_airport,
    validate_air_suitability_configuration,
)
from .booking_fingerprint import transition_booking_configuration_to_production_choice
from .construction import (
    add_aircraft,
    add_airport_reference,
    add_directional_market,
    create_new_world,
)
from .migration import migrate_schema_1_to_2, migrate_schema_2_to_3, migrate_schema_3_to_4
from .demand_fingerprint import calculate_market_pack_fingerprint
from .schema import LATEST_SAVE_SCHEMA_VERSION
from .validation import validate_world


STAGE1_SCENARIO_ID = "stage1-philippines-v1"
STAGE1_SCENARIO_CONTRACT = "STAGE1_CURATED_SCENARIO_V1"
_SCENARIO_PATH = (
    Path(__file__).resolve().parents[2] / "Data" / "Stage1" / "philippines_v1.json"
)
PHILIPPINES_AIRPORT_PACK_CONTRACT = "PHILIPPINES_COMMERCIAL_AIRPORT_PACK_V1"
PHILIPPINES_AIRPORT_PACK_VERSION = "ph-commercial-airports-v1-2026-09-01"
PHILIPPINES_AIRPORT_PACK_REFERENCE_DATE = "2026-09-01"
PHILIPPINES_ACTIVE_AIRPORT_COUNT = 43
PHILIPPINES_DIRECTIONAL_MARKET_COUNT = 1_806
_PACK_STATUSES = frozenset({
    "ACTIVE_SERVICE_MEMBER",
    "INACTIVE_HISTORICAL_REFERENCE",
    "REFERENCE_ONLY_NO_CURRENT_SCHEDULED_SERVICE",
    "EXCLUDED_PENDING_RELIABLE_CORRECTION",
})
_ACTIVE_STATUS = "ACTIVE_SERVICE_MEMBER"
_PACK_VERSION_PATTERN = re.compile(r"^ph-commercial-airports-v[1-9][0-9]*-[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class Stage1BootstrapError(ValueError):
    """Structured bootstrap rejection that never exposes partial authority."""

    def __init__(self, code, message, path=None):
        super().__init__(message)
        self.code = code
        self.path = path


def _reject(code, message, path=None):
    raise Stage1BootstrapError(code, message, path)


def _required_text(value, field, *, maximum=120):
    if not isinstance(value, str) or not value.strip():
        _reject("INVALID_TEXT", f"{field} must be non-empty text", field)
    value = value.strip()
    if len(value) > maximum:
        _reject("INVALID_TEXT", f"{field} is too long", field)
    return value


def _minor_to_major_text(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _reject("INVALID_SCENARIO", f"{field} must be a non-negative integer", field)
    whole, fraction = divmod(value, 100)
    return f"{whole}.{fraction:02d}"


def _positive_integer(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _reject("INVALID_SCENARIO", f"{field} must be a positive integer", field)
    return value


def _canonical_date(value, field):
    if not isinstance(value, str):
        _reject("INVALID_SCENARIO", f"{field} must be canonical YYYY-MM-DD", field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _reject("INVALID_SCENARIO", f"{field} must be canonical YYYY-MM-DD", field)
    if parsed.isoformat() != value:
        _reject("INVALID_SCENARIO", f"{field} must be canonical YYYY-MM-DD", field)
    return value


def _optional_date(value, field):
    return None if value is None else _canonical_date(value, field)


def _validate_airport_pack(airport_pack, foundation, *, suitability_required=False):
    path = "$.airport_pack"
    required = {
        "contract", "pack_id", "pack_version", "reference_date",
        "country_reference", "timezone", "inclusion_policy",
        "population_calibration_version", "active_airport_count",
        "inactive_reference_airport_count", "sources", "records",
    }
    if type(airport_pack) is not dict or set(airport_pack) != required:
        _reject("INVALID_AIRPORT_PACK", "airport pack fields are not canonical", path)
    if airport_pack["contract"] != PHILIPPINES_AIRPORT_PACK_CONTRACT:
        _reject("INVALID_AIRPORT_PACK", "unsupported airport-pack contract", f"{path}.contract")
    if (
        airport_pack["pack_version"] != PHILIPPINES_AIRPORT_PACK_VERSION
        or _PACK_VERSION_PATTERN.fullmatch(airport_pack["pack_version"]) is None
    ):
        _reject("INVALID_AIRPORT_PACK", "malformed or unsupported airport-pack version", f"{path}.pack_version")
    if _canonical_date(airport_pack["reference_date"], f"{path}.reference_date") != PHILIPPINES_AIRPORT_PACK_REFERENCE_DATE:
        _reject("INVALID_AIRPORT_PACK", "unsupported airport-pack reference date", f"{path}.reference_date")
    for field in ("pack_id", "inclusion_policy", "population_calibration_version"):
        _required_text(airport_pack.get(field), f"{path}.{field}", maximum=800)
    country = foundation.get("country", {}) if type(foundation) is dict else {}
    if (
        airport_pack.get("country_reference") != "PH"
        or country.get("external_reference_code") != "PH"
    ):
        _reject("UNSUPPORTED_COUNTRY_REFERENCE", "airport pack must reference the canonical PH country", f"{path}.country_reference")
    if airport_pack.get("timezone") != "Asia/Manila":
        _reject("INVALID_AIRPORT_PACK", "airport pack timezone must be Asia/Manila", f"{path}.timezone")
    sources = airport_pack.get("sources")
    if not isinstance(sources, list) or not sources:
        _reject("INVALID_AIRPORT_PACK", "airport pack requires source provenance", f"{path}.sources")
    seen_source_ids = set()
    for index, source in enumerate(sources):
        source_path = f"{path}.sources.{index}"
        if type(source) is not dict or set(source) != {"source_id", "title", "url", "retrieved_date"}:
            _reject("INVALID_AIRPORT_PACK", "source records must be exact dictionaries", source_path)
        for field in ("source_id", "title", "url"):
            value = _required_text(source.get(field), f"{source_path}.{field}", maximum=500)
            if value != source[field]:
                _reject("INVALID_AIRPORT_PACK", "source text must already be canonical", f"{source_path}.{field}")
        if source["source_id"] in seen_source_ids:
            _reject("INVALID_AIRPORT_PACK", "source IDs must be unique", f"{source_path}.source_id")
        seen_source_ids.add(source["source_id"])
        _canonical_date(source["retrieved_date"], f"{source_path}.retrieved_date")

    records = airport_pack.get("records")
    if not isinstance(records, list) or not records:
        _reject("INVALID_AIRPORT_PACK", "airport records must be a non-empty list", f"{path}.records")
    record_fields = {
        "catalog_airport_id", "reference_code", "iata", "icao",
        "display_name", "city", "timezone", "population",
        "latitude_microdegrees", "longitude_microdegrees", "country_reference",
        "demand_destination_type", "status", "active",
        "demand_allocation_member", "scheduled_commercial_service_member",
        "passenger_demand_eligible", "active_from_date", "active_until_date",
        "population_calibration_version",
    }
    seen_catalog_ids = set()
    seen_references = set()
    seen_iata = set()
    seen_icao = set()
    active_records = []
    inactive_records = []
    for index, record in enumerate(records):
        record_path = f"{path}.records.{index}"
        extra_fields = {"ground_network_id", "tourism_pull_ppm"}
        if type(record) is not dict or set(record) - extra_fields != record_fields:
            _reject("INVALID_AIRPORT_PACK", "airport records must contain exactly the canonical fields", record_path)
        try:
            validate_air_suitability_airport(record, required=(suitability_required and record.get("active") is True))
        except ValueError as exc:
            _reject("INVALID_AIRPORT_PACK", str(exc), record_path)
        for field, seen in (
            ("catalog_airport_id", seen_catalog_ids),
            ("reference_code", seen_references),
            ("iata", seen_iata),
            ("icao", seen_icao),
        ):
            value = record.get(field)
            expected_length = 3 if field in {"reference_code", "iata"} else 4 if field == "icao" else None
            if (
                not isinstance(value, str) or not value or value != value.strip()
                or (expected_length is not None and (len(value) != expected_length or value != value.upper()))
                or value in seen
            ):
                _reject("INVALID_AIRPORT_PACK", f"{field} must be canonical and unique", f"{record_path}.{field}")
            seen.add(value)
        if record["reference_code"] != record["iata"]:
            _reject("INVALID_AIRPORT_PACK", "reference_code must equal the IATA code in Philippines v1", record_path)
        for field in ("display_name", "city"):
            value = _required_text(record.get(field), f"{record_path}.{field}")
            if value != record[field]:
                _reject("INVALID_AIRPORT_PACK", f"{field} must already be canonical", f"{record_path}.{field}")
        if record.get("timezone") != "Asia/Manila":
            _reject("INVALID_AIRPORT_PACK", "airport timezone must be Asia/Manila", f"{record_path}.timezone")
        if record.get("country_reference") != "PH":
            _reject("UNSUPPORTED_COUNTRY_REFERENCE", "airport country reference must be PH", f"{record_path}.country_reference")
        _positive_integer(record.get("population"), f"{record_path}.population")
        latitude = record.get("latitude_microdegrees")
        longitude = record.get("longitude_microdegrees")
        if (
            isinstance(latitude, bool) or not isinstance(latitude, int)
            or not -90_000_000 <= latitude <= 90_000_000
            or isinstance(longitude, bool) or not isinstance(longitude, int)
            or not -180_000_000 <= longitude <= 180_000_000
        ):
            _reject("INVALID_AIRPORT_PACK", "airport coordinates must be valid integer microdegrees", record_path)
        from .schema import DEMAND_DESTINATION_TYPES
        if record.get("demand_destination_type") not in DEMAND_DESTINATION_TYPES:
            _reject("INVALID_AIRPORT_PACK", "airport destination type is missing or unsupported", f"{record_path}.demand_destination_type")
        if record.get("status") not in _PACK_STATUSES:
            _reject("INVALID_AIRPORT_PACK", "airport status is unsupported", f"{record_path}.status")
        flags = tuple(record.get(field) for field in (
            "active", "demand_allocation_member",
            "scheduled_commercial_service_member", "passenger_demand_eligible",
        ))
        if any(type(value) is not bool for value in flags):
            _reject("INVALID_AIRPORT_PACK", "airport membership flags must be booleans", record_path)
        expected_active = record["status"] == _ACTIVE_STATUS
        if flags != ((True, True, True, True) if expected_active else (False, False, False, False)):
            _reject("INVALID_AIRPORT_PACK", "airport status and membership flags contradict", record_path)
        _optional_date(record.get("active_from_date"), f"{record_path}.active_from_date")
        _optional_date(record.get("active_until_date"), f"{record_path}.active_until_date")
        if (
            record["active_from_date"] is not None
            and record["active_until_date"] is not None
            and record["active_until_date"] <= record["active_from_date"]
        ):
            _reject("INVALID_AIRPORT_PACK", "active_until_date must follow active_from_date", record_path)
        if record.get("population_calibration_version") != airport_pack["population_calibration_version"]:
            _reject("INVALID_AIRPORT_PACK", "airport population calibration is inconsistent", f"{record_path}.population_calibration_version")
        (active_records if expected_active else inactive_records).append(record)
    if (
        airport_pack.get("active_airport_count") != PHILIPPINES_ACTIVE_AIRPORT_COUNT
        or len(active_records) != PHILIPPINES_ACTIVE_AIRPORT_COUNT
        or airport_pack.get("inactive_reference_airport_count") != len(inactive_records)
        or len(inactive_records) != 1
    ):
        _reject("INVALID_AIRPORT_PACK", "airport-pack record counts are inconsistent", path)
    by_code = {record["reference_code"]: record for record in records}
    lgp = by_code.get("LGP")
    drp = by_code.get("DRP")
    if (
        lgp is None or lgp["status"] != "INACTIVE_HISTORICAL_REFERENCE"
        or lgp["active_until_date"] != "2021-10-08"
        or drp is None or drp["status"] != _ACTIVE_STATUS
        or lgp["catalog_airport_id"] == drp["catalog_airport_id"]
        or lgp["icao"] == drp["icao"]
    ):
        _reject("INVALID_AIRPORT_PACK", "LGP must be inactive and DRP must be a distinct active airport", path)
    return tuple(sorted((deepcopy(record) for record in active_records), key=lambda item: item["reference_code"]))


def _validate_scenario(pack):
    if type(pack) is not dict:
        _reject("INVALID_SCENARIO", "scenario reference must be an object", "$")
    required = {
        "contract", "scenario_id", "reference_data_version", "start_time_utc",
        "simulation_seed", "canonical_timezone", "authoritative_currency",
        "starting_cash_minor", "starting_debt_minor", "country_foundation",
        "airport_pack", "starter_aircraft", "rotation", "display_currencies",
    }
    if set(pack) - {"air_suitability_configuration"} != required:
        _reject(
            "INVALID_SCENARIO", f"scenario fields must be exactly {sorted(required)}", "$"
        )
    if pack["contract"] != STAGE1_SCENARIO_CONTRACT:
        _reject("INVALID_SCENARIO", "unsupported scenario contract", "$.contract")
    if pack["scenario_id"] != STAGE1_SCENARIO_ID:
        _reject("UNSUPPORTED_SCENARIO", "unsupported Stage 1 scenario", "$.scenario_id")
    if pack["authoritative_currency"] != "USD":
        _reject(
            "UNSUPPORTED_CURRENCY", "Stage 1 scenario authority must be USD",
            "$.authoritative_currency",
        )
    if pack["canonical_timezone"] != "Asia/Manila":
        _reject("INVALID_SCENARIO", "scenario timezone must be Asia/Manila")
    _minor_to_major_text(pack["starting_cash_minor"], "$.starting_cash_minor")
    _minor_to_major_text(pack["starting_debt_minor"], "$.starting_debt_minor")
    if (
        isinstance(pack["simulation_seed"], bool)
        or not isinstance(pack["simulation_seed"], int)
        or pack["simulation_seed"] < 0
    ):
        _reject("INVALID_SCENARIO", "simulation_seed must be non-negative")
    if "air_suitability_configuration" in pack:
        try:
            validate_air_suitability_configuration(pack["air_suitability_configuration"])
        except ValueError as exc:
            _reject("INVALID_SCENARIO", str(exc), "$.air_suitability_configuration")
    _validate_airport_pack(
        pack["airport_pack"], pack["country_foundation"],
        suitability_required="air_suitability_configuration" in pack,
    )
    starter = pack["starter_aircraft"]
    if type(starter) is not dict or set(starter) != {
        "model_reference", "display_registration", "economy_capacity", "status"
    }:
        _reject("INVALID_SCENARIO", "invalid starter-aircraft reference")
    if (
        starter["model_reference"] != "A320-200"
        or starter["display_registration"] != "RP-C0001"
        or starter["status"] != "PARKED"
        or starter["economy_capacity"] != 180
    ):
        _reject("INVALID_SCENARIO", "unsupported starter-aircraft configuration")
    rotation = pack["rotation"]
    if type(rotation) is not dict or set(rotation) != {
        "outbound_departure_local_time", "outbound_arrival_local_time",
        "return_departure_local_time", "return_arrival_local_time",
        "minimum_first_departure_lead_days",
    }:
        _reject("INVALID_SCENARIO", "invalid rotation reference")
    if tuple(rotation[key] for key in (
        "outbound_departure_local_time", "outbound_arrival_local_time",
        "return_departure_local_time", "return_arrival_local_time",
    )) != ("08:00:00", "10:00:00", "12:00:00", "14:00:00"):
        _reject("INVALID_SCENARIO", "unsupported rotation timetable")
    if rotation["minimum_first_departure_lead_days"] != 6:
        _reject("INVALID_SCENARIO", "first-departure lead time must be six days")
    display = pack["display_currencies"]
    if type(display) is not dict or tuple(sorted(display)) != ("EUR", "PHP", "USD"):
        _reject("INVALID_SCENARIO", "display currencies must be USD, PHP, and EUR")
    for code, rate in display.items():
        if type(rate) is not dict or set(rate) != {
            "minor_per_usd_minor_numerator", "minor_per_usd_minor_denominator", "symbol"
        }:
            _reject("INVALID_SCENARIO", f"invalid {code} display-rate record")
        _positive_integer(rate["minor_per_usd_minor_numerator"], f"$.display_currencies.{code}")
        _positive_integer(rate["minor_per_usd_minor_denominator"], f"$.display_currencies.{code}")
        _required_text(rate["symbol"], f"$.display_currencies.{code}.symbol", maximum=8)
    foundation = pack["country_foundation"]
    if type(foundation) is not dict or set(foundation) != {
        "snapshot_version", "region", "country"
    }:
        _reject("INVALID_SCENARIO", "invalid country foundation")
    return deepcopy(pack)


def active_stage1_airports(pack=None):
    """Return the detached, IATA-ordered allocation members of Philippines v1."""
    scenario = load_stage1_scenario() if pack is None else _validate_scenario(pack)
    return tuple(
        deepcopy(record)
        for record in sorted(
            scenario["airport_pack"]["records"],
            key=lambda item: item["reference_code"],
        )
        if record["status"] == _ACTIVE_STATUS
    )


def load_stage1_scenario(scenario_id=STAGE1_SCENARIO_ID, *, reference_path=None):
    """Load and strictly validate one detached curated reference snapshot."""
    if scenario_id != STAGE1_SCENARIO_ID:
        _reject("UNSUPPORTED_SCENARIO", f"unsupported scenario ID: {scenario_id}")
    path = Path(reference_path) if reference_path is not None else _SCENARIO_PATH
    try:
        with path.open("r", encoding="utf-8") as stream:
            pack = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _reject("INVALID_SCENARIO_REFERENCE", f"cannot load curated scenario: {exc}")
    return _validate_scenario(pack)


def _migration_failure(label, result):
    if result.succeeded:
        return
    issue = result.issues[0] if result.issues else None
    _reject(
        "BOOTSTRAP_MIGRATION_FAILED",
        f"{label} failed: {issue.message if issue else result.status}",
        issue.path if issue else None,
    )


def create_stage1_new_game(
    *, scenario_id, ceo_display_name, airline_display_name, base_airport_reference_code,
    reference_path=None,
):
    """Construct a detached, validated latest-schema temporary Stage 1 world."""
    ceo_name = _required_text(ceo_display_name, "ceo_display_name")
    airline_name = _required_text(airline_display_name, "airline_display_name")
    base_code = _required_text(
        base_airport_reference_code, "base_airport_reference_code", maximum=3
    ).upper()
    # Keep package initialization acyclic: these production domains themselves
    # depend on world-state submodules and are needed only during construction.
    from game.booking import (
        prepare_daily_booking_checkpoint,
        process_daily_booking_checkpoint,
    )
    from game.demand import activate_model4

    pack = load_stage1_scenario(scenario_id, reference_path=reference_path)
    active_airports = active_stage1_airports(pack)
    airport_codes = tuple(record["reference_code"] for record in active_airports)
    if base_code not in airport_codes:
        _reject(
            "INVALID_BASE_AIRPORT",
            "base airport must be an active Philippines v1 service member",
        )
    country_id = pack["country_foundation"]["country"]["country_id"]
    airport_refs = {}
    for record in active_airports:
        airport = deepcopy(record)
        airport["country_id"] = country_id
        airport["latitude"] = Decimal(airport["latitude_microdegrees"]) / Decimal(1_000_000)
        airport["longitude"] = Decimal(airport["longitude_microdegrees"]) / Decimal(1_000_000)
        airport_refs[record["reference_code"]] = airport
    world = create_new_world(
        ceo_display_name=ceo_name,
        airline_display_name=airline_name,
        starting_airport=airport_refs[base_code],
        difficulty="Normal",
        simulation_time_utc=pack["start_time_utc"],
        simulation_seed=pack["simulation_seed"],
        starting_money=_minor_to_major_text(
            pack["starting_cash_minor"], "$.starting_cash_minor"
        ),
        starting_debt=_minor_to_major_text(
            pack["starting_debt_minor"], "$.starting_debt_minor"
        ),
        base_kind="OPERATING_BASE",
        currency="USD",
        reference_data_version=pack["reference_data_version"],
    )
    airport_ids = {base_code: next(iter(world["world_state"]["airports"]))}
    for code in airport_codes:
        if code != base_code:
            airport_ids[code] = add_airport_reference(world, airport_refs[code])
    for origin in airport_codes:
        for destination in airport_codes:
            if origin != destination:
                add_directional_market(
                    world, airport_ids[origin], airport_ids[destination]
                )
    foundation = pack["country_foundation"]
    snapshot = {
        "snapshot_version": foundation["snapshot_version"],
        "regions": {
            foundation["region"]["region_id"]: deepcopy(foundation["region"])
        },
        "countries": {country_id: deepcopy(foundation["country"])},
        "airport_country_ids": {
            airport_id: country_id for airport_id in sorted(airport_ids.values())
        },
        "airport_demand_allocation_members": {
            airport_id: True for airport_id in sorted(airport_ids.values())
        },
    }
    migration = migrate_schema_1_to_2(world, foundation_snapshot=snapshot)
    _migration_failure("schema 1 to 2", migration)
    market_pack = world["simulation"]["configuration"]["demand"][
        "market_pack_configuration"
    ]
    catalog_mapping = {
        airport_refs[code]["catalog_airport_id"]: airport_ids[code]
        for code in airport_codes
    }
    market_pack["market_packs"] = {
        pack["airport_pack"]["pack_id"]: {
            "market_pack_id": pack["airport_pack"]["pack_id"],
            "country_id": country_id,
            "pack_reference": pack["airport_pack"]["contract"],
            "pack_version": pack["airport_pack"]["pack_version"],
            "status": "ENABLED",
            "status_effective_date": pack["airport_pack"]["reference_date"],
            "catalog_airport_ids": sorted(catalog_mapping),
            "airport_id_by_catalog_id": dict(sorted(catalog_mapping.items())),
        }
    }
    market_pack["market_pack_ids"] = [pack["airport_pack"]["pack_id"]]
    market_pack["configuration_fingerprint"] = calculate_market_pack_fingerprint(
        world
    )
    if "air_suitability_configuration" in pack:
        world["simulation"]["configuration"]["demand"]["air_suitability_configuration"] = deepcopy(pack["air_suitability_configuration"])
    activation = activate_model4(
        world,
        expected_revision=world["world_state"]["demand_state"][
            "demand_model_revision"
        ],
    )
    if not activation.succeeded:
        issue = activation.issues[0] if activation.issues else None
        _reject(
            "MODEL4_ACTIVATION_FAILED",
            issue.message if issue else activation.status,
            issue.path if issue else None,
        )
    airline_id = world["world_state"]["player"]["primary_airline_id"]
    starter = pack["starter_aircraft"]
    add_aircraft(
        world,
        airline_id,
        starter["display_registration"],
        starter["model_reference"],
        home_airport_id=airport_ids[base_code],
        current_airport_id=airport_ids[base_code],
        status=starter["status"],
    )
    migration = migrate_schema_2_to_3(world)
    _migration_failure("schema 2 to 3", migration)
    world = migration.world
    configuration = world["simulation"]["configuration"]["booking"]
    transition = transition_booking_configuration_to_production_choice(
        world,
        expected_booking_configuration_revision=configuration["revision"],
        expected_booking_configuration_fingerprint=configuration[
            "configuration_fingerprint"
        ],
    )
    if not transition.succeeded:
        issue = transition.issues[0] if transition.issues else None
        _reject(
            "BOOKING_CONFIGURATION_FAILED",
            issue.message if issue else transition.status,
            issue.path if issue else None,
        )
    prepared = prepare_daily_booking_checkpoint(world)
    if not prepared.succeeded:
        issue = prepared.issues[0]
        _reject("BOOKING_CHECKPOINT_FAILED", issue.message, issue.path)
    checkpoint = process_daily_booking_checkpoint(world, **prepared.as_kwargs())
    if not checkpoint.succeeded:
        issue = checkpoint.issues[0] if checkpoint.issues else None
        _reject(
            "BOOKING_CHECKPOINT_FAILED",
            issue.message if issue else checkpoint.status,
            issue.path if issue else None,
        )
    migration = migrate_schema_3_to_4(world)
    _migration_failure("schema 3 to 4", migration)
    candidate = migration.world
    validation = validate_world(candidate)
    if not validation.is_valid:
        issue = validation.errors[0]
        _reject("INVALID_BOOTSTRAP_WORLD", issue.message, issue.path)
    if candidate["metadata"]["save_schema_version"] != LATEST_SAVE_SCHEMA_VERSION:
        _reject("INVALID_BOOTSTRAP_WORLD", "bootstrap did not reach latest schema")
    return deepcopy(candidate)


__all__ = (
    "STAGE1_SCENARIO_CONTRACT",
    "STAGE1_SCENARIO_ID",
    "PHILIPPINES_ACTIVE_AIRPORT_COUNT",
    "PHILIPPINES_AIRPORT_PACK_CONTRACT",
    "PHILIPPINES_AIRPORT_PACK_REFERENCE_DATE",
    "PHILIPPINES_AIRPORT_PACK_VERSION",
    "PHILIPPINES_DIRECTIONAL_MARKET_COUNT",
    "Stage1BootstrapError",
    "active_stage1_airports",
    "create_stage1_new_game",
    "load_stage1_scenario",
)
