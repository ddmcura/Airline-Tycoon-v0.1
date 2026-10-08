# Quarterly Dependency Read Foundation — Stage 2A

Schema 9 successor (2026-10-08): [flight-number reuse authority](Quarterly%20Flight%20Number%20Reuse%20Authority.md)
now implements protected historical display-number reuse and global retained endpoint
consistency using unchanged fields. Stage 2A reads remain compatible. Statements below
about unchanged Schema 8 or the next schema prerequisite describe this record's original
checkpoint; the next unimplemented slice is 2B. Quarterly workflows and commands
remain dormant; 3G-C remains PARKED.

**IMPLEMENTED: DORMANT READ FOUNDATION ONLY**, 2026-10-08.
Starting baseline **3d23d34f3d3ea6da3fb7f3578f7a274afd39c136**, matched local HEAD,
configured upstream, fetched origin/master and live remote master. Initially the tracked
tree/index were clean with only `.venv/` untracked. The archival stash reference/hash was
verified without reading its contents or using its production code as authority.

Authority: [finalized contracts](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md),
[Schema 8](Stage%201%20State%20Schema.md#quarterly-migration-stage-1-authority-foundation-schema-8)
and subordinate [template](../../Data/Templates/template_reference.txt).
Schema/template, world validation, constructors/allocators and persistence are unchanged.
The existing operational writer remains sole authority; no consumer is migrated.

## Implemented interface and scope

[game/scheduling/quarterly_reads.py](../../game/scheduling/quarterly_reads.py) contains
Scheduling-local `resolve_quarterly_reads`, immutable `PlanReadRequest`, `PlanRead`,
`SlotRead`, `ReadIssue` and `QuarterlyReadResult`. This is not a shared utility, mutation
API, command certificate, editable-state grant or new authoritative quarterly copy.

The caller supplies validated Schema 8 authority and a canonical airline ID with a
nonempty tuple of explicit plan read requests. Each request carries canonical plan ID,
expected CURRENT revision and optionally a retained revision and explicit service/slot
keys. Older facts can be inspected while the expected current pointer must still match.
Duplicate selection, malformed/missing IDs/slots and stale pointers reject explicitly.
Results contain either complete selected read views or issues, never partial successful
views after rejection. Canonical ordering makes equivalent selection order deterministic.

Direct owner proof resolves the actual airline/plan/service/aircraft/connection records
and requires owner equality. Market endpoints and slot facts use existing local validation.
The returned dependency set names only selected plans and their direct services, aircraft,
airports, connections, directional markets and airline number authority. Deadheads do not
invent a market. Display text is derived from current Schema 8 prefix/suffix authority;
it never proves ownership. Retired services remain historically readable.

[app/session.py](../../app/session.py) adds only `quarterly_plan_dependencies`, accepting
canonical plan ID, expected revision, optional retained revision/slot keys and immutable
`compare_with` requests. The existing `_owned_reads` boundary reacquires full validation
on a foreign world binding; unchanged owned authority keeps its existing trusted-read
behavior. No trust-boundary relaxation, private write capability or mutation dispatch.

Nested JSON facts are recursively copied into mapping proxies and tuples; result records
are frozen dataclasses. Neither frontend mutation nor later source changes can alter the
other side. These disposable reads are never serialized as game authority. No read
changes service/number/slot cursors, revisions, lifecycle, events, bookings, journals or
authoritative bytes. `source_time_utc` is the observed simulation time; it is not a saved
clock, session incarnation or future command freshness certificate. Future 2D freshness
remains separate; callers refresh reads after Load.

## Endpoint consistency and explicit coverage limits

The resolver compares endpoint pairs for each service across the slots/versions actually
selected in a request. Same service with changed time/weekdays can resolve consistently;
changed origin OR destination rejects with ENDPOINT_INCONSISTENCY. Explicit comparisons
can cover retained revisions and different quarters. A new service on a different route
is distinct and readable, not automatically matched to the old service.

There is **no global endpoint invariant added to Schema 8**. A single selected version
does not certify unrequested versions; a slot subset does not certify unselected slots.
No unrelated plans/history are searched to discover other references. Current complete
world validation and Save/Load still accept exactly their existing Schema 8 contract.
Global endpoint authority/validation remains part of the later schema-first prerequisite.
Read-local checks reject inconsistent supplied facts without modifying persisted authority.

No inverse relationships, temporal-neighbor expansion, full aircraft chronology, delivery
projection, editability, publication/Booking eligibility or occurrence materialization
is certified. Successful inspection of a published/retired record grants no editing right.

## Verification and scalability evidence

New coverage: [tests/test_quarterly_reads.py](../../tests/test_quarterly_reads.py).
Uses current scenario/constructors and TEMP SaveStore, not real Saves. Tests cover direct
owner chains, foreign references, dangling/mismatched IDs, deterministic requests,
stale/current/retained revision reads, recursive detachment, endpoint consistency scopes,
retirement, deadhead selection, exact serialized save/load equivalence, session foreign-
binding trust acquisition and unchanged repeated owned reads. Existing Stage 1 tests
retain their scheduling/Booking/runtime equivalence witnesses.

`.venv/Scripts/python.exe -B -m unittest tests.test_quarterly_reads
tests.test_quarterly_foundation -q`: **40 PASS in 20.022s** (20 new + 20 Stage 1).
The initial run of 38 cases had two fixture errors: connections were created after
cloning the world for endpoint comparisons. Corrected fixture order, added two cases
and reran the affected scope successfully. No production behavior was changed to fit it.
Targeted `.venv/Scripts/python.exe -B -m unittest tests.test_scheduling_recurrence
tests.test_step7_save_load tests.test_stage1_runtime tests.test_shared_candidate -q`:
**85 PASS in 147.496s**. Full `.venv/Scripts/python.exe -B -m unittest discover -s
tests -q`: **1175 PASS in 2469.631s** with source/tests frozen. Scoped compilation
(`app game tests main.py make_snapshot.py settings.py test.py`) PASS. Documentation
validation: 146 local links / 4 heading anchors, tracked casing/structure/scope and
whitespace PASS; complete diff/authority/alias/locality/scope review PASS. No giant
performance certification or runtime improvement claim. See also
[Current Development Status](Current%20Development%20Status.md).

Guarded table instrumentation forbids table iteration during trusted direct resolution;
no complete-world gate or allocator is called by that pure resolver. Constructor-created,
validated unrelated service populations 1/10/25/50/100/250/500/1000 produce the same direct
lookup count for the selected read. This is structural locality evidence, not a runtime
throughput certification or a 1,000-aircraft benchmark. Selected plan slot-list traversal,
existing local fact/timing validation and output copying cost the selected records.
Foreign session trust acquisition legitimately retains the existing complete gate.
No maintained indexes/caches, threading, global history scans or 3G-C are introduced.

## Remaining sequence and removable boundary

**Schema 9 prerequisite → 2B → 2C → 2D → 2E → later Stage 3 / consumer migration.**
Read-only 2A is implemented; no later slice is authorized by its completion. Schema 8
still permanently reserves historical numbers. No reusable pool, lowest-retired-number
allocation or high-water behavior is implemented. Product rules remain approved future
contracts. Quarterly workflows, carry-forward, automatic/manual publication, target
advancement, Bookings, GUI, acquisition/finance/history and runtime cutover stay dormant.
3G-C remains PARKED and separate; complete validation/transaction semantics stay intact.
Removing the new read module and session entry point leaves existing gameplay unchanged.
