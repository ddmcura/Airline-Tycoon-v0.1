"""Model 4 travel-scope demand derivation and atomic activation.

All objects in this module are disposable runtime derivations.  Only revision
contexts and processed-cohort wrappers cross the authoritative boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
from types import MappingProxyType

from game.world_state.demand_fingerprint import (
    calculate_model4_cohort_fingerprint,
    calculate_model4_input_fingerprint,
    calculate_model4_revision_context_fingerprint,
)
from game.world_state.schema import (
    DEMAND_MULTIPLIER_CATEGORIES,
    DEMAND_ROUNDING_POLICY,
    MODEL4_DEMAND_CONFIGURATION_VERSION,
    MODEL4_DEMAND_MODEL_VERSION,
    MODEL4_TRAVEL_SCOPE_COHORT_V1,
    TRAVEL_SCOPES,
)
from game.world_state.validation import validate_world

from .model import (
    CohortResolution,
    DemandIssue,
    WorldCohortResult,
    _compose_daily_multipliers,
    _distance_km,
    _fixed_decimal_context,
    _replace_envelope,
    _resolve_fraction,
    _validation_issues,
)


_BPS = Decimal(10_000)
_PPM = Decimal(1_000_000)
_PRECISION = 50
_INDEX_CONTRACT = "STAGE1_MODEL4_DEMAND_INDEX_SHA256_JSON_V1"
_PROFILE_FIELD_BY_SCOPE = {
    "DOMESTIC": "domestic_weight_bps",
    "HOME_REGION_INTERNATIONAL": "home_region_international_weight_bps",
    "REST_OF_WORLD_INTERNATIONAL": "rest_of_world_international_weight_bps",
}


@dataclass(frozen=True)
class Model4ActivationResult:
    status: str
    previous_revision: int
    revision: int
    revision_context_id: str | None = None
    issues: tuple[DemandIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


@dataclass(frozen=True)
class AllocationNormalization:
    amount: Decimal
    normalization_denominator: Decimal
    residual_id: str
    residual_amount: Decimal


@dataclass(frozen=True)
class Model4OriginNormalization:
    origin_airport_id: str
    origin_country_id: str
    origin_region_id: str
    origin_daily_booking_pool: Decimal
    scope_amounts: Mapping[str, Decimal]
    country_amounts: Mapping[str, Decimal]
    region_amounts: Mapping[str, Decimal]
    airport_normalization_by_country: Mapping[str, AllocationNormalization]
    empty_scope_latent_amounts: Mapping[str, Decimal]
    unmaterialized_country_latent_amounts: Mapping[str, Decimal]


@dataclass(frozen=True)
class Model4DemandIndexes:
    lineage_id: str
    model_revision: int
    input_fingerprint: str
    source_fingerprint: str
    universe_date: str
    origin_airport_ids: tuple[str, ...]
    market_by_pair: Mapping[tuple[str, str], str]
    normalization_by_origin: Mapping[str, Model4OriginNormalization]
    integrity_fingerprint: str


@dataclass(frozen=True)
class Model4ActiveMarketIntent:
    market_id: str
    base_daily_bookers: Decimal
    daily_multipliers_bps: Mapping[str, int]
    resolved_integer_intent: int
    reused: bool


@dataclass(frozen=True)
class Model4ActiveDayResult:
    status: str
    cohort_date: str
    expected_demand_revision: int
    expected_pack_revision: int
    active_market_ids: tuple[str, ...] = ()
    intents: tuple[Model4ActiveMarketIntent, ...] = ()
    cohorts: tuple[CohortResolution, ...] = ()
    issues: tuple[DemandIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


def _reject_activation(current, code, message, path=None, status="REJECTED"):
    return Model4ActivationResult(
        status,
        current,
        current,
        issues=(DemandIssue(code, message, path),),
    )


def _structured_validation_issues(validation):
    issues = []
    for issue in validation.errors:
        code = issue.code.upper()
        if issue.code == "inconsistent_demand_revision" and issue.path.endswith("input_fingerprint"):
            code = "INCONSISTENT_DEMAND_FINGERPRINT"
        elif "countries" in issue.path and issue.code == "dangling_reference":
            code = "INVALID_REGION_REFERENCE"
        elif "countries" in issue.path:
            code = "INVALID_COUNTRY_INPUT"
        elif "directional_markets" in issue.path:
            code = "INVALID_MARKET_UNIVERSE"
        issues.append(DemandIssue(code, issue.message, issue.path))
    return tuple(issues)


def _effective(country, universe_date):
    start = country.get("effective_from_date")
    end = country.get("effective_until_date")
    return not ((start is not None and universe_date < start) or (end is not None and universe_date >= end))


def _hierarchy_issue(candidate):
    state = candidate["world_state"]
    countries = state["countries"]
    regions = state["regions"]
    universe_date = state["demand_state"]["universe_date"]
    effective = {country_id for country_id, country in countries.items() if _effective(country, universe_date)}
    for country_id in sorted(countries):
        country = countries[country_id]
        if country.get("region_id") not in regions:
            return DemandIssue("INVALID_REGION_REFERENCE", "country references an unknown region", f"$.world_state.countries.{country_id}.region_id")
        population = country.get("population")
        latitude = country.get("centroid_latitude_microdegrees")
        longitude = country.get("centroid_longitude_microdegrees")
        if (
            isinstance(population, bool) or not isinstance(population, int) or population <= 0
            or isinstance(latitude, bool) or not isinstance(latitude, int) or not -90_000_000 <= latitude <= 90_000_000
            or isinstance(longitude, bool) or not isinstance(longitude, int) or not -180_000_000 <= longitude <= 180_000_000
        ):
            return DemandIssue("INVALID_COUNTRY_INPUT", "Model 4 requires positive population and valid integer microdegree centroid coordinates", f"$.world_state.countries.{country_id}")
    airports = state["airports"]
    members = []
    for airport_id in sorted(airports):
        airport = airports[airport_id]
        if airport.get("demand_allocation_member") is not True:
            continue
        members.append(airport_id)
        if airport.get("country_id") not in countries:
            return DemandIssue("INVALID_COUNTRY_INPUT", "allocation member must reference a supplied country", f"$.world_state.airports.{airport_id}.country_id")
        if airport["country_id"] not in effective:
            return DemandIssue("INVALID_MARKET_UNIVERSE", "allocation-member country must be effective on the pinned universe date", f"$.world_state.airports.{airport_id}.country_id")
        for field in ("population", "latitude_microdegrees", "longitude_microdegrees"):
            value = airport.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or (field == "population" and value <= 0):
                return DemandIssue("INVALID_MARKET_UNIVERSE", "allocation member has incomplete demand inputs", f"$.world_state.airports.{airport_id}.{field}")
    return None


def activate_model4(envelope, *, expected_revision, activation_provider=None):
    """Atomically activate Model 4 for a complete schema-2/3 Model 3 world."""
    current = 0
    if type(envelope) is dict:
        state = envelope.get("world_state")
        if type(state) is dict:
            demand = state.get("demand_state")
            if type(demand) is dict:
                current = demand.get("demand_model_revision", 0)
    validation = validate_world(envelope)
    if not validation.is_valid:
        return Model4ActivationResult("REJECTED", current, current, issues=_structured_validation_issues(validation))
    if envelope["metadata"]["save_schema_version"] not in (2, 3, 4):
        return _reject_activation(current, "INVALID_MARKET_UNIVERSE", "Model 4 activation requires schema 2 or 3")
    configuration = envelope["simulation"]["configuration"]["demand"]
    demand_state = envelope["world_state"]["demand_state"]
    if configuration["model_version"] != 3 or demand_state["model3_terminal_demand_revision"] is not None:
        return _reject_activation(current, "INCONSISTENT_DEMAND_REVISION", "Model 4 is already active or Model 3 is not activatable")
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision != current:
        return _reject_activation(current, "STALE_REVISION", "expected demand revision does not match", status="STALE_REVISION")

    try:
        candidate = deepcopy(envelope)
        if activation_provider is not None:
            provided = activation_provider(candidate)
            if provided is not None:
                if type(provided) is not dict:
                    raise TypeError("activation provider must return a detached envelope or None")
                candidate = deepcopy(provided)
        if (
            candidate.get("metadata", {}).get("lineage_id")
            != envelope["metadata"]["lineage_id"]
            or candidate.get("deterministic_state", {}).get("world_seed")
            != envelope["deterministic_state"]["world_seed"]
            or candidate.get("world_state", {}).get("directional_markets")
            != envelope["world_state"]["directional_markets"]
            or candidate.get("world_state", {}).get("demand_state", {}).get("processed_cohorts")
            != envelope["world_state"]["demand_state"]["processed_cohorts"]
            or candidate.get("world_state", {}).get("demand_state", {}).get("demand_model_revision")
            != current
        ):
            raise ValueError(
                "activation provider cannot replace lineage, seed, market identity, "
                "Model 3 cohorts, or the expected revision"
            )
        candidate_validation = validate_world(candidate)
        if not candidate_validation.is_valid:
            return Model4ActivationResult(
                "REJECTED",
                current,
                current,
                issues=_structured_validation_issues(candidate_validation),
            )
        issue = _hierarchy_issue(candidate)
        if issue is not None:
            return Model4ActivationResult("REJECTED", current, current, issues=(issue,))
        candidate_configuration = candidate["simulation"]["configuration"]["demand"]
        candidate_state = candidate["world_state"]["demand_state"]
        candidate_state["model3_terminal_demand_revision"] = current
        candidate_configuration["model_version"] = MODEL4_DEMAND_MODEL_VERSION
        candidate_configuration["configuration_version"] = MODEL4_DEMAND_CONFIGURATION_VERSION
        candidate_configuration["revision"] = current + 1
        candidate_state["demand_model_revision"] = current + 1
        candidate_state["input_fingerprint"] = calculate_model4_input_fingerprint(candidate)
        travel = candidate_configuration["travel_scope_configuration"]
        market_pack = candidate_configuration["market_pack_configuration"]
        context_id = f"model4-demand-revision-{current + 1}"
        context = {
            "revision_context_id": context_id,
            "demand_model_version": MODEL4_DEMAND_MODEL_VERSION,
            "demand_model_revision": current + 1,
            "configuration_version": candidate_configuration["configuration_version"],
            "configuration_revision": candidate_configuration["revision"],
            "universe_date": candidate_state["universe_date"],
            "travel_scope_configuration_version": travel["configuration_version"],
            "travel_scope_revision": travel["revision"],
            "market_pack_configuration_version": market_pack["configuration_version"],
            "market_pack_revision": market_pack["revision"],
            "daily_multiplier_min_bps": candidate_configuration["daily_multiplier_min_bps"],
            "daily_multiplier_max_bps": candidate_configuration["daily_multiplier_max_bps"],
            "country_reference_snapshot_version": travel["reference_snapshot_version"],
            "model4_input_fingerprint": candidate_state["input_fingerprint"],
        }
        context["context_fingerprint"] = calculate_model4_revision_context_fingerprint(context)
        candidate_state["model4_revision_contexts"][context_id] = context
        derived = rebuild_model4_indexes(candidate)
        if not derived.normalization_by_origin and any(airport.get("demand_allocation_member") is True for airport in candidate["world_state"]["airports"].values()):
            raise ArithmeticError("no Model 4 origin normalization was produced")
        final_validation = validate_world(candidate)
        if not final_validation.is_valid:
            return Model4ActivationResult("REJECTED", current, current, issues=_structured_validation_issues(final_validation))
    except Exception as exc:
        return _reject_activation(current, "DEMAND_ALLOCATION_FAILED", str(exc))
    _replace_envelope(envelope, candidate)
    return Model4ActivationResult("COMPLETED", current, current + 1, context_id)


def _conserved_allocations(amount, ids, raw_scores, *, residual_key):
    if not ids:
        return {}, None
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION
        denominator = sum(raw_scores, Decimal(0))
        if denominator <= 0 or not denominator.is_finite():
            raise ArithmeticError("allocation denominator must be positive and finite")
        residual_index = max(
            range(len(ids)),
            key=lambda index: (raw_scores[index], residual_key(ids[index])),
        )
        direct = [amount * score / denominator for score in raw_scores]
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION + len(str(len(ids))) + 8
        residual_amount = amount - sum((value for index, value in enumerate(direct) if index != residual_index), Decimal(0))
    if residual_amount < 0 or any(
        value < 0 or not value.is_finite() for value in direct
    ):
        raise ArithmeticError("allocation produced a negative or non-finite amount")
    allocations = {identity: (residual_amount if index == residual_index else direct[index]) for index, identity in enumerate(ids)}
    return allocations, AllocationNormalization(amount, denominator, ids[residual_index], residual_amount)


def _scope_allocations(pool, profile):
    weights = {scope: profile[_PROFILE_FIELD_BY_SCOPE[scope]] for scope in TRAVEL_SCOPES}
    residual_scope = max(TRAVEL_SCOPES, key=lambda scope: (weights[scope], scope))
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION
        direct = {scope: pool * Decimal(weights[scope]) / _BPS for scope in TRAVEL_SCOPES if scope != residual_scope}
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION + 10
        direct[residual_scope] = pool - sum(direct.values(), Decimal(0))
    return {scope: direct[scope] for scope in TRAVEL_SCOPES}


def _country_raw_score(configuration, origin_country, destination_country):
    distance = _distance_km(
        {"latitude_microdegrees": origin_country["centroid_latitude_microdegrees"], "longitude_microdegrees": origin_country["centroid_longitude_microdegrees"]},
        {"latitude_microdegrees": destination_country["centroid_latitude_microdegrees"], "longitude_microdegrees": destination_country["centroid_longitude_microdegrees"]},
    )
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION
        return (
            (Decimal(destination_country["population"]) / _PPM).sqrt()
            * (Decimal(1) / (Decimal(1) + distance / Decimal(configuration["distance_scale_km"])))
            * Decimal(destination_country["demand_attractiveness_bps"]) / _BPS
            * Decimal(destination_country["relationship_weight_bps"]) / _BPS
        )


def _airport_raw_score(configuration, origin, destination):
    distance = _distance_km(origin, destination)
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION
        return (
            (Decimal(destination["population"]) / _PPM).sqrt()
            * (Decimal(1) / (Decimal(1) + distance / Decimal(configuration["distance_scale_km"])))
            * Decimal(configuration["destination_type_weight_bps"][destination["demand_destination_type"]]) / _BPS
        )


def _source_fingerprint(envelope):
    state = envelope["world_state"]
    material = {
        "contract": _INDEX_CONTRACT,
        "lineage_id": envelope["metadata"]["lineage_id"],
        "demand_revision": state["demand_state"]["demand_model_revision"],
        "input_fingerprint": state["demand_state"]["input_fingerprint"],
        "market_identities": {market_id: state["directional_markets"][market_id] for market_id in sorted(state["directional_markets"])},
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _index_integrity_fingerprint(indexes):
    material = {
        "contract": _INDEX_CONTRACT,
        "lineage_id": indexes.lineage_id,
        "model_revision": indexes.model_revision,
        "input_fingerprint": indexes.input_fingerprint,
        "source_fingerprint": indexes.source_fingerprint,
        "universe_date": indexes.universe_date,
        "origin_airport_ids": indexes.origin_airport_ids,
        "market_by_pair": [
            (origin_id, destination_id, market_id)
            for (origin_id, destination_id), market_id in sorted(indexes.market_by_pair.items())
        ],
        "normalization_by_origin": {
            origin_id: {
                "origin_airport_id": origin.origin_airport_id,
                "origin_country_id": origin.origin_country_id,
                "origin_region_id": origin.origin_region_id,
                "origin_daily_booking_pool": str(origin.origin_daily_booking_pool),
                "scope_amounts": {key: str(value) for key, value in origin.scope_amounts.items()},
                "country_amounts": {key: str(value) for key, value in origin.country_amounts.items()},
                "region_amounts": {key: str(value) for key, value in origin.region_amounts.items()},
                "airport_normalization_by_country": {
                    country_id: {
                        "amount": str(normalization.amount),
                        "normalization_denominator": str(normalization.normalization_denominator),
                        "residual_id": normalization.residual_id,
                        "residual_amount": str(normalization.residual_amount),
                    }
                    for country_id, normalization in origin.airport_normalization_by_country.items()
                },
                "empty_scope_latent_amounts": {key: str(value) for key, value in origin.empty_scope_latent_amounts.items()},
                "unmaterialized_country_latent_amounts": {key: str(value) for key, value in origin.unmaterialized_country_latent_amounts.items()},
            }
            for origin_id, origin in indexes.normalization_by_origin.items()
        },
    }
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _derive_origin(envelope, origin_id, effective_country_ids, airports_by_country):
    state = envelope["world_state"]
    airports = state["airports"]
    countries = state["countries"]
    configuration = envelope["simulation"]["configuration"]["demand"]
    origin = airports[origin_id]
    home_country_id = origin["country_id"]
    home_country = countries[home_country_id]
    home_region_id = home_country["region_id"]
    travel = configuration["travel_scope_configuration"]
    profile = travel["country_overrides"].get(home_country_id, travel["default_profile"])
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION
        pool = Decimal(origin["population"]) * Decimal(configuration["daily_booker_rate_ppm"]) / _PPM
    scope_amounts = _scope_allocations(pool, profile)
    scope_countries = {
        "DOMESTIC": (home_country_id,),
        "HOME_REGION_INTERNATIONAL": tuple(country_id for country_id in effective_country_ids if country_id != home_country_id and countries[country_id]["region_id"] == home_region_id),
        "REST_OF_WORLD_INTERNATIONAL": tuple(country_id for country_id in effective_country_ids if countries[country_id]["region_id"] != home_region_id),
    }
    country_amounts = {}
    empty_scope_latent = {}
    for scope in TRAVEL_SCOPES:
        ids = scope_countries[scope]
        amount = scope_amounts[scope]
        if not ids:
            empty_scope_latent[scope] = amount
        elif scope == "DOMESTIC":
            country_amounts[home_country_id] = amount
        else:
            scores = [_country_raw_score(configuration, home_country, countries[country_id]) for country_id in ids]
            allocations, _ = _conserved_allocations(amount, ids, scores, residual_key=lambda identity: identity)
            country_amounts.update(allocations)
    region_amounts = {}
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION + len(str(max(1, len(country_amounts)))) + 8
        for country_id, amount in country_amounts.items():
            region_id = countries[country_id]["region_id"]
            region_amounts[region_id] = region_amounts.get(region_id, Decimal(0)) + amount
    airport_normalizations = {}
    unmaterialized = {}
    for country_id, country_amount in sorted(country_amounts.items()):
        destination_ids = tuple(airport_id for airport_id in airports_by_country.get(country_id, ()) if airport_id != origin_id)
        if not destination_ids:
            unmaterialized[country_id] = country_amount
            continue
        scores = [_airport_raw_score(configuration, origin, airports[destination_id]) for destination_id in destination_ids]
        _allocations, normalization = _conserved_allocations(country_amount, destination_ids, scores, residual_key=lambda identity: identity)
        airport_normalizations[country_id] = normalization
    return Model4OriginNormalization(
        origin_id,
        home_country_id,
        home_region_id,
        pool,
        MappingProxyType(scope_amounts),
        MappingProxyType(dict(sorted(country_amounts.items()))),
        MappingProxyType(dict(sorted(region_amounts.items()))),
        MappingProxyType(dict(sorted(airport_normalizations.items()))),
        MappingProxyType(dict(sorted(empty_scope_latent.items()))),
        MappingProxyType(dict(sorted(unmaterialized.items()))),
    )


def rebuild_model4_indexes(envelope, *, indexes=None):
    validation = validate_world(envelope)
    if not validation.is_valid:
        raise ValueError("cannot derive Model 4 indexes for an invalid world")
    configuration = envelope["simulation"]["configuration"]["demand"]
    if configuration["model_version"] != MODEL4_DEMAND_MODEL_VERSION:
        raise ValueError("Model 4 is not active")
    state = envelope["world_state"]
    source = _source_fingerprint(envelope)
    origins = tuple(airport_id for airport_id, airport in sorted(state["airports"].items()) if airport.get("demand_allocation_member") is True)
    if (
        type(indexes) is Model4DemandIndexes
        and indexes.lineage_id == envelope["metadata"]["lineage_id"]
        and indexes.model_revision == state["demand_state"]["demand_model_revision"]
        and indexes.input_fingerprint == state["demand_state"]["input_fingerprint"]
        and indexes.source_fingerprint == source
        and indexes.universe_date == state["demand_state"]["universe_date"]
        and indexes.origin_airport_ids == origins
        and tuple(indexes.normalization_by_origin) == origins
        and _index_structure_valid(indexes, envelope)
    ):
        return indexes
    universe_date = state["demand_state"]["universe_date"]
    effective_countries = tuple(country_id for country_id, country in sorted(state["countries"].items()) if _effective(country, universe_date))
    airports_by_country = {}
    for airport_id in origins:
        airports_by_country.setdefault(state["airports"][airport_id]["country_id"], []).append(airport_id)
    market_by_pair = MappingProxyType({(market["origin_airport_id"], market["destination_airport_id"]): market_id for market_id, market in sorted(state["directional_markets"].items())})
    normalizations = {origin_id: _derive_origin(envelope, origin_id, effective_countries, airports_by_country) for origin_id in origins}
    indexes = Model4DemandIndexes(
        envelope["metadata"]["lineage_id"],
        state["demand_state"]["demand_model_revision"],
        state["demand_state"]["input_fingerprint"],
        source,
        universe_date,
        origins,
        market_by_pair,
        MappingProxyType(normalizations),
        "",
    )
    return replace(indexes, integrity_fingerprint=_index_integrity_fingerprint(indexes))


def _index_structure_valid(indexes, envelope):
    airports = envelope["world_state"]["airports"]
    countries = envelope["world_state"]["countries"]
    expected_market_by_pair = {
        (market["origin_airport_id"], market["destination_airport_id"]): market_id
        for market_id, market in sorted(
            envelope["world_state"]["directional_markets"].items()
        )
    }
    if (
        type(indexes.market_by_pair) is not MappingProxyType
        or dict(indexes.market_by_pair) != expected_market_by_pair
        or type(indexes.normalization_by_origin) is not MappingProxyType
    ):
        return False
    try:
        if indexes.integrity_fingerprint != _index_integrity_fingerprint(indexes):
            return False
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
    for origin_id, origin in indexes.normalization_by_origin.items():
        if (
            not isinstance(origin, Model4OriginNormalization)
            or origin.origin_airport_id != origin_id
            or origin_id not in airports
            or origin.origin_country_id != airports[origin_id].get("country_id")
            or origin.origin_country_id not in countries
            or origin.origin_region_id != countries[origin.origin_country_id].get("region_id")
            or not isinstance(origin.origin_daily_booking_pool, Decimal)
            or not origin.origin_daily_booking_pool.is_finite()
            or origin.origin_daily_booking_pool < 0
            or tuple(origin.scope_amounts) != TRAVEL_SCOPES
            or any(
                type(mapping) is not MappingProxyType
                for mapping in (
                    origin.scope_amounts,
                    origin.country_amounts,
                    origin.region_amounts,
                    origin.airport_normalization_by_country,
                    origin.empty_scope_latent_amounts,
                    origin.unmaterialized_country_latent_amounts,
                )
            )
        ):
            return False
        decimal_mappings = (
            origin.scope_amounts,
            origin.country_amounts,
            origin.region_amounts,
            origin.empty_scope_latent_amounts,
            origin.unmaterialized_country_latent_amounts,
        )
        if any(
            not isinstance(value, Decimal) or not value.is_finite() or value < 0
            for mapping in decimal_mappings
            for value in mapping.values()
        ):
            return False
        effective_country_ids = tuple(
            country_id
            for country_id, country in sorted(countries.items())
            if _effective(country, indexes.universe_date)
        )
        scope_country_ids = {
            "DOMESTIC": (origin.origin_country_id,),
            "HOME_REGION_INTERNATIONAL": tuple(
                country_id
                for country_id in effective_country_ids
                if country_id != origin.origin_country_id
                and countries[country_id]["region_id"] == origin.origin_region_id
            ),
            "REST_OF_WORLD_INTERNATIONAL": tuple(
                country_id
                for country_id in effective_country_ids
                if countries[country_id]["region_id"] != origin.origin_region_id
            ),
        }
        if set(origin.country_amounts) != {
            country_id
            for country_ids in scope_country_ids.values()
            for country_id in country_ids
        }:
            return False
        with _fixed_decimal_context(
            _PRECISION + len(str(max(1, len(countries)))) + 8
        ):
            for scope, country_ids in scope_country_ids.items():
                if country_ids:
                    if scope in origin.empty_scope_latent_amounts or sum(
                        (origin.country_amounts.get(country_id, Decimal(0)) for country_id in country_ids),
                        Decimal(0),
                    ) != origin.scope_amounts[scope]:
                        return False
                elif origin.empty_scope_latent_amounts.get(scope) != origin.scope_amounts[scope]:
                    return False
            expected_regions = {}
            for country_id, amount in origin.country_amounts.items():
                if country_id not in countries:
                    return False
                region_id = countries[country_id]["region_id"]
                expected_regions[region_id] = expected_regions.get(region_id, Decimal(0)) + amount
            if expected_regions != dict(origin.region_amounts):
                return False
        detailed_country_ids = set(origin.airport_normalization_by_country)
        latent_country_ids = set(origin.unmaterialized_country_latent_amounts)
        if (
            detailed_country_ids & latent_country_ids
            or detailed_country_ids | latent_country_ids != set(origin.country_amounts)
        ):
            return False
        if any(
            amount != origin.country_amounts.get(country_id)
            for country_id, amount in origin.unmaterialized_country_latent_amounts.items()
        ):
            return False
        for country_id, normalization in origin.airport_normalization_by_country.items():
            if (
                country_id not in countries
                or not isinstance(normalization, AllocationNormalization)
                or not isinstance(normalization.amount, Decimal)
                or not normalization.amount.is_finite()
                or normalization.amount < 0
                or not isinstance(normalization.normalization_denominator, Decimal)
                or not normalization.normalization_denominator.is_finite()
                or normalization.normalization_denominator <= 0
                or normalization.residual_id not in airports
                or airports[normalization.residual_id].get("country_id") != country_id
                or airports[normalization.residual_id].get("demand_allocation_member") is not True
                or normalization.residual_id == origin_id
                or not isinstance(normalization.residual_amount, Decimal)
                or not normalization.residual_amount.is_finite()
                or normalization.residual_amount < 0
                or normalization.residual_amount > normalization.amount
                or normalization.amount != origin.country_amounts.get(country_id)
            ):
                return False
    return True


def _airport_leaf(envelope, indexes, origin_id, destination_id):
    normalization = indexes.normalization_by_origin[origin_id]
    destination = envelope["world_state"]["airports"][destination_id]
    country_normalization = normalization.airport_normalization_by_country.get(destination["country_id"])
    if country_normalization is None:
        return None
    if destination_id == country_normalization.residual_id:
        return country_normalization.residual_amount
    score = _airport_raw_score(envelope["simulation"]["configuration"]["demand"], envelope["world_state"]["airports"][origin_id], destination)
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION
        return country_normalization.amount * score / country_normalization.normalization_denominator


def project_model4_origin(envelope, origin_airport_id, *, indexes=None):
    indexes = rebuild_model4_indexes(envelope, indexes=indexes)
    if origin_airport_id not in indexes.normalization_by_origin:
        raise ValueError("origin is not a Model 4 allocation member")
    normalization = indexes.normalization_by_origin[origin_airport_id]
    airports = envelope["world_state"]["airports"]
    leaves = {}
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION + len(str(max(1, len(indexes.origin_airport_ids)))) + 8
        unavailable = Decimal(0)
        unmaterialized_market = Decimal(0)
        latent_airport = Decimal(0)
        materialized = Decimal(0)
        for destination_id in indexes.origin_airport_ids:
            if destination_id == origin_airport_id:
                continue
            leaf = _airport_leaf(envelope, indexes, origin_airport_id, destination_id)
            if leaf is None:
                continue
            leaves[destination_id] = leaf
            has_market = (origin_airport_id, destination_id) in indexes.market_by_pair
            available = _airport_available(airports[destination_id], envelope["simulation"]["time_utc"][:10])
            if has_market and available:
                materialized += leaf
            else:
                latent_airport += leaf
            if not available:
                unavailable += leaf
            if not has_market:
                unmaterialized_market += leaf
        latent_unmaterialized = sum(normalization.unmaterialized_country_latent_amounts.values(), Decimal(0))
        empty_scope = sum(normalization.empty_scope_latent_amounts.values(), Decimal(0))
        conservation_total = materialized + latent_airport + latent_unmaterialized + empty_scope
    return deepcopy({
        "origin_airport_id": origin_airport_id,
        "origin_daily_booking_pool": normalization.origin_daily_booking_pool,
        "scope_amounts": dict(normalization.scope_amounts),
        "country_amounts": dict(normalization.country_amounts),
        "region_amounts": dict(normalization.region_amounts),
        "airport_leaf_amounts": leaves,
        "latent": {
            "empty_scope_amounts": dict(normalization.empty_scope_latent_amounts),
            "unmaterialized_country_amounts": dict(normalization.unmaterialized_country_latent_amounts),
            "airport_leaf_amount": latent_airport,
            "unavailable_airport_leaf_amount": unavailable,
            "unmaterialized_market_airport_leaf_amount": unmaterialized_market,
        },
        "conservation_total": conservation_total,
        "materialized_leaf_total": materialized,
    })


def _pair_projection_from_indexes(envelope, indexes, origin_airport_id, destination_airport_id):
    market_id = indexes.market_by_pair.get((origin_airport_id, destination_airport_id))
    if market_id is None:
        raise ValueError("directional market is not materialized")
    leaf = _airport_leaf(envelope, indexes, origin_airport_id, destination_airport_id)
    if leaf is None:
        raise ValueError("destination has no Model 4 allocation leaf")
    pool = indexes.normalization_by_origin[origin_airport_id].origin_daily_booking_pool
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION
        share = leaf / pool if pool else Decimal(0)
    return deepcopy({
        "market_id": market_id,
        "origin_airport_id": origin_airport_id,
        "destination_airport_id": destination_airport_id,
        "base_daily_bookers": leaf,
        "diagnostic_pair_share": share,
        "available": _airport_available(envelope["world_state"]["airports"][destination_airport_id], envelope["simulation"]["time_utc"][:10]),
    })


def project_model4_pair(envelope, origin_airport_id, destination_airport_id, *, indexes=None):
    indexes = rebuild_model4_indexes(envelope, indexes=indexes)
    return _pair_projection_from_indexes(
        envelope, indexes, origin_airport_id, destination_airport_id
    )


def _airport_available(airport, universe_date):
    return (
        airport.get("passenger_demand_eligible") is True
        and (airport.get("active_from_date") is None or universe_date >= airport["active_from_date"])
        and (airport.get("active_until_date") is None or universe_date < airport["active_until_date"])
    )


def _current_context(envelope):
    revision = envelope["world_state"]["demand_state"]["demand_model_revision"]
    matches = [(context_id, context) for context_id, context in envelope["world_state"]["demand_state"]["model4_revision_contexts"].items() if context["demand_model_revision"] == revision]
    if len(matches) != 1:
        raise ValueError("current Model 4 revision context is missing or ambiguous")
    return matches[0]


def _seed_material(envelope, market_id, cohort_date, canonical, *, purpose):
    configuration = envelope["simulation"]["configuration"]["demand"]
    travel = configuration["travel_scope_configuration"]
    pack = configuration["market_pack_configuration"]
    return json.dumps({
        "purpose": purpose,
        "rounding_policy": DEMAND_ROUNDING_POLICY,
        "world_seed": envelope["deterministic_state"]["world_seed"],
        "demand_model_version": MODEL4_DEMAND_MODEL_VERSION,
        "demand_configuration_version": configuration["configuration_version"],
        "travel_scope_configuration_version": travel["configuration_version"],
        "travel_scope_revision": travel["revision"],
        "country_reference_snapshot_version": travel["reference_snapshot_version"],
        "universe_date": envelope["world_state"]["demand_state"]["universe_date"],
        "market_pack_configuration_version": pack["configuration_version"],
        "market_id": market_id,
        "cohort_date": cohort_date,
        "daily_multipliers_bps": canonical,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _model4_record(envelope, indexes, market_id, cohort_date, multipliers):
    market = envelope["world_state"]["directional_markets"].get(market_id)
    if not isinstance(market, Mapping):
        raise ValueError("market does not exist")
    pair = _pair_projection_from_indexes(envelope, indexes, market["origin_airport_id"], market["destination_airport_id"])
    if not pair["available"]:
        raise ValueError("market destination is unavailable")
    configuration = envelope["simulation"]["configuration"]["demand"]
    canonical, composed = _compose_daily_multipliers(configuration, multipliers)
    context_id, _context = _current_context(envelope)
    with _fixed_decimal_context() as context:
        context.prec = _PRECISION
        actual = _resolve_fraction(pair["base_daily_bookers"] * composed, _seed_material(envelope, market_id, cohort_date, canonical, purpose="MODEL4_PAIR_DAILY_INTENT_V1"))
        origin_normalization = indexes.normalization_by_origin[market["origin_airport_id"]]
        scope_bookers = {
            scope: _resolve_fraction(amount * composed, _seed_material(envelope, market_id, cohort_date, canonical, purpose=f"MODEL4_SCOPE_DAILY_INTENT_V1:{scope}"))
            for scope, amount in origin_normalization.scope_amounts.items()
        }
        composite_ppm = int((composed * _PPM).to_integral_value(rounding=ROUND_HALF_EVEN))
    payload = {
        "cohort_key": f"{market_id}@{cohort_date}",
        "market_id": market_id,
        "cohort_date": cohort_date,
        "demand_model_revision": indexes.model_revision,
        "revision_context_id": context_id,
        "daily_multipliers_bps": canonical,
        "composite_multiplier_ppm": composite_ppm,
        "travel_scope_bookers": scope_bookers,
        "actual_daily_bookers": actual,
        "rounding_policy": DEMAND_ROUNDING_POLICY,
    }
    wrapper = {"contract": MODEL4_TRAVEL_SCOPE_COHORT_V1, "payload": payload}
    payload["resolution_fingerprint"] = calculate_model4_cohort_fingerprint(envelope, wrapper)
    return wrapper, pair, canonical


def _existing_resolution(record, market_id, cohort_date):
    payload = record["payload"]
    return CohortResolution(market_id, cohort_date, payload["actual_daily_bookers"], True, payload["demand_model_revision"])


def resolve_model4_daily_cohort(envelope, market_id, cohort_date, *, multipliers=None, indexes=None):
    validation = validate_world(envelope)
    if not validation.is_valid:
        raise ValueError(validation.errors[0].message)
    key = f"{market_id}@{cohort_date}"
    existing = envelope["world_state"]["demand_state"]["processed_cohorts"].get(key)
    if existing is not None:
        return _existing_resolution(existing, market_id, cohort_date)
    raise ValueError(
        "UNSUPPORTED_COMPATIBILITY_COMMAND: new Model 4 markers require the prospective active-market command"
    )


def resolve_model4_active_daily_cohorts(envelope, cohort_date, *, multipliers_by_market=None, indexes=None, activation_start_utc=None, activation_end_utc=None, activation_providers=None, dated_flight_indexes=None):
    from .activation import discover_active_market_ids

    multipliers_by_market = {} if multipliers_by_market is None else multipliers_by_market
    revision = envelope.get("world_state", {}).get("demand_state", {}).get("demand_model_revision", 0)
    pack_revision = envelope.get("simulation", {}).get("configuration", {}).get("demand", {}).get("market_pack_configuration", {}).get("revision", 0)
    validation = validate_world(envelope)
    if not validation.is_valid:
        return Model4ActiveDayResult("REJECTED", str(cohort_date), revision, pack_revision, issues=_validation_issues(validation))
    if not isinstance(multipliers_by_market, Mapping):
        return Model4ActiveDayResult("REJECTED", str(cohort_date), revision, pack_revision, issues=(DemandIssue("INVALID_MULTIPLIERS", "must be a market mapping"),))
    try:
        parsed = date.fromisoformat(cohort_date)
        if parsed.isoformat() != cohort_date or cohort_date != envelope["simulation"]["time_utc"][:10]:
            raise ValueError("Model 4 active processing is limited to the current simulation UTC date")
        derived = rebuild_model4_indexes(envelope, indexes=indexes)
        active_ids = tuple(market_id for market_id in discover_active_market_ids(envelope, start_utc=activation_start_utc, end_utc=activation_end_utc, providers=activation_providers, dated_flight_indexes=dated_flight_indexes, require_model4_pack_authority=True) if market_id in envelope["world_state"]["directional_markets"])
        unknown = [key for key in multipliers_by_market if key not in active_ids]
        if unknown:
            raise ValueError(f"modifier markets are not active: {sorted(map(repr, unknown))}")
        candidate = deepcopy(envelope)
        records = candidate["world_state"]["demand_state"]["processed_cohorts"]
        intents = []
        cohorts = []
        for market_id in active_ids:
            key = f"{market_id}@{cohort_date}"
            existing = records.get(key)
            if existing is not None:
                payload = existing["payload"]
                market = candidate["world_state"]["directional_markets"][market_id]
                pair = _pair_projection_from_indexes(candidate, derived, market["origin_airport_id"], market["destination_airport_id"])
                canonical = deepcopy(payload.get("daily_multipliers_bps", {category: 10_000 for category in DEMAND_MULTIPLIER_CATEGORIES}))
                reused = True
            else:
                wrapper, pair, canonical = _model4_record(candidate, derived, market_id, cohort_date, multipliers_by_market.get(market_id))
                records[key] = wrapper
                payload = wrapper["payload"]
                reused = False
            baseline = pair["base_daily_bookers"]
            if not isinstance(baseline, Decimal):
                raise TypeError("Model 4 pair baseline must be Decimal")
            cohorts.append(CohortResolution(market_id, cohort_date, payload["actual_daily_bookers"], reused, payload["demand_model_revision"]))
            intents.append(Model4ActiveMarketIntent(market_id, baseline, MappingProxyType(dict(canonical)), payload["actual_daily_bookers"], reused))
        final = validate_world(candidate)
        if not final.is_valid:
            return Model4ActiveDayResult("REJECTED", cohort_date, revision, pack_revision, issues=_validation_issues(final))
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        message = str(exc)
        code = "UNAVAILABLE_DEMAND_MARKET" if message.startswith("UNAVAILABLE_DEMAND_MARKET:") else "DEMAND_ALLOCATION_FAILED"
        return Model4ActiveDayResult("REJECTED", str(cohort_date), revision, pack_revision, issues=(DemandIssue(code, message),))
    _replace_envelope(envelope, candidate)
    return Model4ActiveDayResult("COMPLETED", cohort_date, revision, pack_revision, active_ids, tuple(intents), tuple(cohorts))


def reject_model4_world_cohorts(envelope, cohort_date):
    revision = envelope.get("world_state", {}).get("demand_state", {}).get("demand_model_revision", 0)
    return WorldCohortResult("REJECTED", str(cohort_date), issues=(DemandIssue("UNSUPPORTED_COMPATIBILITY_COMMAND", f"whole-world cohort creation is unsupported for active Model 4 revision {revision}"),))
