# Quarterly Restricted Command Foundation — Stage 2B

Stage 2C successor (2026-10-08): [dormant feasibility and chronology](Quarterly%20Feasibility%20and%20Chronology.md)
now implements affected aircraft-chain proof and explicit continuation/edit/removal/retirement
commands. Stage 2D/2E and quarterly activation remain unimplemented; earlier checkpoint
limitations below are historical.

**IMPLEMENTED: DORMANT RESTRICTED COMMANDS ONLY**, 2026-10-08.
Starting baseline `ef47546140db2070768dc7cb5b3117d639281f2f` matched local HEAD,
configured upstream, fetched origin/master and live remote master. Tracked tree/index
were clean, only `.venv/` untracked. Archival stash
`cba6426b52f7dfb229a524c0e986fe9680946c81` was checked by reference only;
no contents were inspected, used, applied or altered.

Authority remains [Schema 9](Stage%201%20State%20Schema.md#schema-9--reusable-flight-number-authority),
the subordinate [template](../../Data/Templates/template_reference.txt), and
[finalized contracts](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md).
No persistent shape, version, template, formula, reference data or operational writer changes.

## Restricted API and validation scope

[quarterly_commands.py](../../game/scheduling/quarterly_commands.py) is Scheduling-local.
`CreateQuarterlyService` carries quarter ID, fixed flight-number prefix, explicit plan
ID/current revision or absence (`None`, revision 0), and canonical initial slot facts.
Slot facts exclude service ID, slot number and planning timing: the domain allocates
identities and derives timing from resolved aircraft/airport authority. One service
and initial frequency enter either one new plan or one new revision of an existing
plan atomically. Existing facts/versions are retained.

`ReviseQuarterlyFare` carries plan ID/current revision, canonical service/slot key and
the canonical `fare_offer` fields. It appends a revision changing only that frequency's
fare. Service identity, number, endpoints, aircraft, timing, weekdays and all allocation
cursors remain unchanged. This is the smallest non-temporal edit needing no new
chronology/inverse proof. Non-endpoint identity continuity does not grant permission
to change other facts through this restricted API.

Only these exact request types are accepted. Full source and candidate validation,
canonical direct owner chains, missing-reference rejection, exact expected revision,
retirement and published locks remain mandatory. The editability query derives the
normal UTC target and skips already committed quarters; it does not store/advance a
target, carry forward, publish or generate supply. Only the eligible unpublished
future quarter can be edited. Airport-local scheduling semantics remain unchanged.

Initial slot structural/timing/range/configuration and reference facts use existing
Schema 9 primitives/gates. **Creation is a dormant definition, not certification that
the plan can operate.** Cyclic conflicts, positioning, turnaround chronology, aircraft
temporal neighbors, adjacent-quarter/DST occurrence conflicts and complete feasibility
remain 2C. No publication/operational consumer accepts these plans in this slice.
Time/weekday/aircraft edits, adding frequencies, continuation/removal/retirement,
endpoint replacement and whole-plan replacement remain unexposed until their complete
contracts are implemented. No sophisticated service matching is introduced.

## Session, freshness and atomicity

[app/session.py](../../app/session.py) exposes `prepare_quarterly_command(request)`
and `apply_quarterly_command(prepared)`. The session supplies its canonical airline ID;
UI focus/labels do not select owners. Editing requires paused authority and no continuous
runtime drain/processing or explicit Advance work. Rejection does not pause/advance
the world or alter management counters. The owner invokes apply synchronously with no
yield to another mutator.

Preparation returns immutable copied intent plus exact relevant source observations;
it consumes no authoritative IDs/numbers and does not commit. Successful preparation
is not candidate acceptance: apply still checks all final facts. Session-issued weak
identity registrations authenticate preparation objects; fabricated copies and other
sessions fail. World rebind, New Game and Load discard these runtime-only registrations,
including same-byte loads. Accepted preparations cannot be replayed. These registrations
are not simulation IDs, persisted state, maintained dependency indexes or certificates.

Observations cover exact simulation UTC, selected current plan facts, relevant direct
references, owner plan commitments/memberships, and creation's owner service/number
authority. They include old plan references as well as proposed creation references.
Selected plan history is not copied into the freshness observation. Other-airline
allocation, UI changes and unrelated accounting can remain valid when relevant facts
are unchanged; no global world fingerprint or progression counter decides freshness.
The current global allocator is read at apply, not predicted/allocated by preparation.

Apply revalidates the current source and observations, constructs one private whole-world
candidate, stages allocations/revision, validates it fully, makes a detached commit copy
and validates that copy. It builds immutable result/read records and checks freshness
again **before** exposing the accepted dictionary contents through the existing envelope
identity. No allocation, revision, event or writable candidate escapes a rejection.
Known invalid input/validation failures return immutable `ReadIssue` records with stable
codes/paths and observed revision where relevant. Unexpected programming exceptions
surface, but pre-publication staging still leaves authority unchanged.

Schema 9 lowest eligible retired-number selection and exclusive draft reservations are
reused unchanged. Reuse never rewinds/advances the fresh cursor; new IDs remain monotonic.
Global retained endpoint consistency remains enforced. New endpoints require a different
service, not a fare revision or reuse-based reinterpretation of old identity.

Success returns committed service/slot/plan IDs, revision, recursively immutable 2A reads
and the union of old/new direct dependencies. Those dependencies are **not** a complete
inverse/temporal closure or command certificate. No event, Booking, journal, legacy
schedule/publication row or GUI workflow is created. Session dirty/progression/read
notifications occur only after acceptance. Save/Load remains Schema 9 and exact; runtime
preparations/registrations are reconstructed by fresh issuance, never serialized.

## Temporary cost and remaining limitations

Full copies and gates are a conservative transitional implementation for dormant 2B,
not a permanent architecture/API promise. They are isolated behind the domain command
boundary, without broad runtime transaction changes. Full validation/copy cost remains
O(world + retained history). Observation and Schema 9 allocation reconstruction traverse
service/plan mappings and process owner/current memberships, with relevant direct reads;
no maintained inverse indexes or stale cache are introduced. Revision storage/copy costs
the retained plan/candidate size. No broad runtime throughput improvement is claimed.

2C owns complete feasibility and additional lifecycle/membership operations; 2D owns
maintained relationships and dependency freshness; 2E owns certification and adversarial
transaction-boundary proof. All three remain unimplemented. Later Stage 3 owns carry-forward,
automatic/Manual Publish and workflow advancement. Coherent Booking/runtime consumer
migration remains later; Booking365/legacy operating authority remains active. 3G-C is
PARKED and separate. No schema/save conversion, GUI, acquisition, finance, history,
AI, threading or unrelated refactor is included.

## Verification

[tests/test_quarterly_commands.py](../../tests/test_quarterly_commands.py) uses Stage 1
constructors, Schema 9 fixtures and TEMP save roots. Coverage includes bundled creation,
fare continuity, owner/dangling/stale references, same-byte Load/rebind freshness,
forged/cross-session preparation rejection, nested alias protection, eligible number
reuse/protected future use/draft exclusivity, deterministic retry after injected failures,
allocation/revision/candidate/detached/response/final-freshness staging failures, command
boundaries, unchanged operational roots and exact save/load.

Final focused/regression command `.venv/Scripts/python.exe -B -m unittest
 tests.test_quarterly_commands tests.test_quarterly_reads tests.test_quarterly_foundation
 tests.test_service_number_reuse tests.test_step7_save_load tests.test_scheduling_recurrence
 tests.test_stage1_runtime tests.test_shared_candidate -q`: **180 PASS in 82.528s**
(31 new command cases). Earlier 93-case foundation/command scope PASS in 19.026s.
Initial fixture failures concerned airline constructor arguments and accepted connection
metadata; later foreign-owner tests required the explicit existing-plan expectation.
Fixed fixtures; no production rule was weakened. Final full discovery
`.venv/Scripts/python.exe -B -m unittest discover -s tests -q`:
**1230 PASS in 1180.341s**. Source/test hashes confirmed unchanged after the run.
Scoped compilation (`app game tests main.py make_snapshot.py settings.py test.py`) PASS.
Documentation: **175 local links / 6 heading targets**, seven changed documents;
tracked casing, fences, authority/scope/complete diff review and whitespace PASS.
No separate giant performance certification. See also
[Current Development Status](Current%20Development%20Status.md).

Remaining sequence: **2C → 2D → 2E → later Stage 3 / consumer migration.**
No next-slice product decision is resolved speculatively or permission inferred here.
