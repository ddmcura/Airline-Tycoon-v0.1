"""Authoritative-boundary Stage 1 world passenger demand.

Only demand versions, reference inputs, directional market identities, and
resolved cohort markers are persistent. Formula tables and indexes returned by
this module are deterministic runtime derivations.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
import hashlib
import json
import math
from types import MappingProxyType
from typing import Mapping

from game.world_state.ids import allocate_id
from game.world_state.demand_fingerprint import (
    calculate_demand_cohort_fingerprint,
    calculate_demand_input_fingerprint,
)
from game.world_state.serialization import json_compatibility_error
from game.world_state.schema import (
    DEMAND_MODEL_VERSION,
    DEMAND_MULTIPLIER_CATEGORIES,
    DEMAND_ROUNDING_POLICY,
)
from game.world_state.validation import validate_world


_BPS = Decimal(10_000)
_PPM = Decimal(1_000_000)
_SCORE_PRECISION = 50
_SOURCE_FINGERPRINT_CONTRACT = "STAGE1_DEMAND_INDEX_SHA256_JSON_V1"
_AIRPORT_DEMAND_FIELDS = frozenset(
    {
        "passenger_demand_eligible",
        "population",
        "latitude_microdegrees",
        "longitude_microdegrees",
        "country_reference",
        "demand_destination_type",
        "active_from_date",
        "active_until_date",
    }
)
_CONFIGURATION_UPDATE_FIELDS = frozenset(
    {
        "configuration_version",
        "daily_booker_rate_ppm",
        "distance_scale_km",
        "destination_type_weight_bps",
        "same_country_weight_bps",
        "international_weight_bps",
        "relationship_weight_bps",
        "daily_multiplier_min_bps",
        "daily_multiplier_max_bps",
    }
)


@dataclass(frozen=True)
class DemandIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class PairDemand:
    market_id: str
    origin_airport_id: str
    destination_airport_id: str
    origin_daily_booking_pool: Decimal
    distance_km: Decimal
    raw_pair_score: Decimal
    destination_pair_share: Decimal
    base_daily_bookers: Decimal


@dataclass(frozen=True)
class DemandIndexes:
    """Disposable, immutable demand derivation for one model revision."""

    lineage_id: str
    model_version: int
    model_revision: int
    universe_date: str
    source_fingerprint: str
    eligible_airport_ids: tuple[str, ...]
    by_market: Mapping[str, PairDemand]
    market_by_pair: Mapping[tuple[str, str], str]
    markets_by_origin: Mapping[str, tuple[str, ...]]

    def pair(self, origin_airport_id, destination_airport_id):
        market_id = self.market_by_pair.get(
            (origin_airport_id, destination_airport_id)
        )
        return self.by_market.get(market_id) if market_id is not None else None


@dataclass(frozen=True)
class DemandBuildResult:
    status: str
    indexes: DemandIndexes | None = None
    created_market_ids: tuple[str, ...] = ()
    cache_reused: bool = False
    issues: tuple[DemandIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


@dataclass(frozen=True)
class DemandRevisionResult:
    status: str
    previous_revision: int
    revision: int
    issues: tuple[DemandIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


@dataclass(frozen=True)
class CohortResolution:
    market_id: str
    cohort_date: str
    actual_daily_bookers: int
    reused: bool
    demand_model_revision: int


@dataclass(frozen=True)
class WorldCohortResult:
    status: str
    cohort_date: str
    cohorts: tuple[CohortResolution, ...] = ()
    issues: tuple[DemandIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


def _replace_envelope(target, candidate):
    committed = deepcopy(candidate)
    target.clear()
    target.update(committed)


def _validation_issues(validation):
    return tuple(
        DemandIssue(issue.code, issue.message, issue.path)
        for issue in validation.errors
    )


def _canonical_date(value, field_name="cohort_date"):
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be canonical YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be canonical YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} must be canonical YYYY-MM-DD")
    return parsed


def _airport_is_eligible(airport, universe_date):
    if airport.get("passenger_demand_eligible") is not True:
        return False
    active_from = airport.get("active_from_date")
    active_until = airport.get("active_until_date")
    if active_from is not None and universe_date < active_from:
        return False
    if active_until is not None and universe_date >= active_until:
        return False
    return True


def _eligible_airport_ids(envelope):
    universe_date = envelope["world_state"]["demand_state"]["universe_date"]
    _canonical_date(universe_date, "universe_date")
    airports = envelope["world_state"]["airports"]
    return tuple(
        airport_id
        for airport_id in sorted(airports)
        if _airport_is_eligible(airports[airport_id], universe_date)
    )


def _require_valid_world(envelope):
    validation = validate_world(envelope)
    if not validation.is_valid:
        first = validation.errors[0]
        raise ValueError(f"{first.path}: {first.message}")


def eligible_airport_ids(envelope):
    """Return the validated, revision-pinned passenger-demand universe."""
    _require_valid_world(envelope)
    return _eligible_airport_ids(envelope)


def _distance_km(origin, destination):
    lat1 = math.radians(origin["latitude_microdegrees"] / 1_000_000)
    lon1 = math.radians(origin["longitude_microdegrees"] / 1_000_000)
    lat2 = math.radians(destination["latitude_microdegrees"] / 1_000_000)
    lon2 = math.radians(destination["longitude_microdegrees"] / 1_000_000)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    haversine = min(1.0, max(0.0, haversine))
    kilometres = 6_371 * 2 * math.asin(math.sqrt(haversine))
    return Decimal(str(kilometres)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_EVEN
    )


def calculate_origin_daily_booking_pool(envelope, origin_airport_id):
    _require_valid_world(envelope)
    airports = envelope["world_state"]["airports"]
    if origin_airport_id not in airports:
        raise ValueError("origin_airport_id must reference an existing airport")
    airport = airports[origin_airport_id]
    if origin_airport_id not in _eligible_airport_ids(envelope):
        raise ValueError("origin airport is not eligible for passenger demand")
    rate = envelope["simulation"]["configuration"]["demand"][
        "daily_booker_rate_ppm"
    ]
    with localcontext() as context:
        context.prec = _SCORE_PRECISION
        return Decimal(airport["population"]) * Decimal(rate) / _PPM


def _raw_pair_score(configuration, origin, destination, *, distance=None):
    with localcontext() as context:
        context.prec = _SCORE_PRECISION
        population_pull = (
            Decimal(destination["population"]) / Decimal(1_000_000)
        ).sqrt()
        distance = _distance_km(origin, destination) if distance is None else distance
        distance_weight = Decimal(1) / (
            Decimal(1)
            + distance / Decimal(configuration["distance_scale_km"])
        )
        destination_weight = Decimal(
            configuration["destination_type_weight_bps"][
                destination["demand_destination_type"]
            ]
        ) / _BPS
        geography_weight = Decimal(
            configuration[
                "same_country_weight_bps"
                if origin["country_reference"] == destination["country_reference"]
                else "international_weight_bps"
            ]
        ) / _BPS
        relationship_weight = Decimal(
            configuration["relationship_weight_bps"]
        ) / _BPS
        return (
            population_pull
            * distance_weight
            * destination_weight
            * geography_weight
            * relationship_weight
        )


def calculate_raw_pair_score(envelope, origin_airport_id, destination_airport_id):
    """Calculate the approved Model 3 score before origin normalization."""
    _require_valid_world(envelope)
    if origin_airport_id == destination_airport_id:
        raise ValueError("origin and destination must differ")
    airports = envelope["world_state"]["airports"]
    eligible = set(_eligible_airport_ids(envelope))
    if origin_airport_id not in eligible or destination_airport_id not in eligible:
        raise ValueError("both airports must be in the eligible demand universe")
    origin = airports[origin_airport_id]
    destination = airports[destination_airport_id]
    configuration = envelope["simulation"]["configuration"]["demand"]
    return _raw_pair_score(configuration, origin, destination)


def _source_fingerprint(envelope):
    state = envelope["world_state"]
    airport_fields = (
        "passenger_demand_eligible",
        "population",
        "latitude_microdegrees",
        "longitude_microdegrees",
        "country_reference",
        "demand_destination_type",
        "active_from_date",
        "active_until_date",
        "demand_input_revision",
    )
    material = {
        "fingerprint_contract": _SOURCE_FINGERPRINT_CONTRACT,
        "lineage_id": envelope["metadata"]["lineage_id"],
        "configuration": envelope["simulation"]["configuration"]["demand"],
        "demand_state": {
            "demand_model_revision": state["demand_state"][
                "demand_model_revision"
            ],
            "universe_date": state["demand_state"]["universe_date"],
        },
        "airports": {
            airport_id: {
                field: state["airports"][airport_id].get(field)
                for field in airport_fields
            }
            for airport_id in sorted(state["airports"])
        },
        "markets": {
            market_id: {
                "origin_airport_id": market.get("origin_airport_id"),
                "destination_airport_id": market.get("destination_airport_id"),
            }
            for market_id, market in sorted(state["directional_markets"].items())
        },
    }
    try:
        encoded = json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ValueError(
            "demand index fingerprint inputs must be finite canonical JSON values"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _derive_indexes(envelope, fingerprint=None):
    state = envelope["world_state"]
    airports = state["airports"]
    eligible = _eligible_airport_ids(envelope)
    market_by_pair = {
        (market["origin_airport_id"], market["destination_airport_id"]): market_id
        for market_id, market in state["directional_markets"].items()
    }
    by_market = {}
    markets_by_origin = {}
    configuration = envelope["simulation"]["configuration"]["demand"]
    with localcontext() as context:
        context.prec = _SCORE_PRECISION
        for origin_id in eligible:
            destinations = tuple(
                destination_id
                for destination_id in eligible
                if destination_id != origin_id
            )
            if not destinations:
                continue
            distances = [
                _distance_km(airports[origin_id], airports[destination_id])
                for destination_id in destinations
            ]
            raw_scores = [
                _raw_pair_score(
                    configuration,
                    airports[origin_id],
                    airports[destination_id],
                    distance=distance,
                )
                for destination_id, distance in zip(destinations, distances)
            ]
            total = sum(raw_scores, Decimal(0))
            if total <= 0:
                raise ValueError(f"origin {origin_id} has no positive pair scores")
            shares = [raw_score / total for raw_score in raw_scores]
            residual_index = max(
                range(len(destinations)),
                key=lambda index: (raw_scores[index], destinations[index]),
            )
            with localcontext() as conservation_context:
                conservation_context.prec = (
                    _SCORE_PRECISION + len(str(len(shares))) + 2
                )
                other_total = sum(
                    (
                        share
                        for index, share in enumerate(shares)
                        if index != residual_index
                    ),
                    Decimal(0),
                )
                shares[residual_index] = Decimal(1) - other_total
            if any(share < 0 for share in shares):
                raise ArithmeticError("normalization produced a negative pair share")
            origin_pool = (
                Decimal(airports[origin_id]["population"])
                * Decimal(configuration["daily_booker_rate_ppm"])
                / _PPM
            )
            origin_market_ids = []
            for destination_id, distance, raw_score, share in zip(
                destinations, distances, raw_scores, shares
            ):
                market_id = market_by_pair[(origin_id, destination_id)]
                pair = PairDemand(
                    market_id=market_id,
                    origin_airport_id=origin_id,
                    destination_airport_id=destination_id,
                    origin_daily_booking_pool=origin_pool,
                    distance_km=distance,
                    raw_pair_score=raw_score,
                    destination_pair_share=share,
                    base_daily_bookers=origin_pool * share,
                )
                by_market[market_id] = pair
                origin_market_ids.append(market_id)
            markets_by_origin[origin_id] = tuple(origin_market_ids)
    demand_state = state["demand_state"]
    return DemandIndexes(
        lineage_id=envelope["metadata"]["lineage_id"],
        model_version=configuration["model_version"],
        model_revision=demand_state["demand_model_revision"],
        universe_date=demand_state["universe_date"],
        source_fingerprint=fingerprint or _source_fingerprint(envelope),
        eligible_airport_ids=eligible,
        by_market=MappingProxyType(dict(sorted(by_market.items()))),
        market_by_pair=MappingProxyType(
            dict(sorted(market_by_pair.items(), key=lambda item: item[0]))
        ),
        markets_by_origin=MappingProxyType(dict(sorted(markets_by_origin.items()))),
    )


def rebuild_demand_indexes(envelope):
    """Rebuild derived values without creating missing market authority."""
    validation = validate_world(envelope)
    if not validation.is_valid:
        raise ValueError("cannot rebuild demand indexes for an invalid world")
    eligible = _eligible_airport_ids(envelope)
    represented_pairs = {
        (market["origin_airport_id"], market["destination_airport_id"])
        for market in envelope["world_state"]["directional_markets"].values()
    }
    missing = [
        (origin, destination)
        for origin in eligible
        for destination in eligible
        if origin != destination and (origin, destination) not in represented_pairs
    ]
    if missing:
        raise ValueError("demand market authority is incomplete; recalculate first")
    return _derive_indexes(envelope)


def calculate_world_demand(envelope, *, indexes=None):
    """Atomically create missing world markets and calculate all baselines."""
    validation = validate_world(envelope)
    if not validation.is_valid:
        return DemandBuildResult(
            "REJECTED", issues=_validation_issues(validation)
        )
    fingerprint = _source_fingerprint(envelope)
    configuration = envelope["simulation"]["configuration"]["demand"]
    demand_state = envelope["world_state"]["demand_state"]
    if (
        isinstance(indexes, DemandIndexes)
        and indexes.source_fingerprint == fingerprint
        and indexes.lineage_id == envelope["metadata"]["lineage_id"]
        and indexes.model_version == configuration["model_version"]
        and indexes.model_revision == demand_state["demand_model_revision"]
        and indexes.universe_date == demand_state["universe_date"]
        and indexes.eligible_airport_ids == _eligible_airport_ids(envelope)
    ):
        return DemandBuildResult("COMPLETED", indexes, cache_reused=True)

    candidate = deepcopy(envelope)
    eligible = _eligible_airport_ids(candidate)
    markets = candidate["world_state"]["directional_markets"]
    represented = {
        (record["origin_airport_id"], record["destination_airport_id"])
        for record in markets.values()
    }
    created = []
    try:
        for origin_id in eligible:
            for destination_id in eligible:
                pair = (origin_id, destination_id)
                if origin_id == destination_id or pair in represented:
                    continue
                market_id = allocate_id(candidate, "market")
                markets[market_id] = {
                    "market_id": market_id,
                    "origin_airport_id": origin_id,
                    "destination_airport_id": destination_id,
                }
                represented.add(pair)
                created.append(market_id)
        candidate_validation = validate_world(candidate)
        if not candidate_validation.is_valid:
            return DemandBuildResult(
                "REJECTED", issues=_validation_issues(candidate_validation)
            )
        derived = _derive_indexes(candidate)
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        return DemandBuildResult(
            "REJECTED", issues=(DemandIssue("DEMAND_CALCULATION_FAILED", str(exc)),)
        )
    _replace_envelope(envelope, candidate)
    return DemandBuildResult(
        "COMPLETED", derived, tuple(created), cache_reused=False
    )


def recalculate_origin_demand(envelope, origin_airport_id, *, indexes=None):
    """Build the full stable universe and return one origin's derived pairs."""
    result = calculate_world_demand(envelope, indexes=indexes)
    if not result.succeeded:
        return result
    if origin_airport_id not in result.indexes.eligible_airport_ids:
        return DemandBuildResult(
            "REJECTED",
            issues=(
                DemandIssue(
                    "INELIGIBLE_ORIGIN",
                    f"origin is not in the demand universe: {origin_airport_id}",
                ),
            ),
        )
    return result


def get_base_daily_bookers(
    envelope, origin_airport_id, destination_airport_id, *, indexes=None
):
    result = calculate_world_demand(envelope, indexes=indexes)
    if not result.succeeded:
        raise ValueError(result.issues[0].message if result.issues else "demand failed")
    pair = result.indexes.pair(origin_airport_id, destination_airport_id)
    if pair is None:
        raise ValueError("directional pair is not in the eligible demand universe")
    return pair.base_daily_bookers


def _compose_daily_multipliers(configuration, multipliers=None):
    multipliers = {} if multipliers is None else multipliers
    if not isinstance(multipliers, Mapping):
        raise ValueError("daily multipliers must be a mapping")
    keys = tuple(multipliers.keys())
    if any(not isinstance(key, str) for key in keys):
        raise ValueError("daily multiplier categories must be strings")
    try:
        unknown = set(keys) - set(DEMAND_MULTIPLIER_CATEGORIES)
    except TypeError as exc:
        raise ValueError("daily multiplier categories must be hashable strings") from exc
    if unknown:
        raise ValueError(f"unknown daily multiplier categories: {sorted(unknown)}")
    minimum = configuration["daily_multiplier_min_bps"]
    maximum = configuration["daily_multiplier_max_bps"]
    canonical = {}
    numerator = 1
    for category in DEMAND_MULTIPLIER_CATEGORIES:
        value = multipliers.get(category, 10_000)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < minimum
            or value > maximum
        ):
            raise ValueError(
                f"{category} must be integer basis points from {minimum} through {maximum}"
            )
        canonical[category] = value
        numerator *= value
    with localcontext() as context:
        context.prec = _SCORE_PRECISION
        composed = Decimal(numerator) / (_BPS ** len(DEMAND_MULTIPLIER_CATEGORIES))
    return canonical, composed


def compose_daily_multipliers(envelope, multipliers=None):
    """Return canonical basis-point inputs and their once-rounded composition."""
    _require_valid_world(envelope)
    configuration = envelope["simulation"]["configuration"]["demand"]
    return _compose_daily_multipliers(configuration, multipliers)


def _resolve_fraction(expected, seed_material):
    if expected <= 0:
        return 0
    floor = int(expected)
    fraction = Fraction(expected - Decimal(floor))
    if fraction.numerator == 0:
        return floor
    threshold_scale = 1 << 256
    acceptance_limit = threshold_scale - (
        threshold_scale % fraction.denominator
    )
    counter = 0
    while True:
        draw_material = (
            seed_material
            if counter == 0
            else seed_material
            + b"\x00KEYED_SHA256_FRACTION_V1_RETRY\x00"
            + counter.to_bytes(8, "big")
        )
        draw = int.from_bytes(hashlib.sha256(draw_material).digest(), "big")
        if draw < acceptance_limit:
            return floor + int(
                draw % fraction.denominator < fraction.numerator
            )
        counter += 1


def _cohort_record(envelope, indexes, market_id, cohort_date, multipliers):
    configuration = envelope["simulation"]["configuration"]["demand"]
    canonical, composed = _compose_daily_multipliers(configuration, multipliers)
    pair = indexes.by_market.get(market_id)
    if pair is None:
        raise ValueError("market is not in the eligible demand universe")
    revision = indexes.model_revision
    material = json.dumps(
        {
            "purpose": DEMAND_ROUNDING_POLICY,
            "world_seed": envelope["deterministic_state"]["world_seed"],
            "demand_model_version": indexes.model_version,
            "demand_configuration_version": configuration[
                "configuration_version"
            ],
            "market_id": market_id,
            "cohort_date": cohort_date,
            "daily_multipliers_bps": canonical,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    with localcontext() as context:
        context.prec = _SCORE_PRECISION
        expected = pair.base_daily_bookers * composed
        actual = _resolve_fraction(expected, material)
        composite_ppm = int(
            (composed * _PPM).to_integral_value(rounding=ROUND_HALF_EVEN)
        )
    cohort_key = f"{market_id}@{cohort_date}"
    record = {
        "cohort_key": cohort_key,
        "market_id": market_id,
        "cohort_date": cohort_date,
        "demand_model_revision": revision,
        "daily_multipliers_bps": deepcopy(canonical),
        "composite_multiplier_ppm": composite_ppm,
        "actual_daily_bookers": actual,
        "rounding_policy": DEMAND_ROUNDING_POLICY,
    }
    record["resolution_fingerprint"] = calculate_demand_cohort_fingerprint(
        envelope, record
    )
    return record


def resolve_daily_cohort(
    envelope, market_id, cohort_date, *, multipliers=None, indexes=None
):
    """Resolve one pair/date once; no booking or service lookup occurs."""
    _canonical_date(cohort_date)
    if not isinstance(market_id, str):
        raise ValueError("market_id must be a string")
    _require_valid_world(envelope)
    cohort_key = f"{market_id}@{cohort_date}"
    existing = envelope.get("world_state", {}).get("demand_state", {}).get(
        "processed_cohorts", {}
    ).get(cohort_key)
    if isinstance(existing, Mapping):
        return CohortResolution(
            market_id,
            cohort_date,
            existing["actual_daily_bookers"],
            True,
            existing["demand_model_revision"],
        )

    candidate = deepcopy(envelope)
    build = calculate_world_demand(candidate, indexes=indexes)
    if not build.succeeded:
        raise ValueError(build.issues[0].message if build.issues else "demand failed")
    record = _cohort_record(
        candidate, build.indexes, market_id, cohort_date, multipliers
    )
    candidate["world_state"]["demand_state"]["processed_cohorts"][
        cohort_key
    ] = record
    validation = validate_world(candidate)
    if not validation.is_valid:
        raise ValueError("resolved cohort failed authoritative validation")
    _replace_envelope(envelope, candidate)
    return CohortResolution(
        market_id,
        cohort_date,
        record["actual_daily_bookers"],
        False,
        record["demand_model_revision"],
    )


def resolve_world_daily_cohorts(
    envelope, cohort_date, *, multipliers_by_market=None, indexes=None
):
    """Atomically resolve every eligible directional pair for one date."""
    try:
        _canonical_date(cohort_date)
    except ValueError as exc:
        return WorldCohortResult(
            "REJECTED", str(cohort_date), issues=(DemandIssue("INVALID_DATE", str(exc)),)
        )
    multipliers_by_market = (
        {} if multipliers_by_market is None else multipliers_by_market
    )
    if not isinstance(multipliers_by_market, Mapping):
        return WorldCohortResult(
            "REJECTED",
            cohort_date,
            issues=(DemandIssue("INVALID_MULTIPLIERS", "must be a market mapping"),),
        )
    validation = validate_world(envelope)
    if not validation.is_valid:
        return WorldCohortResult(
            "REJECTED", cohort_date, issues=_validation_issues(validation)
        )
    candidate = deepcopy(envelope)
    build = calculate_world_demand(candidate, indexes=indexes)
    if not build.succeeded:
        return WorldCohortResult(
            "REJECTED", cohort_date, issues=build.issues
        )
    unknown_markets = [
        key
        for key in multipliers_by_market.keys()
        if not isinstance(key, str) or key not in build.indexes.by_market
    ]
    if unknown_markets:
        return WorldCohortResult(
            "REJECTED",
            cohort_date,
            issues=(
                DemandIssue(
                    "INVALID_MULTIPLIERS",
                    f"modifier markets are not eligible: {sorted(map(repr, unknown_markets))}",
                ),
            ),
        )
    records = candidate["world_state"]["demand_state"]["processed_cohorts"]
    resolutions = []
    try:
        for market_id in sorted(build.indexes.by_market):
            cohort_key = f"{market_id}@{cohort_date}"
            record = records.get(cohort_key)
            reused = record is not None
            if record is None:
                record = _cohort_record(
                    candidate,
                    build.indexes,
                    market_id,
                    cohort_date,
                    multipliers_by_market.get(market_id),
                )
                records[cohort_key] = record
            resolutions.append(
                CohortResolution(
                    market_id,
                    cohort_date,
                    record["actual_daily_bookers"],
                    reused,
                    record["demand_model_revision"],
                )
            )
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        return WorldCohortResult(
            "REJECTED",
            cohort_date,
            issues=(DemandIssue("INVALID_MULTIPLIERS", str(exc)),),
        )
    validation = validate_world(candidate)
    if not validation.is_valid:
        return WorldCohortResult(
            "REJECTED", cohort_date, issues=_validation_issues(validation)
        )
    _replace_envelope(envelope, candidate)
    return WorldCohortResult("COMPLETED", cohort_date, tuple(resolutions))


def revise_demand_model(
    envelope,
    *,
    configuration_updates=None,
    airport_updates=None,
    universe_date=None,
    expected_revision=None,
):
    """Atomically apply demand-side inputs and increment exactly one revision."""
    validation = validate_world(envelope)
    current = envelope.get("world_state", {}).get("demand_state", {}).get(
        "demand_model_revision", 0
    )
    if not validation.is_valid:
        return DemandRevisionResult(
            "REJECTED", current, current, _validation_issues(validation)
        )
    if expected_revision is not None and (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision != current
    ):
        return DemandRevisionResult(
            "STALE_REVISION",
            current,
            current,
            (DemandIssue("STALE_REVISION", "expected revision does not match"),),
        )
    configuration_updates = (
        {} if configuration_updates is None else configuration_updates
    )
    airport_updates = {} if airport_updates is None else airport_updates
    if not isinstance(configuration_updates, Mapping) or not isinstance(
        airport_updates, Mapping
    ):
        return DemandRevisionResult(
            "REJECTED",
            current,
            current,
            (DemandIssue("INVALID_REVISION_INPUT", "updates must be mappings"),),
        )
    for value, label in (
        (configuration_updates, "configuration_updates"),
        (airport_updates, "airport_updates"),
    ):
        compatibility_error = json_compatibility_error(value)
        if compatibility_error:
            path, message = compatibility_error
            return DemandRevisionResult(
                "REJECTED",
                current,
                current,
                (
                    DemandIssue(
                        "INVALID_REVISION_INPUT",
                        f"{label} at {path}: {message}",
                    ),
                ),
            )
    try:
        unknown_configuration = (
            set(configuration_updates) - _CONFIGURATION_UPDATE_FIELDS
        )
    except TypeError:
        return DemandRevisionResult(
            "REJECTED",
            current,
            current,
            (
                DemandIssue(
                    "INVALID_REVISION_INPUT",
                    "demand configuration field names must be hashable strings",
                ),
            ),
        )
    if unknown_configuration:
        return DemandRevisionResult(
            "REJECTED",
            current,
            current,
            (
                DemandIssue(
                    "INVALID_REVISION_INPUT",
                    f"unsupported demand configuration fields: {sorted(unknown_configuration, key=repr)}",
                ),
            ),
        )
    if configuration_updates and "configuration_version" not in configuration_updates:
        return DemandRevisionResult(
            "REJECTED",
            current,
            current,
            (
                DemandIssue(
                    "MISSING_CONFIGURATION_VERSION",
                    "coefficient changes require an explicit configuration_version",
                ),
            ),
        )
    target_universe_date = (
        envelope["simulation"]["time_utc"][:10]
        if universe_date is None
        else universe_date
    )
    try:
        _canonical_date(target_universe_date, "universe_date")
    except ValueError as exc:
        return DemandRevisionResult(
            "REJECTED",
            current,
            current,
            (DemandIssue("INVALID_REVISION_INPUT", str(exc)),),
        )
    if (
        not configuration_updates
        and not airport_updates
        and target_universe_date
        == envelope["world_state"]["demand_state"]["universe_date"]
    ):
        return DemandRevisionResult(
            "REJECTED",
            current,
            current,
            (DemandIssue("NO_DEMAND_INPUT_CHANGE", "revision has no input change"),),
        )

    candidate = deepcopy(envelope)
    new_revision = current + 1
    configuration = candidate["simulation"]["configuration"]["demand"]
    for field, value in configuration_updates.items():
        configuration[field] = deepcopy(value)
    configuration["model_version"] = DEMAND_MODEL_VERSION
    configuration["revision"] = new_revision
    airports = candidate["world_state"]["airports"]
    try:
        for airport_id, updates in airport_updates.items():
            if not isinstance(airport_id, str) or airport_id not in airports:
                raise ValueError(f"unknown airport_id: {airport_id!r}")
            if not isinstance(updates, Mapping):
                raise ValueError(f"airport update for {airport_id} must be a mapping")
            try:
                unknown_fields = set(updates) - _AIRPORT_DEMAND_FIELDS
            except TypeError as exc:
                raise ValueError(
                    "airport demand field names must be hashable strings"
                ) from exc
            if unknown_fields:
                raise ValueError(
                    f"unsupported airport demand fields: {sorted(unknown_fields, key=repr)}"
                )
            for field, value in updates.items():
                airports[airport_id][field] = deepcopy(value)
            airports[airport_id]["demand_input_revision"] = new_revision
    except (TypeError, ValueError) as exc:
        return DemandRevisionResult(
            "REJECTED",
            current,
            current,
            (DemandIssue("INVALID_REVISION_INPUT", str(exc)),),
        )
    demand_state = candidate["world_state"]["demand_state"]
    demand_state["demand_model_revision"] = new_revision
    demand_state["universe_date"] = target_universe_date
    try:
        demand_state["input_fingerprint"] = calculate_demand_input_fingerprint(
            candidate
        )
    except (TypeError, ValueError) as exc:
        return DemandRevisionResult(
            "REJECTED",
            current,
            current,
            (DemandIssue("INVALID_REVISION_INPUT", str(exc)),),
        )
    candidate_validation = validate_world(candidate)
    if not candidate_validation.is_valid:
        return DemandRevisionResult(
            "REJECTED",
            current,
            current,
            _validation_issues(candidate_validation),
        )
    _replace_envelope(envelope, candidate)
    return DemandRevisionResult("COMPLETED", current, new_revision)
