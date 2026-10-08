# Quarterly Transaction Certification — Stage 2E

**CERTIFIED: DORMANT COMMAND BOUNDARY ONLY**, 2026-10-09.

Certification scope: the dormant Stage 2B–2D command boundary at baseline
`54880246726c47900457e1d75e6e7e6cb86a4460`, 2026-10-08. Verification is recorded
in [Current Development Status](Current%20Development%20Status.md).

Authority: [finalized command contract](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md#atomicity-and-stale-write-protection),
[Schema 9](Stage%201%20State%20Schema.md#schema-9--reusable-flight-number-authority),
the subordinate [template mirror](../../Data/Templates/template_reference.txt),
[Stage 2C chronology](Quarterly%20Feasibility%20and%20Chronology.md) and
[Stage 2D indexes](Quarterly%20Maintained%20Dependency%20Indexes%20and%20Freshness.md).

## Boundary and command coverage

[Certification tests](../../tests/test_quarterly_transactions.py) exercise the actual
[session](../../app/session.py) and [Scheduling command implementation](../../game/scheduling/quarterly_commands.py).
Every command retains prepare-source validation, apply-source revalidation,
candidate validation and detached-publication validation. Instrumentation asserts
the four gates and two whole-world copies in order and distinguishes their objects.
The first copy isolates staging; the second detaches committed facts from staged
objects. These checks supplement validation, rather than replacing any gate.

The command matrix covers `CreateQuarterlyService`, `ReviseQuarterlyFare`,
`ReviseQuarterlySlot`, `AddQuarterlyFrequency`, `ContinueQuarterlySlot`,
`ReplaceQuarterlyService`, `RemoveQuarterlySlots` and `RetireQuarterlyService`.
Continuation uses explicit retained lineage; replacement changes endpoints using
a new service identity; removal does not imply retirement or number release.

## Reference methodology

Each indexed command runs against a validated, loaded session world. A separate
world executes the same request through the unindexed authoritative source-scan
path. Compare exact prepared observations, structured outcomes and serialized
authority, including allocator cursors, number state, all retained revisions,
commitments and pending events. The source-scan path independently discovers
dependencies; it shares transaction construction and chronology formulas. It is
not claimed as a second independent implementation of those formulas.

Independent direct-field enumeration verifies service/aircraft/airport/connection
edges and legacy schedule/flight/operation relationships. A separate retained-slot
scan proves endpoint bindings. A literal Schema 9 calendar/retirement rule derives
protected holders and deduplicated reusable suffixes without using allocator or
index eligibility helpers. A separate ordered dated-flight scan checks neighbors.
Fresh rebuilds compare all index payloads, with root identity and epoch treated as
runtime provenance rather than authority. Existing 2C/2D literal timing, readiness,
DST, wrap, published-quarter and active-operation cases remain required regressions.

The new suite additionally compares actual legacy continuous conflicts beyond
the materialized horizon and cross-aircraft duplicate lineage at a quarter boundary.
Removal → retirement → reuse verifies new immutable service identity, lowest
eligible suffix and unchanged fresh-number cursor. Committed membership continues
protecting a retired number. Reversed mapping construction and cold index rebuilds
must produce the same exact outcomes.

## Adversarial evidence

For every command, inject failure after each apply gate, complete feasibility,
index delta construction, delta verification, detached index rebind, result
construction and publication preparation. Allocation-specific cases fail after
service/slot allocation and revision staging. Candidate and detached copies are
also corrupted so the real validators must reject them. The latest practical seam
fails after final source observation, immediately before authority exposure.

Every rejected attempt preserves exact serialized authority and the prior index
object, payload and epoch. Retry the same owner-issued preparation and compare it
with an uninterrupted source-scan control, including IDs and number allocations.
Instrumentation verifies live authority and index visibility during fallible
staging. A real late UTC mutation at publication readiness rejects stale intent;
the external mutation remains, while the command's candidate is discarded.

Caller dictionaries may change after prepare without changing frozen intent.
Normal mutations of preparation/result fields and nested returned facts reject.
Retained staging candidates and slot lists cannot mutate published authority.
Wrong owner, competing revisions, forged copies, Load and same-byte rebind reject
the old preparation. Legacy writer invalidation reconstructs complete coverage.

## Operational noninterference and trust limits

An exact witness excludes only the three dormant quarterly roots and the service/
weekly-plan ID namespaces. Every other envelope field must remain identical across
accepted commands: legacy scheduling, bookings, inventory, journals, aircraft,
events, simulation configuration/time, UI state and retained operational history.
Existing operational regression suites separately exercise runtime, Booking365,
acquisition, finance, GUI and persistence behavior.

Index root identity/size guards do not deeply detect arbitrary unnotified private
row writes. A test explicitly demonstrates this documented unsupported bypass;
it does not treat it as a permitted writer or certify its subsequent command use.
Supported owner writers must invalidate or publish verified deltas. Foreign borrowed
worlds retain source scanning. Deliberate bypasses of frozen dataclasses or private
owner state are not public mutation capabilities. No production hooks are added.

## Retained costs and next scope

No validation, copying, schema, template, persistence, public command capability,
runtime or gameplay algorithm changes. No performance improvement is claimed.
Stage 2D's approximately 357 ms gate / 36 ms copy diagnostic at 250 unrelated
services remains historical, host-dependent evidence, not a fresh benchmark.
Full-world history validation and copying, retained revision scans, finite chronology
projection and immutable index-map publication remain known costs.

Later Stage 3 needs separately approved workflow/publication, readiness ordering,
carry-forward and coherent dated-supply/Booking/runtime/save consumer contracts.
Availability/configuration history and delivery authority cannot be invented by
certification. Transaction-copy optimization and 3G-C remain separate scope.
Quarterly gameplay remains dormant; Stage 2E creates no operations, supply, Booking
frontier, persisted certificates or publication commands.

## Verification record

2026-10-08 standalone certification: **32 PASS in 204.479s**. The final caller-alias
control was strengthened afterward; the final 2026-10-09 combined command in
[Current Development Status](Current%20Development%20Status.md) verifies that complete
working-tree scope: **365 PASS in 623.445s**, including all 32 certification cases,
Stage 2A–2D/Schema 9 and operational scheduling, Booking checkpoint, runtime,
acquisition/marketplace, economy, GUI and Save/Load regressions. Scoped compilation
passed. Full `.venv/Scripts/python.exe -B -m unittest discover -s tests -v`:
**1,335 PASS in 2,556.780s**, zero failures/errors/skips. All 304 application/test-file
witnesses (tracked scope plus the new test module) had identical SHA-256 values
before/after the run. Final local-link/heading/casing/fence validation and whitespace
checks pass; the final diff contains only tests and documentation. No production
behavior, approved formulas, compatibility witnesses or validation safeguards changed.

Initial environment failures were denied sandbox temporary saves/cleanup; normal
Windows temporary-file access resolved them without repository tooling changes.
Oracle iteration corrected holder set/tuple representation, class-method mock
binding, empty relation-container comparison and the exact existing stale-index
diagnostic. A 32-test intermediate run had 40 assertion failures in 198.377s from
the latter two assumptions; the corrected runs above pass. Relationship equality,
authority witnesses, full validation and copying were never relaxed. No production
defect correction or test-only production hook was necessary.
