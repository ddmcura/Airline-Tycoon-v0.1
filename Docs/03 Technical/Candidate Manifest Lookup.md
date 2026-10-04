# Candidate Manifest Lookup â€” Stage 3D.3

Approved bounded implementation, 2026-10-04. Local HEAD, upstream and live
origin/master matched `a58fdd021ac904aea161a1d7e6bb023dbb6b61de` before editing.
This succeeds [candidate ownership](Runtime%20Candidate%20Ownership.md) under the
[canonical event contract](Stage%201%20State%20Schema.md#clock-and-event-contract).
Schema remains **7**. Only candidate-local Booking/manifest lookup changes.
Normal session/Kivy/Advance execution remains strict. No Stage 3E/3F, extra handler
certification, gameplay, pacing, full-world validation/clone/history redesign,
save migration or persistent field is introduced.

## Reproduction and exact access audit

Same eleven frozen Stage 3C TEMP inputs and targets, cap 64, generation ceiling
10,000. Observed Divine Air is a detached TEMP fixture; production saves/data are
untouched. A TEMP archive preserves the pre-change engine for fresh controls.
Three-sample latency medians exclude fixture construction, initial copy, hashing
and post-validation. Separate exclusive stack profiles subtract instrumented
children; inclusive capture/proof regions are not added to the exclusive table.
Instrumentation and structural-memory diagnostics are not latency measurements.

Fresh before-change dense-25: **200 manifest calls, 355,200 Booking visits**,
**7,104 relevant manifest rows**, **3.998 s** manifest work. Divine-next:
2 calls / 43,802 visits / 72 relevant rows / 1.130 s. Divine-short:
6 calls / 131,406 visits / 198 relevant rows / 1.930 s. This reproduces the
Stage 3D.2 hotspot; timings differ with host load.

| Reader | Collection / original predicate | Ordering / repetitions | Mutable dependency and existing IDs |
| --- | --- | --- | --- |
| Departure witness `_capture` | All `world_state.bookings`; aggregate V1 CONFIRMED Booking, linked direct Economy CONFIRMED itinerary with `dated_flight_ids == [flight_id]` | Sorted Booking IDs; one scan/event | Event owner and flight ID known; Booking/itinerary source remains protected |
| Departure `_departure` | Same canonical manifest builder and predicate | Another full scan of the same flight | Current capsule authority, not witness rows |
| Completion witness `_capture` | Same full Booking scan | One scan/event; often repeats Departure's flight lookup within this candidate | Current flight/operation; exact frozen IDs already available but do not prove completeness alone |
| Completion `_completion` | Same canonical builder | Another full scan of the same flight | Current authority compared with frozen Booking/inventory manifest |
| Transition validators / settlement | Exact selected manifest, complete operation/result, journal/account effects, inventory/configuration/maintenance/Booking witnesses | No extra broad Booking scan; deterministic record/ID ordering retained | Witness is genuine predecessor authority, not candidate compared to itself |
| Manifest lineage helpers | Current relevant Booking/itinerary, checkpoint market/date ID membership and sale transaction source IDs | Existing checkpoint/journal membership scans retained | Checkpoint, cohort/date, sale ID and revision pins are known |
| Ownership | Read-only recursive Booking/itinerary views | Before: wrappers for unrelated scanned rows, repeated lookups across events | No mutable protected nodes accessible through ordinary API |
| Full world gates | Existing Booking/manifest/global validators | Unchanged entry/final/strict gates | All authority remains fully validated |

There are **two** manifest calls per certified flight event, including Completion,
not four. Four is the count for one Departure plus one Completion. Completion
retains current Booking validation and its exact frozen-manifest comparison.

## Authority relationship and ordering

The source is `Booking.itinerary_id â†’ world_state.itineraries[itinerary_id]
â†’ dated_flight_ids`. V1 direct itineraries contain exactly one flight. OD/date,
registration, current focus, cached operation and GUI projection are not foreign
keys. Compatibility wrappers establish no confirmed carriage and remain excluded
by the original predicate. Supported shared flight inputs remain Schema 7 only;
unsupported inputs keep the existing strict fallback, with no save rewrite.

The lookup stores `flight_id â†’ tuple(sorted(booking_ids))`. It duplicates no
Booking/itinerary/manifest record. Sorting per flight preserves the subsequence
of the original full sorted-ID scan exactly, regardless of dictionary insertion
order. Paid/zero-fare partitions, journal ID ordering, source IDs, witness hashes,
capacity, revenue and frozen output are unchanged.

The canonical builder still resolves each returned ID against **current**
capsule/predecessor authority and checks airline, market, endpoints, departure/
arrival UTC, Economy classification, complete schedule lineage, currency,
inventory-at-commit revision, completed checkpoint membership and sale lineage.
It constructs the same detached witnesses/fingerprints and capacity/revenue totals.
The lookup itself checks current ID/itinerary association and rejects disagreement;
it never repairs authority or silently substitutes independent rows.

## Mutability proof and exact construction

The actual identity-bound `mutation_footprint` callbacks are authoritative for
write capabilities, not event-name assumptions:

| Certified handler | Permitted records | Booking-derived lookup effect |
| --- | --- | --- |
| Payment | Own contract, airline/accounts, new journal, own pending/history and successor event; simulation/allocator | Bookings/itineraries untouched; no lookup needed |
| Departure | Own flight/aircraft/active operation, own pending/history and completion event; simulation/allocator | Booking/itinerary and inventory authority untouched |
| Completion | Own flight/aircraft/operation, airline/accounts, new settlement journal/result, own pending/history; simulation/allocator | Booking/itinerary and inventory authority untouched |

Guarded Booking/itinerary tables admit no in-place mutation, raw mutable return,
root replacement or writable aliases through the supported handler API. Capsules
seal protected roots and validate every changed record. Existing sale journals and
checkpoint state remain protected; Payment/Completion add only their exact new
journals. Global finance changes do not change Booking membership. No revision
counter is assumed to detect arbitrary deep mutation.

A lazy `CandidateManifestLookup`, localized with carriage in
`game/aircraft_operations`, derives groups directly from raw validated candidate
source. A **second linear coverage pass** independently checks sorted/unique IDs,
correct association and complete eligible coverage, rejecting omissions, duplicate,
surplus and wrong-flight IDs. Two O(Bookings) passes happen once per candidate,
not once per event; their separate visited-row counts/timings are reported.
Group sorting costs sum O(B_f log B_f). Temporary reverse coverage state is released
at construction; only immutable grouped IDs and bounded source bindings remain.

Construction/coverage is trusted domain code, tested against the separate slow
canonical manifest oracle. The stored map is a mapping proxy over tuples. A
handler receives only a read callable returning tuples, never the service object
or mutable map. Each query resolves current rows, checks source roots/sizes and
selected association. Completeness is inherited only from verified construction
plus enforced non-mutation, **not** root identity/cardinality alone. Illicit raw
in-place mutation by reflection/monkeypatching is outside the existing ordinary
Python ownership contract, not something an identity check is claimed to prove.

`HandlerExecutionContract.read_lookup_factory` is runtime-only, exact-certificate
bound. Generic ownership lifecycle resides in `game/simulation`; it does not
contain flight selectors. Metadata spoofing/custom replacements stay strict.
Before beginning a later capsule, ownership rejects a footprint touching any
existing lookup's protected sources. This guards mixed-handler reuse against
future footprint expansion. No write capability is broadened.

## Lifetime, lazy construction and failure

Candidate begins â†’ first flight read constructs/checks IDs â†’ repeated reads use
current relevant rows â†’ service closes before validation/commit/discard/recovery.
Payment-only candidates construct no Booking lookup. The read callback weakly
binds its capsule to avoid a callback cycle retaining one-event copied records.
Consumed/expired/foreign predecessor/capsule queries reject. Source replacement
or selected association/missing ID disagreement fails closed.

No lookup lives on a resolution request between `step()` returns. Batch limits,
a strict event, FENCE, NO_OP/probe broad write path, final flush or any exception
end reuse. Generated certified completions reuse only the same candidate's
protected membership; every event still has a fresh exact transition witness.
Booking checkpoint/weekly publication/contract expiry remain FENCE and market
rotation remains STRICT. A new candidate after a fence builds its own lookup from
its newly validated Booking authority. There is no in-place update requirement
for the current certified mutation union, no speculative revision and no persistent
index. Services clear maps/source references before strict replay or final gates.
Save/load, world replacement, session rebind and cooperative return cannot reuse
previous lookup state. Retained expired read callbacks cannot retrieve authority.

Build/query/handler/proof/final-validation/divergence failures retain Stage 3A
strict successful-prefix recovery. Strict replay receives no read capability and
uses the full scan. Later events cannot repair the first invalid transition.
Shadow retains the full canonical manifest scan, broad protected/alias witness
and strict per-event whole-world oracle; it remains deliberately expensive.

## JSON, aliases, Stage 2 and persistence

No compatibility/alias check is removed. Stage 3D.2 entry inheritance, exact local
changed-output JSON and canonical alias predicate, detached publication bridge,
full final gate/commit and whole-world shadow checks remain unchanged. The lookup
returns immutable strings/tuples, not candidate mutable containers. Selected
outputs remain detached plain JSON. No new alias path to committed authority,
GUI projections or retained handler objects is introduced.

Stage 2 continues using separate committed-world `BookingIndexes`; it is never
passed into this candidate. No shared builder or utility is introduced merely
because both indexes mention Bookings. Existing committed epoch invalidation,
lazy Fleet/Flights/Finance rebind, and external ownership gates remain unchanged.
Schema remains **7**; no index, read capability, witness, factory or proof state
enters saves. In-flight/completed/equal-time/mixed/fenced save continuations retain
exact Stage 1 complete-world equality and paused restoration.

## Repeatable tooling

```text
python -B -m tests.profile_flight_proof --fixtures <frozen-temp> --case all --mode shared --latency --repeats 3
python -B -m tests.profile_flight_proof --fixtures <frozen-temp> --case all
python -B -m tests.profile_flight_proof --fixtures <frozen-temp> --case all --mode strict --latency --repeats 1
python -B -m tests.profile_flight_proof --fixtures <frozen-temp> --case round-trip --mode shadow --latency --repeats 3
python -B -m tests.profile_candidate_manifest --fixtures <scaling-temp> --build --repeats 3
python -B -m tests.profile_candidate_manifest --fixtures <same-scaling-temp> --repeats 3
python -B -m tests.profile_contract_payment --case all --mode both --repeats 1
```

Scaling fixtures begin with one real 14-day published schedule, then use public
scheduling to extend finite service to 28/56 days and deterministic Booking/flight
continuation. No recurrence model or gameplay policy changes. At ages 1/4/10, the SAME first completed flight's manifest
and source IDs remain exactly unchanged while unrelated Booking history grows.
The shared next-departure/completion probe (plus its intervening Booking fence) uses each aged valid world;
its actual relevant rows may vary and are not claimed a perfectly controlled
whole-request causal experiment. Canonical/indexed manifest lookup is the
controlled fixed-relevant-authority comparison. No fake historical Bookings,
zero-income operations or production saves are manufactured.

Performance, regression gates, limitations and the Stage 3E decision follow below.

## Before/after performance

Seconds; historical Stage 3D.2 values are recorded evidence, not same-run controls.
Fresh pre/post shared columns are quiet three-sample medians. Current strict is
one independent sample; paired isolated measurements below address its variance.
All eleven hashes match pre-change, post-change and strict complete authority;
shared commit vectors match too. No fixture/workload/batch semantics changed.

| Fixture | Recorded D2 shared | Fresh pre shared | D3 shared | Current strict (1) |
| --- | ---: | ---: | ---: | ---: |
| one-departure | 0.408 | 0.460 | 0.384 | 0.396 |
| one-completion | 0.457 | 0.442 | 0.401 | 0.381 |
| round-trip | 0.445 | 0.429 | 0.431 | 0.848 |
| dense-departure | 0.987 | 0.918 | 0.876 | 3.027 |
| dense-completion | 1.050 | 1.027 | 0.902 | 3.147 |
| mixed-ten | 2.156 | 2.038 | 1.656 | 12.582 |
| representative-ten | 7.244 | 6.712 | 4.810 | 39.125 |
| aged-ten | 3.728 | 3.710 | 3.078 | 13.172 |
| dense-25 | 7.869 | 7.931 | 4.688 | 53.285 |
| divine-next-departure | 12.072 | 10.913 | 9.929 | 10.434 |
| divine-short | 13.053 | 12.569 | 10.154 | 18.669 |

Dense-25 improves **40.9%**, 7.931 → 4.688 s; historical D2 was 7.869 s.
Maximum dense shared step **4.997 → 2.730 s**; largest step across all fixtures
**9.698 → 7.470 s** (see exact pre-case maxima in tooling). These are still
long synchronous operations, not a human GUI responsiveness guarantee.
Divine-next is 10.913 → 9.929 s; Divine-short 12.569 → 10.154 s.
Round-trip .429 → .431 s is effectively unchanged; no universal speedup claimed.

### Exclusive pipeline and retained boundaries

| Category (dense-25) | Fresh pre | D3 |
| --- | ---: | ---: |
| manifest | 3.997621 | 1.331026 |
| lookup_build | 0.000000 | 0.010878 |
| lookup_verify | 0.000000 | 0.005347 |
| lookup_query | 0.000000 | 0.113075 |
| kernel_witness | 0.143066 | 0.139790 |
| full_world_validation | 1.526253 | 1.390848 |
| clone | 0.336260 | 0.257892 |
| detached_commit | 0.016022 | 0.014624 |
| canonical_json | 0.110259 | 0.111434 |
| mutable_alias | 0.115446 | 0.111765 |
| ownership_begin | 0.239518 | 0.220450 |
| ownership_boundary | 0.100904 | 0.096619 |
| ownership_publish | 0.203954 | 0.189042 |
| ownership_close | 0.008203 | 0.010553 |

`lookup_build` is exclusive construction excluding its nested coverage pass;
add `lookup_verify` once for inclusive build cost. Query verifies returned current
associations; `manifest` excludes query/build child timings. Protected encoding
remains zero on the owned path; final gates retain all canonical/alias validators.

| Fixture | Capture + transition proof before → after | Manifest before → after | Gates / whole-world clones / commits | Builds / queries |
| --- | ---: | ---: | --- | --- |
| dense-25 | 1.187 → 0.865 | 3.998 → 1.331 | 4 / 4 / 2 | 2 / 200 |
| mixed-ten | 0.321 → 0.310 | 0.723 → 0.390 | 3 / 2 / 1 | 1 / 80 |
| aged-ten | 0.374 → 0.343 | 0.727 → 0.355 | 3 / 2 / 1 | 1 / 80 |
| divine-next-departure | 0.053 → 0.106 | 1.130 → 0.029 | 3 / 2 / 1 | 1 / 2 |
| divine-short | 0.146 → 0.133 | 1.930 → 0.088 | 3 / 2 / 1 | 1 / 6 |

The validation/clone/commit counts are unchanged by D3. Dense-25 has two
candidates (64/36 events), two builds, 3,552 source-build visits plus 3,552
independent coverage visits, 200 queries returning 7,104 IDs, and 7,104 actual
manifest Booking visits instead of 355,200. Including both build passes and
query association checks gives 21,312 logical Booking visits; lineage helpers
still perform their existing relevant checkpoint/journal membership reads.
Divine-next builds/coverage-checks 21,901 rows each, then both manifests visit
only 72 relevant rows instead of 43,802. Divine-short visits 198 instead of
131,406; lookup membership is not rebuilt for each event.

### Controlled unrelated Booking growth

Same completed flight, same 14 Booking IDs/witnesses and same canonical result.
Finite future service is explicitly extended via public commands; checkpoints
create real unrelated future Bookings. This isolates membership lookup, while
whole-request probes also contain the existing Booking FENCE and growing world.

| Age | Bookings | Relevant IDs | Canonical manifest ms | Indexed manifest ms | Build + coverage ms | Shared request pre → D3 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| age-1 | 896 | 14 | 16.397 | 3.336 | 1.854 | 1.457 → 1.417 |
| age-4 | 1616 | 14 | 23.542 | 2.563 | 9.266 | 2.349 → 2.273 |
| age-10 | 4453 | 14 | 53.310 | 3.385 | 16.145 | 5.000 → 4.717 |

Canonical guarded lookup grows .0164 → .0533 s for 896 → 4,453 rows;
indexed manifest stays approximately .0026–.0034 s for the fixed 14 IDs.
100-query average ID-only lookup is .100–.151 ms. Build timings include noise,
not a claimed precise linear slope. Rows are exactly 2B per candidate (build +
coverage); recurring reads are R, independent of unrelated B. No rebuild/update
occurs while protected sources remain immutable. Whole-request time still grows
because Booking FENCE/full validation/cloning/history are intentionally unchanged.

### Manifest size, aircraft/history scaling and next wall

Primary fixtures span 1/10/25 aircraft, 21/680/1,776 Booking rows and up to
21,901 rows in Divine Air. Relevant manifests/witnesses still require O(R)
work per event; no cached whole manifest is substituted for current authority.
Total lookup work is O(candidates × B + events × R), plus per-group sorting
at construction. Small batches and frequent fences necessarily rebuild more often.
The fixed-manifest experiment establishes independence from unrelated rows;
varying primary fleet fixtures changes R as well, not a controlled aircraft-only
slope. Checkpoint/journal membership scans can still depend on relevant lineage
collection sizes. No persistent historical pruning/index is introduced.
Aged-ten versus mixed-ten keeps 680 Bookings / 40 events, adds 1,000 real NO_OP
history rows, and increases kernel copied event records 1,718 → 41,690.
Exclusive kernel witness rises about .035 → .530 s; full topology seals/read
views and validators retain history costs. Chronology guards still scan results.
This is remaining O(events × event/result history) work, not fixed by D3.
Divine-next final/entry full validation is **8.102 s**, whole-world cloning
**1.406 s**, compared with manifest .029 s + build/coverage .097 s.
Divine-short validation **8.127 s**, cloning **1.429 s**; Book/history/journal
growth still affects full validators and clones. Those are reported, not redesigned.

### Memory and lazy versus eager

IDs are borrowed immutable strings; tuples/dict tables are new private structures.
Structural estimates include service bookkeeping, group table/proxy and tuples,
exclude source world, shared strings/code and temporary construction coverage
dicts. They are not precise total heap allocation or working-set measurements.
Dense-25: 1,776 IDs / 50 groups, about **18.1 KiB** per lookup; guarded read memo
falls **6.24 → 5.77 MiB**. Divine: 21,901 IDs / 709 groups, about **224.9 KiB**;
guarded memo falls **30.49 → 1.61 MiB**. All are cleared before final gate/replay.

| Isolated process (one sample) | Pre peak MiB | D3 peak MiB |
| --- | ---: | ---: |
| dense-25 | 81.19 | 82.45 |
| Divine-next | 374.37 | 372.94 |

Process high-water includes interpreter, fixture/input worlds and unchanged
clones/validators. Dense peak slightly rises despite smaller private memo;
Divine peak essentially unchanged. Do not claim overall RSS was greatly reduced.
No persistent accumulation exists; transient coverage state is bounded O(B).
Eager construction would pay the measured build/coverage cost on every candidate
(.097 s on Divine), even Payment-only/no-manifest work. Lazy construction pays
zero builds/rows/memory there; regression enforces this. Actual flight candidates
pay that cost once on first read, not per event. This justifies the simpler lazy
choice without claiming a separate eager engine implementation.

### Payment, shadow and exploratory 50

All six Payment strict/shared fixtures retain exact complete-world hashes.
Identity checking of the new factory field prevents value-equality spoofing of
Payment’s required absent lookup; no Payment domain behavior changes.
Four-event shadow round-trip median **1.659 s**, versus optimized .431 s and
strict .848 s (separate runs). Diagnostic full scans/protected/alias/strict reference
remain enabled in shadow, not removed for speed.
Exploratory 50 aircraft / 200 events: **12.471 s** (one shared sample), max step
**4.048 s**, batches 64/64/64/8. Instrumented final authority validates and hash
matches the uninstrumented run; 2,856 IDs / 100 groups / ~30.1 KiB private lookup.
No strict whole-run 50-aircraft comparison, sustained pacing, overload recovery
or formal Ultra/Stage 3F certification is claimed.

### Isolated-event policy and Stage 3E gate

Three alternating strict/shared samples per isolated fixture avoid treating
one current strict sample as an optimal-routing result.

| Isolated fixture | Strict median s | Shared median s |
| --- | ---: | ---: |
| one-departure | 0.378 | 0.368 |
| one-completion | 0.376 | 0.383 |
| divine-next-departure | 10.473 | 9.906 |

Observed isolated paths are broadly comparable: small advantages change sign
and samples overlap. Both have 3 full gates / 2 whole clones / 1 commit; shared
adds genuine proof, a lazy lookup and two manifest reads without saving a full
transaction boundary. For future Stage 3E, a conservative strict path for exactly
one eligible event is reasonable; shared for 2+ eligible events can amortize gates
and proof setup. This is a **recommendation**, not a policy implemented in D3
or evidence that strict always wins on every isolated host sample.
**A — PROCEED TO STAGE 3E** is justified for a separately approved bounded
production integration: dominant repeated Booking scans are removed, dense/mixed
throughput improves with exact equality, and isolated regression is reduced to
near parity. Another engine optimization is not a prerequisite merely because
remaining checks can be cheaper. Stage 3E must still measure/bound real cooperative
step latency and expose honest remaining synchronous stalls; existing saves
can require ~7.5-second shared steps. This gate is not a responsiveness/Ultra
acceptance claim. Full-validation/clone/history optimization remains distinct
future work, not silently included here. **No Stage 3E/3F was implemented.**


## Correctness gates and final review

2026-10-04, final source working-tree scope on verified baseline a58fdd0.

- Focused: `python -B -m unittest tests.test_candidate_manifest_lookup
  tests.test_candidate_ownership tests.test_flight_proof_optimization
  tests.test_flight_certification tests.test_payment_certification
  tests.test_shared_candidate -q` — **183 passed, 641.146 s**.
- Full: `python -B -m unittest discover -s tests` — **938 passed, 1557.209 s**,
  predecessor 912. No source edits followed the run. All expected authoritative
  gameplay results remain unchanged.
- Complete Stage 1 oracle across batch sizes 1/2/8/64, irregular/target partitions,
  save continuation, equal-time/generated/multi-aircraft, seeds/insertion order,
  mixed Payment/Departure/Completion, Booking/weekly/expiry fences and aged worlds
  remains covered, with no ignored authoritative fields.
- Stage 2 owned/invalidation reads, Booking/manifest, finance/journal, aircraft/
  maintenance, kernel/simulation/runtime/Advance and save/migration/load tests pass.
  All existing Stage 3A/B/C/D/D2 fault/replay/certification tests remain. Fault
  wrappers now forward the runtime-only read argument; their corruption/expected
  strict-prefix assertions were not weakened.
- 26 new tests cover canonical/indexed equality, sorted IDs/insertion variation,
  paid/zero/empty manifests, invalid lineage/revision/checkpoint/sale/capacity,
  independent missing/duplicate/wrong/surplus group rejection, invalid entry with
  no mutation/index, current relevant association/missing-source/root mismatch,
  protected Booking/itinerary writes, foreign/expired/consumed capabilities,
  lazy Payment/no-read behavior, one build per candidate, cooperative expiry,
  future source-footprint rejection, exact factory metadata identity including
  Payment value-equality spoofing, full shadow scan, before-replay/before-final-gate
  disposal, weak callback non-retention, in-flight/completed save-load/continuation
  and public unowned-hint rejection. No GUI/source index is serialized.
- Handler, transition proof, protected mutation, aliases/non-JSON, final validation,
  divergence and strict replay disagreement retain original successful-prefix
  behavior. Intermediate invalidity cannot be repaired by a later event. Full
  shadow/reference and final world authority remain independently checked.
- `python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
  — exit 0, explicit application scope only.
- `python -B -m tests.smoke_runtime_startup` — **PASS**, fresh separate native
  Windows Python 3.12.10 / Kivy 2.3.1 / SDL2 / Intel UHD 630 OpenGL GUI process,
  direct Load Game with New Game forbidden; Normal Speed/Advance crosses pending
  DAILY_BOOKING_CHECKPOINT, two completed checkpoints /14 Bookings, validated exact
  paused save/reload at `2026-09-02T00:00:30Z`, window 2560 ×1377. This tests
  unchanged strict production startup, not shared pacing or human responsiveness.
- Local documentation-link existence and `git diff --check` pass on final scope.

Review includes all source/tests/new tooling/docs, genuine predecessor versus
successor, protected source reachability, sorted complete membership, current
lineage/capacity, no shadow removal, alias/JSON guarantees, mixed-handler factories,
no stale reuse over return/commit/fence/strict/recovery, no candidate access to
Stage 2, no manifest-record authority cache, source ownership, save exclusion,
Schema 7, allocator/order/RNG, ordinary-handler identity and no production pacing
activation. No unresolved in-scope finding remains. Scoped ordinary fixes added
weak capsule binding and exact Payment factory identity, with regressions and
final focused/full verification. There is no additional handler certification,
Stage 3E/3F implementation or unrelated gameplay/GUI work.

Changed implementation modules: carriage lookup/fulfilment; generic candidate
ownership, contracts, kernel context and shared dispatch; flight proof and the
Payment certificate metadata guard. Changed tests: two profiling tools, one new
26-test lookup suite and four existing fault-wrapper suites. Documentation updates
are this audit, current status, canonical runtime-only contract/subordinate template,
README/decision routing and dated successor notes. No authoritative JSON changes.

Pre-existing untracked `.venv/` remains untouched. Live origin/master was rechecked
at a58fdd0 before preparation; actual commit/push/live verification are reported
only after those operations. Stop after Stage 3D.3.
