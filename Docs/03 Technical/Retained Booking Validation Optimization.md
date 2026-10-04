# Retained Booking Validation Optimization — Stage 3E.2

Approved bounded implementation, **2026-10-04**. Initial local HEAD, upstream and
live origin/master matched **b9e8cde819deec22fcdd0bb4d8eb92fbcc643d1c**.
Authority remains [Stage 1 State Schema](Stage%201%20State%20Schema.md).
This follows [E.1](Atomic%20Boundary%20Cost%20Optimization.md). Schema remains **7**.
Only internals of retained Booking validation change. Stage 3F is unimplemented;
no automatic E.3, gameplay, handler certification, worker or pacing change.

## Findings and measurement method

The proposed Booking × itinerary hypothesis was **rejected**. The predecessor
already resolves Booking.itinerary_id by dictionary lookup. It scans all
itineraries once for direct structure/lineage, again for orphans; all Bookings
once for structure/relationships, again for result coverage; then resolves
Bookings/itineraries repeatedly in desired-date, market and paid-journal passes.
Direct flight facts, exact field sets, date syntax and diagnostic paths are rebuilt
for repeated retained records. Checkpoint results also contain many empty dates.
The retained checks are material; none can simply be dropped.

Before production edits, quiet Booking/full-validation controls, cProfile and
exclusive phase probes ran on the five original frozen Stage 3C world shapes.
A first line-trace experiment was rejected for latency attribution because its
heavy per-line overhead distorted phase weights. The retained tooling inserts
phase marks and actual loop-entry probes in a test-only AST copy instead. Each
interval is charged once; untraced helpers are included in their owning phase.
Nested cumulative cProfile times are **not summed**. Probe times include the
small visit-counter overhead and are separate from quiet latency medians.

An early cProfile Divine Booking run: **5,360,245 calls**, **2.676 instrumented s**;
2,522,202 dict.get calls; 21,901 direct-itinerary helper calls, .732 s inclusive;
84,227 exact-field checks; 40,417 date syntax calls. This is instrumentation,
not the quiet .546-second predicate latency. No fixture/workload is reduced.

Final runtime controls alternate frozen Booking predicates and optimized ones
on identical worlds/targets through real Stage1Session.pump, cap eight. Both
use E.1 graph validation and the SAME other engine code. Complete hashes AND
callback event/commit vectors must agree. Construction, input copy/load/resume,
output validation/hash and memory diagnosis are outside callback timing.
Initial controls establish pre-change behavior; final paired controls address
host variation. Timings are observations on this Windows/Python 3.12.10 host,
not portable guarantees. Production saves/data and .venv are untouched.

## Exact predicate audit and replacement

Every relationship is rebuilt from **current** world_state on each validation
call. Eligibility requires this invocation's successful E.1 exact JSON/alias/
forbidden-field/money/UTC traversal, no preceding identity/structure errors,
and successful unchanged checkpoint/configuration/event-prefix predicates.
This is a real predecessor proof, not world identity, revision or session trust.

| Predicate | Exact source inputs / invalidators | Optimized proof |
| --- | --- | --- |
| Itinerary structure/status | Every itinerary, direct contract and exact field keys | Inspect every row; reject non-direct/unusual shapes to diagnostics; Economy/CONFIRMED remain mandatory |
| Flight association | Each dated_flight_ids, flight, airline, market | Exactly one existing flight; passenger/Economy, owner/endpoints/times/fare currency and all three schedule-lineage values match |
| Fare snapshot | Itinerary snapshot, accepted amount and currency | Exact two fields; nonnegative integer amount; pure currency syntax; amount need not match later flight display fare |
| Booking structure/status | Every Booking, contract, exact keys, count, date/time, revision | Every row checked; positive non-bool passenger count, CONFIRMED, canonical required time/date and revisions remain |
| Booking → itinerary | Immutable itinerary ID, airline, snapshot | Source-derived itinerary tuple; exact owner, currency and count × accepted fare equality |
| Itinerary → Booking | Every Booking association, complete itinerary key set | Reject duplicate owner as encountered; owners are proven subset of all itineraries, equal cardinality proves no orphan |
| Inventory | Booking commit revision, current flight inventory and capacity | Compare every commit revision; aggregate same confirmed passengers per flight and enforce capacity |
| Desired-date result | Every checkpoint desired-date Booking ID, date, passenger total | Source Booking facts; no missing/duplicate ID, exact date and passenger sum |
| Market result | Every result Booking ID, owning checkpoint/cohort/time/market/revision | Exact source facts; global unique owner; exact totals; final set cardinality after subset proof gives complete coverage |
| Paid journal | All result-paid IDs, checkpoint-listed transaction IDs, source IDs, accounts/currency/entries | Exact transaction-key set equality, one paid transaction per airline/checkpoint, exact source IDs and integer totals/ordered entries |
| Zero fare | Accepted amount and finance_transaction_id | Null exactly for zero; no paid-journal membership invented; capacity still counts |
| Historical carriage/results | Frozen operations/results and current source lineage | Existing fulfilment/manifest validators remain unchanged; graph does not replace them |
| Checkpoint event topology | Completed checkpoints, pending/history, revisions, dates | Original prefix retained, including exact successor ownership/lifecycle and revision sequence |

The graph stores **no alternative status, fare, capacity, revenue or outcome**.
Source scalar values are used to evaluate the existing equations; temporary sums
serve validation only. Inputs that can invalidate a predicate are all reread on
its next call, including deep borrowed mutations and unrelated cross-domain edits.
No revision is assumed to prove deep immutability.

### Graph shape, completeness and uniqueness

- itinerary ID → immutable query tuple (source airline ID, flight ID, snapshot
  currency/amount, market ID).
- Booking ID → immutable query tuple (source checkpoint/cohort/date/airline/market,
  passenger count, booked time, total fare, transaction ID, Booking revision).
- Distinct flight ID → current immutable owner/endpoints/times/currency/schedule
  facts, only inside the itinerary pass. Current inventory is checked in the
  Booking pass, not treated as a retained validity token.
- Temporary owner sets and transaction → result Booking-ID groups establish the
  same exact subset/cardinality/equality predicates as the predecessor.

Both source tables are traversed completely. An anomaly returns False/None,
**not a partial index**. Collection/embedded-ID uniqueness is already checked by
this invocation's identity validator; add also rejects duplicate lookup keys.
Duplicate relationship ownership is rejected before cardinality is used.
Market ownership guarantees transaction groups contain unique IDs. Thus exact
sorted source-ID equality proves ordering, uniqueness AND coverage without three
redundant scans. Sorting affects predicate comparison only, never gameplay order.
All genuine references are immutable IDs, not display labels or UI focus.

Only fields read by actual predicates are represented; no future indexes.
ScalarRows uses a private flat scalar list and ID → offset dictionary, returning
immutable tuples. No mutable record reference is retained. Initial per-record
tuples saved CPU but introduced ~.311 s of GC in Divine validation regions;
measured allocation evidence justified flat storage, avoiding one retained
GC-tracked object per record. This is not disabling GC or changing transactions.
The list is derived private implementation storage, never world authority.

Lifetime: complete validation call → prove structure → build → query → discard.
There is no cache on validator/session/request/world, no rebind/epoch protocol,
and nothing survives return, fence, strict event, save/load or candidate commit.
Pure date syntax memoization is bounded to 512 exact strings **within the call**;
non-string/unusual values use the original predicate. Currency syntax is reused
only for immutable source currency strings during one itinerary pass.

### Diagnostic equivalence

The original ordered suffix remains in booking_validation.py. Fast success emits
no issues. Any unsupported compatibility contract, malformed reference, shape,
status, value, duplicate or equation returns to that original suffix; preceding
errors bypass the graph entirely. Prefix diagnostics retain order and messages.
Unusual malformed values that already raise in the predecessor retain their
exact exception/rejection behavior; no new acceptance or silent repair is added.
The frozen b9e8cde validator is an independent test-only differential oracle.

Ordinary exact-integer predicates avoid repeated isinstance calls, preserving the
original fallback for unusual scalar subclasses. Exact-field comparison uses a
key view against the same set/dict keys, preserving other iterable callers.
Required non-null UTC strings inherit canonical syntax from the ACTUAL E.1 walk;
null still fails the domain requirement. No E.1 JSON/money/UTC/alias rule is
reimplemented or bypassed. Graph construction cannot precede the alias proof.

### Candidate manifest lookup and Stage 2

[Stage 3D.3](Candidate%20Manifest%20Lookup.md) groups sorted immutable Booking IDs
by authoritative itinerary flight association for protected candidate carriage.
It does not prove all validation invariants and has a different source/lifetime.
E.2 uses the SAME relationship, but validates all records and result/finance
lineage. It does not borrow committed Stage 2 indexes or extend candidate lookup
lifetime. Candidate services close before full flush validation; entry validation
precedes candidate creation. A few milliseconds of map reuse cannot justify
crossing those proof boundaries. Manifest construction, transition witnesses,
strict replay and shadow remain unchanged. Stage 2 reads committed authority,
invalidates existing epochs after commits, and cannot see these local scalars.

## Controlled scaling

Bookings, itineraries and direct dated-flight-reference counts cannot independently
grow in a valid current direct V1 world: exactly one itinerary per Booking and one
flight reference per itinerary are canonical constraints. Invalid orphan/additional
reference cases are tested, not advertised as valid performance fixtures.

The test-only split_aggregates control splits existing **unflown** passenger batches
with fresh canonical IDs, maintaining linked desired/market/journal ID lists and
allocator cursors. It preserves exact total passengers/fares, capacity/inventory,
cash/accounts, checkpoint outcome totals, aircraft/flights/events/history/results.
It is synthetic schema-valid scaling evidence, NOT a gameplay command, historical
manifest rewrite, production save modification or new Booking formula. It keeps
flight/event dimensions fixed while jointly increasing the three inseparable
lineage counts. The five primary fixtures retain real public-command/observed data.

Predecessor work is approximately linear in retained B/I/result associations plus
checkpoint-date structures; it is NOT B × I. Its checkpoint successor ownership
check still scans E events for each completed checkpoint (C × E), unchanged here.
The optimized relationship work is O(I + B + result associations + paid source IDs)
plus per-transaction sorting. It eliminates redundant source-row traversals and
repeated invariant facts; no asymptotic claim beyond observed counts/source paths.
Existing all-world graph traversal, identities, other domain predicates, detached
copies and per-event topology/manifest proofs still scale with retained authority.

## Repeatable tooling

```text
python -B -m tests.profile_booking_validation --fixtures <temp> --trace --repeats 3
python -B -m tests.profile_booking_validation --fixtures <temp> --cases split-1,split-2,split-4 --trace
python -B -m tests.profile_booking_validation --fixtures <temp> --cases divine-next-departure --memory
python -B -m tests.profile_booking_validation --fixtures <temp> --runtime --repeats 3 --cases one-departure,one-completion,round-trip,representative-ten,aged-ten,dense-25,divine-next-departure,divine-short,clock-small,clock-divine
python -B -m tests.smoke_atomic_boundaries
python -B -m tests.smoke_atomic_boundaries --fixture <temp>/divine-next-departure.json
python -B -m tests.smoke_atomic_boundaries --fixture <temp>/divine-next-departure.json --booking-fence
```

## Measurements and verification

Implementation measurements follow. Final verification and readiness are recorded at the end.

### Authoritative world shapes

| Fixture | Aircraft | Bookings | Itineraries | Flight refs | Flights | Completed / planned | Results | Pending / history events |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| one-departure | 1 | 21 | 21 | 21 | 2 | 0 / 2 | 0 | 5 / 7 |
| representative-ten | 10 | 1491 | 1491 | 1491 | 40 | 0 / 40 | 0 | 43 / 7 |
| aged-ten | 10 | 680 | 680 | 680 | 20 | 0 / 20 | 0 | 23 / 1007 |
| dense-25 | 25 | 1776 | 1776 | 1776 | 50 | 0 / 50 | 0 | 53 / 7 |
| divine-next-departure | 1 | 21901 | 21901 | 21901 | 718 | 117 / 601 | 117 | 603 / 245 |

### Exclusive baseline predicate profile

Single frozen-original diagnostic call inside complete validation. Each interval
is counted once; helpers are included in their phase. Percentages refer to the
SAME instrumented full-validation call. Do not add quiet/inclusive totals.

| Fixture | Config | Checkpoint structure | Event lineage | Inventory | Itinerary | Booking/association | Orphan itinerary | Result/journal lineage | Orphan Booking/capacity | Full call |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| one-departure | 0.0001 | 0.0285 | 0.0001 | 0.0000 | 0.0002 | 0.0002 | 0.0000 | 0.0014 | 0.0000 | 0.0707 |
| representative-ten | 0.0001 | 0.0341 | 0.0002 | 0.0001 | 0.0094 | 0.0161 | 0.0011 | 0.0101 | 0.0006 | 0.1536 |
| aged-ten | 0.0001 | 0.0312 | 0.0013 | 0.0000 | 0.0040 | 0.0051 | 0.0004 | 0.0043 | 0.0003 | 0.1265 |
| dense-25 | 0.0002 | 0.0276 | 0.0001 | 0.0000 | 0.0119 | 0.0213 | 0.0010 | 0.0093 | 0.0009 | 0.1644 |
| divine-next-departure | 0.0001 | 0.1549 | 0.0012 | 0.0005 | 0.1735 | 0.2222 | 0.0183 | 0.1286 | 0.0173 | 1.5526 |

Divine percentage of its complete validation, same exclusive phases:

| Phase | Percentage |
| --- | ---: |
| configuration | 0.01% |
| checkpoint_structure | 9.97% |
| checkpoint_event_topology | 0.08% |
| airline_flight_inventory | 0.03% |
| itinerary_structure_lineage | 11.17% |
| booking_structure_and_association | 14.31% |
| orphan_itinerary | 1.18% |
| checkpoint_booking_lineage | 8.29% |
| orphan_booking_capacity | 1.12% |

Flights/results/manifest, generic event validation and financial validators outside
Booking remain separate full-world predicates. Booking does not validate a
new flight outcome or mutate capacity. Its result/journal phase includes both
desired-date/market ownership and actual paid transaction/source/entry checks.

### Quiet isolated predicates and complete validation

Three-sample medians, seconds; E.1 graph implementation in both modes.

| Fixture | Booking before | Booking after | Full before | Full after |
| --- | ---: | ---: | ---: | ---: |
| one-departure | 0.0265 | 0.0186 | 0.0666 | 0.0579 |
| representative-ten | 0.0552 | 0.0302 | 0.1244 | 0.1065 |
| aged-ten | 0.0359 | 0.0233 | 0.1019 | 0.0896 |
| dense-25 | 0.0554 | 0.0343 | 0.1799 | 0.1187 |
| divine-next-departure | 0.5391 | 0.3190 | 1.2894 | 0.9912 |

Divine retained Booking predicate **.5391 → .3190 s (~41% reduction)**.
Small starter **.0265 → .0186 s**; no quiet small-world regression. These are
not mixed with the earlier tuple prototype or per-line trace experiment.

### Actual source visits and derived queries

Scope is Booking validation, excluding unchanged E.1/identity/generic walks.
The AST counters count loop body entries; direct helper/list-comprehension
resolves are accounted separately by their exact call/source paths. B and I
denote source cardinalities, P denotes paid Bookings. All primary fixtures are
validated, so exact result coverage gives B desired-date and B market references.

| Operation | Predecessor | Optimized |
| --- | --- | --- |
| Raw Booking source iteration | 2B | B |
| Raw itinerary source iteration | 2I | I |
| Booking dictionary resolves including result/sale passes | 4B + P | B; later reads are source-scalar queries |
| Itinerary source resolves including associations/results | 2I + 2B | I; B queries of local itinerary scalars |
| Rewalk Booking itinerary flight-ID lists | 2B | 0; exact single flight ID carried from checked itinerary |
| Direct itinerary flight references checked | I | I; distinct flight facts reused, no missing ID ignored |
| Graph builds | 0 | 2 scalar tables once per full call |
| Local scalar queries | 0 | B itinerary + 2B desired/market + P journal |
| Duplicate/orphan checks | Per-row original loops/owner maps | Exact subset/cardinality and duplicate owner sets |
| Diagnostic suffix | Always | Zero on valid ordinary worlds; one on graph anomaly |

Divine: raw Booking and itinerary iterations **43,802 → 21,901 each**;
source Booking resolves **109,505 → 21,901** and source itinerary resolves
**87,604 → 21,901** (P=B in this fixture). Local measured queries:
21,901 itinerary gets, 43,802 Booking gets and 21,901 journal Booking queries.
Graph adds: 21,901 per table. Its 43,802 repeated itinerary flight-list entries
disappear; all 21,901 direct flight references and 21,901 current inventory
comparisons remain. Graph construction examines ALL records, not just relevant
manifest rows. Checkpoint date results still visit 18,504 rows in each required
structure/lineage pass; 66 market results, 11 paid journals and 848 event rows
remain in the baseline shape. Event-owner matching still scans C × E.

### Production runtime before/after

Recorded E.1 values are historical. Fresh pre-change controls use two samples
and final paired controls use three alternating samples. Quiet medians, seconds.
Early overlapping diagnostics and noisy provisional samples are not substituted
for the final quiet table. Host variation explains differences between fresh
and recorded timings; no universal or statistically precise gain is claimed.

| Fixture | Recorded E.1 | Fresh pre-change | Final paired control | Optimized | Max control → optimized | Events |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| one-departure | 0.207 | 0.247 | 0.246 | 0.224 | 0.192 → 0.194 | 1 |
| one-completion | 0.229 | 0.243 | 0.232 | 0.231 | 0.175 → 0.172 | 1 |
| round-trip | 0.235 | 0.268 | 0.281 | 0.261 | 0.232 → 0.206 | 4 |
| representative-ten | 6.149 | 6.441 | 6.693 | 6.432 | 0.725 → 0.807 | 81 |
| aged-ten | 3.296 | 3.836 | 4.052 | 3.645 | 0.859 → 0.805 | 40 |
| dense-25 | 7.527 | 8.386 | 7.465 | 7.064 | 0.758 → 0.637 | 100 |
| divine-next-departure | 5.177 | 5.389 | 5.363 | 4.689 | 4.195 → 3.809 | 1 |
| divine-short | 5.416 | 5.586 | 5.587 | 4.938 | 4.685 → 3.927 | 3 |
| clock-small | 0.125 | 0.131 | 0.135 | 0.125 | 0.171 → 0.131 | 0 |
| clock-divine | 2.518 | 2.668 | 2.653 | 2.150 | 2.681 → 2.171 | 0 |

Every paired complete-world digest AND callback event/commit vector matches.
Only dictionary insertion order is normalized by the existing complete oracle.
No authority fields, histories, financial witnesses or clock facts are excluded.

### Retained validation/copy boundaries

Separate exclusive diagnostic run; performed alongside verification, not used
as quiet latency. All entry/result/final clock gates and physical copies remain.

| Fixture | Full gates before/after | Clones before/after | Detached commits before/after | Inclusive validation before → after | Booking exclusive before → after |
| --- | --- | --- | --- | --- | --- |
| one-departure | 3/3 | 2/2 | 1/1 | 0.224 → 0.168 | 0.077 → 0.055 |
| dense-25 | 15/15 | 26/26 | 13/13 | 3.214 → 2.788 | 1.023 → 0.599 |
| divine-next-departure | 3/3 | 2/2 | 1/1 | 4.392 → 3.516 | 1.906 → 1.132 |
| clock-divine | 2/2 | 0/0 | 0/0 | 2.897 → 2.463 | 1.280 → 0.793 |

### Controlled retained-lineage scaling

Earlier quiet synthetic split controls (before final flat-storage refinement);
actual dimensions and visit counts remain the same. Final representation has
also been replayed with equal validation results and source hashes.

| Split | Bookings / itineraries / flight refs | Flights | Booking control → optimized s | Full control → optimized s | Raw B/I iterations control → optimized |
| --- | --- | ---: | --- | --- | --- |
| split-1 | 1491/1491/1491 | 40 | 0.0842 → 0.0458 | 0.1802 → 0.1628 | 2982 → 1491 each |
| split-2 | 2619/2619/2619 | 40 | 0.0985 → 0.0612 | 0.2459 → 0.2179 | 5238 → 2619 each |
| split-4 | 3585/3585/3585 | 40 | 0.1340 → 0.0836 | 0.2932 → 0.2914 | 7170 → 3585 each |

The measured visits grow linearly with retained lineage at fixed 40 flights,
43 pending and seven history events. They do not multiply Booking × itinerary.
Late memory/count probes ran during the suite and are diagnostics, not a new
quiet scaling slope. No exploratory 50-aircraft workload was run; formal capacity
and sustained Ultra acceptance remain Stage 3F.

### Memory

Divine local tables: 21,901 itinerary and 21,901 Booking entries; owned table/list/offset storage **5,880,312 bytes** (~5.61 MiB). Borrowed immutable scalar/string objects are excluded from that estimate. Measured isolated Booking-call tracemalloc peak **8,724,379 bytes** (~8.32 MiB), including temporary ownership/groups/date facts. It ends with the call.

Isolated diagnostic process lifetime high-water **193.8 MiB**, including fixture JSON parsing, repeated validation/hash and interpreter work. Runtime paired peaks include both modes and earlier cases, so they are not standalone graph allocation. The additional temporary O(B+I) storage is explicit and bounded; no growing session cache, persistent graph or record duplication is introduced.

Flattening follows measured GC cost, not speculative caching. The per-record-tuple
prototype had ~.311 s GC attributed to Divine Booking regions; final diagnostic
records .000338 s GC inside the optimized Booking regions (control .000066 s),
versus .311445 s for the tuple prototype. Overall diagnostic GC also falls,
with clone/history/other GC still reported. No GC
disable/freeze, reduced workloads or validation/copy removal is used.


## Native Windows Kivy verification

Fresh child processes, SDL2/OpenGL on Intel UHD 630, Python 3.12.10 / Kivy 2.3.1.
All three smokes **PASS**: direct Load with New Game forbidden, initially paused,
real production pump/registered handlers, actual flight boundaries, all four
ratios, player pause/drain, temporary manual save and exact paused reload with
zero pacing credit/no offline progress. No production save was changed.

| Smoke | Callbacks | Median s | p95 s | Maximum s | GUI refresh maximum s | Shared / strict units |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Starter through daily Booking fence | 21 | .125 | .243 | .276 | .00140 | 1 / 1 |
| Comparable Divine next-departure | 14 | 2.119 | 3.699 | 3.934 | .00247 | 2 / 0 |
| Divine through daily Booking fence | 16 | 2.411 | 4.672 | 6.839 | .00340 | 3 / 1 |

Comparable recorded E.1 Divine native median **2.780 -> 2.119 s** (~24% lower),
maximum **5.397 -> 3.934 s** (~27% lower), GUI maximum **.0074 -> .00247 s**.
These are short programmatic samples, not statistical or human smoothness proof.
The longer Booking-fence run still peaks at **6.839 s** and is reported separately;
its strict checkpoint is not newly certified or split into incomplete transactions.
Both fence smokes execute Departure, Completion and DAILY_BOOKING_CHECKPOINT.

Normal is selected first; ratios 30/210/900/1800 are then selected through actual
controls. The initial finite credit is explicitly stimulated to reach the relevant
boundary without waiting game hours. Approximate initial targets are 86,345 game
seconds (starter fence), 1,800 (Divine departure), 42,000 (Divine fence); later
callbacks use actual monotonic pacing. It is not a sustained natural-backlog test.
Each sample records before/after pacing credit, committed UTC, engine time,
presentation time and strict/shared units. Earned work drains to paused committed
authority; fractional subsecond credit is retained at pause, then reload resets
credit to zero as before. No dropped time, offline advance or overload-policy
change is used. Save/reload exact hashes match. The GUI refresh remains measured
in milliseconds; the remaining seconds are engine work between complete boundaries.

## Verification and complete self-review

Evidence covers this Stage 3E.2 working-tree implementation on **2026-10-04**:

- `python -B -m unittest tests.test_booking_lineage_optimization tests.test_atomic_boundary_optimization tests.test_stage1_booking_foundation tests.test_stage1_booking_checkpoint -q`:
  **79 passed in 39.854 s**, including **23 new tests**. Differential full validation
  agrees with the frozen predecessor, including original diagnostics/exceptions.
- `python -B -m unittest discover -s tests`: **1009 passed in 1288.163 s**,
  versus baseline 986. This includes E.1 graph predicates; Stage 3E production runtime, all prior Stage 3 infrastructure/certification/
  proof/ownership/manifest/recovery/shadow tests; Stage 1 complete-world oracle;
  Stage 2 ownership/epoch invalidation; finance/journal, aircraft/lifecycle,
  Booking/itinerary/manifest, event/history, persistence/migration/autosave/bookmark,
  and runtime/explicit Advance/GUI regressions. No later E.3 stage is implemented.
- Production and functional regression source remained unchanged during the full
  suite. Later test-only profiler phase-percentage/counter attribution refinements
  were exercised by successful predicate/runtime/scaling/memory diagnostic runs.
- Frozen baseline validator: **all ten function ASTs match b9e8cde**. The retained
  original relationship diagnostic suffix also matches its original AST exactly.
- Deliberate corruptions cover every Booking/itinerary field, missing/duplicate/
  wrong IDs, invalid flight lists/containers, associations/status/counts/capacity/
  fares/revisions, result/journal lineage, alias and non-JSON values, and required
  canonical UTC. Anomalies are rejected with predecessor-equivalent behavior.
- Eight deterministic insertion-order variations, stale/deep mutation across
  separate calls, scalar graph completeness and fresh save/load validation pass.
  Complete authoritative hashes (and pickle bytes for non-JSON corruptions) stay
  unchanged across validation. Paired runtime whole-world hashes and callback
  event/commit vectors match for all ten primary scenarios.
- `python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`:
  PASS. Scoped documentation links and `git diff --check`: PASS.

Self-review checks the full changed scope: all records are consumed; no malformed
record is filtered away, ID overwritten or forbidden association deduplicated;
subset/cardinality proof follows exact ownership/uniqueness; no mutable records,
call-local tables, UI or Stage 2 state escape to saves; actual E.1 traversal precedes
graph use; diagnostics retain ordering; no trust across validations or commits.
Strict/fence execution, certification identities, intermediate validity/recovery,
shadow and full-world oracle, deterministic ordering, financial/history witnesses,
save/load/migration and paused restore remain unchanged. No schema/template,
formula/RNG/fare/capacity/recurrence/acquisition/GUI/pacing/worker changes.

Schema **7**, cap **8**, one safe unit per callback, speed ratios **30/210/900/1800**,
exact pacing credit, player/overload drains, recovered pause/error state and no
offline progression remain. Shared certifications are still only Payment,
Departure and Completion. Stage 3F and any later optimization are unimplemented.
Pre-existing untracked `.venv/` remains untouched.

## Remaining cost and Stage 3F decision

Successor: the approved measurement-only [Stage 3F certification](Runtime%20Capacity%20Certification.md)
has now tested the production model and reports **PH 1.0 RUNTIME NOT CERTIFIED**.
The readiness conclusion below meant readiness to measure, not a capacity pass.
Stage 3 remains incomplete; no automatic additional optimization stage begins.

**READY FOR STAGE 3F**, as a separately approved formal measurement/certification
stage. This is readiness to test, not sustained 50-aircraft Ultra acceptance.

The specifically targeted retained Booking cost is ~41% lower on Divine; ordinary
native median/maximum are ~24%/~27% lower, and Divine clock-only is **2.653 ->
2.150 s** in final paired controls. Exact gates/copies and oracle outcomes remain.
The retained-lineage hypothesis is resolved with measured visits and bounded
memory. No new correctness or measured performance failure makes a formal
50-aircraft test meaningless; no automatic E.3 is proposed or started.

Remaining measured work is whole-world structural/identity/domain traversal,
checkpoint/date structures and C x E owner scans, detached copies/commit work,
plus strict daily checkpoint gameplay on its fence (native 6.839 s peak). Those
can still produce noticeable stalls and should be measured under formal capacity
loads. The optimized retained graph remains linear in B/I/result associations,
with transaction source sorting; it does not eliminate growth of historical
world authority. No exploratory 50-aircraft fixture was run in this slice.

## Changed files

Production: `game/world_state/booking_validation.py`,
`game/world_state/booking_lineage_validation.py`.
Tests/tooling: `tests/booking_validation_oracle.py`,
`tests/test_booking_lineage_optimization.py`, `tests/profile_booking_validation.py`,
`tests/smoke_atomic_boundaries.py`.
Documentation: this audit, `Current Development Status.md`,
`Atomic Boundary Cost Optimization.md`, `Docs/README.md`.
