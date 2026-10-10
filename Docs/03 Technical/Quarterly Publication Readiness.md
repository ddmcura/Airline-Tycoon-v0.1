# Quarterly Publication Readiness — Stage 3A

Stage 3B successor: [bounded lineage resolution](Quarterly%20Operational%20Lineage.md)
provides derived dated references without publication, materialization or consumer
activation. The three readiness classifications and this record's evidence remain.

**IMPLEMENTED: DORMANT DIAGNOSTIC ONLY**, 2026-10-10. Verification is recorded
in [Current Development Status](Current%20Development%20Status.md).
Starting baseline: `7f9336c85ae7a256be2e06618d829264bab907c1`.

Authority: [quarterly product architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md),
[finalized contracts](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md),
[Schema 9](Stage%201%20State%20Schema.md#schema-9--reusable-flight-number-authority),
the subordinate [template](../../Data/Templates/template_reference.txt),
[2C chronology](Quarterly%20Feasibility%20and%20Chronology.md) and
[2E certification](Quarterly%20Transaction%20Certification.md).
No persistent field, schema, template or operational consumer changes.

## Ownership and API

[quarterly_readiness.py](../../game/scheduling/quarterly_readiness.py) owns the
Scheduling query `inspect_quarterly_publication_readiness(envelope, *, airline_id,
request=None)`. `PublicationReadinessRequest` accepts an optional selected
`weekly_plan_id`, expected current revision, expected canonical UTC and expected
source observations. Explicit plan selection requires a positive expected revision.
Without selection, discover the eligible future target; revision 0 can explicitly
observe absence. Full Schema 9 source validation precedes discovery.

[Stage1Session](../../app/session.py) exposes
`quarterly_publication_readiness(weekly_plan_id=None, *, expected_revision=None,
expected_time_utc=None, previous=None)`. It uses the existing paused, completed
command boundary and session airline ownership. Bulk/runtime processing rejects
inspection. This diagnostic does not advance progression, set unsaved flags, or
add GUI controls. Scheduling retains domain ownership; no second state owner exists.

Results and issue tuples are frozen dataclasses; source maps and selected/baseline
views are recursively detached mapping proxies/tuples. All output fields are derived
or runtime-only, never authoritative state. A valid inspection has `succeeded=True`
even when readiness is blocked; `issues` describe invalid/stale inspection, while
eligibility/planning/execution diagnostics describe a valid inspected snapshot.

## Three independent classifications

| Field | Meaning |
| --- | --- |
| `publication_eligible` | Current calendar/lifecycle permission: selected existing unpublished plan is the eligible Manual Publish target or is exactly at its automatic boundary. This is not a publication acceptance result. |
| `planning_feasible` | Existing Stage 2C complete projected chronology and constraints pass. Hypothetical travel can satisfy this proof. |
| `execution_ready` | Planning passes, the inspected complete chain needs no hypothetical positioning, and lessor-owned arrivals fit confirmed contract horizons. This is a snapshot diagnostic, not a future execution guarantee. |

Missing plans and ended operating quarters have no planning/execution assertion
(`None`). Missing plans are reported without manufacturing slots or a baseline plan.
An existing empty plan is vacuously feasible/executable; this query does not settle
later empty-plan publication/event policy. Published or closed selections are
inspectable but do not gain publication permission. Historical inspection cannot
be used to authorize past operation or failed-publication correction.

## Calendar and baseline

Quarters and intervals are UTC `[start, next_start)`; flight intent stays airport-local.
The automatic date is the first UTC second of the preceding calendar month: March 1
for Q2, June 1 for Q3, September 1 for Q4, December 1 for next-year Q1. Arithmetic uses
calendar dates, not a fixed number of days. `automatic_due` is exact equality, not a
late retry or a persisted fence. Manual eligibility uses the existing target helper:
months 1–2 target next quarter, month 3 targets after next, skipping committed quarters.

`next_publication_boundary_utc` skips past/committed periods and incoming periods
with neither an existing plan, a preceding published baseline nor current initial-target
eligibility. A new month-three airline therefore retains the eligible after-next
quarter date. This field describes the applicable calendar pipeline; it schedules
nothing and does not declare a required publication event or recovery fence.

`baseline` is the latest preceding published current version for that owner. Early
Q2 commitment makes Q2 the Q3 baseline rather than an older active Q1. Stable service/
slot references are retained. Baseline inspection creates no carry-forward revision,
does not revive retired identities, and does not commit or materialize anything.

## Planning and literal execution

The query reuses the exact Stage 2C proof: all affected current quarterly versions,
complete week/quarter wrap, origin-local UTC applicability, pinned timezone/fold/gap
rules, cross-aircraft occurrence lineage, timing/range/airport/configuration,
active arrivals, recent actual handling and relevant legacy obligations. Maintained
Stage 2D relationships narrow discovery in owned sessions; borrowed worlds scan sources.

An optional diagnostic collector on that traversal records every adjacency whose
actual predecessor destination differs from the next origin. Feasible hypothetical
travel reports `UNRESOLVED_POSITIONING`; it inserts no DEADHEAD, movement, cost,
maintenance or event. Explicit quarterly DEADHEAD slots and authoritative legacy
timed movements participate in the same literal chain. A planning failure blocks
execution rather than fabricating a location or discarding an obligation.

Existing marketplace authority requires lessor-owned arrivals no later than the
confirmed contract horizon. The query reuses `confirmed_contract_horizon`, including
confirmed renewal chains, and observes their canonical contract IDs/facts. Projected
quarterly arrivals beyond that horizon report `CONTRACT_HORIZON_EXCEEDED`. No delivery,
renewal, ownership transfer or accounting action is introduced.

The explicit legacy positioning test exposed a Stage 2C defect: `_expand_schedule`
returns already materialized occurrence keys as well as virtual future rows. Counting
both created a false self-overlap. The minimal correction excludes known keys from
the virtual additions, retaining the actual committed dated facts. Timing equations,
real overlaps, source validation, command gates/copies and legacy operational writers
remain intact. Direct Stage 2C and readiness coverage verify the real positioning case.

## Freshness and read-only guarantees

Observe exact UTC, current owned plan versions/publication facts, selected and baseline
lineage, relevant aircraft/airport/connection/service facts, full temporal/legacy
dependencies and confirmed contracts. Expected observations are detached on entry;
changed facts reject with a stale diagnostic. A second full source validation and
final observation comparison guard the returned snapshot against late source changes.
Unrelated-owner cache epochs alone do not invalidate otherwise equal observations.

The session weakly registers issued read results only for optional `previous` freshness
comparison. New/Load/world rebind revoke them, including same-byte rebinds and forged
copies. A fresh inspection after Load derives equivalent output but does not restore
the old result's session provenance. A readiness result cannot enter command apply
and never serves as a reusable publication certificate.

No service/number/slot cursor, revision, publication timestamp, dated row, inventory,
event, finance/history fact or authoritative world byte is changed. Warm accepted
index objects/epochs remain unchanged. Cold reconstruction after explicit invalidation
is existing source-derived coverage at epoch 0, not an accepted mutation epoch.
Private unnotified writes and deliberate frozen/private-owner bypasses remain outside
the supported writer contract; full gates and owner invalidation are retained.

## Verification and deferred work

[Focused tests](../../tests/test_quarterly_readiness.py) compare literal calendar dates,
independent known positioning/lease cases, exact world witnesses, indexed/reference
outputs, cold rebuilds, active/legacy obligations, DST/collisions, source freshness,
Load/rebind, nested immutability and command-capability rejection. Scenario dates use
validated temporary scenario files so pending Booking successor witnesses are preserved.
No tests use real Saves. Final commands/counts are in Current Development Status.

Final focused/regression command: **313 PASS in 324.172s**, including all 33 readiness
cases. Scoped application compilation passes. Documentation validation: 170 local
links / 5 heading targets across 6 documents; tracked casing/fences and whitespace
pass. Full discovery: **1,368 PASS in 1,736.634s**; all 306 source/test SHA-256
witnesses match before/after the run. Final scope review passes. Initial failures were one
duplicate-keyword fixture error, the real duplicate legacy projection described above,
and a later test method placement error; these were corrected before this final run.

Known costs remain: two full source gates for inspection, current owner-plan observations,
finite complete chronology, retained legacy dependencies, contract-horizon reads and
existing index cold builds. The four command gates/two command copies are unchanged.
No new benchmark or performance improvement is claimed; this query is paused diagnostic
work, not incremental preparation or an optimization of publication/runtime.

Stage 3B–3G remain deferred: publication/occurrence schema and coherent consumer lineage,
carry-forward commitment, Manual/automatic publication, queue ordering, persisted fences,
failure correction/retry, Booking desired-date/lead policy, supply cutover, GUI and
end-to-end activation. Delayed delivery, configuration history, automatic positioning,
thinning, analytical skipping and 3G-C are not implemented. Later publication must
revalidate; none of these diagnostics resolves those contracts or activates gameplay.
