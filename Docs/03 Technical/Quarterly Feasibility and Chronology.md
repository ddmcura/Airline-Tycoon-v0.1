# Quarterly Feasibility and Chronology — Stage 2C

Stage 2D successor (2026-10-08): [maintained inverse indexes and freshness](Quarterly%20Maintained%20Dependency%20Indexes%20and%20Freshness.md)
are implemented for dormant Scheduling-owned dependencies. Stage 2C proof/gates remain;
2E and quarterly activation remain pending. Earlier checkpoint limitations below are historical.

**IMPLEMENTED: DORMANT PLANNING COMMANDS ONLY**, 2026-10-08.
Starting baseline `3c7bddb4e03176022d6256975f393777cf8924b1` matched local HEAD,
upstream, fetched origin/master and live remote master. Tracked tree/index were clean;
only `.venv/` was untracked. Archival stash
`cba6426b52f7dfb229a524c0e986fe9680946c81` was verified by reference only.

Authority: [finalized contracts](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md),
[Schema 9](Stage%201%20State%20Schema.md#schema-9--reusable-flight-number-authority),
the subordinate [template](../../Data/Templates/template_reference.txt), and
[existing planning timing/positioning contract](Scheduling%20Planning%20Reposition%20Feasibility.md).
No schema/template, persistent field, gameplay formula, acquisition or operational writer changes.

## Explicit command surface

[quarterly_commands.py](../../game/scheduling/quarterly_commands.py) extends the existing
owner-issued session prepare/apply boundary; it does not replace it.
The requests in [quarterly_edits.py](../../game/scheduling/quarterly_edits.py) are:

| Request | Intent and retained identity |
| --- | --- |
| `ReviseQuarterlySlot` | Explicit non-endpoint facts on one existing service/slot. Timing is rederived; service, number and slot remain unchanged. |
| `AddQuarterlyFrequency` | New allocated slot on an existing nonretired service, with identical endpoints. Number is unchanged. |
| `RemoveQuarterlySlots` | Explicit canonical service/slot pairs removed only from the editable target revision. Removing all frequencies removes plan membership, not global identity. |
| `ContinueQuarterlySlot` | Explicit earlier source plan, expected current pointer, retained revision and service/slot lineage; optional non-endpoint changes. Existing target or explicit absence/quarter/revision 0. No service/slot/number allocation; a missing destination plan alone may be allocated. |
| `ReplaceQuarterlyService` | Remove the selected service's target-plan frequencies and create one distinct replacement service/initial slot atomically. Old service/history remain; no implicit retirement. Schema 9 chooses the new number. |
| `RetireQuarterlyService` | Explicit service and expected editable target plan. Unpublished nonended-quarter continuation must first be absent. Existing committed memberships remain unchanged and keep their number protection. Retirement retains history and does not append an otherwise unchanged plan revision. |

Existing `CreateQuarterlyService` and `ReviseQuarterlyFare` remain available, now with
affected chronology checks at apply. Surviving services are never renumbered. Endpoint
changes through a continuing-service edit reject; only explicit replacement allocates
new identity. Retired IDs never continue, although an explicit removal can clear an
old retired editable reference. Removal alone never releases a nonretired reservation.
Historical ended-quarter references do not prevent retirement. Unpublished future
continuation blocks retirement; active/future-committed memberships survive retirement
and continue protecting the number until their quarters end. No broad CRUD, automatic semantic matching or
automatic quarterly carry-forward is added.

## Chronology and dependency closure

[quarterly_feasibility.py](../../game/scheduling/quarterly_feasibility.py) reconstructs
the union of removed/old and inserted/new slot relationships. Changed assignments
check both aircraft. For each affected aircraft, all relevant current plan versions
are projected over their finite UTC quarters using origin-local pinned timezone/fold
conversion. Maximum preparation/block/post bounds come from `planning_snapshot` and
`timing_bounds`; overlap, handling, minimum turnaround and positioning use the existing
`PlanningFeasibility.conflict` inequalities. Every later adjacency is checked, without
a fixed two-neighbor cutoff or initial-prefix omission.

Weekly wrap, overnight work and adjacent quarters share one chronological sequence.
Origin-local dates can straddle UTC-quarter boundaries. A canonical service/date/slot
collision rejects even when the two quarter versions assign different aircraft.
Nonexistent DST departures reject rather than shift. Publication state never grants
permission to alter a committed version.

Legacy dated reservations, recent actual arrival/readiness and active arrivals remain
in the proof. Relevant active legacy definitions are virtually expanded through the
entire affected quarter/neighboring retained plans, rather than only the legacy 90-day
planning window. Removal still checks the old aircraft through the removed quarter.
Continuous legacy obligations are not suppressed at a proposed quarterly cutover.
Proof rows are disposable; no dated authority, event, passenger, movement or accounting
record is created. History is not used to discover future aircraft location; only
still-relevant actual arrival/handling facts anchor readiness.

## Planning proof versus execution

The approved draft positioning rule permits a hypothetical reposition when existing
maximum travel/handling and scalar range fit the gap. This is **planning feasibility**,
not literal execution readiness. It does not move an aircraft, insert DEADHEAD supply,
charge costs or authorize teleportation. Later publication/consumer migration must
resolve actual positioning explicitly. Impossible gaps reject now.

Current acquisition delivers immediately to authoritative fleet/location state.
Only PARKED or an authoritative IN_FLIGHT arrival can anchor planning; missing aircraft
or unsupported availability fails closed. There is no delayed-delivery authority to
project. Current scalar range, installed configuration/capacity and approved airport
timing profiles are enforced. Runway/payload-range performance, reconfiguration history,
advanced maintenance/disruption and future delivery contracts are not implemented;
this slice does not claim to certify those absent rules.

## Freshness, atomicity and transitional cost

Preparation remains an immutable intent/source witness, **not acceptance or a reusable
feasibility certificate**. It allocates nothing in authoritative state. Observations
include relevant current plan/lineage facts, aircraft, airport rules, scheduling policy,
legacy definitions, future/residual dated reservations and active operations. Missing
or newly inserted relationships are discovered again at apply. Current source/destination
pointers, UTC, ownership, unpublished target and session incarnation are still required.

Apply stages existing constructors on an isolated candidate, validates full authority,
proves final affected chronology, builds detached validated state/results and compares
live observations again before synchronous commit. Rejection leaves all world bytes,
IDs/numbers/slot cursors, revisions, events and session progress unchanged. Failed
attempts can retry deterministically. New/Load/rebind invalidates issued preparations.
Successful results expose recursively immutable reads and canonical dependency IDs,
including relevant temporal plans, legacy reservations and operations.

Discovery still enumerates shared plan/schedule/flight mappings to filter relevant
relationships; retained legacy definition revisions may be observed. It does not scan
Booking or accounting for the new proof. Old quarterly revisions are not projected.
Finite projected occurrences are sorted, approximately O(projected relevant occurrences
log occurrences), with plan/legacy mapping discovery overhead. Independent complete-world
gates and two complete candidate copies remain and still scale with world/history size.
There is no performance improvement claim. Stage 2D owns maintained inverse relationships
and freshness; Stage 2E owns narrow transaction certification. Neither is implemented.

## Verification and remaining scope

Focused tests and exact verification results are recorded in
[Current Development Status](Current%20Development%20Status.md).
[Stage 2C regressions](../../tests/test_quarterly_feasibility.py) cover real timing,
weekly/UTC-quarter boundaries, DST, cross-aircraft occurrence collisions, legacy
continuous obligations, actual active arrivals, scalar range/profile rejection,
explicit continuation/replacement/removal/retirement, stale/foreign references,
atomic failure/retry, exact save/load and immutable reads.
Two old 2B fixtures now use feasible second departures: their original same-aircraft
same-time duplicates are intentionally rejected under the new chronology contract.

Schema 9 and Stage 2A remain valid. Schedule Builder, legacy publication/recurrence,
Booking365, runtime events, acquisition, finance, GUI and history remain operational
and unchanged. Quarterly workflows remain dormant. Stage 2D -> 2E -> later Stage 3 /
consumer migration require separate scope. Auto/Manual Publish, carry-forward activation,
Booking cutover, operational generation, maintained indexes, narrow transaction proof,
threading and 3G-C are absent/parked. No archival stash code was used.
