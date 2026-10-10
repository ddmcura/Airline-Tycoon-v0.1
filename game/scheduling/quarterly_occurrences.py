"""Bounded, derived quarterly lineage; no operational supply or certificates."""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping

from game.utils.quarters import parse_quarter_id
from game.world_state.timestamps import parse_canonical_utc, format_utc
from .quarterly_commands import _entry
from .quarterly_reads import (
    PlanReadRequest, ReadIssue, _ReadFailure, _positive, _freeze, resolve_quarterly_reads,
)
from .service_identity import occurrence_identity
from .local_time import local_departure
from .timing import timing_bounds


MAX_OCCURRENCE_REFERENCES = 128


@dataclass(frozen=True)
class QuarterlyOccurrenceReference:
    weekly_plan_id: str
    revision: int
    service_id: str
    slot_number: int
    operating_date: str

    @property
    def occurrence_key(self):
        return occurrence_identity(self.service_id, self.slot_number, self.operating_date)


@dataclass(frozen=True)
class OccurrenceReadRequest:
    reference: QuarterlyOccurrenceReference
    expected_revision: int
    expected_published_at_utc: str | None = None


@dataclass(frozen=True)
class QuarterlyOccurrence:
    reference: QuarterlyOccurrenceReference
    airline_id: str
    quarter_id: str
    published_at_utc: str | None
    flight_number: str
    market_id: str | None
    slot_facts: Mapping
    departure_utc: str
    planning_arrival_utc: str
    reservation_start_utc: str
    reservation_end_utc: str

    @property
    def occurrence_key(self):
        return self.reference.occurrence_key

    @property
    def committed(self):
        return self.published_at_utc is not None


@dataclass(frozen=True)
class OccurrenceReadResult:
    occurrences: tuple[QuarterlyOccurrence, ...] = ()
    source_time_utc: str | None = None
    issues: tuple[ReadIssue, ...] = ()

    @property
    def succeeded(self):
        return bool(self.occurrences) and not self.issues


def _sources(envelope, read):
    state = envelope['world_state']
    return _freeze({table + '/' + identity: state[table][identity]
                    for table, identity in read.dependencies if table != 'weekly_plans'})


def resolve_quarterly_occurrences(envelope, *, airline_id, requests,
                                  require_published=True, expected_time_utc=None):
    """Resolve up to 128 explicit dates, atomically returning detached diagnostics.

    No date enumeration, cached identity registry, legacy aliases, or allocations.
    Published lineage does not assert feasibility, sale eligibility or execution.
    """
    try:
        if (type(requests) is not tuple or not 0 < len(requests) <= MAX_OCCURRENCE_REFERENCES
                or type(require_published) is not bool):
            raise _ReadFailure('INVALID_REQUEST', 'requests', '1..128 immutable explicit requests required')
        selections, seen = {}, set()
        for request in requests:
            if (type(request) is not OccurrenceReadRequest
                    or type(request.reference) is not QuarterlyOccurrenceReference
                    or not _positive(request.expected_revision)
                    or not _positive(request.reference.revision)):
                raise _ReadFailure('INVALID_REQUEST', 'requests', 'canonical lineage and revision observations required')
            ref = request.reference
            key = ref.occurrence_key  # canonical service ID, date and positive slot
            if key in seen:
                raise _ReadFailure('DUPLICATE_OCCURRENCE', 'requests', 'one selected lineage per dated identity required')
            seen.add(key)
            if request.expected_published_at_utc is not None:
                parse_canonical_utc(request.expected_published_at_utc)
            group = (ref.weekly_plan_id, ref.revision)
            expected, slots = selections.setdefault(group, (request.expected_revision, set()))
            if expected != request.expected_revision:
                raise _ReadFailure('INVALID_REQUEST', 'expected_revision', 'conflicting current observations')
            slots.add((ref.service_id, ref.slot_number))
        _entry(envelope)
        now = envelope['simulation']['time_utc']
        if expected_time_utc is not None:
            parse_canonical_utc(expected_time_utc)
            if now != expected_time_utc:
                raise _ReadFailure('STALE_CONTEXT', 'time_utc', 'simulation UTC changed')
        plan_requests = tuple(PlanReadRequest(pid, expected, rev, tuple(sorted(slots)))
                              for (pid, rev), (expected, slots) in sorted(selections.items()))
        read = resolve_quarterly_reads(envelope, airline_id=airline_id, selections=plan_requests)
        if not read.succeeded:
            return OccurrenceReadResult(issues=read.issues)
        sources = _sources(envelope, read)
        views = {(p.weekly_plan_id, p.revision): p for p in read.plans}
        slots = {(p.weekly_plan_id, p.revision, s.service_id, s.slot_number): s
                 for p in read.plans for s in p.slots}
        output = []
        for request in requests:
            ref = request.reference
            plan = views[(ref.weekly_plan_id, ref.revision)]
            slot = slots[(ref.weekly_plan_id, ref.revision, ref.service_id, ref.slot_number)]
            if require_published and plan.published_at_utc is None:
                raise _ReadFailure('UNPUBLISHED_LINEAGE', 'revision', 'published commitment required')
            if (request.expected_published_at_utc is not None
                    and request.expected_published_at_utc != plan.published_at_utc):
                raise _ReadFailure('STALE_CONTEXT', 'published_at_utc', 'commitment observation changed')
            facts = slot.facts
            if date.fromisoformat(ref.operating_date).weekday() not in facts['weekdays']:
                raise _ReadFailure('INVALID_REFERENCE', 'operating_date', 'date not in selected frequency')
            departure = local_departure(envelope['world_state'], facts['origin_airport_id'],
                ref.operating_date, facts['departure_local_time'], fold=facts['departure_local_fold'])
            quarter = parse_quarter_id(plan.quarter_id)
            if not quarter.start_utc <= departure < quarter.end_exclusive_utc:
                raise _ReadFailure('INVALID_REFERENCE', 'operating_date', 'departure outside selected UTC quarter')
            pre, block, post = timing_bounds(facts['planning_timing'])[1]
            arrival = departure + timedelta(seconds=block)
            output.append(QuarterlyOccurrence(ref, airline_id, plan.quarter_id, plan.published_at_utc,
                slot.flight_number, slot.market_id, facts, format_utc(departure), format_utc(arrival),
                format_utc(departure - timedelta(seconds=pre)), format_utc(arrival + timedelta(seconds=post))))
        _entry(envelope)
        final = resolve_quarterly_reads(envelope, airline_id=airline_id, selections=plan_requests)
        if final != read or _sources(envelope, final) != sources:
            raise _ReadFailure('STALE_CONTEXT', 'sources', 'sources changed during resolution')
        output.sort(key=lambda row: (row.departure_utc, row.occurrence_key))
        return OccurrenceReadResult(tuple(output), now)
    except _ReadFailure as exc:
        return OccurrenceReadResult(issues=(exc.issue,))
    except (ValueError, KeyError, TypeError, OverflowError, AttributeError) as exc:
        return OccurrenceReadResult(issues=(ReadIssue('INVALID_REFERENCE', 'quarterly_occurrences', str(exc)),))
