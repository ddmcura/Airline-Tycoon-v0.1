# Quarterly Boundary Orchestration and Recovery — Stage 3D

Bounded dormant foundation, 2026-10-10. Approved starting revision:
`7c3fb6110bb3aa1550e3a919ce8a4ec8a4effae4`; HEAD, upstream, fetched origin/master
and live remote matched. Authority: [Schema 9](Stage%201%20State%20Schema.md),
[quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md),
[finalized Stage 2 contracts](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md),
[shared publication](Quarterly%20Shared%20Publication.md),
[runtime safety](Runtime%20Causal%20Generation%20Accounting.md) and
[save specification](Game%20State%20%26%20Save%20Technical%20Specification.md).

## Ownership and isolated enrollment

Scheduling owns the strict `QUARTERLY_PUBLICATION` handler and fresh Stage 3C
prepare/apply work. Simulation owns queue selection, complete-event transactions,
strict/shared fences, time and failure pause. World State owns optional obligation
construction/validation. The session remains the serialized application owner.

`enable_quarterly_boundaries_for_testing` explicitly enrolls one owner in a valid
paused isolated world. No New Game, ordinary Load, pacing or GUI path calls it.
Enrollment needs an upcoming real draft or preceding committed baseline. A new
month-three airline's first after-next target keeps its later automatic date;
no incoming/current initial plan is invented. Ordinary PH worlds omit enrollment.
An explicitly enrolled save retains that controlled test-world behavior after Load.
Default dispatch is bound lazily only when processing enrolled worlds; ordinary
startup's built-in registrations remain unchanged. A custom registry must supply
the exact strict publication handler; an unknown/substitute handler fences safely.

## Calendar and ordering barrier

The obligation's quarter determines its exact UTC boundary: March 1 → Q2,
June 1 → Q3, September 1 → Q4, December 1 → next year's Q1, at 00:00:00Z.
There is no local-time arithmetic or elapsed-day approximation.

The derived queue key is `(due UTC, (publication rank, persisted priority),
persisted sequence, event ID)`. Publication rank is 0 for quarterly boundary events
and 1 otherwise. Persisted priorities remain nonnegative and unchanged. Mandatory
publication therefore precedes Booking even when Booking was enqueued first with
priority 0. All unrelated events retain their existing relative order. Pending-event
projections use the same key. No Booking event is silently rescheduled or repriced.

Quarterly publication is always strict, flushing preceding shared work before its
transaction. Next Event retains its one-event semantics: it may complete publication
and leave Booking at the same UTC for the next call. Each owner has an atomic plan
transaction; the kernel preserves a successful chronological prefix across owners.
No same-boundary consumer can pass a remaining failed owner obligation.

## Durable obligation, failure and correction

Optional `simulation.quarterly_publication` maps an immutable airline ID to exactly
`{next_quarter_id, failure}`. This is authoritative required domain work, independent
of a reconstructible queue index. `failure` is null or `{code, message, details}`.
The frontier is advanced exactly one quarter only with a successful publication
or validated committed skip in the same complete event. Unrelated handlers cannot
change or erase these entries. No separate scheduler or saved preparation exists.

On rejection the isolated publication candidate is discarded. A separately validated
detached fence transition sets only boundary UTC, PAUSED/no fast-forward target, and
diagnostics. The original event, all dependent events, plan versions, financial state,
history and domain allocators remain unchanged. The session exposes detached durable
diagnostics through `quarterly_boundary_status`; failure reports retain structured
Scheduling issue code/path/message. Explicit advancement cannot cross the obligation.

The sole edit-window exception is a genuinely failed obligation whose due equals
current UTC. It authorizes the existing certified Scheduling commands for that
unpublished quarter, including initialization from a real carry-forward baseline.
It never permits published revision rewriting, an unrelated closed quarter, forged
preparation or stale issuance. Correction appends ordinary complete revisions and
retains ownership, endpoint identity, numbering and full chronology protections.
Successful correction leaves the fence outstanding until publication succeeds.
No arbitrary past-quarter editor or operational exception/amendment policy exists.

Explicit retry processes the original obligation with fresh owner/current revisions,
sources, chronology, literal positioning and confirmed lease horizon checks. Stage 3C
retains all four full gates and both world copies; the outer event transaction adds
its existing isolation/validation/detachment. Readiness is never a certificate.
Before frontier advancement, the handler confirms the actual target commitment.
Repeated unchanged failures preserve identical world bytes. A confirmed prior manual
commit is skipped without recommitment; only event lifecycle/frontier bookkeeping
changes. Pending consumers resume in authoritative order after successful retry.

## Versioned reconciliation and save recovery

`QUARTERLY_BOUNDARY_V1` stores one outstanding quarter per enrolled owner, rather
than enumerating future occurrences. Processing reconstructs at most one missing
current-revision publication event per owner, in immutable owner-ID order. It never
scans/regenerates historical quarters or introduces retroactive Booking effects.

STALE events retain normal lifecycle history but cannot discharge the obligation.
A fresh matching event remains or is reconstructed. Duplicate/obsolete publication
events complete as budgeted lifecycle-only work once their quarter no longer matches
the outstanding frontier; they cannot advance it again. Future duplicates remain
queued and are individually resolved, rather than removed outside processing limits.
One successful event schedules the next calendar obligation, so large advances cross
each required boundary through the same kernel and its finite request limits.

Existing serialization preserves the optional JSON state without a version bump or
migration. Older Schema 9 saves omit it and remain ordinary worlds. Before-boundary,
fenced, missing-event and stale-event snapshots validate separately and restore
paused. Dispatch and queue reconciliation happen on subsequent explicit processing;
Load/rebind revoke prior command issuance and retain the saved fence. A frontier
before saved UTC is invalid; no unsupported historical repair is attempted.
Pending or historical quarterly events require their owner's enrollment entry;
omitted continuation authority rejects instead of silently converting to ordinary
gameplay. Detection uses the validator's existing event traversal, so ordinary
validation does not add a separate history scan.
SaveStore's complete-boundary, previous-valid-file and no-real-Saves test rules remain.

## Safety, verification and performance

Patch 1.2B remains unchanged: default 100 same-time causal generations and 10,000
processed/stale events per request, counts across yields and shared flushes, reset
only on chronological progress. Later-time children stay queued and do not consume
the same-time budget. Explicit Advance retains its existing configured generation
limit. Quarterly duplicates count as events; no publication-specific bypass exists.

Focused tests in [test_quarterly_boundaries.py](../../tests/test_quarterly_boundaries.py)
cover four calendar boundaries, leap/year rollover, manual skip, earlier-enqueued
Booking, unrelated order, source/cursor preservation on failure, unchanged retries,
certified correction including missing carry target, immutable commitments, no
consumer leakage, stale/missing/duplicate obligations, Save/Load/rebind, multi-boundary
advance, strict/shared/caps equivalence, actual four-gate/two-copy instrumentation,
same-time and processed-event limits, future child retention, forged success and
protected obligation writes. Ordinary-world strict/shared witnesses remain exact.
Final results and representative timings are recorded in
[Current Development Status](Current%20Development%20Status.md).

Final-source focused: **39 PASS, 99.242s**. Boundary/kernel/shared/resolver/safety/
startup: **166 PASS, 563.904s**. Quarterly 2A–2E/3A–3C and legacy/save regressions:
**396 PASS, 751.659s**. Full discovery: **1,476 PASS, 2,226.264s**, all **313**
source/test hashes unchanged. Scoped compilation, documentation/casing/fences,
whitespace and final scope review pass. Literal four-gate/two-copy instrumentation
and the same-time 100-generation stop are exercised by the new tests.

Three-run median strict one-aircraft boundary resolution **0.574298s**, unchanged
failed retry **0.397819s**, corrected empty retry **0.392059s**. Compact source sizes
321571/321165/321219 bytes; concurrent tests, selected two-slot/empty patterns,
outer event transaction included. No consumer processing or fleet-scale claim.

Initial focused iteration: 27 tests, 52.559s, four fixture errors. A helper shadowed
unittest's failure method; it was renamed. Late-month marketplace bootstrap seeds
also rejected their existing asking-price/utilization witnesses, so those boundaries
use validated exact-boundary scenarios without changing marketplace behavior. March
also tests the exact preceding second. Corrected 27 passed in 49.762s; expanded 34
passed in 80.163s before the final defensive checks/coverage. Full/final-source
verification supersedes these intermediate iterations.

Self-review added rejection of missing enrollment with retained publication history.
Earlier combined/full runs were stopped for that source correction. The intermediate
runtime run completed 164 cases in 529.379s with two stale fence-enumeration assertions;
they now include the new protected fence while explicitly requiring its absence in
ordinary gameplay. Final coverage is 39 added boundary cases. No partial discovery
or interrupted regression run is reported as passing.

Reconciliation uses finite enrolled-owner/pending-event scans, not an unbounded
calendar/occurrence registry. Publication retains full-world gates/copies and complete
finite chronology. Runtime capacity remains NOT CERTIFIED; small fixture measurements
are observations, not a fleet-scale performance certification.

## Deferred consumer integration

Quarterly operational gameplay remains dormant. No quarterly dated flights/inventory,
Booking365 economics/migration, Departure/Completion/Finance consumer cutover, automatic
positioning, GUI controls, offline progress or runtime pacing changes are introduced.
Stage 3E owns consumer migration and its unresolved commercial policies, 3F GUI/session
flows, and 3G coherent end-to-end activation. Runtime 3G-C remains parked and separate.

## Exact changed-file scope

Source and tests:

- [app/session.py](../../app/session.py)
- [game/scheduling/quarterly_boundary.py](../../game/scheduling/quarterly_boundary.py)
- [game/scheduling/quarterly_commands.py](../../game/scheduling/quarterly_commands.py)
- [game/simulation/kernel.py](../../game/simulation/kernel.py)
- [game/simulation/projections.py](../../game/simulation/projections.py)
- [game/simulation/resolver.py](../../game/simulation/resolver.py)
- [game/simulation/shared_candidate.py](../../game/simulation/shared_candidate.py)
- [game/world_state/quarterly_boundary.py](../../game/world_state/quarterly_boundary.py)
- [game/world_state/validation.py](../../game/world_state/validation.py)
- [tests/test_quarterly_boundaries.py](../../tests/test_quarterly_boundaries.py)
- [tests/test_simulation_resolver.py](../../tests/test_simulation_resolver.py)

Documentation and template:

- [Data/Templates/template_reference.txt](../../Data/Templates/template_reference.txt)
- [Docs/README.md](../README.md)
- [Quarterly Planning, Weekly Services & Bounded Booking Architecture.md](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md)
- [Continuous Runtime Technical Specification.md](Continuous%20Runtime%20Technical%20Specification.md)
- [Current Development Status.md](Current%20Development%20Status.md)
- [Decision Register.md](Decision%20Register.md)
- [Game State & Save Technical Specification.md](Game%20State%20%26%20Save%20Technical%20Specification.md)
- [Quarterly Boundary Orchestration.md](Quarterly%20Boundary%20Orchestration.md)
- [Quarterly Dependency Ownership and Command Contracts.md](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md)
- [Quarterly Shared Publication.md](Quarterly%20Shared%20Publication.md)
- [Stage 1 State Schema.md](Stage%201%20State%20Schema.md)

No protected metadata, environment, reference scenario, operational consumer or
unrelated source change is included. Verification scratch files are excluded.
