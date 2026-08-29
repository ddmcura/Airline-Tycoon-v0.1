"""Milestone 5B current-day demand integration and direct-flight shopping."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from fractions import Fraction
import hashlib
import json
from types import MappingProxyType
from typing import Protocol

from game.demand import (
    DirectPublishedServiceActivationProvider,
    is_usable_direct_passenger_flight,
    resolve_active_daily_cohorts,
)
from game.scheduling import DatedFlightIndexes, rebuild_dated_flight_indexes
from game.world_state.booking_fingerprint import (
    calculate_booking_configuration_fingerprint,
)
from game.world_state.schema import (
    BOOKING_CURRENCY_POLICY,
    MODEL3_PROCESSED_COHORT_V1,
    MODEL4_DEMAND_MODEL_VERSION,
    MODEL4_TRAVEL_SCOPE_COHORT_V1,
)
from game.world_state.timestamps import parse_canonical_utc
from game.world_state.validation import validate_world


DESIRED_DATE_RANK_PURPOSE = (
    "STAGE1_DESIRED_DATE_INTEGER_RESIDUAL_RANK_SHA256_V1"
)
SHOPPING_OFFER_CONTRACT = "STAGE1_DIRECT_ECONOMY_SHOPPING_OFFER_V1"
SHOPPABLE = "SHOPPABLE"
NO_ELIGIBLE_SERVICE = "NO_ELIGIBLE_SERVICE"
NO_DEPARTURE_ON_DESIRED_DATE = "NO_DEPARTURE_ON_DESIRED_DATE"
_DISPOSITIONS = frozenset(
    {SHOPPABLE, NO_ELIGIBLE_SERVICE, NO_DEPARTURE_ON_DESIRED_DATE}
)


@dataclass(frozen=True)
class BookingShoppingIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class FareSnapshot:
    currency: str
    amount_minor: int


@dataclass(frozen=True)
class ShoppingScheduleLineage:
    schedule_id: str
    schedule_revision: int
    occurrence_key: str


@dataclass(frozen=True)
class DirectShoppingOffer:
    contract: str
    market_id: str
    desired_travel_date: str
    dated_flight_id: str
    airline_id: str
    origin_airport_id: str
    destination_airport_id: str
    scheduled_departure_utc: str
    scheduled_arrival_utc: str
    date_deviation_days: int
    journey_duration_seconds: int
    cabin: str
    fare_snapshot: FareSnapshot
    schedule_lineage: ShoppingScheduleLineage
    flight_status: str
    published_capacity: int
    observed_inventory_revision: int


@dataclass(frozen=True)
class DesiredDateShoppingGroup:
    desired_travel_date: str
    requested_passengers: int
    disposition: str
    failure_reason: str | None
    offers: tuple[DirectShoppingOffer, ...] = ()


@dataclass(frozen=True)
class MarketShoppingPlan:
    market_id: str
    cohort_key: str
    cohort_contract: str
    requested_passengers: int
    shoppable_passengers: int
    terminal_unsuccessful_passengers: int
    desired_date_groups: tuple[DesiredDateShoppingGroup, ...] = ()


@dataclass(frozen=True)
class DailyBookingShoppingResult:
    status: str
    cohort_date: str
    observed_demand_revision: int
    observed_market_pack_revision: int
    observed_booking_configuration_revision: int
    observed_booking_configuration_fingerprint: str
    created_cohort_count: int = 0
    reused_cohort_count: int = 0
    requested_passengers: int = 0
    shoppable_passengers: int = 0
    terminal_unsuccessful_passengers: int = 0
    market_plans: tuple[MarketShoppingPlan, ...] = ()
    issues: tuple[BookingShoppingIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


@dataclass(frozen=True)
class DirectFlightShoppingIndexEntry:
    market_id: str
    dated_flight_id: str
    airline_id: str
    origin_airport_id: str
    destination_airport_id: str
    scheduled_departure_utc: str
    scheduled_arrival_utc: str
    departure_date: str
    journey_duration_seconds: int
    fare_currency: str
    fare_amount_minor: int
    schedule_id: str
    schedule_revision: int
    occurrence_key: str
    flight_status: str
    published_capacity: int
    observed_inventory_revision: int


@dataclass(frozen=True)
class DirectFlightShoppingIndexes:
    """Detached, rebuildable indexes over qualifying 5B direct service."""

    by_market: Mapping[str, tuple[str, ...]]
    by_market_and_departure_date: Mapping[tuple[str, str], tuple[str, ...]]
    by_dated_flight_id: Mapping[str, DirectFlightShoppingIndexEntry]
    indexed_flight_count: int


class _ActivationProvider(Protocol):
    def active_market_ids(self, envelope, window, *, dated_flight_indexes=None): ...


class _IsolatedActivationProvider:
    """Protect the command candidate from provider aliases and mutation."""

    def __init__(self, provider: _ActivationProvider):
        self._provider = provider

    def active_market_ids(self, envelope, window, *, dated_flight_indexes=None):
        detached = deepcopy(envelope)
        before = deepcopy(detached)
        provided = self._provider.active_market_ids(
            detached,
            deepcopy(window),
            # DatedFlightIndexes contains read-only mapping proxies. It is a
            # runtime snapshot rather than authority and cannot be mutated.
            dated_flight_indexes=dated_flight_indexes,
        )
        if detached != before:
            raise ValueError("activation provider mutated its detached input")
        if isinstance(provided, (str, bytes)):
            raise ValueError("activation provider must return market IDs")
        values = deepcopy(tuple(provided))
        if any(type(value) is not str for value in values):
            raise ValueError("activation provider returned a non-string market ID")
        if len(set(values)) != len(values):
            raise ValueError("activation provider returned duplicate market IDs")
        markets = envelope.get("world_state", {}).get("directional_markets", {})
        unknown = sorted(value for value in values if value not in markets)
        if unknown:
            raise ValueError(
                f"activation provider returned unknown market IDs: {unknown!r}"
            )
        direct_ids = set(
            DirectPublishedServiceActivationProvider().active_market_ids(
                envelope,
                window,
                dated_flight_indexes=dated_flight_indexes,
            )
        )
        unserved = sorted(set(values) - direct_ids)
        if unserved:
            raise ValueError(
                f"activation provider returned markets without qualifying direct service: {unserved!r}"
            )
        state = envelope["world_state"]
        airports = state["airports"]
        current_date = envelope["simulation"]["time_utc"][:10]
        return tuple(
            sorted(
                market_id
                for market_id in values
                if (
                    _airport_available_on(
                        airports[markets[market_id]["origin_airport_id"]],
                        current_date,
                    )
                    and _airport_available_on(
                        airports[markets[market_id]["destination_airport_id"]],
                        current_date,
                    )
                )
            )
        )


def _replace_envelope(target, candidate):
    committed = deepcopy(candidate)
    target.clear()
    target.update(committed)


def _observed(envelope):
    try:
        demand = envelope["world_state"]["demand_state"]["demand_model_revision"]
        pack = envelope["simulation"]["configuration"]["demand"][
            "market_pack_configuration"
        ]["revision"]
        booking = envelope["simulation"]["configuration"]["booking"]
        return demand, pack, booking["revision"], booking["configuration_fingerprint"]
    except (KeyError, TypeError):
        return 0, 0, 0, ""


def _exception_message(exc):
    try:
        return str(exc)
    except Exception:
        return f"unprintable {type(exc).__name__}"


def _reject(envelope, code, message, path=None, *, status="REJECTED"):
    demand, pack, booking_revision, fingerprint = _observed(envelope)
    cohort_date = ""
    if type(envelope) is dict:
        value = envelope.get("simulation", {}).get("time_utc")
        if isinstance(value, str):
            cohort_date = value[:10]
    return DailyBookingShoppingResult(
        status,
        cohort_date,
        demand,
        pack,
        booking_revision,
        fingerprint,
        issues=(BookingShoppingIssue(code, message, path),),
    )


def _world_validation_rejection(envelope, validation):
    issue = validation.errors[0]
    if issue.code == "inconsistent_booking_configuration_fingerprint":
        code = "INCONSISTENT_BOOKING_CONFIGURATION_FINGERPRINT"
    elif issue.code == "invalid_fare_offer":
        code = "INVALID_FARE"
    elif "booking" in issue.path.lower() and "configuration" in issue.path.lower():
        code = "INVALID_BOOKING_CONFIGURATION"
    else:
        code = "INVALID_WORLD_STATE"
    return _reject(envelope, code, issue.message, issue.path)


def _rank(world_seed, cohort_date, market_id, lead_day, configuration):
    material = {
        "purpose": DESIRED_DATE_RANK_PURPOSE,
        "world_seed": world_seed,
        "cohort_date": cohort_date,
        "market_id": market_id,
        "lead_day": lead_day,
        "desired_date_policy": configuration["desired_date_policy"],
        "booking_configuration_fingerprint": configuration[
            "configuration_fingerprint"
        ],
    }
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).digest()


def allocate_desired_travel_dates(
    passenger_count,
    *,
    world_seed,
    cohort_date,
    market_id,
    booking_configuration,
):
    """Allocate aggregate integer intent across inclusive configured lead days."""
    if (
        isinstance(passenger_count, bool)
        or not isinstance(passenger_count, int)
        or passenger_count < 0
    ):
        raise ValueError("passenger_count must be a non-negative integer")
    if not isinstance(world_seed, int) or isinstance(world_seed, bool):
        raise ValueError("world_seed must be an integer")
    if type(market_id) is not str or not market_id:
        raise ValueError("market_id must be non-empty text")
    try:
        base_date = date.fromisoformat(cohort_date)
        if base_date.isoformat() != cohort_date:
            raise ValueError
        horizon = booking_configuration["booking_horizon_days"]
        buckets = booking_configuration["lead_time_buckets"]
        if type(horizon) is not int or not 0 <= horizon <= 365:
            raise ValueError
        if type(buckets) is not list or not buckets:
            raise ValueError
        if calculate_booking_configuration_fingerprint(booking_configuration) != booking_configuration["configuration_fingerprint"]:
            raise ValueError("Booking configuration fingerprint is inconsistent")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid Booking desired-date configuration") from exc

    day_weights = [None] * (horizon + 1)
    for bucket in buckets:
        if type(bucket) is not dict or set(bucket) != {
            "minimum_lead_days",
            "maximum_lead_days",
            "weight_bps",
        }:
            raise ValueError("invalid Booking desired-date bucket")
        minimum = bucket["minimum_lead_days"]
        maximum = bucket["maximum_lead_days"]
        bucket_weight = bucket["weight_bps"]
        if (
            type(minimum) is not int
            or type(maximum) is not int
            or type(bucket_weight) is not int
            or minimum < 0
            or maximum < minimum
            or bucket_weight < 0
        ):
            raise ValueError("invalid Booking desired-date bucket")
        count = maximum - minimum + 1
        weight = Fraction(bucket_weight, 10_000 * count)
        for lead_day in range(minimum, maximum + 1):
            if lead_day > horizon or day_weights[lead_day] is not None:
                raise ValueError("invalid Booking desired-date bucket coverage")
            day_weights[lead_day] = weight
    if any(weight is None for weight in day_weights) or sum(day_weights) != 1:
        raise ValueError("invalid Booking desired-date weights")
    if passenger_count == 0:
        return ()

    exact = [passenger_count * weight for weight in day_weights]
    allocated = [value.numerator // value.denominator for value in exact]
    remainder = passenger_count - sum(allocated)
    order = sorted(
        range(horizon + 1),
        key=lambda lead_day: (
            -(exact[lead_day] - allocated[lead_day]),
            _rank(
                world_seed,
                cohort_date,
                market_id,
                lead_day,
                booking_configuration,
            ),
        ),
    )
    for lead_day in order[:remainder]:
        allocated[lead_day] += 1
    if sum(allocated) != passenger_count:
        raise ArithmeticError("desired-date allocation did not conserve passengers")
    return tuple(
        ((base_date + timedelta(days=lead_day)).isoformat(), count)
        for lead_day, count in enumerate(allocated)
        if count
    )


def _airport_available_on(airport, travel_date):
    return (
        isinstance(airport, Mapping)
        and airport.get("passenger_demand_eligible") is True
        and (
            airport.get("active_from_date") is None
            or travel_date >= airport["active_from_date"]
        )
        and (
            airport.get("active_until_date") is None
            or travel_date < airport["active_until_date"]
        )
    )


def _freeze_tuple_mapping(values):
    return MappingProxyType(
        {
            key: tuple(item[1] for item in sorted(items))
            for key, items in sorted(values.items(), key=lambda item: repr(item[0]))
        }
    )


def rebuild_direct_flight_shopping_indexes(
    envelope,
    *,
    dated_flight_indexes: DatedFlightIndexes | None = None,
):
    """Build authoritative 5B indexes; untrusted supplied indexes cannot select work."""
    validation = validate_world(envelope)
    if not validation.is_valid:
        raise ValueError(validation.errors[0].message)
    if envelope["metadata"]["save_schema_version"] != 3:
        raise ValueError("Booking shopping requires save schema version 3")
    configuration = envelope["simulation"]["configuration"]["booking"]
    now_text = envelope["simulation"]["time_utc"]
    now = parse_canonical_utc(now_text)
    final_date = now.date() + timedelta(days=configuration["booking_horizon_days"])
    window_end = datetime.combine(final_date, time.max, tzinfo=timezone.utc).replace(
        microsecond=0
    )
    # Caller indexes are untrusted runtime hints. Rebuilding is already required
    # for the authoritative pass, so do not invoke caller equality or traversal
    # methods and never let supplied content select candidate flights.
    schedule_indexes = rebuild_dated_flight_indexes(envelope)

    state = envelope["world_state"]
    flights = state["dated_flights"]
    airports = state["airports"]
    connections = state["connections"]
    by_market = {}
    by_market_date = {}
    by_id = {}
    candidate_ids = sorted(
        {
            flight_id
            for flight_ids in schedule_indexes.direct_services_by_market.values()
            for flight_id in flight_ids
        }
    )
    for flight_id in candidate_ids:
        flight = flights.get(flight_id)
        if not is_usable_direct_passenger_flight(
            envelope, flight_id, flight, now, window_end
        ):
            continue
        departure = parse_canonical_utc(flight["scheduled_off_block_utc"])
        arrival = parse_canonical_utc(flight["scheduled_in_block_utc"])
        departure_date = departure.date().isoformat()
        arrival_date = arrival.date().isoformat()
        if not _airport_available_on(
            airports[flight["origin_airport_id"]], departure_date
        ) or not _airport_available_on(
            airports[flight["destination_airport_id"]], arrival_date
        ):
            continue
        connection = connections[flight["connection_id"]]
        market_id = connection["market_id"]
        indexed = DirectFlightShoppingIndexEntry(
            market_id,
            flight_id,
            flight["airline_id"],
            flight["origin_airport_id"],
            flight["destination_airport_id"],
            flight["scheduled_off_block_utc"],
            flight["scheduled_in_block_utc"],
            departure_date,
            int((arrival - departure).total_seconds()),
            flight["fare_offer"]["currency"],
            flight["fare_offer"]["amount_minor"],
            flight["schedule_id"],
            flight["schedule_revision"],
            flight["occurrence_key"],
            flight["status"],
            flight["capacity"],
            flight["inventory_revision"],
        )
        by_id[flight_id] = indexed
        order_item = ((indexed.scheduled_departure_utc, flight_id), flight_id)
        by_market.setdefault(market_id, []).append(order_item)
        by_market_date.setdefault((market_id, departure_date), []).append(order_item)
    return DirectFlightShoppingIndexes(
        _freeze_tuple_mapping(by_market),
        _freeze_tuple_mapping(by_market_date),
        MappingProxyType(dict(sorted(by_id.items()))),
        len(candidate_ids),
    )


def _offer(indexed, desired_date):
    deviation = (
        date.fromisoformat(indexed.departure_date) - date.fromisoformat(desired_date)
    ).days
    return DirectShoppingOffer(
        SHOPPING_OFFER_CONTRACT,
        indexed.market_id,
        desired_date,
        indexed.dated_flight_id,
        indexed.airline_id,
        indexed.origin_airport_id,
        indexed.destination_airport_id,
        indexed.scheduled_departure_utc,
        indexed.scheduled_arrival_utc,
        deviation,
        indexed.journey_duration_seconds,
        "ECONOMY",
        FareSnapshot(indexed.fare_currency, indexed.fare_amount_minor),
        ShoppingScheduleLineage(
            indexed.schedule_id,
            indexed.schedule_revision,
            indexed.occurrence_key,
        ),
        indexed.flight_status,
        indexed.published_capacity,
        indexed.observed_inventory_revision,
    )


def _plan_market(candidate, resolution, configuration, indexes):
    market_id = resolution.market_id
    cohort_date = resolution.cohort_date
    cohort_key = f"{market_id}@{cohort_date}"
    wrapper = candidate["world_state"]["demand_state"]["processed_cohorts"][
        cohort_key
    ]
    contract = wrapper.get("contract")
    if contract not in (
        MODEL3_PROCESSED_COHORT_V1,
        MODEL4_TRAVEL_SCOPE_COHORT_V1,
    ):
        raise ValueError("unsupported demand cohort contract")
    allocations = allocate_desired_travel_dates(
        resolution.actual_daily_bookers,
        world_seed=candidate["deterministic_state"]["world_seed"],
        cohort_date=cohort_date,
        market_id=market_id,
        booking_configuration=configuration,
    )
    horizon_service = indexes.by_market.get(market_id, ())
    tolerance = configuration["desired_date_tolerance_days"]
    current_date = date.fromisoformat(cohort_date)
    final_date = current_date + timedelta(days=configuration["booking_horizon_days"])
    groups = []
    for desired_date, passenger_count in allocations:
        desired = date.fromisoformat(desired_date)
        window_start = max(current_date, desired - timedelta(days=tolerance))
        window_end = min(final_date, desired + timedelta(days=tolerance))
        flight_ids = []
        current = window_start
        while current <= window_end:
            flight_ids.extend(
                indexes.by_market_and_departure_date.get(
                    (market_id, current.isoformat()), ()
                )
            )
            current += timedelta(days=1)
        flight_ids = sorted(
            set(flight_ids),
            key=lambda flight_id: (
                indexes.by_dated_flight_id[flight_id].scheduled_departure_utc,
                flight_id,
            ),
        )
        offers = tuple(
            _offer(indexes.by_dated_flight_id[flight_id], desired_date)
            for flight_id in flight_ids
        )
        currencies = {offer.fare_snapshot.currency for offer in offers}
        if len(currencies) > 1:
            raise ValueError(
                f"UNSUPPORTED_FARE_CURRENCY: market {market_id} on {desired_date} has competing currencies {sorted(currencies)!r}"
            )
        if offers:
            disposition = SHOPPABLE
            failure = None
        elif horizon_service:
            disposition = NO_DEPARTURE_ON_DESIRED_DATE
            failure = NO_DEPARTURE_ON_DESIRED_DATE
        else:
            disposition = NO_ELIGIBLE_SERVICE
            failure = NO_ELIGIBLE_SERVICE
        groups.append(
            DesiredDateShoppingGroup(
                desired_date, passenger_count, disposition, failure, offers
            )
        )
    shoppable = sum(
        group.requested_passengers
        for group in groups
        if group.disposition == SHOPPABLE
    )
    terminal = resolution.actual_daily_bookers - shoppable
    return MarketShoppingPlan(
        market_id,
        cohort_key,
        contract,
        resolution.actual_daily_bookers,
        shoppable,
        terminal,
        tuple(groups),
    )


def _current_date_resolutions(candidate, demand_result, cohort_date):
    """Include valid existing current-date V1/V2 markers even if service vanished."""
    from game.demand import CohortResolution

    by_market = {item.market_id: item for item in demand_result.cohorts}
    records = candidate["world_state"]["demand_state"]["processed_cohorts"]
    suffix = f"@{cohort_date}"
    for cohort_key in sorted(records):
        if not cohort_key.endswith(suffix):
            continue
        wrapper = records[cohort_key]
        contract = wrapper.get("contract")
        payload = wrapper.get("payload")
        if contract not in (
            MODEL3_PROCESSED_COHORT_V1,
            MODEL4_TRAVEL_SCOPE_COHORT_V1,
        ) or not isinstance(payload, Mapping):
            raise ValueError("invalid current-date demand cohort")
        market_id = payload.get("market_id")
        if market_id in by_market:
            continue
        by_market[market_id] = CohortResolution(
            market_id,
            cohort_date,
            payload["actual_daily_bookers"],
            True,
            payload["demand_model_revision"],
        )
    return tuple(by_market[market_id] for market_id in sorted(by_market))


def _validate_result(result):
    if result.status != "COMPLETED":
        return False
    if tuple(sorted(plan.market_id for plan in result.market_plans)) != tuple(
        plan.market_id for plan in result.market_plans
    ):
        return False
    requested = shoppable = terminal = 0
    for plan in result.market_plans:
        if plan.requested_passengers != sum(
            group.requested_passengers for group in plan.desired_date_groups
        ):
            return False
        plan_shoppable = plan_terminal = 0
        for group in plan.desired_date_groups:
            if group.disposition not in _DISPOSITIONS or group.requested_passengers <= 0:
                return False
            if group.disposition == SHOPPABLE:
                if not group.offers or group.failure_reason is not None:
                    return False
                if len({offer.fare_snapshot.currency for offer in group.offers}) != 1:
                    return False
                plan_shoppable += group.requested_passengers
            else:
                if group.offers or group.failure_reason != group.disposition:
                    return False
                plan_terminal += group.requested_passengers
        if (
            plan_shoppable != plan.shoppable_passengers
            or plan_terminal != plan.terminal_unsuccessful_passengers
            or plan.requested_passengers != plan_shoppable + plan_terminal
        ):
            return False
        requested += plan.requested_passengers
        shoppable += plan_shoppable
        terminal += plan_terminal
    return (
        requested == result.requested_passengers
        and shoppable == result.shoppable_passengers
        and terminal == result.terminal_unsuccessful_passengers
        and requested == shoppable + terminal
    )


def prepare_daily_booking_shopping(
    envelope,
    *,
    expected_demand_revision,
    expected_market_pack_revision,
    expected_booking_configuration_revision,
    expected_booking_configuration_fingerprint,
    multipliers_by_market=None,
    demand_indexes=None,
    activation_providers: Sequence[_ActivationProvider] | None = None,
    dated_flight_indexes: DatedFlightIndexes | None = None,
):
    """Atomically apply today's cohort markers and return detached 5B plans."""
    validation = validate_world(envelope)
    if not validation.is_valid:
        return _world_validation_rejection(envelope, validation)
    if envelope["metadata"]["save_schema_version"] != 3:
        return _reject(
            envelope, "INVALID_WORLD_STATE", "Booking shopping requires schema 3"
        )
    demand_revision, pack_revision, booking_revision, fingerprint = _observed(
        envelope
    )
    expected_values = (
        expected_demand_revision,
        expected_market_pack_revision,
        expected_booking_configuration_revision,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in expected_values):
        return _reject(
            envelope,
            "STALE_REVISION",
            "expected revisions must be integers",
            status="STALE_REVISION",
        )
    if expected_values != (demand_revision, pack_revision, booking_revision):
        return _reject(
            envelope,
            "STALE_REVISION",
            "an expected revision does not match",
            status="STALE_REVISION",
        )
    if type(expected_booking_configuration_fingerprint) is not str:
        return _reject(
            envelope,
            "INCONSISTENT_BOOKING_CONFIGURATION_FINGERPRINT",
            "expected Booking configuration fingerprint must be text",
        )
    if expected_booking_configuration_fingerprint != fingerprint:
        return _reject(
            envelope,
            "INCONSISTENT_BOOKING_CONFIGURATION_FINGERPRINT",
            "expected Booking configuration fingerprint does not match",
        )
    configuration = envelope["simulation"]["configuration"]["booking"]
    if configuration["choice_policy"].get("currency_policy") != BOOKING_CURRENCY_POLICY:
        return _reject(
            envelope,
            "INVALID_BOOKING_CONFIGURATION",
            "5B requires the single-currency Booking policy",
        )
    candidate = deepcopy(envelope)
    cohort_date = candidate["simulation"]["time_utc"][:10]
    final_date = date.fromisoformat(cohort_date) + timedelta(
        days=configuration["booking_horizon_days"]
    )
    activation_end = datetime.combine(
        final_date, time.max, tzinfo=timezone.utc
    ).replace(microsecond=0)
    try:
        if (
            activation_providers is None
            and candidate["simulation"]["configuration"]["demand"][
                "model_version"
            ]
            == MODEL4_DEMAND_MODEL_VERSION
        ):
            isolated_providers = None
        else:
            providers = (
                (DirectPublishedServiceActivationProvider(),)
                if activation_providers is None
                else tuple(activation_providers)
            )
            isolated_providers = tuple(
                _IsolatedActivationProvider(provider) for provider in providers
            )
    except Exception as exc:
        return _reject(
            candidate,
            "UNAVAILABLE_BOOKING_MARKET",
            "invalid activation provider collection: "
            f"{_exception_message(exc)}",
        )
    try:
        effective_multipliers = multipliers_by_market
        if isinstance(multipliers_by_market, Mapping):
            records = candidate["world_state"]["demand_state"][
                "processed_cohorts"
            ]
            suffix = f"@{cohort_date}"
            reused_market_ids = {
                wrapper["payload"]["market_id"]
                for cohort_key, wrapper in records.items()
                if cohort_key.endswith(suffix)
                and wrapper.get("contract")
                in (MODEL3_PROCESSED_COHORT_V1, MODEL4_TRAVEL_SCOPE_COHORT_V1)
            }
            effective_multipliers = deepcopy(
                {
                    market_id: value
                    for market_id, value in multipliers_by_market.items()
                    if market_id not in reused_market_ids
                }
            )
        demand_result = resolve_active_daily_cohorts(
            candidate,
            cohort_date,
            multipliers_by_market=effective_multipliers,
            indexes=demand_indexes,
            activation_start_utc=candidate["simulation"]["time_utc"],
            activation_end_utc=activation_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            activation_providers=isolated_providers,
            dated_flight_indexes=None,
        )
        if not demand_result.succeeded:
            issue = demand_result.issues[0]
            code = (
                "UNAVAILABLE_BOOKING_MARKET"
                if issue.code in {"UNAVAILABLE_DEMAND_MARKET", "INVALID_ACTIVATION_WINDOW"}
                else "INVALID_DEMAND_COHORT"
            )
            return _reject(candidate, code, issue.message, issue.path)
        shopping_indexes = rebuild_direct_flight_shopping_indexes(
            candidate, dated_flight_indexes=None
        )
        resolutions = _current_date_resolutions(
            candidate, demand_result, cohort_date
        )
        plans = tuple(
            _plan_market(candidate, resolution, configuration, shopping_indexes)
            for resolution in resolutions
        )
        requested = sum(plan.requested_passengers for plan in plans)
        shoppable = sum(plan.shoppable_passengers for plan in plans)
        terminal = sum(plan.terminal_unsuccessful_passengers for plan in plans)
        created = sum(not item.reused for item in resolutions)
        reused = len(resolutions) - created
        result = DailyBookingShoppingResult(
            "COMPLETED",
            cohort_date,
            demand_revision,
            pack_revision,
            booking_revision,
            fingerprint,
            created,
            reused,
            requested,
            shoppable,
            terminal,
            plans,
        )
        if not _validate_result(result):
            return _reject(
                candidate,
                "RESULT_VALIDATION_FAILED",
                "Booking shopping result failed conservation or topology validation",
            )
        final_validation = validate_world(candidate)
        if not final_validation.is_valid:
            return _world_validation_rejection(candidate, final_validation)
    except Exception as exc:
        message = _exception_message(exc)
        if message.startswith("UNSUPPORTED_FARE_CURRENCY:"):
            code = "UNSUPPORTED_FARE_CURRENCY"
        elif "fare" in message.lower():
            code = "INVALID_FARE"
        elif "inventory" in message.lower() or "flight" in message.lower():
            code = "INVALID_INVENTORY"
        elif "configuration" in message.lower():
            code = "INVALID_BOOKING_CONFIGURATION"
        else:
            code = "BOOKING_SHOPPING_FAILED"
        return _reject(candidate, code, message)
    _replace_envelope(envelope, candidate)
    return deepcopy(result)


__all__ = (
    "BookingShoppingIssue",
    "DailyBookingShoppingResult",
    "DesiredDateShoppingGroup",
    "DirectFlightShoppingIndexes",
    "DirectFlightShoppingIndexEntry",
    "DirectShoppingOffer",
    "FareSnapshot",
    "MarketShoppingPlan",
    "NO_DEPARTURE_ON_DESIRED_DATE",
    "NO_ELIGIBLE_SERVICE",
    "SHOPPABLE",
    "ShoppingScheduleLineage",
    "allocate_desired_travel_dates",
    "prepare_daily_booking_shopping",
    "rebuild_direct_flight_shopping_indexes",
)
