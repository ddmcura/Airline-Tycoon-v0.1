"""Explicit atomic migrations between authoritative world schema versions."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import json

from .demand_fingerprint import (
    calculate_demand_input_fingerprint,
    calculate_market_pack_fingerprint,
)
from .ids import parse_entity_id
from .booking_fingerprint import new_booking_configuration
from .schema import (
    DEFAULT_MARKET_PACK_CONFIGURATION,
    DEFAULT_TRAVEL_SCOPE_CONFIGURATION,
    MODEL3_PROCESSED_COHORT_V1,
    PROCESSED_COHORT_SCHEMA_VERSION,
    SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT,
    SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT,
)
from .serialization import json_compatibility_error
from .validation import ValidationIssue, validate_world


@dataclass(frozen=True)
class MigrationResult:
    status: str
    source_schema_version: object
    target_schema_version: int
    issues: tuple = ()
    migrated_world: dict | None = None

    @property
    def succeeded(self):
        return self.status == "COMPLETED"

    def as_dict(self):
        return {
            "status": self.status,
            "source_schema_version": self.source_schema_version,
            "target_schema_version": self.target_schema_version,
            "issues": [issue.as_dict() for issue in self.issues],
        }

    @property
    def candidate(self):
        return self.migrated_world

    @property
    def world(self):
        return self.migrated_world


def _issue(code, path, message, entity_type=None, entity_id=None):
    return ValidationIssue(code, path, message, entity_type, entity_id)


def _snapshot_candidate(snapshot) -> tuple[dict | None, tuple]:
    """Return detached canonical snapshot records or structured issues."""
    if not isinstance(snapshot, Mapping):
        return None, (_issue("invalid_migration_snapshot", "$", "snapshot must be a mapping"),)
    compatibility_error = json_compatibility_error(snapshot)
    if compatibility_error:
        path, message = compatibility_error
        return None, (_issue("invalid_migration_snapshot", path, message),)
    required = {
        "snapshot_version",
        "regions",
        "countries",
        "airport_country_ids",
        "airport_demand_allocation_members",
    }
    try:
        fields = set(snapshot)
    except TypeError:
        return None, (_issue("invalid_migration_snapshot", "$", "snapshot keys must be strings"),)
    if fields != required:
        return None, (
            _issue(
                "invalid_migration_snapshot",
                "$",
                f"snapshot fields must be exactly {sorted(required)}",
            ),
        )
    snapshot_version = snapshot.get("snapshot_version")
    regions = snapshot.get("regions")
    countries = snapshot.get("countries")
    airport_country_ids = snapshot.get("airport_country_ids")
    airport_members = snapshot.get("airport_demand_allocation_members")
    if not isinstance(snapshot_version, str) or not snapshot_version.strip():
        return None, (_issue("invalid_migration_snapshot", "$.snapshot_version", "must be non-empty text"),)
    if not isinstance(regions, Mapping):
        return None, (_issue("invalid_migration_snapshot", "$.regions", "must be a mapping"),)
    if not isinstance(countries, Mapping):
        return None, (_issue("invalid_migration_snapshot", "$.countries", "must be a mapping"),)
    if not isinstance(airport_country_ids, Mapping):
        return None, (_issue("invalid_migration_snapshot", "$.airport_country_ids", "must be a mapping"),)
    if not isinstance(airport_members, Mapping):
        return None, (_issue("invalid_migration_snapshot", "$", "snapshot collections must be mappings"),)
    return (
        {
            "snapshot_version": snapshot_version,
            "regions": deepcopy(dict(regions)),
            "countries": deepcopy(dict(countries)),
            "airport_country_ids": deepcopy(dict(airport_country_ids)),
            "airport_demand_allocation_members": deepcopy(dict(airport_members)),
        },
        (),
    )


def migrate_schema_1_to_2(envelope, *, foundation_snapshot):
    """Validate, transform, validate, and atomically commit schema 1 to schema 2."""
    source_version = None
    if isinstance(envelope, dict):
        metadata = envelope.get("metadata")
        if type(metadata) is dict:
            source_version = metadata.get("save_schema_version")
    if (
        type(envelope) is not dict
        or type(source_version) is not int
        or source_version != 1
    ):
        return MigrationResult(
            "REJECTED",
            source_version,
            2,
            (_issue("unsupported_migration_source", "$.metadata.save_schema_version", "must equal 1"),),
        )
    source_validation = validate_world(envelope)
    if not source_validation.is_valid:
        return MigrationResult(
            "REJECTED", source_version, 2, source_validation.errors
        )
    snapshot, issues = _snapshot_candidate(foundation_snapshot)
    if issues:
        return MigrationResult("REJECTED", source_version, 2, issues)
    if snapshot is None:
        return MigrationResult(
            "REJECTED",
            source_version,
            2,
            (_issue("invalid_migration_snapshot", "$", "snapshot validation failed"),),
        )

    candidate = deepcopy(envelope)
    state = candidate["world_state"]
    airports = state["airports"]
    mappings = snapshot["airport_country_ids"]
    members = snapshot["airport_demand_allocation_members"]
    if set(mappings) != set(airports) or set(members) != set(airports):
        return MigrationResult(
            "REJECTED",
            source_version,
            2,
            (_issue("incomplete_airport_country_mapping", "$.airport_country_ids", "country and allocation-member mappings must cover every existing airport exactly once"),),
        )

    regions = snapshot["regions"]
    countries = snapshot["countries"]
    for entity_type, records, id_field in (
        ("region", regions, "region_id"),
        ("country", countries, "country_id"),
    ):
        for key, record in records.items():
            if (
                not isinstance(key, str)
                or not isinstance(record, Mapping)
                or record.get(id_field) != key
                or parse_entity_id(key, entity_type) is None
            ):
                return MigrationResult(
                    "REJECTED",
                    source_version,
                    2,
                    (_issue("invalid_migration_identity", f"$.{entity_type}s.{key}", f"must be keyed by an immutable {entity_type} ID"),),
                )
    for airport_id, country_id in mappings.items():
        if not isinstance(country_id, str) or country_id not in countries:
            return MigrationResult(
                "REJECTED",
                source_version,
                2,
                (_issue("invalid_airport_country_mapping", f"$.airport_country_ids.{airport_id}", "must reference a supplied country ID", "airport", str(airport_id)),),
            )
        legacy_reference = airports[airport_id].get("country_reference")
        external_reference = countries[country_id].get("external_reference_code")
        if legacy_reference is not None and legacy_reference != external_reference:
            return MigrationResult(
                "REJECTED",
                source_version,
                2,
                (_issue("ambiguous_airport_country_mapping", f"$.airport_country_ids.{airport_id}", "explicit country external reference does not match the airport snapshot", "airport", airport_id),),
            )
        if type(members.get(airport_id)) is not bool:
            return MigrationResult(
                "REJECTED",
                source_version,
                2,
                (_issue("invalid_demand_allocation_member", f"$.airport_demand_allocation_members.{airport_id}", "must explicitly supply a boolean", "airport", airport_id),),
            )

    candidate["metadata"]["save_schema_version"] = 2
    state["regions"] = regions
    state["countries"] = countries
    for country in state["countries"].values():
        country["airport_allocation_revision"] = 1
    for airport_id, country_id in mappings.items():
        airports[airport_id]["country_id"] = country_id
        airports[airport_id]["demand_allocation_member"] = members[airport_id]

    allocator = candidate["deterministic_state"]["id_allocator"]["next_by_type"]
    for entity_type, records in (("region", regions), ("country", countries)):
        issued = []
        for key in records:
            parsed = parse_entity_id(key, entity_type)
            if parsed is not None:
                issued.append(parsed[1])
        allocator[entity_type] = max(issued, default=0) + 1

    configuration = candidate["simulation"]["configuration"]["demand"]
    configuration["market_pack_configuration"] = deepcopy(
        DEFAULT_MARKET_PACK_CONFIGURATION
    )
    configuration["market_pack_configuration"][
        "configuration_fingerprint"
    ] = calculate_market_pack_fingerprint(candidate)
    travel_scope = deepcopy(DEFAULT_TRAVEL_SCOPE_CONFIGURATION)
    travel_scope["reference_snapshot_version"] = snapshot["snapshot_version"]
    configuration["travel_scope_configuration"] = travel_scope

    demand_state = state["demand_state"]
    demand_state["processed_cohort_schema_version"] = PROCESSED_COHORT_SCHEMA_VERSION
    demand_state["model3_terminal_demand_revision"] = None
    demand_state["model4_revision_contexts"] = {}
    demand_state["processed_cohorts"] = {
        key: {"contract": MODEL3_PROCESSED_COHORT_V1, "payload": deepcopy(payload)}
        for key, payload in demand_state["processed_cohorts"].items()
    }
    demand_state["input_fingerprint"] = calculate_demand_input_fingerprint(candidate)

    candidate_validation = validate_world(candidate)
    if not candidate_validation.is_valid:
        return MigrationResult(
            "REJECTED", source_version, 2, candidate_validation.errors
        )
    envelope.clear()
    envelope.update(candidate)
    return MigrationResult("COMPLETED", source_version, 2)


def _compatibility_wrapper(record, primary_id_field, contract):
    return {
        primary_id_field: record[primary_id_field],
        "contract": contract,
        "payload": deepcopy(record),
    }


def migrate_schema_2_to_3(envelope):
    """Return a detached validated schema-3 candidate without mutating source."""
    source_version = None
    if type(envelope) is dict:
        metadata = envelope.get("metadata")
        if type(metadata) is dict:
            source_version = metadata.get("save_schema_version")
    if type(source_version) is not int or source_version != 2:
        return MigrationResult(
            "REJECTED",
            source_version,
            3,
            (
                _issue(
                    "unsupported_migration_source",
                    "$.metadata.save_schema_version",
                    "must equal 2",
                ),
            ),
        )
    source_validation = validate_world(envelope)
    if not source_validation.is_valid:
        return MigrationResult(
            "REJECTED", source_version, 3, source_validation.errors
        )

    try:
        candidate = json.loads(
            json.dumps(envelope, ensure_ascii=True, allow_nan=False)
        )
        candidate["metadata"]["save_schema_version"] = 3
        candidate["simulation"]["configuration"]["booking"] = (
            new_booking_configuration()
        )
        state = candidate["world_state"]
        state["booking_state"] = {
            "booking_revision": 0,
            "booking_checkpoints": {},
        }
        for flight in state["dated_flights"].values():
            flight["inventory_revision"] = 0
        for airline in state["airlines"].values():
            airline["finance_revision"] = 0
        candidate["deterministic_state"]["id_allocator"]["next_by_type"][
            "booking_checkpoint"
        ] = 1
        state["itineraries"] = {
            itinerary_id: _compatibility_wrapper(
                state["itineraries"][itinerary_id],
                "itinerary_id",
                SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT,
            )
            for itinerary_id in sorted(state["itineraries"])
        }
        state["bookings"] = {
            booking_id: _compatibility_wrapper(
                state["bookings"][booking_id],
                "booking_id",
                SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT,
            )
            for booking_id in sorted(state["bookings"])
        }
    except (KeyError, OverflowError, RecursionError, TypeError, ValueError) as exc:
        return MigrationResult(
            "REJECTED",
            source_version,
            3,
            (
                _issue(
                    "migration_failed",
                    "$",
                    f"schema-3 candidate construction failed: {exc}",
                ),
            ),
        )

    candidate_validation = validate_world(candidate)
    if not candidate_validation.is_valid:
        return MigrationResult(
            "REJECTED", source_version, 3, candidate_validation.errors
        )
    return MigrationResult(
        "COMPLETED", source_version, 3, migrated_world=candidate
    )
