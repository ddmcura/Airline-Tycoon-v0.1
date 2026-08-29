"""Milestone 5C deterministic choice and detached capacity allocation plans."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json

from game.world_state.schema import BOOKING_CHOICE_POLICY_CONTRACT
from game.world_state.validation import validate_world

from .indexes import rebuild_booking_indexes
from .shopping import (
    NO_DEPARTURE_ON_DESIRED_DATE,
    NO_ELIGIBLE_SERVICE,
    SHOPPABLE,
    DirectShoppingOffer,
    prepare_daily_booking_shopping,
)


ALLOCATION_PLAN_CONTRACT = "STAGE1_DAILY_BOOKING_ALLOCATION_PLAN_V1"
ALLOCATION_PLAN_VERSION = "stage1-booking-allocation-v1"
CHOICE_RESIDUAL_RANK_PURPOSE = "STAGE1_CHOICE_INTEGER_RESIDUAL_RANK_SHA256_V1"
CAPACITY_RESIDUAL_RANK_PURPOSE = (
    "STAGE1_CAPACITY_CONTENTION_INTEGER_RESIDUAL_RANK_SHA256_V1"
)
OUTSIDE_OPTION = "OUTSIDE_OPTION"
INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"
OUTSIDE_OPTION_SENTINEL = "__OUTSIDE_OPTION__"


@dataclass(frozen=True)
class BookingAllocationIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class OfferScoreEvidence:
    dated_flight_id: str
    airline_id: str
    fare_score: int
    desired_date_score: int
    journey_duration_score: int
    composite_numerator: int
    composite_denominator: int = 10_000


@dataclass(frozen=True)
class SelectedOfferAllocation:
    dated_flight_id: str
    airline_id: str
    selected_passengers: int


@dataclass(frozen=True)
class DesiredDateAllocationResult:
    desired_travel_date: str
    requested_passengers: int
    selected_passengers: int
    outside_option_passengers: int
    insufficient_capacity_passengers: int
    no_eligible_service_passengers: int
    no_departure_on_desired_date_passengers: int
    selected_offer_allocations: tuple[SelectedOfferAllocation, ...] = ()
    offer_scores: tuple[OfferScoreEvidence, ...] = ()


@dataclass(frozen=True)
class MarketAllocationResult:
    market_id: str
    cohort_key: str
    cohort_contract: str
    requested_passengers: int
    selected_passengers: int
    outside_option_passengers: int
    insufficient_capacity_passengers: int
    no_eligible_service_passengers: int
    no_departure_on_desired_date_passengers: int
    desired_date_results: tuple[DesiredDateAllocationResult, ...] = ()


@dataclass(frozen=True)
class InventoryRevisionObservation:
    dated_flight_id: str
    observed_inventory_revision: int


@dataclass(frozen=True)
class DailyBookingAllocationResult:
    status: str
    contract: str
    version: str
    cohort_date: str
    observed_demand_revision: int
    observed_market_pack_revision: int
    observed_booking_configuration_revision: int
    observed_booking_configuration_fingerprint: str
    requested_passengers: int = 0
    selected_passengers: int = 0
    outside_option_passengers: int = 0
    insufficient_capacity_passengers: int = 0
    no_eligible_service_passengers: int = 0
    no_departure_on_desired_date_passengers: int = 0
    market_results: tuple[MarketAllocationResult, ...] = ()
    observed_inventory_revisions: tuple[InventoryRevisionObservation, ...] = ()
    contention_rounds: int = 0
    issues: tuple[BookingAllocationIssue, ...] = ()

    @property
    def succeeded(self):
        return self.status == "COMPLETED"


@dataclass
class _GroupState:
    market_id: str
    cohort_key: str
    cohort_contract: str
    desired_travel_date: str
    requested: int
    offers: dict[str, DirectShoppingOffer]
    scores: dict[str, OfferScoreEvidence]
    selected: dict[str, int]
    outside: int = 0
    insufficient: int = 0


def _half_even(numerator, denominator):
    """Quantize an exact non-negative rational to nearest integer, ties to even."""
    quotient, remainder = divmod(numerator, denominator)
    doubled = remainder * 2
    if doubled > denominator or (doubled == denominator and quotient % 2):
        return quotient + 1
    return quotient


def fare_score(amount_minor, minimum_amount_minor):
    """Return the canonical integer V1 fare score using exact half-even quantization."""
    if any(type(value) is not int or value < 0 for value in (amount_minor, minimum_amount_minor)):
        raise ValueError("fare amounts must be non-negative integers")
    if minimum_amount_minor == 0:
        return 10_000 if amount_minor == 0 else 0
    if amount_minor < minimum_amount_minor:
        raise ValueError("fare amount cannot be below the declared minimum")
    penalty = _half_even(
        10_000 * (amount_minor - minimum_amount_minor), minimum_amount_minor
    )
    return max(0, 10_000 - penalty)


def desired_date_score(date_deviation_days):
    if type(date_deviation_days) is not int or abs(date_deviation_days) > 3:
        raise ValueError("date deviation must be an integer inside the approved tolerance")
    return max(0, 10_000 - 2_500 * abs(date_deviation_days))


def journey_duration_score(duration_seconds, minimum_duration_seconds):
    """Return the canonical floor of the exact fastest/offer duration ratio."""
    if any(type(value) is not int or value <= 0 for value in (duration_seconds, minimum_duration_seconds)):
        raise ValueError("journey durations must be positive integer seconds")
    score = (10_000 * minimum_duration_seconds) // duration_seconds
    if not 1 <= score <= 10_000:
        raise ValueError("journey-duration score is outside its canonical range")
    return score


def score_group_offers(offers):
    """Score one validated same-currency desired-date offer group exactly."""
    offers = tuple(offers)
    if not offers:
        return ()
    if len({offer.fare_snapshot.currency for offer in offers}) != 1:
        raise ValueError("UNSUPPORTED_FARE_CURRENCY: competing offers must share currency")
    minimum_fare = min(offer.fare_snapshot.amount_minor for offer in offers)
    minimum_duration = min(offer.journey_duration_seconds for offer in offers)
    evidence = []
    for offer in sorted(offers, key=lambda item: item.dated_flight_id):
        fare = fare_score(offer.fare_snapshot.amount_minor, minimum_fare)
        date = desired_date_score(offer.date_deviation_days)
        duration = journey_duration_score(
            offer.journey_duration_seconds, minimum_duration
        )
        numerator = 5_000 * fare + 3_000 * date + 2_000 * duration
        evidence.append(
            OfferScoreEvidence(
                offer.dated_flight_id,
                offer.airline_id,
                fare,
                date,
                duration,
                numerator,
            )
        )
    return tuple(evidence)


def _rank(*, purpose, world_seed, cohort_date, market_id, desired_date, identity,
          policy_contract, configuration_fingerprint):
    material = {
        "purpose": purpose,
        "world_seed": world_seed,
        "cohort_date": cohort_date,
        "market_id": market_id,
        "desired_travel_date": desired_date,
        "choice_identity": identity,
        "choice_policy_contract": policy_contract,
        "booking_configuration_fingerprint": configuration_fingerprint,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _largest_remainder(total, weights, rank):
    if type(total) is not int or total < 0:
        raise ValueError("allocation total must be a non-negative integer")
    canonical = {identity: Fraction(weight) for identity, weight in weights.items()}
    if any(weight < 0 for weight in canonical.values()):
        raise ValueError("allocation weights must be non-negative")
    denominator = sum(canonical.values(), Fraction(0))
    if denominator == 0:
        return {identity: 0 for identity in canonical}
    exact = {
        identity: Fraction(total) * weight / denominator
        for identity, weight in canonical.items()
    }
    allocated = {identity: value.numerator // value.denominator for identity, value in exact.items()}
    residual = total - sum(allocated.values())
    order = sorted(
        canonical,
        key=lambda identity: (
            -(exact[identity] - allocated[identity]),
            rank(identity),
            identity,
        ),
    )
    for identity in order[:residual]:
        allocated[identity] += 1
    return allocated


def _choice(group, passenger_count, available_ids, *, world_seed, cohort_date,
            policy, fingerprint):
    # Saturated offers are removed before every overflow round, so fare and
    # fastest-duration benchmarks are recomputed over the remaining choice set.
    round_scores = {
        item.dated_flight_id: item
        for item in score_group_offers(group.offers[flight_id] for flight_id in available_ids)
    }
    weights = {
        flight_id: Fraction(round_scores[flight_id].composite_numerator, 10_000)
        for flight_id in sorted(available_ids)
    }
    weights[OUTSIDE_OPTION_SENTINEL] = Fraction(
        policy["outside_option_weight_score_units"]
    )
    return _largest_remainder(
        passenger_count,
        weights,
        lambda identity: _rank(
            purpose=CHOICE_RESIDUAL_RANK_PURPOSE,
            world_seed=world_seed,
            cohort_date=cohort_date,
            market_id=group.market_id,
            desired_date=group.desired_travel_date,
            identity=identity,
            policy_contract=policy["contract"],
            configuration_fingerprint=fingerprint,
        ),
    )


def _capacity_shares(flight_id, capacity, requests, groups, *, world_seed,
                     cohort_date, policy, fingerprint):
    return _largest_remainder(
        capacity,
        requests,
        lambda group_key: _rank(
            purpose=CAPACITY_RESIDUAL_RANK_PURPOSE,
            world_seed=world_seed,
            cohort_date=cohort_date,
            market_id=groups[group_key].market_id,
            desired_date=groups[group_key].desired_travel_date,
            identity=flight_id,
            policy_contract=policy["contract"],
            configuration_fingerprint=fingerprint,
        ),
    )


def _observed(envelope):
    try:
        demand = envelope["world_state"]["demand_state"]["demand_model_revision"]
        pack = envelope["simulation"]["configuration"]["demand"]["market_pack_configuration"]["revision"]
        booking = envelope["simulation"]["configuration"]["booking"]
        return demand, pack, booking["revision"], booking["configuration_fingerprint"]
    except Exception:
        return 0, 0, 0, ""


def _exception_message(exc):
    try:
        message = str(exc)
    except Exception:
        message = type(exc).__name__
    return message if type(message) is str else type(exc).__name__


def _reject(envelope, code, message, path=None, status="REJECTED"):
    demand, pack, booking, fingerprint = _observed(envelope)
    cohort_date = envelope.get("simulation", {}).get("time_utc", "")[:10] if type(envelope) is dict else ""
    return DailyBookingAllocationResult(
        status, ALLOCATION_PLAN_CONTRACT, ALLOCATION_PLAN_VERSION, cohort_date,
        demand, pack, booking, fingerprint,
        issues=(BookingAllocationIssue(code, message, path),),
    )


def _validate_expected_inventory(expected, relevant):
    if type(expected) is not dict:
        raise TypeError("expected inventory revisions must be a dictionary")
    if any(type(key) is not str or type(value) is not int or value < 0 for key, value in expected.items()):
        raise TypeError("expected inventory revisions require string IDs and non-negative integer values")
    required = set(relevant)
    supplied = set(expected)
    missing = sorted(required - supplied)
    extra = sorted(supplied - required)
    if missing:
        raise KeyError(f"missing expected inventory revisions: {missing!r}")
    if extra:
        raise KeyError(f"extra expected inventory revisions: {extra!r}")
    stale = sorted(flight_id for flight_id in required if expected[flight_id] != relevant[flight_id])
    if stale:
        raise RuntimeError(f"stale inventory revisions: {stale!r}")


def _validate_result(
    result, *, capacity_limits=None, expected_inventory_revisions=None
):
    if (
        type(result) is not DailyBookingAllocationResult
        or result.status != "COMPLETED"
        or result.contract != ALLOCATION_PLAN_CONTRACT
        or result.version != ALLOCATION_PLAN_VERSION
        or type(result.cohort_date) is not str
        or type(result.market_results) is not tuple
        or type(result.observed_inventory_revisions) is not tuple
        or result.issues
        or any(
            type(value) is not int or value < 0
            for value in (
                result.observed_demand_revision,
                result.observed_market_pack_revision,
                result.observed_booking_configuration_revision,
                result.contention_rounds,
            )
        )
        or type(result.observed_booking_configuration_fingerprint) is not str
        or len(result.observed_booking_configuration_fingerprint) != 64
        or any(
            character not in "0123456789abcdef"
            for character in result.observed_booking_configuration_fingerprint
        )
    ):
        return False
    if any(type(item) is not MarketAllocationResult for item in result.market_results):
        return False
    market_ids = tuple(item.market_id for item in result.market_results)
    if (
        any(type(market_id) is not str for market_id in market_ids)
        or market_ids != tuple(sorted(market_ids))
        or len(market_ids) != len(set(market_ids))
    ):
        return False
    observations = result.observed_inventory_revisions
    if any(type(item) is not InventoryRevisionObservation for item in observations):
        return False
    observation_ids = tuple(item.dated_flight_id for item in observations)
    if (
        any(type(flight_id) is not str for flight_id in observation_ids)
        or observation_ids != tuple(sorted(observation_ids))
        or len(observation_ids) != len(set(observation_ids))
        or any(
            type(item.dated_flight_id) is not str
            or item.dated_flight_id == OUTSIDE_OPTION_SENTINEL
            or type(item.observed_inventory_revision) is not int
            or item.observed_inventory_revision < 0
            for item in observations
        )
    ):
        return False
    totals = [0] * 6
    selected_by_flight = {}
    seen_groups = set()
    for market in result.market_results:
        if (
            type(market) is not MarketAllocationResult
            or type(market.market_id) is not str
            or market.cohort_key != f"{market.market_id}@{result.cohort_date}"
            or market.cohort_contract
            not in {"MODEL3_PROCESSED_COHORT_V1", "MODEL4_TRAVEL_SCOPE_COHORT_V1"}
            or type(market.desired_date_results) is not tuple
        ):
            return False
        market_totals = [0] * 6
        if any(
            type(item) is not DesiredDateAllocationResult
            for item in market.desired_date_results
        ):
            return False
        dates = tuple(item.desired_travel_date for item in market.desired_date_results)
        if (
            any(type(desired_date) is not str for desired_date in dates)
            or dates != tuple(sorted(dates))
            or len(dates) != len(set(dates))
        ):
            return False
        for group in market.desired_date_results:
            if (
                type(group) is not DesiredDateAllocationResult
                or type(group.desired_travel_date) is not str
                or type(group.selected_offer_allocations) is not tuple
                or type(group.offer_scores) is not tuple
            ):
                return False
            key = (market.market_id, group.desired_travel_date)
            if key in seen_groups:
                return False
            seen_groups.add(key)
            values = (
                group.requested_passengers, group.selected_passengers,
                group.outside_option_passengers, group.insufficient_capacity_passengers,
                group.no_eligible_service_passengers,
                group.no_departure_on_desired_date_passengers,
            )
            if any(type(value) is not int or value < 0 for value in values):
                return False
            if values[0] != sum(values[1:]):
                return False
            selections = group.selected_offer_allocations
            if any(type(item) is not SelectedOfferAllocation for item in selections):
                return False
            selection_ids = tuple(item.dated_flight_id for item in selections)
            if (
                any(type(flight_id) is not str for flight_id in selection_ids)
                or selection_ids != tuple(sorted(selection_ids))
                or len(selection_ids) != len(set(selection_ids))
                or any(
                    type(item.dated_flight_id) is not str
                    or item.dated_flight_id == OUTSIDE_OPTION_SENTINEL
                    or type(item.airline_id) is not str
                    or type(item.selected_passengers) is not int
                    or item.selected_passengers <= 0
                    for item in selections
                )
            ):
                return False
            if values[1] != sum(item.selected_passengers for item in selections):
                return False
            scores = group.offer_scores
            if any(type(item) is not OfferScoreEvidence for item in scores):
                return False
            score_ids = tuple(item.dated_flight_id for item in scores)
            if (
                any(type(flight_id) is not str for flight_id in score_ids)
                or score_ids != tuple(sorted(score_ids))
                or len(score_ids) != len(set(score_ids))
            ):
                return False
            score_by_id = {}
            for score in scores:
                components = (
                    score.fare_score,
                    score.desired_date_score,
                    score.journey_duration_score,
                )
                if (
                    type(score.dated_flight_id) is not str
                    or score.dated_flight_id == OUTSIDE_OPTION_SENTINEL
                    or type(score.airline_id) is not str
                    or any(type(value) is not int for value in components)
                    or not 0 <= score.fare_score <= 10_000
                    or not 0 <= score.desired_date_score <= 10_000
                    or not 1 <= score.journey_duration_score <= 10_000
                    or type(score.composite_numerator) is not int
                    or score.composite_numerator
                    != 5_000 * score.fare_score
                    + 3_000 * score.desired_date_score
                    + 2_000 * score.journey_duration_score
                    or score.composite_denominator != 10_000
                ):
                    return False
                score_by_id[score.dated_flight_id] = score
            if any(
                item.dated_flight_id not in score_by_id
                or item.airline_id != score_by_id[item.dated_flight_id].airline_id
                for item in selections
            ):
                return False
            for item in selections:
                selected_by_flight[item.dated_flight_id] = (
                    selected_by_flight.get(item.dated_flight_id, 0)
                    + item.selected_passengers
                )
            for index, value in enumerate(values):
                market_totals[index] += value
        expected = (
            market.requested_passengers, market.selected_passengers,
            market.outside_option_passengers, market.insufficient_capacity_passengers,
            market.no_eligible_service_passengers,
            market.no_departure_on_desired_date_passengers,
        )
        if any(type(value) is not int or value < 0 for value in expected):
            return False
        if tuple(market_totals) != expected:
            return False
        for index, value in enumerate(expected):
            totals[index] += value
    result_totals = (
        result.requested_passengers, result.selected_passengers,
        result.outside_option_passengers, result.insufficient_capacity_passengers,
        result.no_eligible_service_passengers,
        result.no_departure_on_desired_date_passengers,
    )
    if capacity_limits is not None:
        if type(capacity_limits) is not dict or any(
            type(flight_id) is not str
            or type(capacity) is not int
            or capacity < 0
            for flight_id, capacity in capacity_limits.items()
        ):
            return False
        if any(
            flight_id not in capacity_limits
            or selected > capacity_limits[flight_id]
            for flight_id, selected in selected_by_flight.items()
        ):
            return False
    if expected_inventory_revisions is not None:
        if type(expected_inventory_revisions) is not dict:
            return False
        observed_mapping = {
            item.dated_flight_id: item.observed_inventory_revision
            for item in observations
        }
        if observed_mapping != expected_inventory_revisions:
            return False
    return (
        all(type(value) is int and value >= 0 for value in result_totals)
        and tuple(totals) == result_totals
        and totals[0] == sum(totals[1:])
    )


def prepare_daily_booking_allocation(
    envelope,
    *,
    expected_demand_revision,
    expected_market_pack_revision,
    expected_booking_configuration_revision,
    expected_booking_configuration_fingerprint,
    expected_inventory_revisions,
    multipliers_by_market=None,
    demand_indexes=None,
    activation_providers=None,
    dated_flight_indexes=None,
):
    """Return a detached 5C plan; commit at most the already-approved 5B marker."""
    try:
        candidate = deepcopy(envelope)
    except Exception as exc:
        return _reject(
            envelope,
            "INVALID_WORLD_STATE",
            f"could not detach allocation input: {_exception_message(exc)}",
        )
    shopping = prepare_daily_booking_shopping(
        candidate,
        expected_demand_revision=expected_demand_revision,
        expected_market_pack_revision=expected_market_pack_revision,
        expected_booking_configuration_revision=expected_booking_configuration_revision,
        expected_booking_configuration_fingerprint=expected_booking_configuration_fingerprint,
        multipliers_by_market=multipliers_by_market,
        demand_indexes=demand_indexes,
        activation_providers=activation_providers,
        dated_flight_indexes=dated_flight_indexes,
    )
    if not shopping.succeeded:
        issue = shopping.issues[0]
        return _reject(envelope, issue.code, issue.message, issue.path, shopping.status)
    try:
        configuration = candidate["simulation"]["configuration"]["booking"]
        policy = configuration["choice_policy"]
        if policy.get("contract") != BOOKING_CHOICE_POLICY_CONTRACT:
            raise ValueError("unsupported production choice policy")
        shopping_revisions = {
            offer.dated_flight_id: offer.observed_inventory_revision
            for plan in shopping.market_plans
            for group in plan.desired_date_groups
            for offer in group.offers
        }
        relevant = {
            flight_id: candidate["world_state"]["dated_flights"][flight_id][
                "inventory_revision"
            ]
            for flight_id in sorted(shopping_revisions)
        }
        changed_after_shopping = sorted(
            flight_id
            for flight_id in relevant
            if shopping_revisions[flight_id] != relevant[flight_id]
        )
        if changed_after_shopping:
            return _reject(
                envelope,
                "STALE_REVISION",
                f"inventory changed after shopping: {changed_after_shopping!r}",
                status="STALE_REVISION",
            )
        try:
            _validate_expected_inventory(expected_inventory_revisions, relevant)
        except RuntimeError as exc:
            return _reject(
                envelope,
                "STALE_REVISION",
                _exception_message(exc),
                status="STALE_REVISION",
            )
        except (KeyError, TypeError) as exc:
            return _reject(envelope, "INVALID_INVENTORY", _exception_message(exc))
        booking_indexes = rebuild_booking_indexes(candidate)
        remaining = {}
        for flight_id in sorted(relevant):
            flight = candidate["world_state"]["dated_flights"][flight_id]
            consumed = booking_indexes.booked_passenger_count_by_dated_flight_id.get(flight_id, 0)
            value = flight["capacity"] - consumed
            if value < 0:
                raise ValueError(f"negative remaining capacity for {flight_id}")
            remaining[flight_id] = value
        capacity_limits = dict(remaining)

        world_seed = candidate["deterministic_state"]["world_seed"]
        cohort_date = shopping.cohort_date
        fingerprint = shopping.observed_booking_configuration_fingerprint
        groups = {}
        preterminal = {}
        for plan in shopping.market_plans:
            for group in plan.desired_date_groups:
                key = (plan.market_id, group.desired_travel_date)
                if group.disposition != SHOPPABLE:
                    preterminal[key] = group
                    continue
                scores = score_group_offers(group.offers)
                groups[key] = _GroupState(
                    plan.market_id, plan.cohort_key, plan.cohort_contract,
                    group.desired_travel_date, group.requested_passengers,
                    {offer.dated_flight_id: offer for offer in group.offers},
                    {item.dated_flight_id: item for item in scores}, {},
                )

        pending = {key: group.requested for key, group in groups.items()}
        available = {
            # Full offers deliberately participate in the first choice round.
            # Their selected share then becomes capacity overflow, preserving
            # the distinction between weighted OUTSIDE_OPTION choice and
            # terminal INSUFFICIENT_CAPACITY.
            key: set(group.offers)
            for key, group in groups.items()
        }
        rounds = 0
        while pending:
            requests_by_flight = {}
            round_requests = {}
            for key in sorted(pending):
                group = groups[key]
                if not available[key]:
                    group.insufficient += pending[key]
                    continue
                allocation = _choice(
                    group, pending[key], available[key], world_seed=world_seed,
                    cohort_date=cohort_date, policy=policy, fingerprint=fingerprint,
                )
                group.outside += allocation.pop(OUTSIDE_OPTION_SENTINEL, 0)
                round_requests[key] = allocation
                for flight_id, count in allocation.items():
                    if count:
                        requests_by_flight.setdefault(flight_id, {})[key] = count
            pending = {}
            if not requests_by_flight:
                break
            rounds += 1
            overflow = {}
            saturated = set()
            for flight_id in sorted(requests_by_flight):
                requests = requests_by_flight[flight_id]
                requested = sum(requests.values())
                capacity = remaining[flight_id]
                if requested <= capacity:
                    accepted = requests
                else:
                    accepted = _capacity_shares(
                        flight_id, capacity, requests, groups,
                        world_seed=world_seed, cohort_date=cohort_date,
                        policy=policy, fingerprint=fingerprint,
                    )
                assigned = sum(accepted.values())
                remaining[flight_id] -= assigned
                if remaining[flight_id] == 0:
                    saturated.add(flight_id)
                for key, wanted in requests.items():
                    got = accepted[key]
                    if got:
                        groups[key].selected[flight_id] = groups[key].selected.get(flight_id, 0) + got
                    if wanted > got:
                        overflow[key] = overflow.get(key, 0) + wanted - got
            if overflow and not saturated:
                raise ArithmeticError("capacity overflow did not remove an unavailable offer")
            for key in available:
                available[key].difference_update(saturated)
            pending = overflow

        market_results = []
        for plan in shopping.market_plans:
            date_results = []
            for shopping_group in plan.desired_date_groups:
                key = (plan.market_id, shopping_group.desired_travel_date)
                if key in preterminal:
                    no_service = shopping_group.requested_passengers if shopping_group.disposition == NO_ELIGIBLE_SERVICE else 0
                    no_date = shopping_group.requested_passengers if shopping_group.disposition == NO_DEPARTURE_ON_DESIRED_DATE else 0
                    date_results.append(DesiredDateAllocationResult(
                        shopping_group.desired_travel_date, shopping_group.requested_passengers,
                        0, 0, 0, no_service, no_date,
                    ))
                    continue
                state = groups[key]
                selections = tuple(
                    SelectedOfferAllocation(flight_id, state.offers[flight_id].airline_id, count)
                    for flight_id, count in sorted(state.selected.items()) if count
                )
                date_results.append(DesiredDateAllocationResult(
                    state.desired_travel_date, state.requested, sum(state.selected.values()),
                    state.outside, state.insufficient, 0, 0, selections,
                    tuple(state.scores[flight_id] for flight_id in sorted(state.scores)),
                ))
            sums = tuple(sum(getattr(item, field) for item in date_results) for field in (
                "requested_passengers", "selected_passengers", "outside_option_passengers",
                "insufficient_capacity_passengers", "no_eligible_service_passengers",
                "no_departure_on_desired_date_passengers",
            ))
            market_results.append(
                MarketAllocationResult(
                    market_id=plan.market_id,
                    cohort_key=plan.cohort_key,
                    cohort_contract=plan.cohort_contract,
                    requested_passengers=sums[0],
                    selected_passengers=sums[1],
                    outside_option_passengers=sums[2],
                    insufficient_capacity_passengers=sums[3],
                    no_eligible_service_passengers=sums[4],
                    no_departure_on_desired_date_passengers=sums[5],
                    desired_date_results=tuple(date_results),
                )
            )
        totals = tuple(sum(getattr(item, field) for item in market_results) for field in (
            "requested_passengers", "selected_passengers", "outside_option_passengers",
            "insufficient_capacity_passengers", "no_eligible_service_passengers",
            "no_departure_on_desired_date_passengers",
        ))
        result = DailyBookingAllocationResult(
            status="COMPLETED",
            contract=ALLOCATION_PLAN_CONTRACT,
            version=ALLOCATION_PLAN_VERSION,
            cohort_date=cohort_date,
            observed_demand_revision=shopping.observed_demand_revision,
            observed_market_pack_revision=shopping.observed_market_pack_revision,
            observed_booking_configuration_revision=(
                shopping.observed_booking_configuration_revision
            ),
            observed_booking_configuration_fingerprint=fingerprint,
            requested_passengers=totals[0],
            selected_passengers=totals[1],
            outside_option_passengers=totals[2],
            insufficient_capacity_passengers=totals[3],
            no_eligible_service_passengers=totals[4],
            no_departure_on_desired_date_passengers=totals[5],
            market_results=tuple(market_results),
            observed_inventory_revisions=tuple(
                InventoryRevisionObservation(key, relevant[key])
                for key in sorted(relevant)
            ),
            contention_rounds=rounds,
        )
        if not _validate_result(
            result,
            capacity_limits=capacity_limits,
            expected_inventory_revisions=relevant,
        ):
            return _reject(envelope, "RESULT_VALIDATION_FAILED", "Booking allocation result failed conservation or topology validation")
        final_validation = validate_world(candidate)
        if not final_validation.is_valid:
            issue = final_validation.errors[0]
            return _reject(envelope, issue.code, issue.message, issue.path)
    except Exception as exc:
        message = _exception_message(exc)
        if "choice" in message.lower() or "score" in message.lower():
            code = "INVALID_CHOICE_POLICY"
        elif "capacity" in message.lower() or "inventory" in message.lower():
            code = "INVALID_INVENTORY"
        else:
            code = "BOOKING_ALLOCATION_FAILED"
        return _reject(envelope, code, message)
    envelope.clear()
    envelope.update(deepcopy(candidate))
    return deepcopy(result)


__all__ = (
    "ALLOCATION_PLAN_CONTRACT", "ALLOCATION_PLAN_VERSION",
    "CAPACITY_RESIDUAL_RANK_PURPOSE", "CHOICE_RESIDUAL_RANK_PURPOSE",
    "DailyBookingAllocationResult", "DesiredDateAllocationResult",
    "INSUFFICIENT_CAPACITY", "InventoryRevisionObservation",
    "MarketAllocationResult", "OfferScoreEvidence", "OUTSIDE_OPTION",
    "SelectedOfferAllocation", "desired_date_score", "fare_score",
    "journey_duration_score", "prepare_daily_booking_allocation",
    "score_group_offers",
)
