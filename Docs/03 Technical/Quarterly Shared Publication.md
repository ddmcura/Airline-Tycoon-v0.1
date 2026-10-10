# Shared Quarterly Publication Workflow — Stage 3C

**IMPLEMENTED: DORMANT SHARED TRANSACTION**, 2026-10-10. Starting baseline:
`13a01deeaa978a003e9103ec4a5554538fc49b7e`.
Authority: [Schema 9](Stage%201%20State%20Schema.md#schema-9--reusable-flight-number-authority),
[finalized domain contracts](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md),
[quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md),
[readiness](Quarterly%20Publication%20Readiness.md),
[lineage](Quarterly%20Operational%20Lineage.md) and
[transaction certification](Quarterly%20Transaction%20Certification.md).

## Shared command and invocation

Scheduling owns `PublishQuarterlyPlan(mode, quarter_id, weekly_plan_id=None,
expected_revision=0, expected_time_utc=None)`. `mode` is exactly `MANUAL` or
`AUTOMATIC`. Both enter the existing session `prepare_quarterly_command` /
`apply_quarterly_command` transaction and exact-object issuance boundary. No GUI,
timer or runtime event invokes this command. A readiness/occurrence snapshot never
substitutes for an issued preparation. Pause/completed-boundary requirements remain.

Manual target is the currently eligible unpublished future quarter, starting from
normal UTC targeting and skipping committed periods. It may publish early without
changing operating dates or simulation UTC. Automatic invocation is legal only at
March/June/September/December 1, 00:00:00 UTC, for the immediately following quarter.
It never jumps forward to publish the planning target. Late recovery/fences are 3D.

Expected current revision and actual owner/quarter must agree for an existing plan;
explicit absence requires ID null/revision 0. An existing manually committed automatic
target requires its actual ID/revision observation and succeeds as an immutable skip,
not a new commitment. Manual recommit rejects. Successful publication advances only
the derived planning target; no pointer is saved or moved backwards.

## Carry-forward and storage

The latest preceding published current version is the baseline, including an early
commitment. An existing target's complete current revision is authoritative: its
edits/removals/empty pattern are used exactly, never merged with absent baseline rows.
A missing target derives baseline slots, excluding explicitly retired services, then
creates one ordinary Schema 9 plan/revision in the isolated candidate. An existing
draft containing a retired service rejects rather than silently repairing its facts.
No baseline and no target rejects `MISSING_PLAN`; a new airline gets no invented plan.

Schema 9 requires full slot lists, so the new target stores the one required detached
weekly snapshot. Services, slot numbers, aircraft IDs and numbers are reused; no
new service/frequency allocation or extra inheritance/supply representation exists.
Historical baseline/versions remain untouched. Publication sets only the existing
current revision's `published_at_utc`; it does not append a redundant revision.
The first `CreateQuarterlyService` or `ContinueQuarterlySlot` edit of a missing
eligible target also seeds this same default baseline before applying its explicit
change. A new service appends to the inherited snapshot; explicit continuation may
amend its one inherited frequency while preserving all others. Baseline dependencies
are included in preparation/freshness and the full affected-aircraft proof. Subsequent
edits address that complete stored revision, so omission/removal is unambiguous and
publication never has to infer whether a row was removed or merely not copied.
An explicitly empty target, or an empty valid baseline after retirement, may commit
an empty strategic version. This records no service and introduces no operational
event policy. Saved baseline IDs/inheritance flags/frontiers are unnecessary: fixed
new plan/version facts and permanent IDs fully resolve dated lineage.

## Atomic boundary, readiness and retry

Actual publications retain all four full gates: prepare source, apply source,
candidate and detached commit state; both whole-world copies retain their separate
isolation/alias roles. Existing Stage 2 commands keep their certified paths.
Stage 2D stages/verifies the affected plan delta and prepares the rebound immutable
index before exposure. All selected aircraft participate even for unchanged rows.
Stage 2C complete finite chronology covers neighboring quarters, service/date/slot
collisions, active arrivals and still-authoritative legacy commitments.

Reuse 3A literal positioning diagnostics and confirmed contract-horizon checks.
Hypothetical travel blocks executable publication. Explicit timed DEADHEAD may close
a chain; no flight, movement or charge is inserted. Schema/configuration, range,
airport, handling, lease/delivery and retained identity rules stay intact.

Exact owner/current plans, selected/baseline facts, service/dependency/contract and
temporal/legacy observations guard prepare/apply and the final no-yield exposure.
Every fallible construction, validation, proof, response and index preparation runs
before authoritative exposure. Failure consumes no allocation or accepted epoch;
an unchanged valid issued preparation can retry deterministically after transient
failure. Correcting source plans/dependencies requires fresh preparation, preserving
all existing commitments. Load/rebind revoke issuance. No failure state is saved.

An already-committed automatic skip has no mutation candidate or index delta. It
uses source validation/freshness and immutable committed reads, consumes issuance,
and leaves world bytes/root, accepted index and unsaved status unchanged. It does
not bypass validation on any write or relax the four gates/two copies of publication.

## Persistence, performance and deferred integration

No new persistent shape, schema version, serializer or migration is required.
Save/Load preserves current Schema 9 commitment timestamps/full revisions with
separate-candidate validation and paused restoration. Derived planning targets,
baseline observations, command mode/results and occurrence descriptors are unsaved.
One service/date/slot identity remains qualified by its exact published plan/revision.
No operational rows, inventory, event, finance/history or legacy supply change occurs.

Owner/index discovery uses Stage 2D where covered; current selected facts and finite
quarter proof still cost their actual size. Full gates/copies retain world/history
cost, and Schema 9 snapshots cost selected slots. No full-quarter authoritative
materialization, persisted cache or optimization claim. Verification and measured
candidate size/latency/gate/copy costs are recorded before completion.

Final-source deterministic probes, one selected aircraft/two slots, with 0/10/25
unrelated aircraft. Existing-plan measurement includes a cold index; carry-forward
uses the accepted warm index from that commitment. All four gates and two whole-world
copies are separately timed; serialized candidate and detached sizes agree. End-to-end
times include response/index work and byte-count instrumentation. Concurrent test
runs and single samples preclude throughput/capacity/scalability claims.

| Path / total aircraft | Source bytes | Candidate/detached bytes | Prepare+apply seconds | Four gates total seconds | Two world copies total seconds |
| --- | --- | --- | --- | --- | --- |
| Existing / 1 | 321127 | 321145 | 0.354378 | 0.188046 | 0.033517 |
| Carry-forward / 1 | 321145 | 322859 | 0.418161 | 0.215626 | 0.028369 |
| Existing / 11 | 345635 | 345653 | 0.386365 | 0.241883 | 0.028235 |
| Carry-forward / 11 | 345653 | 347367 | 0.445568 | 0.254526 | 0.028180 |
| Existing / 26 | 379731 | 379749 | 0.464096 | 0.276695 | 0.029289 |
| Carry-forward / 26 | 379749 | 381463 | 0.472331 | 0.282027 | 0.038797 |

Every probe preserves the exact operational witness. Source/world history validation,
copy bytes, finite chronology and immutable index-map publication still scale with
their real inputs. No permanent occurrence/state reduction or runtime certification
is inferred. Temporary measurement fixtures/artifacts are excluded.

## Verification record

[Publication tests](../../tests/test_quarterly_publication.py) cover literal UTC
calendar/second/year/leap expectations, explicit snapshot/removal/retirement oracles,
first-edit baseline preservation, independent indexed/source-scan observations and
exact serialized outcomes. Shared transaction/timing formulas are not claimed as
independent reimplementations. Four-gate/two-copy/alias instrumentation, real candidate
validation corruption, fallible staging/index/result/final-freshness failures,
allocation rollback and deterministic issued-object retry preserve authority/epochs.
Legacy timed DEADHEAD, cross-aircraft adjacent-quarter key collisions, lease expiry,
Load/rebind/forgery and published Save/Load/3B reconstruction are included.

Final focused run: **41 PASS in 85.654s**. Relevant command/feasibility/index regressions:
**104 PASS in 90.068s**. Final combined regressions: **396 PASS in 673.335s**.
First-edit carry-forward was corrected during self-review;
superseded combined/full runs were stopped, not claimed as final verification. Final
full discovery: **1,437 PASS in 2,156.201s**, baseline 1,396 + 41. All 310 source/test
SHA-256 witnesses match before/after final discovery. Scoped application compilation,
375 local links / 63 heading targets / 9 documents, tracked casing/fences, whitespace
and final scope review PASS. Exact commands and scope evidence are recorded in
[Current Development Status](Current%20Development%20Status.md). Quarterly operational
gameplay remains dormant throughout.

Stage 3D owns boundary events, publication-before-Booking queue mechanics, visible
pause/correction, failure persistence/fences and recovery. Stage 3E owns Booking
policy/consumer migration; operational Departure/Completion/Finance/save integration,
GUI and coherent activation remain later scope. No automatic positioning, delayed
delivery, new configuration history or 3G-C. Quarterly operational gameplay is dormant.
