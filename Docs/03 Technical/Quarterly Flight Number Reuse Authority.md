# Quarterly Flight Number Reuse Authority — Schema 9

**IMPLEMENTED: DORMANT AUTHORITY PREREQUISITE ONLY**, 2026-10-08.
Baseline `d606fa3cd4dfdcd9fde15ae0c4114f31f0daffa7` matched local HEAD,
configured upstream, fetched origin/master and live remote master. Tracked tree
and index were clean; only pre-existing `.venv/` was untracked. Archival
stash `cba6426b52f7dfb229a524c0e986fe9680946c81` was verified by reference,
without reading, applying or altering its contents.

## Authority and protection

[Canonical Schema 9](Stage%201%20State%20Schema.md#schema-9--reusable-flight-number-authority)
was updated first, then the subordinate [template mirror](../../Data/Templates/template_reference.txt),
before production. The shapes/names introduced by Schema 8 are unchanged;
only persisted meaning changes. Service IDs and service slot cursors stay permanent;
display numbers may repeat across distinct historical services. This supersedes
Stage 1's provisional lifetime display-number reservation, not its identity/history.

A non-retired service reserves its suffix, including an unbound draft allocation.
A retired service still protects its suffix while referenced by a current published
revision whose UTC quarter has not ended. This includes active and any future
committed quarter, even beyond the immediately following quarter. Distinct protected
holders of one airline/suffix are invalid. Repeated references to one continuing
service are valid. Historical published quarters and retained unpublished revisions
alone do not reserve a retired number. Removing plan membership does not retire
the service; retiring does not remove committed obligations or retained facts.

`service_numbering.next_number` exceeds every retained airline suffix. New service
allocation selects the numerically lowest eligible retired suffix, deduplicated
across old holders, otherwise the next fresh suffix. Reuse leaves the cursor
unchanged; fresh allocation advances it by one. No surviving services are renumbered,
no flight numbers are consumed for weekly occurrences, and no cooldown is invented.
Display format remains fixed airline prefix plus at least two digits, growing as needed.

All retained slots for a service agree on origin/destination, across frequencies,
revisions and quarters. Different endpoints require a new service ID even when that
service receives an eligible reused number. Occurrence identity is still
`service_id@origin-local-date#slot_number`; number text never identifies history.

## Implementation and boundaries

[service_numbers.py](../../game/world_state/service_numbers.py) reconstructs
protected holders and eligible suffixes from existing authority, simulation UTC and
selected published revisions. It mutates nothing and persists no cache/pool/index.
[quarterly_construction.py](../../game/world_state/quarterly_construction.py)
uses that lookup before service ID/cursor writes. Prefix/cursor/protection rejection
and allocator failure consume no number. These remain caller-owned isolated-candidate
primitives, not transactional Stage 2B commands; complete candidate validation remains
required at trust boundaries. No general mutation/session command is added.

[quarterly_validation.py](../../game/world_state/quarterly_validation.py)
retains all shape, ownership, timing, fare, cursor and publication checks, adding
Schema 9 protected-holder exclusivity and global retained endpoint consistency.
Plan creation/revision primitives reject endpoint reinterpretation before writing.
Historical Schema 8 fixtures still use their original lifetime-number uniqueness.
Schema 8-introduced namespace/root constants are reused because shapes do not change.

New Game directly completes its fresh bootstrap with Schema 9 empty roots.
Disk Save/Load accepts only 9; earlier development files reject cleanly without
conversion. Complete snapshots, separate validated candidates, paused Load, previous
valid-file safety and deterministic serialization remain intact. Cold Load validates
protection from authority without consuming IDs, changing suffixes or moving cursors.

Existing operational consumers/certification guards accept version 9 with unchanged
algorithms/proofs. Stage 2A accepts validated 8/9 authority; its direct read path remains
detached and immutable, without number scans or allocation. Session code is unchanged.
Legitimate historical display duplicates resolve through service IDs. Malformed endpoint
worlds now reject at full trust acquisition; read-local consistency checks still exist.
No supply, events, Booking365, finance, acquisition, GUI or history mechanics change.

## Verification and scalability

[Reuse regressions](../../tests/test_service_number_reuse.py) cover reservations,
active/future commitments, end-exclusive release, deterministic lowest reuse, duplicate
pool holders, high-water gaps/growth, failure/no consumption, distinct historical IDs,
endpoint replacement, cross-owner/dangling references, cold reconstruction, exact
save/load, immutable 2A reads and unchanged operational roots.
Existing tests retain weekly repetition/continuation and legacy scheduling/Booking
equivalence. Historical fixed hashes are preserved by explicit schema-tag projection;
the old-save rejection test now includes 8 and uses 10 as its newer-version case.

Focused and regression command: `.venv/Scripts/python.exe -B -m unittest
tests.test_service_number_reuse tests.test_quarterly_foundation tests.test_quarterly_reads
tests.test_step7_save_load tests.test_scheduling_recurrence tests.test_stage1_runtime
tests.test_shared_candidate tests.test_advancement_performance -q`:
**162 PASS in 147.521s**. Earlier focused foundation/read run: **40 PASS in 13.472s**.
Scoped compilation `app game tests main.py make_snapshot.py settings.py test.py` PASS.
Initial full discovery: **1199 cases in 1465.114s, 18 failure entries / 11 errors**.
Two compact `(7,8)` Departure/Completion certificate declarations had not yet added 9,
although their input predicates had. This caused strict routing instead of existing
certified routing. Added 9 to those declarations without changing proofs, event semantics,
rollback or transaction boundaries. Corrective command `.venv/Scripts/python.exe -B
-m unittest tests.test_candidate_manifest_lookup tests.test_candidate_ownership
tests.test_flight_certification tests.test_flight_proof_optimization
tests.test_local_runtime_proofs tests.test_runtime_capacity tests.test_runtime_forensics
tests.test_atomic_boundary_optimization tests.test_cooperative_runtime -q`:
**202 PASS in 443.144s**. Scoped compilation PASS again after correction.
Corrected `.venv/Scripts/python.exe -B -m unittest discover -s tests -q`:
**1199 PASS in 1265.353s** on frozen final source/tests. Source hashes confirmed
unchanged after the run. Final documentation: **440 local links / 64 heading targets**
across 12 changed documents PASS, including tracked-path casing and fence structure;
legacy linked encodings read without modifying those files. Whitespace, full diff,
canonical/mirror agreement, historical supersession and scope review PASS.
No standalone giant performance certification. All 22 other operational files have
only additive schema-version guards; no handler algorithm/proof changes.

Reconstruction processes relevant airline services and current published slot references;
without inverse indexes it traverses shared service/plan mappings to select that owner.
Allocation is approximately O(total services + total plans + relevant committed slots),
with an additional service traversal to derive eligible suffixes. Protected IDs,
holder keys and eligible suffixes are sorted deterministically (sorting adds n log n
for those sets).
It never scans legacy dated flights, bookings, journals, events or operational history.
Endpoint insertion comparison visits retained plan/revision slots; global validation
already retains full trust-boundary checks. These are temporary reconstruction costs,
not a broad runtime optimization. 2D owns maintained inverse relationships; no caches,
threads, occurrence expansion or 3G-C are introduced. Existing 2A locality instrumentation
still covers up to 1,000 unrelated services without increasing direct read lookups.

## Remaining sequence

**2B → 2C → 2D → 2E → later Stage 3 / consumer migration.**
Schema 9 prerequisite and dormant 2A are implemented. No Stage 2B command API,
feasibility certification, maintained indexes or transaction certification is started.
Carry-forward, automatic/Manual Publish, quarterly Booking/runtime handoff and GUI remain
unimplemented; Booking365 remains operational. 3G-C is PARKED and separate.
No unresolved product decision blocks the completed prerequisite. Publication correction
state/event mechanics, consumer migration, configuration/delivery authority and maintained
index details remain scoped later work, not reasons to expand this implementation.

## Exact production file scope

Core authority/persistence/read files are described above. Other listed operational
files have additive schema guards only, independently checked against the baseline.

- [game/aircraft_market/acquisition.py](../../game/aircraft_market/acquisition.py)
- [game/aircraft_market/step5.py](../../game/aircraft_market/step5.py)
- [game/aircraft_operations/fulfilment.py](../../game/aircraft_operations/fulfilment.py)
- [game/aircraft_operations/manifest_lookup.py](../../game/aircraft_operations/manifest_lookup.py)
- [game/aircraft_operations/projections.py](../../game/aircraft_operations/projections.py)
- [game/booking/checkpoint.py](../../game/booking/checkpoint.py)
- [game/booking/indexes.py](../../game/booking/indexes.py)
- [game/booking/shopping.py](../../game/booking/shopping.py)
- [game/demand/model.py](../../game/demand/model.py)
- [game/demand/model4.py](../../game/demand/model4.py)
- [game/fleet_management/acquisition.py](../../game/fleet_management/acquisition.py)
- [game/scheduling/publication.py](../../game/scheduling/publication.py)
- [game/scheduling/quarterly_reads.py](../../game/scheduling/quarterly_reads.py)
- [game/scheduling/weekly.py](../../game/scheduling/weekly.py)
- [game/simulation/kernel.py](../../game/simulation/kernel.py)
- [game/world_state/acquisition_validation.py](../../game/world_state/acquisition_validation.py)
- [game/world_state/booking_fingerprint.py](../../game/world_state/booking_fingerprint.py)
- [game/world_state/construction.py](../../game/world_state/construction.py)
- [game/world_state/demand_fingerprint.py](../../game/world_state/demand_fingerprint.py)
- [game/world_state/flight_transition_validation.py](../../game/world_state/flight_transition_validation.py)
- [game/world_state/fulfilment_validation.py](../../game/world_state/fulfilment_validation.py)
- [game/world_state/ids.py](../../game/world_state/ids.py)
- [game/world_state/payment_validation.py](../../game/world_state/payment_validation.py)
- [game/world_state/persistence.py](../../game/world_state/persistence.py)
- [game/world_state/planning_validation.py](../../game/world_state/planning_validation.py)
- [game/world_state/quarterly_construction.py](../../game/world_state/quarterly_construction.py)
- [game/world_state/quarterly_validation.py](../../game/world_state/quarterly_validation.py)
- [game/world_state/schema.py](../../game/world_state/schema.py)
- [game/world_state/service_numbers.py](../../game/world_state/service_numbers.py)
- [game/world_state/validation.py](../../game/world_state/validation.py)

No app/session.py, GUI, game data or historical audit file changes.
