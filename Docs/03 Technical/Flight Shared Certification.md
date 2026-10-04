# Flight Shared Certification — Stage 3C

Bounded approved scope, 2026-10-04. Baseline
`3f6f6ab76194b36825d3850651b6f96d1fd7267e` matched live origin/master.
Authority: [canonical contract](Stage%201%20State%20Schema.md#clock-and-event-contract).
Schema remains 7. Both exact built-ins now have independently enabled certificates
for supported schema-7 inputs. Verification and repeatable before/after measurements
are recorded in [Current Development Status](Current%20Development%20Status.md).

## Stage 3D.2 successor — bounded mutation ownership

[Runtime Candidate Ownership](Runtime%20Candidate%20Ownership.md) documents the
separately approved successor. Exact built-in Payment/Departure/Completion receive
one-event write capsules and recursively read-only protected authority. Genuine
predecessor/selected-output proofs remain; protected JSON/alias validity inherits
from fully validated entry plus enforced write isolation and local output checks.
Full protected/alias oracles remain in shadow mode, with strict replay, final full
validation and detached commit unchanged. Memoized read capabilities end before
flush/recovery; they are neither authority nor Stage 2 indexes. Schema stays 7.
Normal session/Kivy/Advance pacing remains strict; no Stage 3E/3F or new certificate.
Earlier dated sections below retain their historical implementation evidence.

## Revised Stage 3D successor

[Flight Proof Cost Optimization](Flight%20Proof%20Cost%20Optimization.md) retains
these exact footprints/certificates and intermediate correctness guarantees.
Protected values now use exact typed runtime bytes; canonical JSON is checked on
all changed/excluded records with unchanged compatibility inherited only after
protected equality. The whole-candidate alias predicate remains equivalent but
avoids unused path construction. The dated Stage 3C measurements below are the
baseline, not current production pacing certification. Schema stays 7; no new
handlers or Stage 3E/3F are implemented.

## Departure audit

The exact built-in calls fulfilment._departure using the kernel transaction token.
It checks the selected canonical event, exact scheduled off-block UTC, PLANNED
status, ownership and PARKED aircraft at the origin. It uses the existing strict
confirmed direct Economy manifest builder; timed deadheads have an empty manifest.

Writes: selected dated flight status OPERATIONALLY_LOCKED and operation revision
+1, matching simulation.operation_revisions; actual (built-in planned) aircraft
IN_FLIGHT with null current airport; one new frozen active operation keyed by the
flight; one completion event at scheduled in-block UTC, priority 100, current
operation revision, exact lineage payload, new event ID and sequence. Schema-7
maintenance distance/source/class/rate/configuration witnesses freeze at departure.
The kernel archives the selected departure COMPLETED at due UTC.

Unchanged: booking/itinerary rows, booking/inventory revisions, passenger inventory,
fares, reservations, schedule definitions, airline/finance revisions, accounts,
journals, aircraft lifetime counters/condition/ownership, RNG and expiry.
Booking carriage is represented by immutable source IDs/witnesses in the operation,
not a mutation to CONFIRMED Booking status.

## Completion audit

The exact built-in calls fulfilment._completion with the same transaction token.
It requires the exact locked flight/operation/event at scheduled in-block UTC,
pinned configuration and a manifest identical to the departure freeze. Account
ownership/currency and sufficient unflown-ticket liability remain required.

Writes: flight COMPLETED and operation revision +1 plus matching simulation
revision; remove its active operation; add one immutable result keyed by flight;
actual aircraft PARKED at destination, lifetime flight seconds += exact block
seconds and lifetime cycles +=1 where lifecycle exists; one settlement transaction
and transaction allocator +1; airline finance revision +1. Unflown-ticket liability
-= recognized revenue, passenger revenue += revenue, operating expense += total
base+routine maintenance, cash -= total cost. No debt/asset changes or second
maintenance journal. Negative cash is allowed. Result V2 retains frozen maintenance
witnesses; migrated V1 in-flight operations remain V1. Kernel archives completion
COMPLETED at due UTC. No successor events or event allocator/sequence increment.
Booking/itinerary rows and booking/inventory revisions remain unchanged.

## Validator dependency map

| Dependency | Departure | Completion |
| --- | --- | --- |
| Generic flight/revision/identity validators | Exact selected record + simulation revision | Exact completed record + simulation revision |
| fulfilment_validation operation/result topology | One exact operation, departure history and completion pending; exclusive aircraft/carriage | Exact result replaces operation; exact terminal events, no duplicate settlement/carriage |
| Booking/inventory/lineage | Existing manifest predicates, source IDs, capacity, witnesses; all source authority unchanged | Same immutable manifest, exact paid/zero partition and source sale lineage |
| Finance/accounts/journal | All unchanged | Existing integer settlement/cost helpers; exact balanced journal and signed account effects; revision +1 |
| Aircraft/latest-result/lifecycle | PARKED origin becomes IN_FLIGHT, one active owner, unchanged counters | PARKED destination and exact counters; new result must be latest by canonical timestamp/ID |
| Planning/turnaround/contracts | Reservation endpoints and assignments unchanged; removing first future PLANNED head preserves its destination chain | Remaining future chain uses the same projected destination as the former active operation |
| Clock/event/allocator | Canonical selected minimum, monotonic due UTC, one exact fresh completion | Canonical selected minimum and exact lifecycle; only fresh transaction ID |
| Configuration/reference/RNG/history | Protected unchanged source structures; no external/deferred effects | Protected unchanged source structures; older financial/result witnesses remain bounded by increasing revisions |
| JSON types / mutable alias graph | Canonical json_compatibility_error and _container_alias_error predicates, every event | Same canonical predicate, every event |
| Final full gate | Required before detached commit | Required before detached commit |

Proofs use genuine detached before-event selected rows and kernel witnesses,
existing domain constructors/predicates, exact typed JSON comparisons and protected
unchanged-state fingerprints. Every logical event must pass before the next runs.
Unsupported/custom/stale inputs remain strict. No formulas belong in the resolver.
No runtime proof/index/candidate enters saved state. Booking, weekly publication and
expiry stay fences; Rotation stays strict. Production Kivy pacing remains strict.
Stage 3D–3F, history compaction and candidate-local booking indexes are outside scope.

## Proof boundary and exact binding

`game/world_state/flight_transition_validation.py` owns separate capture, input
predicate and validation functions, versioned as `ph-flight-departure-shared-v1`
and `ph-flight-completion-shared-v1`. The shared dispatcher accepts only exact
built-in callable AND callback identities and metadata, not arbitrary certificates.
`game/aircraft_operations/fulfilment.py` owns pure frozen-operation, cost and
journal/result builders reused by strict handlers and proofs. No formulas moved
into simulation or utilities. The selected canonical event and domain preconditions
still run; replacement handlers execute strictly once.

Each event checks exact selected records, the whole simulation record, all ID
allocator cursors, pending/history topology and exact completed/generated events.
A SHA-256 fingerprint compares every untouched envelope structure, including
bookings/itineraries/checkpoint state, old results/journals, reservations, schedules,
reference configuration, RNG, metadata and UI state. JSON comparison retains types
(boolean/float cannot replace an integer). Canonical JSON compatibility and alias
validation supplement value comparison; two equal-valued lists must not become one shared mutable object.
Completion additionally checks all owning-airline accounts, the finance revision,
frozen manifest, balanced journal and result including maintenance and lifecycle.

Valid predecessor reservations and projected location remain unchanged except for
replacing PARKED origin with the first active leg's projected destination, or that
active destination with PARKED destination. The new completed result must become
the canonical latest result for its actual aircraft. The conservative predicate
falls back to strict for unsupported chronology. In-flight V1 operations in schema
7 are supported without backfilling maintenance. Schemas 4–6 remain strict.

## Certification evidence and remaining costs

Independent Departure gates passed before enabling Departure; independent Completion
and existing fulfilment/maintenance gates passed before enabling Completion.
Regression tests compare fully validated intermediate successors and complete strict
worlds through shadow/non-shadow batches, generated equal-time interleaving,
multiple seeds, insertion order, target partitions, save continuation and private
Stage 2 reads. Controlled faults show invalid intermediate location/settlement
cannot wait for later repair; equal-valued mutable aliases are rejected. Successful
prefix replay, proof/final-gate failures, strict disagreement and shadow divergence
retain the independent strict outcome without duplicate operations or settlement.

`python -B -m tests.profile_flight_certification --fixtures <temporary-directory>
--mode both --repeats 3` reuses caller-owned fixture files; `--observed-fixture`
accepts a detached validated Divine Air envelope. Setup and output hashing are not
included in latency; instrumentation runs separately. Timed/instrumented commit
boundaries must match, and startup explicitly initializes the registry before
sampling. Pre-mock process memory is recorded separately; compare fresh cases
because mock argument retention inflates later high-water marks.
Batch cap 64 is an exploratory
throughput bound, not a production latency policy or Stage 3F acceptance.

Protected-state serialization, canonical JSON/alias scans, kernel history witnesses and
full manifest/result scans still grow with retained authority. No second booking
index, speculative cache, compaction or thread is added. An isolated event has no
clone/full-validation benefit and pays extra proof overhead. Dense bursts reduce
full gates/copies, but long synchronous batch steps still prevent a production
responsiveness claim. Stage 3D should be considered only with another approved
bounded scope; Stage 3E requires separate production pacing and latency verification.
