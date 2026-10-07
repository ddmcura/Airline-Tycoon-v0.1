# Runtime Candidate Ownership — Stage 3D.2

## Stage 3G-B successor

[Runtime Local Certified Proofs](Runtime%20Local%20Certified%20Proofs.md) localizes
the existing per-event proof surface with structurally protected tables and sealed
canonical selection. Genuine predecessor/output proofs, JSON/aliases, detached
output publication, both outer world copies, full final validation and strict/
shadow recovery remain. Earlier dated measurements below are preserved.

## Stage 3D.3 successor

[Candidate Manifest Lookup](Candidate%20Manifest%20Lookup.md) adds a lazy verified
Booking-ID lookup only inside protected opt-in shared candidates. Current manifest
checks, strict full-scan oracle, fences/replay/final gates and separate Stage 2
committed read ownership remain. Schema 7 and normal Kivy/session pacing stay
unchanged. The dated sections below retain their original evidence.

Approved bounded implementation, 2026-10-04. Baseline
`1bf99b647163ee0834908ec8820a6abd4339ba56` matched local HEAD, upstream and
live origin/master before changes. Authority remains the
[canonical event contract](Stage%201%20State%20Schema.md#clock-and-event-contract).
This succeeds [Revised Stage 3D](Flight%20Proof%20Cost%20Optimization.md).
Schema remains **7**. No gameplay, schema field, save migration, speed, pacing
credit, overload recovery, production batching or additional certification changes.
Normal session/Kivy/Advance stays strict. Stages 3E and 3F are unimplemented.

## Reproduction and measurement

The same eleven Stage 3C TEMP fixtures, targets, batch cap 64 and generated-event
ceiling 10,000 are reused. Observed Divine Air authority is a detached TEMP copy;
production data/saves are never changed. A read-only TEMP archive of the verified
baseline provides fresh original controls even after source edits. Timings exclude
fixture construction, input copying and complete-world output hashing. Baseline
latency medians use three samples; exclusive profiles are separate runs. Early
baseline latency had limited overlap with focused tests, so quiet archived
exclusive controls are also reported; machine timing is not portable.

Commands (repository-relative; replace `<temp>` with the caller-owned fixture path):

```text
python -B -m tests.profile_flight_certification --fixtures <temp> --mode both --repeats 3 --observed-fixture <detached-world>
python -B -m tests.profile_flight_proof --fixtures <temp> --case all
python -B -m tests.profile_flight_proof --fixtures <temp> --case all --mode shared --latency --repeats 3
python -B -m tests.profile_flight_proof --fixtures <temp> --case all --mode strict --latency --repeats 1
python -B -m tests.profile_flight_proof --fixtures <temp> --case round-trip --mode shadow --latency --repeats 3
python -B -m tests.profile_contract_payment --case all --mode both --repeats 1
```

Exclusive stack timings subtract nested instrumented children. Their sum is
non-overlapping; unattributed and diagnostic work are explicit. Capture/validator
region totals are inclusive and are reported separately, **not added** to the
exclusive table. Local alias record visits and private memo structural estimates
are diagnostic overhead, outside their parent category. Process peak is a lifetime
high-water mark, not retained witness size; isolated runs distinguish memory from
an all-case process. Full hashes and commit vectors must match, not only aggregates.

## Pre-change reachability audit

`EventContext.envelope` previously gave every handler the entire mutable detached
world. Frozen EventContext fields did not freeze nested dictionaries/lists. Helpers
could obtain raw protected rows through ordinary indexing; no guaranteed global
revision covers in-place mutations. Identity equality does not prove unchanged
values. Per-event protected serialization and whole-graph alias checking were
therefore necessary without a stronger execution boundary.

| Handler / helpers | Reads | Actual writes / capability |
| --- | --- | --- |
| Payment: `_payment_handler`, `payment_terms`, integer market journal constructors, `post_aircraft_market_transaction`, `purchase_accounts`, allocator and `schedule_event` | Contract terms, own airline/accounts, catalog/configuration, next event facts | Own contract, own airline and account set, one new journal, selected pending/history event and predicted next payment; simulation and allocator |
| Departure: `_departure_handler`, `_departure`, `_common_checks`, matching/next event, manifest/checkpoint/sale lineage, `departure_operation`, maintenance `departure_witness`, timing/classification, allocator and `schedule_event` | Flight/aircraft/configuration, Bookings/itineraries/checkpoints/sales, schedule/timing/maintenance sources, airports/markets/connections, event facts | Own flight, planned aircraft, own active operation, selected pending/history event and predicted completion; simulation and allocator |
| Completion: `_completion_handler`, `_completion`, common/event/configuration checks, manifest, `_account_ids`, `completion_cost`, integer maintenance/cost and `settlement_records`, allocator | Locked flight/actual aircraft/frozen manifest, Booking lineage, own accounts/airline, cost sources and prior results | Own flight/actual aircraft/lifecycle, own airline/account set, one new journal/result, removal of own active operation, selected pending/history event; simulation and allocator |

The audited exact built-ins/helpers have no authoritative-world global, retained
mutable world reference, GUI callback, external world supplier or reflection path.
Reference/classification caches are data sources, not private candidate authority.
Public gameplay commands remain unchanged and strict. Only private validated read
guards in fulfilment/timing accept the exact read-view classes; arbitrary Mapping
objects, subclasses or non-JSON save worlds are not admitted by world validation.

## Enforced ownership boundary

`game/simulation/candidate_ownership.py` contains generic transaction ownership;
flight/payment footprint selectors remain in their owning world proof modules.
`HandlerExecutionContract.mutation_footprint` is runtime-only and identity-checked
alongside the existing exact handler/support/capture/validator metadata. Custom or
replacement handlers cannot acquire certification by event name or copied version.

1. Existing full world validation establishes predecessor JSON compatibility,
   global alias freedom and all schema/domain invariants. The resolver clones that
   validated world into a detached private candidate. A subsequent shared batch
   begins after a valid prior commit; a full-gated probe validates before restart.
   The internal validated-entry assertion reuses these actual gates, never a
   revision/identity heuristic. Standalone ownership construction independently
   checks canonical JSON and the original full alias predicate, fail-closed.
2. A lazy recursive read capability returns only primitives or guarded Mapping /
   Sequence views. Views are **not** dict/list subclasses: base-class mutator
   tricks cannot reach underlying source containers. Assignment, mutators,
   attribute replacement and reinitialization reject. Deepcopy produces detached
   plain JSON objects. No ordinary read operation returns a raw mutable node.
3. For each event, a write capsule copies simulation, allocator and only approved
   existing rows. Other collection entries are protected read views. Root identities,
   protected row identities and non-footprint key topology are checked after the
   handler. Writable-table base-class insertion/replacement bypasses are caught.
4. Trusted pure proof capture reads the **genuine original predecessor** and makes
   the same exact selected snapshots, manifest and kernel witnesses. Its capsule
   must be live and bound to that exact source identity (held alive by its owner).
   A different predecessor is rejected. The handler never receives that raw source,
   the owner or the capsule object; only the capability envelope is passed.
5. The unchanged exact domain proof checks the selected flight/aircraft/operation,
   manifest/carriage/maintenance, settlement, journal/account balances, event
   topology/order and generated IDs, simulation/revisions and allocator deltas.
   Local canonical JSON and the **canonical alias predicate** cover the entire
   output pack, including cross-record aliases and nested events/manifests/journals.
6. Publication deepcopies the validated output pack and inserts only permitted
   records/roots into the private candidate. Independent sorted typed JSON compares
   actual inserted authority against output serialized **before** copying. A copy
   divergence fails immediately, not at a later event. A capsule is consumed once.
7. Full final world validation and detached whole-world commit remain mandatory.
   Any first failure discards the candidate and runs the unchanged strict successful
   prefix replay. Shadow adds the original flight whole-world protected/alias oracle, Payment
   protected fingerprints and a fully validated strict per-event reference
   (including global JSON/aliases), retaining independent certification.

This is an enforced ordinary Python capability API, **not a hostile-code sandbox**.
Deliberate closure inspection, stack reflection, monkeypatching or `object` tricks
are outside the audited built-in contract. Python code with such access can also
replace validators/handlers directly. No security guarantee is inferred from Python
private names. The exact builtin/helper call graph is the trusted computing base;
changes to it require renewed footprint/equivalence review. Proof helpers remain
trusted and pure as in Stages 3B–3D; handler helper reads receive guarded authority.

## Protected-state and alias proof

| Former broad witness | Exact replacement / reason |
| --- | --- |
| Bookings, itineraries, checkpoint/demand sources | Guarded recursively; no raw mutable protected reference is reachable through handler APIs. Manifest lineage/capacity checks still run exactly. |
| Airports, markets, connections, definitions/reservations, configuration, catalog and maintenance sources | Same read-only boundary. No identity/revision assumption about source immutability and no timing change. |
| Other aircraft/flights/operations/results/contracts/accounts/journals/airlines | Read-only rows, sealed protected row identities and collection key sets; exact selected complete records remain validated. |
| RNG, metadata, UI and deterministic facts outside allocator | Sealed protected roots and recursively guarded descendants. No writes admitted. |
| Simulation, allocator and selected/new records | Genuine predecessor snapshots, exact successor proof, local JSON/alias checks and detached publication bridge. |
| Pending/history nonselected rows | Existing kernel before witness remains; protected rows cannot mutate, topology and selected/generated events remain exact. |

Alias induction: validated entry has no mutable aliases. A handler can modify only
its independent copied writable region. Protected source nodes cannot be inserted
as raw writable objects; inserting a read view fails canonical JSON. The complete
output pack detects aliases within/between all writable/new records. Deepcopy into
the candidate prevents sharing with external/retained handler objects or protected
candidate containers. Unchanged protected structures therefore inherit global
alias freedom. Equal-valued aliases still reject; value equality is not substituted
for alias proof. Final full validation and shadow whole-graph alias checking remain.

JSON induction: unchanged protected structures inherit validated entry types;
changed/new outputs receive exact canonical compatibility checks at each event.
Publication preserves types and independently verifies content. Ordering for proof
comparison is canonical; save serialization/order is unchanged. Unsupported objects,
non-finite values, read views and subclasses cannot be published. No incompatible
intermediate state can wait for a later repair or final save validation.

## Request reuse, mixed handlers and fences

The only reusable state is a candidate-local capability memo `source identity →
(strong source reference, read view)`. Strong references prevent ID reuse; the
original source identity is checked on every cache hit. It is not a Booking,
manifest/history index, equality witness, authoritative lookup or Stage 2 cache.
Sources/views are derived from this private candidate and never saved/exposed to
frontends. Selected records are detached for each event; the lazy read root follows
actual published candidate replacements. Old views remain read-only.

The actual identity-bound footprint callback supplies each event's write surface;
there is no Departure-only assumption about mixed Payment/Departure/Completion.
Every event has a fresh selected predecessor witness/capsule. No later event may
repair an invalid earlier transition. Generated completion/payment events use the
same kernel IDs, priorities, order cursors and deterministic queue.

Close revokes read/write capabilities, clears the memo and releases owner roots
before final validation/commit or failure/replay. A full-gated NO_OP/probe closes
and restarts ownership; a strict event/fence flushes and starts a new candidate.
No reuse crosses `step()` return, authoritative commit, save/load, session rebind or
world replacement. Rotation stays strict; Booking checkpoint, weekly publication
and contract expiry remain strict fences. Stage 2 remains committed-world-only and
uses existing epoch invalidation/lazy rebind after commit.

## Alternatives measured and rejected

An eager immutable full-world replica passed correctness but made Divine-next
13.432 s and increased the all-case process peak to 428.92 MiB. Its exclusive
construction cost was 1.563 s; it duplicated 159,309 containers / 1,112,362 entries.
It was removed. A lazy version still redundantly checked entry JSON/aliases and
retained wrappers for the whole Booking scan. Removing the duplicate entry gate
was justified by the existing full validation/clone induction above.

Weak memoization was also measured, not assumed: dense-25 was 14.603 s versus
10.799 s for the strong-memo prototype, and introduced wrapper churn. It was removed.
The final bounded strong memo plus pure raw-predecessor capture avoids guarded
wrapping of the proof's read-only scan while preserving handler isolation. No
persistent index, schema revision counter or Stage 2 candidate cache was added.

## Regression, recovery and verification

New ownership regressions deliberately exercise protected nested writes, base-class
mutator bypass, unexpected IDs, root/row replacement, read-view leakage, fake
capsules, foreign predecessor/candidate, expired/consumed capabilities, output copy
divergence, generated payload/journal/result/manifest aliases, equal-value and
randomized aliases versus the full canonical predicate, retained external copies,
NO_OP restart, full shadow oracle, footprint spoofing and schema-7 paused save/load.
Existing first-invalid-event, kernel/allocator/revision, wrong settlement/journal,
manifest, alias/serialization, final-validation, replay disagreement and strict
successful-prefix recovery tests remain. The encoding-fault test explicitly uses
shadow, where that expensive diagnostic oracle remains applicable.

Stage 1's complete-world oracle includes all authority across partitions/batch
sizes 1/2/8/64, insertion order/seeds, mixed/generated/equal-time events, fences,
aged history and save/load continuation. Stage 2 ownership/invalidation, booking,
finance, aircraft/maintenance, kernel/runtime and persistence suites remain gates.
No witness/memo/capsule enters saved authority; Schema 7 and paused restore remain.

Measurement tables and final verification follow below.

## Performance results

Seconds. Recorded Stage 3D is historical evidence on an earlier host run. Fresh
pre-control medians and optimized medians use three samples; current strict uses
one independent post-change sample. Variance is visible; do not infer causality
from comparisons to recorded historical timings.

| Fixture | Recorded 3D shared | Fresh pre strict | Fresh pre shared | Current strict (1 sample) | Owned shared (3-sample median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| one-departure | 0.369 | 0.377 | 0.386 | 0.414 | 0.408 |
| one-completion | 0.367 | 0.361 | 0.389 | 0.486 | 0.457 |
| round-trip | 0.474 | 0.801 | 0.493 | 0.997 | 0.445 |
| dense-departure | 1.070 | 2.891 | 1.207 | 3.330 | 0.987 |
| dense-completion | 1.155 | 2.960 | 1.285 | 3.498 | 1.050 |
| mixed-ten | 3.142 | 11.985 | 3.496 | 13.476 | 2.156 |
| representative-ten | 10.147 | 37.076 | 11.778 | 42.289 | 7.244 |
| aged-ten | 3.935 | 14.195 | 4.442 | 14.249 | 3.728 |
| dense-25 | 12.283 | 48.296 | 15.873 | 59.542 | 7.869 |
| divine-next-departure | 9.689 | 10.532 | 11.199 | 10.630 | 12.072 |
| divine-short | 11.484 | 18.682 | 12.846 | 20.458 | 13.053 |

All eleven strict/original/owned complete-world hashes and shared commit vectors
match. Dense-25 median improves 50.4%; isolated and aged fixtures do not uniformly
improve. Divine-next remains slower than both original shared and current strict.
Dense-25 max step is 9.350 → 4.698 s. The largest optimized step is 10.834 s (Divine-short), above the historical Stage 3D 9.018 s result. This is **not** a production
responsiveness or Stage 3F acceptance claim.

### Exclusive proof pipeline

Dense-25 category seconds below are exclusive, not nested sums. Diagnostic
measurement overhead is explicitly separate. An absent protected category means
zero calls, not an unmeasured replacement.

| Category | Fresh baseline | Owned |
| --- | ---: | ---: |
| protected_encoding | 6.383227 | 0.000000 |
| protected_capture | 0.010936 | 0.000000 |
| protected_compare | 0.011755 | 0.000000 |
| canonical_json | 0.060007 | 0.117292 |
| mutable_alias | 4.225850 | 0.126797 |
| manifest | 1.068323 | 4.133668 |
| kernel_witness | 0.149180 | 0.155004 |
| ownership_baseline | 0.000000 | 0.000042 |
| ownership_begin | 0.000000 | 0.237326 |
| ownership_boundary | 0.000000 | 0.104641 |
| ownership_publish | 0.000000 | 0.214849 |
| ownership_close | 0.000000 | 0.008220 |
| capture_departure | 0.030576 | 0.030178 |
| capture_completion | 0.062908 | 0.058604 |
| validate_departure | 0.112341 | 0.024314 |
| validate_completion | 0.129067 | 0.030784 |
| selected_encoding | 0.152855 | 0.150397 |
| aircraft_reservation | 0.002293 | 0.002604 |
| operation_result | 0.004206 | 0.004065 |
| finance | 0.000528 | 0.000650 |
| journal | 0.000326 | 0.000399 |
| event_topology | 0.001793 | 0.001766 |
| allocator_revision | 0.001875 | 0.001769 |
| completion_chronology | 0.003922 | 0.003789 |
| cost | 0.003690 | 0.003257 |
| settlement | 0.079114 | 0.045902 |
| full_world_validation | 1.487566 | 1.557299 |
| clone | 0.296418 | 0.330764 |
| detached_commit | 0.012494 | 0.006409 |
| diagnostic_measurement | 0.000000 | 0.194608 |

Capture + transition validation (inclusive, disjoint root regions) is 11.787 → 1.261 s. This does not hide capsule setup/publication: those additional exclusive
categories are listed above and a separate combined measurement is recorded below.
Original protected encoding made 200 calls / 886,445,732 bytes (largest 4,937,655);
owned protected encoding has zero calls/bytes. Original alias proof traversed the
whole candidate 100 times; owned makes 200 small output-pack checks with 32,908
actual container visits. Full-world validator alias/JSON traversals remain inside
the unchanged final/entry gates; they are not claimed eliminated.

### Structural boundaries

| Fixture | Events | Shared full gates | Shared whole-world clones | Event commits |
| --- | ---: | ---: | ---: | --- |
| one-departure | 1 | 3 | 2 | 1 |
| one-completion | 1 | 3 | 2 | 1 |
| round-trip | 4 | 3 | 2 | 4 |
| dense-departure | 10 | 3 | 2 | 10 |
| dense-completion | 10 | 3 | 2 | 10 |
| mixed-ten | 40 | 3 | 2 | 40 |
| representative-ten | 81 | 5 | 6 | 40/1/40 |
| aged-ten | 40 | 3 | 2 | 40 |
| dense-25 | 100 | 4 | 4 | 64/36 |
| divine-next-departure | 1 | 3 | 2 | 1 |
| divine-short | 3 | 3 | 2 | 3 |

These vectors equal pre-change shared. Capsule/output local deepcopies are
additional narrow copies, not mislabeled whole-world clones. Target clock-gap
validation remains a separate existing gate. Strict executes one complete event
per commit. No batches/workload were enlarged/reduced to obtain improvements.

### Scaling and remaining costs

| Fixture | Aircraft | Bookings | Completed results at entry | Journals | Terminal events | Manifest Booking visits | Kernel pending/history rows copied | Private memo views (max) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| round-trip | 1 | 21 | 0 | 2 | 7 | 168 | 52 | 572 |
| mixed-ten | 10 | 680 | 0 | 15 | 7 | 54400 | 1718 | 7612 |
| aged-ten | 10 | 680 | 0 | 15 | 1007 | 54400 | 41690 | 10612 |
| representative-ten | 10 | 1491 | 0 | 15 | 7 | 244960 | 5820 | 11057 |
| dense-25 | 25 | 1776 | 0 | 30 | 7 | 355200 | 9100 | 14039 |
| divine-next-departure | 1 | 21901 | 117 | 128 | 245 | 43802 | 848 | 69217 |
| divine-short | 1 | 21901 | 117 | 128 | 245 | 131406 | 2546 | 69780 |

Controlled mixed/aged-ten have the same 40 events, 680 Bookings and manifest work;
1,000 additional terminal events raise kernel copied rows 1,718 → 41,690 and
kernel-witness cost 0.034 → 0.474 s. Owned alias visits remain 12,920 in both.
Other fixture axes are correlated, so they provide workload scaling diagnostics,
not independent fitted causal slopes or a prediction for 500 aircraft.

- Protected serialization / whole-candidate alias proof no longer costs
  O(events × retained world size) in optimized transitions. Entry/final full
  validators still cost O(world size) per candidate boundary.
- Local proof/alias work scales with writable outputs, simulation/revisions and
  selected manifest size; topology seals scan affected table key/row identities.
- Manifest construction still sorts/scans Bookings O(events × Bookings), twice for
  Departure and four times for Completion (capture plus unchanged handler). Proxy
  read costs make its dense-25 exclusive time **1.068 → 4.134 s**. This is a real
  tradeoff/new dominant cost, not attributed to the removed alias traversal.
- Completion chronology still scans completed results; journal chronology still
  exists in Payment support. No persistent/private manifest lookup index was added.
- Kernel before witnesses retain complete pending/history copies. Capsule simulation
  copying and table seals also grow with history/revisions. This was not redesigned.
- Divine-next: full validation 8.478 s, world clone 1.759 s, manifest 1.169 s;
  proof capture/validation only 0.053 s. Optimizing only proof cannot fix that wall.

The recommended next gate is **ANOTHER ENGINE OPTIMIZATION before Stage 3E**:
retain this correctness foundation, separately scope cheaper guarded manifest/read
access and full validation/copy/event-history scaling. No such follow-up work is
implemented or implicitly approved here. Multi-second steps remain unsuitable for
normal cooperative GUI pacing. No exploratory 50-aircraft fixture was run; formal
Stage 3F and the 50-aircraft Ultra acceptance gate remain unfulfilled.

### Shadow and Payment

Round-trip: owned 0.445 s, full shadow 2.010 s, current strict 0.997 s. Shadow's complete protected/alias proof and strict event reference remain deliberately expensive.

All six original Payment fixtures match strict complete-world hashes (one
sample/path; no speed promise for isolated Payment).

| Payment fixture | Strict | Owned | Gates / clones / commits (owned) |
| --- | ---: | ---: | --- |
| one | 0.117 | 0.132 | 3/2/1 |
| sequential-eight | 0.696 | 0.202 | 3/2/1 |
| dense-64 | 6.138 | 1.176 | 3/2/1 |
| expiry-two | 0.731 | 0.617 | 5/6/3 |
| aged-eight | 1.147 | 0.670 | 3/2/1 |
| same-contract-three | 12.594 | 12.547 | 68/132/66 |

Same-contract-three includes 63 strict market rotations; it is not a three-event
shared-only benchmark. Expiry remains a fence. No additional handler is certified.

## Combined proof overhead and memory

A separate final dense-25 exclusive sample measures capture/validation 1.170 s and all disjoint capture/validation plus ownership entry/setup/publication/close regions 1.942 s. These instrumented root regions include diagnostic work (0.189 s); excluding it gives 1.753 s. That broader total is reported so setup/bridge cost is not hidden by the
capture-only reduction. Original fresh capture/validation was 11.787 s; recorded
Stage 3D was 9.860 s. No nested descendants are added twice.

Fresh isolated processes, one latency sample each; same exact frozen inputs
and targets. These peak counters include interpreter, input/current worlds and
existing validation/cloning work; they are not private memo allocations alone.

| Fixture | Before seconds | After seconds | Before process peak MiB | After process peak MiB |
| --- | ---: | ---: | ---: | ---: |
| dense-25 | 15.811 | 7.992 | 75.93 | 79.76 |
| Divine-next | 11.521 | 11.949 | 373.83 | 373.99 |

Memo structural estimate (dict/keys/pairs/views/access closures/cells, excluding
source world, primitive data, shared code and selected writable copies): dense-25
6.24 MiB / 14,039 views; Divine-next 30.49 MiB / 69,217 views. Not total RSS or a precise heap allocation trace. Process peaks show a small
dense-25 increase and essentially unchanged Divine-next high-water usage.
No unbounded persistent cache replaces the saved world: memo lifetime is one
bounded candidate, O(visited protected structures + replaced records in that
batch), and explicit close clears/revokes it before flush/recovery. Borrowed
capabilities cannot read/write after expiry. Tests verify close/rebind and no
proof data in saves. A caller-retained Python object can still occupy memory;
audited built-ins do not retain contexts/capsules or export private authority.

## Final verification and self-review

- Focused: `python -B -m unittest tests.test_candidate_ownership
  tests.test_flight_proof_optimization tests.test_flight_certification
  tests.test_payment_certification tests.test_shared_candidate -q` —
  **157 passed, 627.348 s**.
- Full: `python -B -m unittest discover -s tests` —
  **912 passed, 1397.137 s**, versus baseline 881. Includes all Stage 1 exact-world
  oracle, Stage 2 ownership/invalidation, Stage 3A infrastructure/recovery,
  Stage 3B Payment, Stage 3C Departure/Completion, Stage 3D optimization, booking /
  manifest, finance/journal, aircraft/maintenance, kernel/runtime, GUI, persistence /
  save-load suites. No expected authoritative gameplay result changed.
- Final review added explicit read-view attribute-deletion rejection and extended
  the existing dict/list mutator tests. This rejects a malformed API operation;
  audited certified handlers never call it. The 912-test run precedes that additive
  guard, followed by a final focused ownership/proof rerun recorded below. All other
  implementation semantics were in the full-run scope; benchmarks are unaffected.
- Native `python -B -m tests.smoke_runtime_startup`: **PASS**, Windows Python
  3.12.10, Kivy 2.3.1 / SDL2 / OpenGL Intel UHD 630. Separate GUI process directly
  loads the TEMP save with New Game forbidden, advances across two Booking
  checkpoints, creates 14 Bookings and validates exact paused save/reload.
  Window 2560 × 1377; authoritative time `2026-09-02T00:00:30Z`. Normal strict GUI
  pacing is tested; human-level shared GUI responsiveness is not established.
- Scoped compilation: `python -B -m compileall -q app game tests main.py
  make_snapshot.py settings.py test.py`; local documentation links and
  `git diff --check` are checked on final scope.

Complete diff review checks predecessor/successor separation, exact output and
publication bridge, mutable references/aliases, trusted entry/clone induction,
source identity lifetimes, expiry, helper read/write paths, NO_OP/fence/strict reset,
recovery and full shadow oracle. No Stage 2 speculative reuse, saved proof state,
new schema field, gameplay change, additional certification or production pacing
activation is introduced. No Stage 3E/3F work was begun. Pre-existing `.venv/`
remains untouched. Stop after this bounded Stage 3D.2 implementation.

Final affected rerun after the deletion guard:
`python -B -m unittest tests.test_candidate_ownership
 tests.test_flight_proof_optimization -q` — **50 passed, 33.018 s**.
Final scoped compilation, **200** local documentation links and
`git diff --check` pass. Self-review is clean within this scope.
The live remote was rechecked before commit preparation and still matched the
verified baseline; commit/push outcomes are reported after the actual operations.
