# Atomic Boundary Cost Optimization — Stage 3E.1

Approved bounded task, **2026-10-04**. Initial local HEAD, upstream and live
origin/master matched **be4fdd356563e7370ffef7e16aee23a4193d9f32**.
This succeeds [production cooperative runtime](Production%20Cooperative%20Runtime.md).
Authority remains the [canonical event contract](Stage%201%20State%20Schema.md#clock-and-event-contract).
Schema stays **7**; no new persistent field, migration, gameplay change, handler
certification, thread, speed/cap/credit change or Stage 3F implementation.

## Result and scope

The measured bottleneck was full validation, especially three overlapping graph
walks: JSON compatibility, mutable aliases, and forbidden fields/money/timestamps.
A single exact traversal now proves those three predicates on ordinary valid
authority. It checks current values on **every validation call**. All structural,
reference, event, Booking, operation, finance and other domain predicates still run.
Full entry, result/flush, strict/fence, final-clock and persistence gates remain.
Candidate creation and final detached commit copies remain.

The final alternating controls reduce Divine-next total **8.621 → 5.177 s**,
maximum callback **6.315 → 3.945 s**; dense-25 **9.216 → 7.527 s**.
Divine clock-only falls **4.696 → 2.518 s**. This improves the boundary, but does
not establish responsive retained-history play: the final native Divine smoke
still has a **5.397 s** callback and **2.780 s** median callback.

Decision: **ONE MORE SPECIFIC BLOCKER BEFORE STAGE 3F**. See the measured gate
below. This is not automatic permission for another E.x milestone.

## Reproduction and measurement protocol

Same frozen Stage 3C authoritative inputs/targets, including a detached Divine
save copy, reused through actual `Stage1Session.pump`, production cap **8**.
No production save/data is changed. Fake monotonic time provides exactly finite
earned work, excluding load/construction/resume, input copying, hard pause,
output validation/hash and diagnostic memory work from callback timing.
This measures real production boundary work without newly earned wall-time debt.
Native Kivy runs separately exercise real active monotonic pacing.

Before edits, fresh original finite controls were recorded twice per fixture.
A separate cProfile Divine validation and exclusive callback profile identified
hotspots. Quiet alternating controls then use the frozen predecessor graph
predicates in `tests/atomic_validation_oracle.py` and the current optimized
predicates on identical inputs. Everything else is the same production engine.
Control/optimized **full hashes and callback event/commit vectors must match**.
No workload, target, batch cap or validation semantics is reduced.

Two-sample latency medians and the larger sample maximum are reported below.
Exclusive profiles are separate single-sample diagnostic runs, not latency medians.
Host load/GC caused substantial variation (an early Divine profile was 12.72 s;
quiet control 8.54 s). Absolute timings are machine observations, not guarantees.

Commands (caller-owned TEMP fixtures, no repository output):

```text
python -B -m tests.profile_atomic_boundaries --fixtures <temp> --compare --repeats 2
python -B -m tests.profile_atomic_boundaries --fixtures <temp> --compare --instrument
python -B -m tests.profile_atomic_boundaries --fixtures <temp> --cases history-0,history-1000 --instrument
python -B -m tests.profile_atomic_boundaries --fixtures <temp> --cases divine-next-departure --reference-graphs
python -B -m tests.profile_atomic_boundaries --fixtures <temp> --cases divine-next-departure
python -B -m tests.smoke_atomic_boundaries
python -B -m tests.smoke_atomic_boundaries --fixture <temp>/divine-next-departure.json
```

The existing `profile_flight_certification` fixture builder creates representative
public-command worlds; its observed input is a detached validated envelope, never
a raw legacy save. The new tool consumes frozen `world`/`target` fixture files.
`--shadow` remains available diagnostically; it does not change normal runtime.

## Pre-change atomic path and exclusive accounting

Earned target → request entry/full validation → next-event heap → private clone
→ ownership/read capabilities → genuine predecessor witness → registered handler
→ event/history contract → exact transition proof → close private services
→ full result validation → detached copy/publication → session/Stage 2 invalidation
→ autosave eligibility. The final quiet UTC gap has its own full validation.
No speculative candidate survives the callback. Strict/fence units retain their
existing isolated transactions and successful-prefix rules.

`ExclusiveProfile` subtracts complete instrumented child intervals from parents.
Nested inclusive totals are shown separately and **must not be added** to child
exclusive totals. GC time is subtracted from its active parent and reported
separately; parent attribution is diagnostic. Frames allocate before their own
timer starts so collection during instrumentation does not get counted twice.
Handler dispatch/lifecycle includes strict fence work, not only flight bodies.
Commit clone is distinguished from initial candidate clone. Autosave eligibility
in finite controls returns at the no-career guard; native saves exercise real
career storage. GUI/header/projection time is measured in native callbacks,
not falsely attributed to the engine-only tool.

A direct pre-change Divine full-validation cProfile had **17,031,645 calls**,
**9.343 instrumented s** (profiler overhead; not an uninstrumented latency):
root 3.023 s inclusive, structure 3.156 s, forbidden-field scan 2.697 s;
within root, JSON 1.437 s and alias paths 1.578 s; Booking 2.727 s inclusive.
These nested numbers are **not summed**. About 2.99 million `dict.get`,
4.69 million `isinstance` and 2.03 million `str.endswith` calls were observed.

## Final exclusive production profile

Separate diagnostic run after functional verification. Times below are exclusive,
including a separate GC category. Sum plus unattributed time equals measured total.
Category I includes the tiny local alias predicate also used on capsule outputs;
the exact complete-world inclusive region is given separately below. L GUI/header
refresh is absent from engine-only controls and measured in the native table.

### Divine next-departure decomposition

| Exclusive category | Control seconds | Optimized seconds |
| --- | ---: | ---: |
| A queue/next selection | 0.000550 | 0.000605 |
| B initial candidate clone | 0.631747 | 0.536423 |
| C ownership/capsules/output/publication | 0.014904 | 0.016479 |
| D handler/lifecycle dispatch | 0.005172 | 0.007652 |
| E transition predecessor capture | 0.000505 | 0.000659 |
| F transition proof | 0.002121 | 0.002366 |
| G private Booking lookup/verification/manifest | 0.101596 | 0.130742 |
| H event/history witness/proof | 0.027197 | 0.034543 |
| I validation predicates/gate overhead (without GC) | 7.316920 | 3.686742 |
| J detached commit clone/replacement | 0.569853 | 0.528251 |
| K session/epoch notification | 0.024693 | 0.021116 |
| M autosave eligibility | 0.000010 | 0.000010 |
| N final-clock orchestration (validation is I) | 0.000014 | 0.000014 |
| O resolver/candidate bookkeeping | 0.036623 | 0.030300 |
| P garbage collection | 0.809330 | 0.144926 |
| Unattributed callback/measurement overhead | 0.000297 | 0.000525 |
| Measured total | 9.541532 | 5.141352 |

Nested inclusive complete-world validation: **7.985793 → 3.699832 s**, three calls each. These are NOT added to the exclusive rows.

| Fixture | Full validation control → optimized (inclusive) | Initial clone control → optimized (exclusive) | Detached clone/replacement control → optimized (exclusive) | History control → optimized (exclusive) | Full gates / copies / physical commits |
| --- | ---: | ---: | ---: | ---: | ---: |
| one-departure | 0.3824 → 0.2061 | 0.0135 → 0.0126 | 0.0141 → 0.0130 | 0.0007 → 0.0006 | 3 / 2 / 1 |
| one-completion | 0.3560 → 0.2142 | 0.0120 → 0.0142 | 0.0123 → 0.0103 | 0.0007 → 0.0007 | 3 / 2 / 1 |
| round-trip | 0.3371 → 0.2134 | 0.0184 → 0.0145 | 0.0111 → 0.0158 | 0.0030 → 0.0023 | 3 / 2 / 1 |
| representative-ten | 4.8061 → 3.9950 | 0.6622 → 0.9095 | 0.7039 → 0.9408 | 0.2692 → 0.3596 | 13 / 22 / 11 |
| aged-ten | 1.9680 → 1.0336 | 0.2313 → 0.1878 | 0.2326 → 0.1731 | 1.3940 → 1.4224 | 7 / 10 / 5 |
| dense-25 | 5.6172 → 3.0314 | 0.8169 → 0.7388 | 0.8821 → 0.8044 | 0.3390 → 0.3313 | 15 / 26 / 13 |
| divine-next-departure | 7.9858 → 3.6998 | 0.6317 → 0.5364 | 0.5699 → 0.5283 | 0.0272 → 0.0345 | 3 / 2 / 1 |
| divine-short | 7.1014 → 3.8008 | 0.5593 → 0.5997 | 0.5304 → 0.5418 | 0.0743 → 0.0776 | 3 / 2 / 1 |
| clock-small | 0.2218 → 0.1233 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 2 / 0 / 0 |
| clock-divine | 4.7966 → 2.5181 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 0.0000 → 0.0000 | 2 / 0 / 0 |

Copies/commits/gates and callback vectors agree with their controls. Clock-only rows have zero copies/physical publications: their costly full UTC gates are included in validation, not misleadingly reported as free clock work. Controller committed-UTC notifications are distinct from physical envelope replacement.

| Input shape | Aircraft | Flights | Bookings | Itineraries | Results | Journals | Terminal events | JSON bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| one-departure | 1 | 2 | 21 | 21 | 0 | 2 | 7 | 1460231 |
| representative-ten | 10 | 40 | 1491 | 1491 | 0 | 15 | 7 | 3436660 |
| aged-ten | 10 | 20 | 680 | 680 | 0 | 15 | 1007 | 2643620 |
| dense-25 | 25 | 50 | 1776 | 1776 | 0 | 30 | 7 | 3844513 |
| divine-next-departure | 1 | 718 | 21901 | 21901 | 117 | 128 | 245 | 36147999 |

## Complete-world predicate audit

The implementation remains in `game/world_state/validation.py`; domain validators
stay in their owning world/domain modules. No helper moves to `game/utils`.

| Category / actual predicates | Certified writes and overlap | E.1 decision |
| --- | --- | --- |
| Structure/schema: `validate_root`, `validate_structure`, exact roots/record fields, configuration contracts/fingerprints | Changed records are checked by capsule/transition constructors; legacy schemas and global configuration still need complete checks | Full gate retained |
| IDs/allocators: `validate_collections_and_ids`, primary key/record ID matching, uniqueness, namespace and next-issued cursors | Allocation is proven per transition, but whole collections/foreign inputs remain broader | Full gate retained |
| References/cross-domain: airlines, airports/countries/markets/connections, schedule revisions, planned/actual aircraft, accounts | Capsules constrain writes; changed references still affect other records | Full gate retained |
| Events: pending/history lifecycle, unique order keys/cursor, owner/revision, UTC, payload, fulfilment/completion and recurrence topology | Kernel witness and generated-event proofs cover certified changes, not arbitrary/strict/fenced inputs | Full gate retained |
| Booking/itinerary: `validate_schema3_booking_authority`, checkpoint outcomes/successors, direct itinerary flight/fare snapshots, one Booking per itinerary, capacity and ticket-sale lineage/equations | Sources are protected during certified flight batches; Payment/Completion affect referenced finance/flight authority indirectly | Full scan retained; overlap is not an induction proof |
| Aircraft/flight: owner/base/location, capacity, reservations, schedule occurrence/time conversion, planning/acquisition validation | Departure/Completion prove exact operation/location/result changes | Full gate retained |
| Finance/journals: account ownership/currency/category, balances, integer amounts, balanced entries, transactions, Booking/settlement lineage | Payment and Completion prove their exact journal/account/airline writes | Full gate retained |
| Operations/results/history: `validate_schema4_fulfilment_authority`, frozen manifests and witnesses, revenue/cost/maintenance equations, event/result lineage and aircraft lifecycle | Exact transitions overlap many predicates, but global retained history is broader | Full gate retained |
| Revisions: operation, inventory, finance, Booking and config versions, lineage/cursor consistency | Per-event witnesses preserve/update exact affected revisions | Full gate retained |
| JSON: exact primitive/container types, finite floats, string keys, cycles/depth | Output constructors/typed proof overlap; persistence requires the complete property | Same complete predicate, combined valid-tree traversal; original diagnostic walker retained |
| Aliases: unique mutable container ownership including metadata/simulation/UI | Capsules reject local/output aliases and publication detaches; global entry/flush still checked | Exact all-container IDs checked once; original first-path walk on failure |
| Forbidden fields/money/UTC: recursive world-only legacy reference prohibition, integer non-bool minor units, nullable canonical UTC | Domain validators cover named fields; unknown nested fields still need generic coverage | Every current value checked in combined traversal; diagnostic scan preserved |
| Other: market-pack/demand fingerprints/cohorts, fleet marketplace, maintenance config, rolling schedule next-Monday completeness | Protected data/strict fences lie outside certified mutation scope | Full gate retained |

### Validated-authority hypothesis and mutation audit

No persistent or session-wide validation trust is introduced. `session.world` is
a borrowed mutable dictionary; identity, cardinality and existing revisions cannot
prove that an arbitrary nested row did not change. Stage 2's declared exclusive
owner contract is not a deep mutation detector. Session commands, runtime commits,
new game/load/migration/replacement have validated boundaries, but raw/debug/test
references can bypass progression notification. Tests corrupt such a row between
request creation and a clock-only step; the result gate still rejects it.

All supported schemas remain covered, including untrusted reconstructions,
startup/load, migrations, strict/custom handlers and fences. Every gate constructs
a fresh validator. `_graph_checked` is only an intra-call fact established by a
genuine complete traversal; it is neither a world/epoch flag nor a promise reused
after a callback, command, save/load, strict replay or world replacement.

## Exact optimizations and correctness arguments

1. **Combined plain-tree proof.** `_plain_authority_tree` visits every exact
   dictionary/list, tracks every mutable ID, checks every dictionary key and
   scalar type/finite float, and checks forbidden names/minor units/UTC for every
   key/value under `world_state`. Success implies all three original predicates
   hold. Immutable scalar sharing remains allowed. Money success requires exact
   `int`, because JSON already forbids integer subclasses and money forbids bool.
   UTC success requires exact `str` (or nullable None), avoiding custom method
   calls on a speculative path. Reference/domain predicates are not bypassed.
2. **Conservative diagnostic fallback.** Any failure, non-plain type/key or depth
   ≥128 falls back to the original ordered checks. The threshold is not a new
   schema limit: deep trees retain the original acceptance/RecursionError behavior.
   First JSON and alias paths, all error codes/messages and field issue ordering
   are compared against frozen predecessor code. Standalone public JSON validation
   and persistence serialization are unchanged.
3. **Local syntax reuse.** Field-name flags are cached only during this call;
   every record value is still checked. Unknown fields are included. Common
   all-false flags use an immutable constant tuple, avoiding per-ID tuple churn.
   This caches key syntax, never record validity or mutable authority.
4. **Allocation reduction.** Parallel traversal stacks replace a GC-tracked tuple
   per container. The visited graph and depth/authority context are unchanged.
   No GC is disabled and no collector policy is modified. A measured precursor
   still spent ~.38 s in graph-associated collection; the allocation change removes
   that temporary-frame/flag source rather than suppressing collection globally.
5. **Alias success path.** Standalone alias checks traverse only mutable
   containers/identities without scalar path strings. A repeat or unusual key
   replays the unchanged diagnostic traversal, preserving its exact first pair.

These are equivalent complete predicates, not candidate-to-itself checks and not
post-hoc declarations of validity. No full validation is removed. No private
history/Booking index or authoritative revision is added. Existing candidate-local
manifest IDs and Stage 2 committed indexes remain separate and unchanged.

## Copy/ownership decision

`_clone_runtime_world` retains the exact internal C object-tree codec and fallback.
`_replace_envelope` still clones the validated candidate before clearing/updating
committed authority. Capsules/proof/debug references can retain private records
or roots; ownership transfer without another enforced boundary would weaken
post-commit isolation. Existing retained-reference/alias attacks remain in the
ownership suite. Neither copy is removed; no COW or borrowed mutable container is
introduced. Shadow reference copies remain deliberately expensive.

## Clock-only audit

`kernel._complete_target` writes only `simulation.time_utc`, fully validates and
restores that UTC on failure. It does not clone the world or invent gameplay,
advance RNG/allocators/event cursors, or create a persistent revision. The resolver
first validates request entry and handles every due event in stable order.
Session/controller committed-unit/UTC notification invalidates the read epoch
and consumes exactly resolved credit; remaining target/debt is runtime-only.

A clock change is not proven safe by timestamp syntax alone: for example
`recurrence_validation.validate_recurrence` derives the expected next base-local
Monday from current UTC. Arbitrary borrowed-world corruption also must not become
trusted. E.1 retains both entry/final gates for the event-free request, applying
the cheaper exact graph checks. No speculative clock-only gate elimination occurs.

## Before/after latency

Seconds. Final source, same frozen inputs/targets and production cap eight.

| Fixture | Recorded Stage 3E | Fresh original | Alternating control | Optimized | Max callback control → optimized | Events |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| one-departure | .341 | 0.356 | 0.339 | 0.207 | 0.252 → 0.149 | 1 |
| one-completion | .337 | 0.336 | 0.330 | 0.229 | 0.232 → 0.171 | 1 |
| round-trip | — | 0.367 | 0.354 | 0.235 | 0.261 → 0.177 | 4 |
| representative-ten | — | 7.788 | 7.297 | 6.149 | 0.774 → 0.710 | 81 |
| aged-ten | — | 4.233 | 3.884 | 3.296 | 0.805 → 0.685 | 40 |
| dense-25 | 9.192 | 9.554 | 9.216 | 7.527 | 0.855 → 0.775 | 100 |
| divine-next-departure | 8.657 | 9.193 | 8.620 | 5.177 | 6.315 → 3.945 | 1 |
| divine-short | — | 9.015 | 8.734 | 5.416 | 6.441 → 4.210 | 3 |
| clock-small | — | 0.207 | 0.203 | 0.124 | 0.206 → 0.129 | 0 |
| clock-divine | — | 6.444 | 4.696 | 2.518 | 4.702 → 2.542 | 0 |

All ten outputs and event/commit vectors match between reference/optimized and
repeat runs; eight flight fixtures also match the original pre-edit control hashes.
Aged/history and Divine results are reported honestly, not inferred from fresh worlds.
No exploratory 50-aircraft run or formal Stage 3F acceptance was performed.

### Complete authoritative output hashes

| Fixture | Complete authoritative SHA-256 |
| --- | --- |
| one-departure | `817bd9127e34faaa9db4ac8f2592098e90e7a9ecbf1f90c84ad454916a5f474e` |
| one-completion | `376917b05f0a7893816aae2fc7352e76ff7ff647fbe196f8697eb1a96d796558` |
| round-trip | `3adc7fbf193fa1f2941ac05c0298bc1affcdfb323f40f46ec5b3efafec9e7d4a` |
| representative-ten | `9e1bb3396562d6d2ca6d18ee346b27c1cd3573d026fe111481b68535ecb275e1` |
| aged-ten | `0dd417b9558b9510ead33072ae7274149e0138c6c1ae59d4aa1f6f439df55cdd` |
| dense-25 | `bd98d3dea448204a61ad550f7dfa5e5d655d82293b97f08ad43b1a7e877d1f9c` |
| divine-next-departure | `85aff62c20cf92053921eef2e940228e845f2eaa6631d36a4259e5c2073f5d51` |
| divine-short | `c9578420b04edb4b63e98274eb92d26fd53e1899905ec4a9e0896b1e0ad0da37` |
| clock-small | `d147857e98332aaded988b715ac526c0f1e30932513b59550451723054bdb07a` |
| clock-divine | `2217f88529bb5baa69ad74455896b71831d999190d0b140da3e6eac833e26f17` |

## Scaling and memory

A controlled history comparison uses the original public-command dense-departure
10-aircraft input at the aged fixture's round-trip target, versus the public-command
aged input containing 1,000 additional real terminal NO_OP events. No production
history is removed or fabricated. Both resolve 40 real flight events in five commits.
Optimized diagnostic total **2.026 → 3.367 s**, max callback **.453 → .745 s**.
Other Bookings/flights/aircraft/journal/result counts are checked and reported.
Remaining exact event witnesses still scan/copy retained pending/history per event;
this is retained, not hidden by an event-history persistence redesign. Exact
exclusive witness capture grows **.0288 → .3848 s**, event-contract comparison
**.0364 → .6868 s** (40 events); combined **.0652 → 1.0717 s**. The 1.341 s total
increase therefore has about 1.006 s in measured topology witness work.

Aircraft 1/10/25 and small/aged/Divine shapes distinguish dense event throughput
from retained data volume. Results/journals/Bookings/itineraries are linked by
canonical lineage/equations; their growth is jointly observed, not manufactured
independently by deleting linked records. No isolated causal coefficient for those
collections or formal asymptotic result is claimed from these few worlds.
The graph predicates are visibly O(all JSON nodes), with one traversal replacing
three. Whole Booking/itinerary and journal/result checks still scale with retained
records, and checkpoint/event ownership scans can involve both histories.
Across bounded batches the remaining cost includes events-per-batch × retained
world validation/copying, plus per-event retained topology witnesses.

Divine input compact JSON size is **36,147,999 bytes**; internal protocol-5 input
encoding **22,591,791 bytes**. Two clones move roughly twice that encoding (changed
manifest/output alters the final size); this is an estimate, not a direct sum of
all allocated object bytes. Isolated native-process profile high-water memory:
control **375.4 MiB**, optimized **373.8 MiB**. The small difference is not a
claimed memory breakthrough. It includes fixture/input copies, runtime, output
validation/hash and interpreter allocations, not just the private candidate.
All-case process peaks are cumulative and unsuitable for per-fixture comparisons.
New seen-ID sets/key flags/stacks have O(current graph) space, call-bounded lifetime;
no runtime accumulation, saved cache or candidate lookup growth is introduced.

## Safety, equivalence and verification

No event certificate, mutation footprint, generated-event ordering or successful-
prefix recovery code changes. Payment/Departure/Completion interleave as before;
Booking/weekly publication/contract expiry remain fences, rotation/custom/replaced
handlers remain strict. Invalid candidate/proof/full-flush results still discard
speculation and replay strictly from unchanged entry authority; optimizer divergence
retains the strict prefix and disables sharing. No proof cache contaminates replay.
Shadow diagnostics and the complete Stage 1 oracle remain available.

New tests freeze predecessor diagnostics, generated alias graphs, cycles/depth,
unknown nested names/money/UTC, custom types, UI-vs-world field scope, genuine
reference/flight/revision/Booking/journal corruption, borrowed in-place mutation,
entry/flush/final validation and two-copy counts, full-world/save equality, and
non-double-counted timing/exception cleanup. The existing JSON scan-count test now
requires one genuine combined graph proof and zero redundant JSON diagnostics on
success; invalid payload/alias rejection remains asserted.

Focused certification/runtime/ownership/owned-read/world suite: **282 passed in
658.522 s**; after final source allocation/guard changes, new and affected Advance
suite: **29 passed in 53.558 s**. `python -B -m unittest discover -s tests`: **986 passed in 1291.308 s**,
versus baseline 970. This includes the complete Stage 1 equivalence/oracle,
Stage 2 ownership/invalidation, all Stage 3 infrastructure/certification/recovery,
Booking/manifest, finance/journal, aircraft/maintenance, simulation/kernel,
runtime/explicit Advance, GUI and persistence suites. No authoritative expected
result changes. Production validator and functional regression-test source stayed unchanged during
the full run. Profiler-only category refinement and its extended timing assertions
were subsequently verified: **2 measurement tests passed in .045 s**; all ten
exclusive control/optimized scenarios completed with matching hashes/vectors.

Scoped `python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
passed on final scope. **55 local document links** resolve; the frozen oracle's
three function ASTs match the verified predecessor exactly. `git diff --check`
passed. Complete source/test/tool/document diff reviewed for all requested
proof/trust/alias/recovery/save/pacing/scope risks; no unresolved in-scope finding.
Only the measured next-stage blocker below remains; it is not implemented here.

Final fresh-process Windows Kivy/SDL2 smoke (TEMP careers; New Game forbidden):

| World | Callbacks | Median | p95 | Maximum | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Starter | 20 | .139 s | .304 s | .312 s | Direct Load paused; Departure/Completion/Booking fence; four speeds; drain; exact save/reload; no offline progress |
| Divine | 14 | 2.780 s | 4.707 s | 5.397 s | Direct Load paused; real Departure; four speeds; drain; exact save/reload; no offline progress |

Divine max engine region **5.290 s**, max graphical refresh **.0074 s**.
Both smokes use a clearly controlled initial earned-credit stimulus to reach the
flight/fence without hours of wall waiting; subsequent speed/pause uses real
active uptime. Native input/control callbacks execute between complete units.
This is programmatic evidence, not human-level responsiveness certification.

## Remaining gate and recommendation

**ONE MORE SPECIFIC BLOCKER BEFORE STAGE 3F:** retained-history complete validation
still dominates ordinary no-event and single-event callbacks. One-aircraft Divine
has 21,901 Bookings/itineraries and produces ~2.5-second clock-only callbacks;
real native play still stalls up to 5.397 seconds. Presentation is milliseconds.
This is a concrete continuous-play boundary problem, not missing visual polish or
an unsupported assertion that every callback must be 16 ms.

Smallest proposed next scope: profile and optimize the retained Booking/itinerary
lineage predicates in `booking_validation.py` and their directly referenced
financial/flight facts (immutable contract tables and exact call-local lookup/work
reuse where proven), rerun the same Divine/clock-only controls and corruption/oracle
gates. Do not adopt a session-wide trust flag, drop strict/fence/save checks, change
pacing/caps or introduce ownership transfer merely to pass timing tests. If scoped
inheritance is considered, audit each cross-domain dependency and mutation boundary
before replacing any scan. This proposal requires separate approval; E.1 stops here.

Literal ratios **30/210/900/1800**, cap **8**, one safe step per tick, exact credit,
player/overload drains, paused recovery, safe saves/exits and no offline progress
are unchanged. No additional handlers certified. Schema **7**, save content and
Stage 2 invalidation/committed-only reads remain unchanged. Stage 3F is unimplemented.
