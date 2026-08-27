"""Atomic country market-pack materialization and lifecycle commands."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext

from .construction import _add_airport_reference_in_place
from .demand_fingerprint import (
    calculate_market_pack_fingerprint,
    calculate_model4_input_fingerprint,
    calculate_model4_revision_context_fingerprint,
)
from .schema import (
    DEFAULT_MARKET_PACK_CONFIGURATION,
    LEGACY_MARKET_PACK_CONFIGURATION_VERSION,
    MODEL4_DEMAND_MODEL_VERSION,
)
from .ids import allocate_id
from .validation import validate_world


@dataclass(frozen=True)
class MarketPackIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class MarketPackLifecycleResult:
    status: str
    command: str
    country_id: str | None
    previous_pack_revision: int
    pack_revision: int
    previous_demand_revision: int
    demand_revision: int
    airport_ids: tuple[str, ...] = ()
    market_ids: tuple[str, ...] = ()
    issues: tuple[MarketPackIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


def _revisions(envelope):
    configuration = (
        envelope.get("simulation", {}).get("configuration", {}).get("demand", {})
        if type(envelope) is dict
        else {}
    )
    pack = configuration.get("market_pack_configuration", {})
    demand = envelope.get("world_state", {}).get("demand_state", {}) if type(envelope) is dict else {}
    return pack.get("revision", 0), demand.get("demand_model_revision", 0)


def _reject(envelope, command, country_id, code, message, path=None, *, status="REJECTED"):
    pack_revision, demand_revision = _revisions(envelope)
    return MarketPackLifecycleResult(
        status,
        command,
        country_id if isinstance(country_id, str) else None,
        pack_revision,
        pack_revision,
        demand_revision,
        demand_revision,
        issues=(MarketPackIssue(code, message, path),),
    )


def _validation_rejection(envelope, command, country_id, validation):
    issue = validation.errors[0]
    code = issue.code.upper()
    if issue.code == "inconsistent_pack_fingerprint":
        code = "INCONSISTENT_PACK_FINGERPRINT"
    elif issue.code == "inconsistent_demand_revision" and issue.path.endswith("input_fingerprint"):
        code = "INCONSISTENT_DEMAND_FINGERPRINT"
    return _reject(envelope, command, country_id, code, issue.message, issue.path)


def _canonical_date(value, default, field):
    value = default if value is None else value
    if not isinstance(value, str):
        raise ValueError(f"{field} must be canonical YYYY-MM-DD")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must be canonical YYYY-MM-DD")
    return value


def _pack_for_country(configuration, country_id):
    matches = [
        (pack_id, pack)
        for pack_id, pack in configuration["market_packs"].items()
        if pack.get("country_id") == country_id
    ]
    return matches[0] if len(matches) == 1 else (None, None)


def _replace_envelope(envelope, candidate):
    envelope.clear()
    envelope.update(deepcopy(candidate))


def _context_for_current_revision(candidate):
    configuration = candidate["simulation"]["configuration"]["demand"]
    state = candidate["world_state"]["demand_state"]
    travel = configuration["travel_scope_configuration"]
    market_pack = configuration["market_pack_configuration"]
    revision = state["demand_model_revision"]
    context_id = f"model4-demand-revision-{revision}"
    context = {
        "revision_context_id": context_id,
        "demand_model_version": MODEL4_DEMAND_MODEL_VERSION,
        "demand_model_revision": revision,
        "configuration_version": configuration["configuration_version"],
        "configuration_revision": configuration["revision"],
        "universe_date": state["universe_date"],
        "travel_scope_configuration_version": travel["configuration_version"],
        "travel_scope_revision": travel["revision"],
        "market_pack_configuration_version": market_pack["configuration_version"],
        "market_pack_revision": market_pack["revision"],
        "daily_multiplier_min_bps": configuration["daily_multiplier_min_bps"],
        "daily_multiplier_max_bps": configuration["daily_multiplier_max_bps"],
        "country_reference_snapshot_version": travel["reference_snapshot_version"],
        "model4_input_fingerprint": state["input_fingerprint"],
    }
    context["context_fingerprint"] = calculate_model4_revision_context_fingerprint(context)
    state["model4_revision_contexts"][context_id] = context


def _catalog_issue(airport_catalog, country_id, countries, existing_reference_codes, existing_catalog_ids):
    if not isinstance(airport_catalog, (list, tuple)) or not airport_catalog:
        return MarketPackIssue("INVALID_AIRPORT_CATALOG", "airport_catalog must be a non-empty complete sequence", "$.airport_catalog")
    seen_catalog = set()
    seen_references = set()
    required = {
        "catalog_airport_id",
        "reference_code",
        "display_name",
        "timezone",
        "population",
        "latitude_microdegrees",
        "longitude_microdegrees",
        "demand_destination_type",
    }
    allowed = required | {
        "country_id",
        "country_reference",
        "active_from_date",
        "active_until_date",
    }
    for index, supplied in enumerate(airport_catalog):
        path = f"$.airport_catalog.{index}"
        if (
            type(supplied) is not dict
            or not required.issubset(supplied)
            or set(supplied) - allowed
        ):
            return MarketPackIssue("INVALID_AIRPORT_CATALOG", "every catalog airport must be a complete dictionary", path)
        catalog_id = supplied.get("catalog_airport_id")
        if (
            not isinstance(catalog_id, str)
            or not catalog_id
            or catalog_id != catalog_id.strip()
        ):
            return MarketPackIssue("INVALID_AIRPORT_CATALOG", "catalog_airport_id must be a non-empty immutable external ID", f"{path}.catalog_airport_id")
        if catalog_id in seen_catalog:
            return MarketPackIssue("INVALID_AIRPORT_CATALOG", "catalog airport IDs must be unique", f"{path}.catalog_airport_id")
        if catalog_id in existing_catalog_ids:
            return MarketPackIssue("CATALOG_ID_CONFLICT", "catalog airport ID is already mapped", f"{path}.catalog_airport_id")
        seen_catalog.add(catalog_id)
        supplied_country = supplied.get("country_id", country_id)
        supplied_reference = supplied.get("country_reference")
        if supplied_country != country_id or (
            supplied_reference is not None
            and supplied_reference != countries[country_id].get("external_reference_code")
        ):
            return MarketPackIssue("PACK_COUNTRY_MISMATCH", "every supplied airport must belong to the target country", path)
        reference = supplied.get("reference_code")
        if not isinstance(reference, str) or not reference.strip():
            return MarketPackIssue("INVALID_AIRPORT_CATALOG", "reference_code must be non-empty", f"{path}.reference_code")
        reference = reference.strip().upper()
        if reference in seen_references or reference in existing_reference_codes:
            return MarketPackIssue("INVALID_AIRPORT_CATALOG", "airport reference_code must be unique", f"{path}.reference_code")
        seen_references.add(reference)
        for field in ("display_name", "timezone", "demand_destination_type"):
            value = supplied.get(field)
            if not isinstance(value, str) or not value.strip():
                return MarketPackIssue(
                    "INVALID_AIRPORT_CATALOG",
                    f"{field} must be a non-empty string",
                    f"{path}.{field}",
                )
        population = supplied.get("population")
        if isinstance(population, bool) or not isinstance(population, int) or population <= 0:
            return MarketPackIssue("INVALID_AIRPORT_CATALOG", "allocation airports require positive population", f"{path}.population")
        latitude = supplied.get("latitude_microdegrees")
        longitude = supplied.get("longitude_microdegrees")
        if (
            isinstance(latitude, bool) or not isinstance(latitude, int) or not -90_000_000 <= latitude <= 90_000_000
            or isinstance(longitude, bool) or not isinstance(longitude, int) or not -180_000_000 <= longitude <= 180_000_000
        ):
            return MarketPackIssue("INVALID_AIRPORT_CATALOG", "catalog airports require valid integer microdegree coordinates", path)
    return None


def materialize_country_pack(
    envelope,
    country_id,
    pack_reference,
    pack_version,
    airport_catalog,
    *,
    expected_pack_revision,
    expected_demand_revision,
    market_pack_id=None,
    status_effective_date=None,
):
    """Atomically materialize one LATENT country pack and its directional pairs."""
    command = "MATERIALIZE_COUNTRY_PACK"
    validation = validate_world(envelope)
    if not validation.is_valid:
        return _validation_rejection(envelope, command, country_id, validation)
    pack_revision, demand_revision = _revisions(envelope)
    if isinstance(expected_pack_revision, bool) or not isinstance(expected_pack_revision, int) or expected_pack_revision != pack_revision:
        return _reject(envelope, command, country_id, "STALE_REVISION", "expected market-pack revision does not match", status="STALE_REVISION")
    if isinstance(expected_demand_revision, bool) or not isinstance(expected_demand_revision, int) or expected_demand_revision != demand_revision:
        return _reject(envelope, command, country_id, "STALE_REVISION", "expected demand revision does not match", status="STALE_REVISION")
    state = envelope["world_state"]
    configuration = envelope["simulation"]["configuration"]["demand"]
    if configuration.get("model_version") != MODEL4_DEMAND_MODEL_VERSION:
        return _reject(envelope, command, country_id, "INVALID_PACK_TRANSITION", "country packs may be materialized only after Model 4 activation")
    if not isinstance(country_id, str) or country_id not in state["countries"]:
        return _reject(envelope, command, country_id, "INVALID_PACK_CONFIGURATION", "country_id must reference an authoritative country")
    if (
        not isinstance(pack_reference, str)
        or not pack_reference
        or pack_reference != pack_reference.strip()
        or not isinstance(pack_version, str)
        or not pack_version
        or pack_version != pack_version.strip()
    ):
        return _reject(envelope, command, country_id, "INVALID_PACK_CONFIGURATION", "pack reference and version must be non-empty strings")
    pack_configuration = configuration["market_pack_configuration"]
    legacy_pack_configuration = (
        pack_configuration.get("configuration_version")
        == LEGACY_MARKET_PACK_CONFIGURATION_VERSION
    )
    existing_pack_id, existing_pack = (
        (None, None)
        if legacy_pack_configuration
        else _pack_for_country(pack_configuration, country_id)
    )
    if existing_pack is not None and existing_pack.get("status") != "LATENT":
        return _reject(envelope, command, country_id, "PACK_ALREADY_MATERIALIZED", "country pack is already materialized")
    if any(
        airport.get("country_id") == country_id
        and airport.get("demand_allocation_member") is True
        for airport in state["airports"].values()
    ):
        return _reject(
            envelope,
            command,
            country_id,
            "PACK_ALREADY_MATERIALIZED",
            "a LATENT country pack cannot already own allocation-member airports",
        )
    if existing_pack is not None and (
        existing_pack.get("pack_reference") != pack_reference
        or existing_pack.get("pack_version") != pack_version
        or (market_pack_id is not None and market_pack_id != existing_pack_id)
    ):
        return _reject(envelope, command, country_id, "PACK_VERSION_CONFLICT", "latent pack identity or version does not match")
    if not legacy_pack_configuration and existing_pack is None and any(
        pack.get("pack_reference") == pack_reference
        for pack in pack_configuration["market_packs"].values()
    ):
        return _reject(envelope, command, country_id, "PACK_VERSION_CONFLICT", "pack reference is already owned by another country")
    market_pack_id = existing_pack_id or market_pack_id or country_id
    if not isinstance(market_pack_id, str) or not market_pack_id or market_pack_id != market_pack_id.strip() or (
        not legacy_pack_configuration
        and market_pack_id in pack_configuration["market_packs"]
        and existing_pack_id is None
    ):
        return _reject(envelope, command, country_id, "INVALID_PACK_CONFIGURATION", "market_pack_id is invalid or already used")
    existing_catalog_ids = set() if legacy_pack_configuration else {
        catalog_id
        for pack in pack_configuration["market_packs"].values()
        for catalog_id in pack.get("airport_id_by_catalog_id", {})
    }
    issue = _catalog_issue(
        airport_catalog,
        country_id,
        state["countries"],
        {airport.get("reference_code") for airport in state["airports"].values()},
        existing_catalog_ids,
    )
    if issue is not None:
        return _reject(envelope, command, country_id, issue.code, issue.message, issue.path)
    try:
        effective_date = _canonical_date(status_effective_date, envelope["simulation"]["time_utc"][:10], "status_effective_date")
        candidate = deepcopy(envelope)
        candidate_configuration = candidate["simulation"]["configuration"]["demand"]
        candidate_state = candidate["world_state"]
        if legacy_pack_configuration:
            candidate_configuration["market_pack_configuration"] = deepcopy(
                DEFAULT_MARKET_PACK_CONFIGURATION
            )
            for country in candidate_state["countries"].values():
                country["airport_allocation_revision"] = 1
        new_demand_revision = demand_revision + 1
        catalog_mapping = {}
        new_airport_ids = []
        for supplied in sorted(airport_catalog, key=lambda record: record["catalog_airport_id"]):
            airport = deepcopy(supplied)
            airport["country_id"] = country_id
            airport["country_reference"] = candidate_state["countries"][country_id]["external_reference_code"]
            airport["demand_allocation_member"] = True
            airport["passenger_demand_eligible"] = True
            # Catalog coordinates are authoritative integer microdegrees. Shield
            # their adapter representation from the caller's Decimal context so
            # construction cannot silently round identity inputs.
            with localcontext() as context:
                context.prec = 32
                airport["latitude"] = Decimal(airport["latitude_microdegrees"]) / Decimal(1_000_000)
                airport["longitude"] = Decimal(airport["longitude_microdegrees"]) / Decimal(1_000_000)
                airport_id = _add_airport_reference_in_place(candidate, airport)
            candidate_state["airports"][airport_id]["demand_input_revision"] = new_demand_revision
            catalog_mapping[supplied["catalog_airport_id"]] = airport_id
            new_airport_ids.append(airport_id)
        allocation_members = tuple(
            airport_id
            for airport_id, airport in sorted(candidate_state["airports"].items())
            if airport.get("demand_allocation_member") is True
        )
        existing_pairs = {
            (market["origin_airport_id"], market["destination_airport_id"])
            for market in candidate_state["directional_markets"].values()
        }
        new_airport_id_set = frozenset(new_airport_ids)
        new_market_ids = []
        for origin_id in allocation_members:
            for destination_id in allocation_members:
                if (
                    origin_id != destination_id
                    and (origin_id in new_airport_id_set or destination_id in new_airport_id_set)
                    and (origin_id, destination_id) not in existing_pairs
                ):
                    market_id = allocate_id(candidate, "market")
                    candidate_state["directional_markets"][market_id] = {
                        "market_id": market_id,
                        "origin_airport_id": origin_id,
                        "destination_airport_id": destination_id,
                    }
                    new_market_ids.append(market_id)
                    existing_pairs.add((origin_id, destination_id))
        pack_configuration = candidate_configuration["market_pack_configuration"]
        pack_configuration["market_packs"][market_pack_id] = {
            "market_pack_id": market_pack_id,
            "country_id": country_id,
            "pack_reference": pack_reference,
            "pack_version": pack_version,
            "status": "ENABLED",
            "status_effective_date": effective_date,
            "catalog_airport_ids": sorted(catalog_mapping),
            "airport_id_by_catalog_id": dict(sorted(catalog_mapping.items())),
        }
        pack_configuration["market_pack_ids"] = sorted(pack_configuration["market_packs"])
        pack_configuration["revision"] = pack_revision + 1
        candidate_state["countries"][country_id]["airport_allocation_revision"] += 1
        candidate_configuration["revision"] = new_demand_revision
        demand_state = candidate_state["demand_state"]
        demand_state["demand_model_revision"] = new_demand_revision
        demand_state["input_fingerprint"] = calculate_model4_input_fingerprint(candidate)
        pack_configuration["configuration_fingerprint"] = calculate_market_pack_fingerprint(candidate)
        _context_for_current_revision(candidate)
        from game.demand.model4 import rebuild_model4_indexes
        rebuild_model4_indexes(candidate)
        final = validate_world(candidate)
        if not final.is_valid:
            return _validation_rejection(envelope, command, country_id, final)
    except Exception as exc:
        return _reject(envelope, command, country_id, "DEMAND_ALLOCATION_FAILED", str(exc))
    _replace_envelope(envelope, candidate)
    return MarketPackLifecycleResult(
        "COMPLETED", command, country_id, pack_revision, pack_revision + 1,
        demand_revision, demand_revision + 1, tuple(new_airport_ids), tuple(new_market_ids),
    )


def _transition_country_pack(
    envelope,
    country_id,
    target_status,
    *,
    expected_pack_revision,
    pack_reference=None,
    pack_version=None,
    status_effective_date=None,
):
    command = "DISABLE_COUNTRY_PACK" if target_status == "DISABLED" else "ENABLE_COUNTRY_PACK"
    validation = validate_world(envelope)
    if not validation.is_valid:
        return _validation_rejection(envelope, command, country_id, validation)
    pack_revision, demand_revision = _revisions(envelope)
    if isinstance(expected_pack_revision, bool) or not isinstance(expected_pack_revision, int) or expected_pack_revision != pack_revision:
        return _reject(envelope, command, country_id, "STALE_REVISION", "expected market-pack revision does not match", status="STALE_REVISION")
    pack_configuration = envelope["simulation"]["configuration"]["demand"]["market_pack_configuration"]
    pack_id, pack = _pack_for_country(pack_configuration, country_id)
    if pack is None or pack.get("status") == "LATENT":
        return _reject(envelope, command, country_id, "PACK_NOT_MATERIALIZED", "country pack is not materialized")
    expected_source = "ENABLED" if target_status == "DISABLED" else "DISABLED"
    if pack.get("status") != expected_source:
        return _reject(envelope, command, country_id, "INVALID_PACK_TRANSITION", f"pack must be {expected_source} before transition to {target_status}")
    if (pack_reference is not None and pack_reference != pack.get("pack_reference")) or (
        pack_version is not None and pack_version != pack.get("pack_version")
    ):
        return _reject(envelope, command, country_id, "PACK_VERSION_CONFLICT", "pack identity or version does not match materialized authority")
    try:
        effective_date = _canonical_date(status_effective_date, envelope["simulation"]["time_utc"][:10], "status_effective_date")
        candidate = deepcopy(envelope)
        candidate_pack_configuration = candidate["simulation"]["configuration"]["demand"]["market_pack_configuration"]
        candidate_pack = candidate_pack_configuration["market_packs"][pack_id]
        candidate_pack["status"] = target_status
        candidate_pack["status_effective_date"] = effective_date
        candidate_pack_configuration["revision"] = pack_revision + 1
        candidate_pack_configuration["configuration_fingerprint"] = calculate_market_pack_fingerprint(candidate)
        final = validate_world(candidate)
        if not final.is_valid:
            return _validation_rejection(envelope, command, country_id, final)
    except (KeyError, TypeError, ValueError) as exc:
        return _reject(envelope, command, country_id, "INVALID_PACK_CONFIGURATION", str(exc))
    _replace_envelope(envelope, candidate)
    return MarketPackLifecycleResult(
        "COMPLETED", command, country_id, pack_revision, pack_revision + 1,
        demand_revision, demand_revision,
    )


def disable_country_pack(envelope, country_id, *, expected_pack_revision, pack_reference=None, pack_version=None, status_effective_date=None):
    """Disable prospective activation while retaining all materialized authority."""
    return _transition_country_pack(
        envelope, country_id, "DISABLED", expected_pack_revision=expected_pack_revision,
        pack_reference=pack_reference, pack_version=pack_version,
        status_effective_date=status_effective_date,
    )


def enable_country_pack(envelope, country_id, *, expected_pack_revision, pack_reference=None, pack_version=None, status_effective_date=None):
    """Re-enable prospective activation using the existing materialized identity."""
    if (
        not isinstance(pack_reference, str)
        or not pack_reference
        or pack_reference != pack_reference.strip()
        or not isinstance(pack_version, str)
        or not pack_version
        or pack_version != pack_version.strip()
    ):
        return _reject(
            envelope,
            "ENABLE_COUNTRY_PACK",
            country_id,
            "INVALID_PACK_CONFIGURATION",
            "re-enable requires the existing non-empty pack reference and version",
        )
    return _transition_country_pack(
        envelope, country_id, "ENABLED", expected_pack_revision=expected_pack_revision,
        pack_reference=pack_reference, pack_version=pack_version,
        status_effective_date=status_effective_date,
    )
