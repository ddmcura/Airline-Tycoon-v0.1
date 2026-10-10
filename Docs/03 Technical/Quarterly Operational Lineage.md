# Quarterly Operational Lineage and Occurrence Contracts — Stage 3B

Stage 3C successor: [shared publication](Quarterly%20Shared%20Publication.md) fixes
the existing revision timestamp or creates one ordinary carry-forward snapshot,
preserving service/slot/date and published-version lineage. Descriptors remain
derived; no dated operational row or consumer migration is added.

**IMPLEMENTED: FINALIZED CONTRACT AND DORMANT FOUNDATION**, 2026-10-10.
Starting baseline: `5d33a62c20c81a165297fef53d3b46470f90e982`.
Implementation and verification evidence belongs in
[Current Development Status](Current%20Development%20Status.md).

Authority: [Schema 9](Stage%201%20State%20Schema.md#schema-9--reusable-flight-number-authority),
[template mirror](../../Data/Templates/template_reference.txt),
[quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md),
[Stage 2 contracts](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md),
[transaction certification](Quarterly%20Transaction%20Certification.md) and
[readiness](Quarterly%20Publication%20Readiness.md).
This finalizes derived reference resolution within existing authority. It does not
select new persisted consumer fields or authorize publication/activation.

## Identity, fixed lineage and lifecycle

| Role | Authoritative representation and relationship |
| --- | --- |
| Permanent service | `services[service_id]`; direct airline owner, retained number allocation and retirement. ID never reused. All retained slot endpoints agree. |
| Frequency | `(service_id, slot_number)`; stable allocated number, never recycled. Facts belong to an explicit plan revision. Multiple weekdays reuse this frequency. |
| Strategic version | `(weekly_plan_id, revision)` under its airline/UTC quarter. Expected current pointer is a freshness observation, distinct from the explicitly selected retained version. |
| Published commitment | That exact revision's non-null `published_at_utc`; Schema 9 permits only the current revision to be published. No extra commitment ID or lifecycle enum. |
| Dated identity | `service_id@origin-local-date#slot_number`, excluding revision, public number, departure time and aircraft. Applicability requires selected membership/weekday and converted UTC departure inside the plan quarter. |
| Dated lineage reference | Explicit plan ID, revision, service ID, slot number and canonical local date. The key is derived from these fields. Parsing a key or matching a number never establishes owner or commitment. |
| Planned assignment | Selected slot's canonical `planned_aircraft_id`, with matching airline ownership. It is a reference to Fleet authority, not actual aircraft location or movement. |
| Planned interval | Pinned origin timezone/fold and retained timing snapshot; maximum preparation/block/post bounds. UTC quarter membership depends on departure, while arrival/handling may extend into the next quarter. |
| Operational obligation | Future materialized fixed commitment/outcome/inventory witnesses must reference the same dated identity and exact published version. Stage 3B creates none. |

Continuation is explicit: same service/slot IDs across allowed versions, even when
time/fare/aircraft changes. Endpoint replacement needs a new service. Removal affects
one plan version; retirement retains committed and historical references. Number reuse
does not identify continuation, move sold obligations or renumber survivors. Retired
committed references remain readable and protected under Schema 9.

The same key in two requested versions is rejected as ambiguous/duplicate, even if
their projected facts agree. One query never returns competing facts for one identity.
Different UTC quarters can map local dates around their shared boundary; a collision
must not be repaired by adding revision/quarter/aircraft to the identity. Stage 2C
remains the complete publication-planning chronology proof. Reference resolution
validates selected lineage, not unrequested chronology or execution permission.

## Representation and consumer boundaries

Stage 3B descriptors are **derived, detached, runtime-only**. Authoritative stored
facts remain services, allocators, plans/revisions and publication timestamps. There
is no occurrence table, frontier, duplicated assignment, supply index or saved cache.
Queries resolve at most 128 explicit date references; they never enumerate a whole
quarter or manufacture an absent plan. Rejection returns no partial descriptors.

The approved staged/hybrid direction is retained: future publication establishes
fixed lineage; reproducible unsold descriptors may be derived, while sold obligations,
inventory/operation witnesses, exceptions and finalized history require schema-first
persistence. This foundation does not choose full-quarter materialization, thinning,
carry-forward storage, event lead times or a generation frontier.

| Consumer | Required future integration boundary; current authority retained |
| --- | --- |
| Booking | Same occurrence identity + published plan/revision, fixed commercial facts and inventory revision; one capacity authority across itinerary/manifest. Publication alone is insufficient sale eligibility. Existing desired-date/lead economics need an explicit Stage 3E decision. |
| Departure/Completion | Resolve committed lineage and validated aircraft/operation/event witnesses; consume actual execution facts independently of strategic intent. Actual cancellation/delay does not rewrite the plan. |
| Finance/history | Transaction/result IDs reference the same occurrence and retained service/version facts; preserve ticket cash/liability/revenue/cost equations and finalized history. No public-number joins. |
| Simulation | Future persisted event payloads must resolve exact committed lineage and operation revision; preserve due/priority/sequence/ID order and causal retry. Publication precedes boundary Booking. No new event in 3B. |
| Save/Load | Persist existing Schema 9 authority unchanged; validate a separate candidate and reconstruct descriptors on explicit request after paused restore. Derived descriptors/provenance are not serialized. |
| Session/GUI | Existing serialized session owns query access at a paused completed boundary. No UI control or second state owner. Consumers must re-resolve after Load/rebind; returned snapshots are not capabilities. |

Legacy Scheduling/dated IDs/Booking365 remain the sole operational supply authority.
There is no lookup union, write-through mirror or automatic legacy-to-quarterly alias.
A later allocated row ID can only be a proven bijective alias to the quarterly key,
with explicit schema and consumer validation before cutover. No silent reinterpretation
of legacy `schedule_id`, `schedule_lineage` or `dated_flight_id` fields is permitted.

## API and trust boundary

Scheduling owns [quarterly_occurrences.py](../../game/scheduling/quarterly_occurrences.py).
`QuarterlyOccurrenceReference` carries
plan/revision/service/slot/date; `OccurrenceReadRequest` adds expected current revision
and optional expected publication timestamp. `resolve_quarterly_occurrences` takes
an immutable nonempty tuple (maximum 128), owner, optional expected UTC and
`require_published=True`. Explicit `False` permits diagnostic draft/retained inspection;
it never opens supply. Outputs contain frozen references, commitment timestamp,
derived key, selected immutable slot facts and maximum planning UTC intervals.

Full Schema 9 validation precedes and follows resolution. Stage 2A direct owner/FK
reads resolve selected versions and slots; expected pointers/UTC/publication facts
reject stale input. Exact selected source observations are compared again before
return. No cache epoch or lifecycle verdict is persisted or changed. Results cannot
enter command apply or act as reusable publication/operation certificates.

Resolution checks date/weekday, pinned timezone/fold/gaps, UTC quarter membership,
canonical ownership, endpoint and dependency consistency. It preserves the separate
3A planning/execution/eligibility conclusions. A resolved explicit DEADHEAD describes
intent only; execution still needs authoritative timed obligations and literal
continuity. No hypothetical positioning, aircraft delivery or costs are created.

## Cost and deferred prerequisites

For R explicit references (R <= 128), output and temporary requested-date work are
O(R), plus selected plan-slot inspection and direct dependency snapshots. Source
validation still costs the complete world/retained history; no constant-time overall
claim, changed gate, smaller transaction copy or performance certification is made.
No occurrence cache rebuild exists: repeated validated resolution is reconstruction.
Large arbitrary iterables are rejected without iteration. Batch size bounds descriptor
count, not bytes of authoritative aircraft/reference records or full validation.

Small deterministic probe (two daily frequencies, final source, concurrent regression
runs, `tracemalloc` enabled):

| Explicit references / returned descriptors | Whole-query seconds | Traced retained bytes | Peak traced bytes |
| --- | --- | --- | --- |
| 1 / 1 | 1.551292 | 112176 | 971093 |
| 32 / 32 | 1.284061 | 141449 | 1005477 |
| 128 / 128 | 1.511189 | 195778 | 1073869 |

These are single diagnostic samples including two full source gates, not throughput,
process RSS, additional persistent memory, or a before/after optimization comparison.
Temporary fixture/probe artifacts are excluded. Every probe preserves exact serialized
authority. Tests count two source gates and exactly one date conversion per reference;
the exact 128 limit yields 128 unique descriptors and 129 rejects before source work.
Full-suite verification and source-freeze evidence are recorded in development status.

[Focused tests](../../tests/test_quarterly_occurrences.py) use literal dated keys and
UTC boundary witnesses as independent expectations, plus the existing Stage 1 identity
helper as a shared-formula cross-check. Reversed request order, fresh world copies and
published Save/Load reconstruct equal output. Exact serialized-world comparisons cover
success and rejection, including operational/Booking/event/finance facts and cursors;
session tests retain accepted index identity/epoch and reject results as commands.
Valid late-source mutation rejects at final freshness comparison. Timing/feasibility
equations are reused rather than claiming independent reimplementation. Fixture API,
return-shape, stale local-pointer and test-placement mistakes were corrected; no
production contract defect or validation relaxation was needed.

Final verification: 28 focused cases PASS in 8.461s; combined regression invocation
341 PASS in 490.478s; frozen final full discovery **1,396 PASS in 1,906.995s**
(baseline 1,368 + 28 new cases). All 308 source/test SHA-256 witnesses match before/
after full discovery. Scoped application compilation, documentation validation
(356 local links / 61 heading targets / 8 documents), whitespace and final scope
review PASS. Exact commands and fixture-refinement timing are in development status.

Stage 3C must implement atomic shared publication/carry-forward/manual commitment;
Stage 3D must specify persisted event/failure/retry and operational witness fields;
Stage 3E must finalize Booking date/lead policy and one-supply migration; later GUI and
coherent activation must include Finance/history/save references. Exact new consumer
storage shapes are prerequisites to those writers, not blockers for derived 3B reads.
No additional persistent field is required here, so Schema 9/version/serialization
and development-save compatibility remain unchanged. Automatic positioning, delayed
delivery, configuration history, 3G-C and operational supply cutover remain deferred.
