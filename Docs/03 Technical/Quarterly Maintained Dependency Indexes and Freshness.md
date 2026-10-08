# Quarterly Maintained Dependency Indexes and Freshness — Stage 2D

Stage 2E successor (2026-10-09): [transaction certification](Quarterly%20Transaction%20Certification.md)
extends independent coverage, rebuild/reference and adversarial atomicity evidence.
Final regression/full verification passes; this record retains its Stage 2D
checkpoint scope and historical measurements.

**IMPLEMENTED: DORMANT SCHEDULING DEPENDENCY INFRASTRUCTURE ONLY**, 2026-10-08.
Baseline `9277d96d126f2c4dcf6351a6f2b1b41ca0e1fabc` matched local HEAD, upstream,
fetched origin/master and live remote. Tracked tree/index were clean, only `.venv/`
untracked. Archival stash `cba6426b52f7dfb229a524c0e986fe9680946c81` was checked
by reference only, never read as implementation authority or changed.
Serena symbol navigation was attempted; Python language-server initialization failed.
Targeted source searches were used; no tooling repair or metadata editing was performed.

Authority: [finalized Stage 2 contracts](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md),
[Schema 9](Stage%201%20State%20Schema.md#schema-9--reusable-flight-number-authority),
subordinate [template](../../Data/Templates/template_reference.txt), and
[Stage 2C feasibility](Quarterly%20Feasibility%20and%20Chronology.md).
No schema/template, persistent field, GUI, Booking365, acquisition or runtime-consumer change.
The folder tree is a selective placement reference and requires no module inventory update.

## Ownership and derived structures

[quarterly_indexes.py](../../game/scheduling/quarterly_indexes.py) owns a private
immutable `QuarterlyDependencyIndex`; [session](../../app/session.py) owns its
`QuarterlyIndexOwner` lifetime. Neither enters `game_state`, saves, returned reads or
prepared command payloads. Internal root bindings are freshness/provenance guards;
they are not a second authoritative world or a frontend write capability.

| Lookup | Authoritative source and rebuild |
| --- | --- |
| Airline/quarter → plan; owner → plans/services | Canonical owner, quarter and ID fields; direct pair map and inverse ID sets |
| Service → retained endpoint pair | All retained revision-slot endpoints, including retired history; conflicting pairs reject |
| Service/aircraft → current plan memberships; aircraft → weekly slot keys | Current revision slots; canonical `(plan_id, service_id, slot_number)` references, not rows/display labels |
| Airport/connection → plans | Current slot endpoint/connection IDs |
| Aircraft → legacy schedules | Every retained schedule revision's assignment; current status/effective facts are read from authority |
| Aircraft → dated reservations, readiness expiry and temporal neighbors | Noncancelled/nonsuperseded dated IDs; sorted canonical departures and max(reservation end, arrival + minimum turnaround) |
| Aircraft → active operations | Authoritative actual-aircraft IDs |
| Number → holders and reusable suffixes | Indexed owner/service/retirement facts plus nonended committed memberships; deduplicated numeric eligibility reconstructed on query |

Number indexes preserve exclusive nonretired draft reservations, committed protection,
lowest eligible suffix ordering and historical service IDs. They do **not** replace the
Schema 9 allocator's authoritative holder/eligibility validation. No persisted pool.
Published market/date supply, Booking obligations/inventory and event selection indexes
remain owned by later consumers/existing Simulation; this slice does not migrate them.

Weekly and occurrence dependencies are indexed as canonical memberships. Quarter/date
and virtual legacy occurrence projections still run through Stage 2C's complete proof;
no cached feasibility verdict, persisted occurrence, new identity or date shortcut.
Retained dated IDs remain necessary for legacy known-occurrence exclusion. Hot readiness
selection uses sorted expiry lookup; history is retained, not compacted or deleted.

## Maintenance and freshness

New Game and validated separate-candidate Load establish exclusive session ownership.
The index is built lazily after the existing full entry gate, then reused across routine
paused quarterly reads/commands. Successful quarterly commands stage old/new membership,
endpoint and service-number deltas on an immutable candidate index. The coverage fence
compares exact resulting affected source facts and preservation of all other cached
relationships before indexed feasibility. A partial delta fails closed.

All fallible delta preparation, coverage checking, feasibility, detached-state validation,
result construction, publication readiness and final source comparison precede commit.
The serialized owner publishes validated authority and one prepared immutable index
reference without yielding. Failed commands publish neither mutation nor delta; cold
read reconstruction represents unchanged source authority and is not a mutation epoch.
Index epochs advance only with accepted quarterly deltas; no epoch is saved or used as
a global stale-command veto. Independent tests enumerate source relationships directly.

Existing exact typed preparation observations remain: canonical owner/current/source
revision, selected facts, memberships, aircraft, airports, legacy obligations, policy
and simulation UTC. Indexed discovery produces the same observations as source scanning.
An unrelated owner's change does not invalidate a preparation merely because a global
index/progression epoch changed. New/Load/rebind still revoke issued preparations.

Every other supported session management writer uses `_management_changed` →
`_mark_progress` invalidation: purchases/market acquisition, connections, rotations,
Schedule Builder save and legacy publication. Continuous runtime commits, explicit
Advance/event reports and time movement invalidate through the existing progress
notification. Invalidation is cheap and reconstruction lazy, not a rebuild every event.
Root identity/size, exact UTC and turnaround-policy guards also reject a mismatched
binding before lookup. Eligibility expires even without a strategic edit.

Foreign `session.world` bindings retain complete validation and source-scan fallback;
they do not acquire exclusive-writer provenance merely by passing structural validation.
The public direct domain functions default to the same reference fallback. This retains
safe behavior for caller-owned construction candidates and external in-place fixture
changes. Borrowed **owned** authority still follows the existing prohibition on direct
frontend writes: supported mutations must use owner notifications/verified deltas.
The root guard is not a deep detector for arbitrary unnotified private writes. New
writers must participate in invalidation before using maintained coverage.

## Stage 2C integration and retained costs

[Commands](../../game/scheduling/quarterly_commands.py),
[edits](../../game/scheduling/quarterly_edits.py) and
[feasibility](../../game/scheduling/quarterly_feasibility.py) select canonical relevant
IDs through maintained inverse relationships. They preserve complete old/new aircraft
chains, weekly/UTC-quarter wrap, cross-aircraft occurrence lineage, ground handling,
turnaround, range/profile checks, current availability and protected legacy/published
commitments. Index lookup alone cannot approve feasibility. Hypothetical positioning
still creates no actual movement; unavailable future delivery/runway/payload/configuration
history remains deferred. No publication or carry-forward activation.

Four full validation gates per prepare/apply pair and two whole-world candidate copies
remain. State constructors still perform authoritative allocation, uniqueness and
retained-endpoint checks. Existing full-plan detached reads/revision retention,
finite occurrence projection/sorting and related legacy history inspection remain.
Foreign bindings and invalidated legacy coverage use reconstruction/fallback.

Cold build scales with source memberships/retained slots/legacy history; dated interval
sorting adds sorting cost. Relevant lookup scales with returned IDs and local sorting,
not unrelated service enumeration; it is not universally constant-time. Immutable map
publication and coverage comparison cost O(index keys), plus affected edge work, because
shallow dictionaries are copied/compared. This is not narrow transaction optimization.
Memory scales with indexed relationships and retained legacy references.
Stage 2E remains **boundary certification**. The finalized contract requires separately
approved scope for any transaction-copy optimization; none is authorized/completed here.

## Reproducible measurements

`.venv/Scripts/python.exe -B -m tests.profile_quarterly_dependencies` uses validated
Schema 9 fixtures: one requested player service/aircraft plus 0/10/100/250 unrelated
services on separate purchased aircraft of another airline. Actual purchase journals
are produced; fixture construction and TEMP Save/Load are outside timing. Python 3.12.10,
this Windows development host; five lookup/build/delta trials (median), three session
prepare/apply trials (median). No hardware-independent SLA or fleet certification.
The committed baseline command module is loaded read-only from Git for gate/copy
diagnostics; archival stash code is never used. Reference/index queries share inputs.

| Unrelated services | Baseline temporal µs | Indexed temporal µs | Cold build µs | Verified delta/rebind µs | Payload estimate bytes | Baseline prepare/apply ms | Indexed prepare/apply ms |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0 | 19.2 | 40.6 | 23.0 | 54.8 | 5,557 | 25.9 / 106.3 | 26.0 / 109.9 |
| 10 | 23.7 | 37.3 | 48.6 | 63.4 | 18,965 | 32.0 / 130.5 | 32.2 / 134.5 |
| 100 | 37.2 | 39.6 | 288.8 | 160.3 | 133,979 | 56.9 / 207.6 | 56.0 / 207.4 |
| 250 | 66.5 | 39.0 | 788.6 | 332.0 | 316,165 | 95.8 / 340.3 | 94.3 / 343.6 |

Paired final-run reference/index temporal medians at 250 were 65.7/39.0 µs. Tiny fixtures
are slower with indexing, crossover is near 100, and total latency does not show a
meaningful improvement. Complete source observations remain about 3.5–3.8 ms because
local structural/reference validation and detached facts are retained.
Paired 250-service diagnostic gate totals: baseline/indexed 360.1/357.4 ms (4 each);
world-copy totals 44.7/36.4 ms (2 each). These are noisy single-pair samples, not evidence
that unchanged validation/copy algorithms improved. Their remaining cost dominates.
Payload is a reachable Python-container estimate, excluding authoritative root bindings
and RSS/allocator overhead, conservatively including shared ID strings; not unique
additional process allocation. These checkpoints are not the final thousands-aircraft target.

## Verification and next scope

[Focused tests](../../tests/test_quarterly_indexes.py) compare separate direct-field
source enumeration, indexed/unindexed observations and command authority, cold rebuild,
number-holder oracle, deterministic order, failure/partial-delta injection, legacy
invalidation, New/Load/rebind, assignment changes and weekly/quarter boundaries.
[Diagnostic harness](../../tests/profile_quarterly_dependencies.py) separates discovery,
build/maintenance, full command latency, validation and copying. Exact final results
are in [Current Development Status](Current%20Development%20Status.md).

Schema 9, templates, save meaning, retained history and operational Scheduling/Booking365/
runtime/acquisition/finance/GUI remain unchanged. Quarterly gameplay remains dormant.
Stage 2E, Stage 3/consumer migration and 3G-C remain unimplemented/parked.
