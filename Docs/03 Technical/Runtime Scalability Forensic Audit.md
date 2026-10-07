# Runtime Scalability and Main-Thread Stall Forensic Audit — Stage 3G-A

Successor: the separately authorized [Stage 3G-B implementation](Runtime%20Local%20Certified%20Proofs.md)
addresses local proofs and canonical selection only. The measurements and proposals
below remain the historical 3G-A baseline; later stages are not authorized here.

Measured **2026-10-07**, baseline **299f53c9f03981d3b1147dfa142978651566cb68**.
Local HEAD, upstream and live origin/master matched before work. Only `.venv/`
was initially untracked; it is untouched. **Audit only: no production changes.**
Schema 7, event safety, formulas, RNG, chronology, persistence and pacing remain.
This report proposes later work; it does not authorize implementation.

Authority: [schema](Stage%201%20State%20Schema.md), subordinate
[template mirror](../../Data/Templates/template_reference.txt),
[production runtime](Production%20Cooperative%20Runtime.md),
[Stage 3F](Runtime%20Capacity%20Certification.md),
[causal safety](Runtime%20Causal%20Generation%20Accounting.md),
[ownership](Runtime%20Candidate%20Ownership.md), and
[manifest lookup](Candidate%20Manifest%20Lookup.md). Stage 1/2 and Stage 3A–E
reports/code, status/roadmap and folder reference were inspected. Transaction
design is embedded in the canonical event contract/shared-candidate report and
execution contracts; no separate tracked Stage 3 Transaction Contract Design exists.

## Executive diagnosis

The engine returns, but complete safe units repeatedly monopolize Kivy's thread.
Cap eight is an **event-count bound**, not a time bound. Callback path:
entry validation/heap → candidate copy → per-event predecessor witness,
capabilities, handler and proof → complete validation → detached commit →
session invalidation/autosave → presentation. Yield follows that complete unit.
The .2-second Kivy ticker cannot interrupt its own callback. A strict Booking
fence is indivisible; lowering the batch cap cannot solve it.

One aircraft can have expensive retained authority: Divine has 21,901 Bookings.
Its native callbacks are multi-second. This compounds insufficient throughput.
No evidence of infinite handlers, recursive publication, timestamp loops,
sleeping simulation or corrupt saves was found. The dominant cost is unrelated
world/event/history traversal around small causal writes, plus periodic Booking work.

## Methodology and limits

Windows/Python 3.12.10/Kivy 2.3.1/SDL2/OpenGL, i5-10400, six physical /12 logical
cores. Host-specific observations, not portable guarantees. Existing processes
were not stopped. Expensive runs were serialized. Setup/telemetry/hash/verification
are outside engine timers. Quiet day runs are one sample each; separate exclusive
profiles validate attribution, not statistical speedup claims.

Exact TEMP Stage 3F inputs use public scenario/acquisitions/definitions/rolling
publication and real warmup. Test funding is confined to purchases. Aircraft fly
two daily round trips across MNL–DVO/CEB/ILO/BCD/PPS, staggered two minutes.
No idle-fleet shortcut, synthetic flight history, pruned history or shorter flights.

The diagnostic uses actual Stage1Session/resolver, cap8 and current routing.
Internal dependencies are timed; identity-bound handlers/certificate entries are
not replaced. Exclusive timers subtract children/GC; inclusive family totals
are separate. Budget stops happen between safe units and are censored.
Existing capacity tooling injects measured engine duration plus unoccupied .2-second
idle, retaining exact ns credit, overload/drain, commits and autosave. Setup earns none.

Native tests use fresh App.run, validated TEMP direct Load, Ultra, Overview, no
navigation/scrolling and actual monotonic pacing. A 50-ms heartbeat measures
same-thread starvation. A separate Windows observer reads Process.Responding,
not simulation. **Correction:** early OS counts included Load and snapshot I/O
after App.run stopped; those are not running-hang evidence. Final Unix markers
filter active samples. Initial native Save correctly rejected retained debt.
Final tooling uses SaveStore only for a diagnostic committed-prefix snapshot after
observation; no claim that player Save/drain completed or debt was saved/cleared.
No human mouse/paint survey or exact unknown human-failure timestamp is claimed.

## Updated Stage 3F baseline and scaling

All start Sep2 03:00 UTC /11:00 PH. Original source counts remain:

| Aircraft | Sectors/day | Dated flights | Bookings/itineraries each | Pending | History | Results | Journals | Definitions | Airborne |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 4 | 136 | 900 | 134 | 11 | 5 | 6 | 4 | 0 |
| 10 | 40 | 1360 | 5790 | 1313 | 108 | 50 | 60 | 40 | 7 |
| 25 | 100 | 3400 | 7469 | 3281 | 256 | 122 | 147 | 100 | 11 |
| 50 | 200 | 6800 | 7819 | 6580 | 482 | 223 | 273 | 200 | 35 |

Fifty has 200 Departures +200 Completions/day, 10 directional markets, 200 rolling
definitions, no contract obligations. Next Booking Sep3 00:00 UTC; weekly Sep6
16:00 UTC; market Oct1 00:00 UTC.

Actual quiet explicit one-day targets, including Booking:

| Aircraft | Events | Engine s | Optimistic service ratio | Callback p50 s | p95 s | Max s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 9 | 1.142 | 75641.5× | .178 | .243 | .628 |
| 10 | 81 | 17.992 | 4802.3× | 1.174 | 1.599 | 3.434 |
| 25 | 201 | 78.870 | 1095.5× | 2.625 | 3.241 | 7.013 |
| 50 | 401 | 280.155 | 308.4× | 5.126 | 5.808 | 12.467 |

Not live certification: pre-earned targets amortize work optimistically. P99 is
not statistically reported for <100-callback day samples. Ultra requires **48s/day**;
50 uses **5.84×** that budget, **17.1%** of 1800×, needing ~83% total reduction.
Stage3F recorded 375.151s /230.307×; new identity-safe profiles are 283.830/283.683s.
No optimization occurred here. Historical differences are host/run conditions;
full-day normalized authority is identical. Old finite 25/50 false generation
stops disappear due to Patch1.2B, not capacity improvement. Patch4 changes draft
feasibility, not flight runtime; GUI patches reduce rendering churn.

10→25: 2.5× aircraft /4.38× day cost. 25→50: 2× aircraft /3.55× cost.
These coupled fixtures show superlinear growth, not independent formal Big-O fits.
100/250/500 are not built/timed: failed50 and this curve make escalation
disproportionate. No thousand-aircraft claim.

### Actual four-speed probes

20 seconds of controlled real input, 30 engine-second budget plus one safe unit.
Fractions/slopes use last RUNNING samples, not later drains. All ledgers balance.
No overload in these short capped windows; no sustained certification claim.

| Fleet | Speed | Running resolved/earned | Running backlog slope game s/input s | Ending owed game s | Max callback s |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | Normal Speed | 0.998 | -0.1 | 0 | 0.178 |
| 1 | Fast | 1.000 | -1.3 | 0 | 0.174 |
| 1 | Very Fast | 1.000 | -5.8 | 0 | 0.178 |
| 1 | Ultra | 1.000 | -11.2 | 0 | 0.183 |
| 10 | Normal Speed | 0.975 | -0.3 | 0 | 1.039 |
| 10 | Fast | 0.971 | -0.8 | 0 | 1.025 |
| 10 | Very Fast | 0.972 | -20.7 | 0 | 1.512 |
| 10 | Ultra | 0.980 | -66.5 | 0 | 1.533 |
| 25 | Normal Speed | 0.900 | +0.9 | 0 | 2.346 |
| 25 | Fast | 0.914 | +3.0 | 0 | 3.039 |
| 25 | Very Fast | 0.583 | +305.2 | 720 | 3.272 |
| 25 | Ultra | 0.427 | +925.5 | 16380 | 3.314 |
| 50 | Normal Speed | 0.900 | -1.4 | 0 | 4.258 |
| 50 | Fast | 0.271 | +145.4 | 1740 | 6.416 |
| 50 | Very Fast | 0.097 | +795.4 | 15420 | 6.412 |
| 50 | Ultra | 0.048 | +1694.7 | 33420 | 6.377 |

Starter/ten fare better; 25 Very Fast/Ultra and50 Fast/Very Fast/Ultra accumulate
marked debt. Small Normal lag/drain is insufficient to certify or fail long-term
service. PLAYER_DRAIN tails are censored. The 180-second native50 separately
enters OVERLOAD_DRAIN, retains ~272,704 game seconds, no observed recovery.
Overload freezes earnings; it cannot make the work faster. Pause waits for safe return.

## Native main-thread evidence

| Input | Callbacks | p50 s | p95 s | Max s | Heartbeat max s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 50 original, 180-s observation | 38 | 4.945 | 5.193 | 6.270 | 6.274 |
| Retained Divine one aircraft, 90-s /40 callbacks | 40 | 2.510 | 3.920 | 6.378 | 6.380 |
| Divine phase-marked 60-s | 29 | 2.704 | 3.357 | 5.034 | 5.042 |
| 50 at Booking, phase-marked 60-s | 10 | 5.528 | 7.004 | **13.508** | **13.580** |

The last source is real advance to Sep2 23:59:59 UTC, not a changed clock/fake
history. Ultra reaches DAILY_BOOKING_CHECKPOINT: **13.504s engine, .00295s GUI**.
Thereafter most units process eight flights in5–7s.
**55/56 active Windows samples report not responding**, excluding startup/shutdown.
UTC advances to Sep3 02:40, every callback returns, authority validates. This
reproduces OS starvation, not deadlock. Counts are not wall-time percentages:
queries can block and sampling is uneven.

Phase-marked one-plane60s has **0/29 active false flags** despite real5.04s
heartbeat stall. Exact one-plane human OS flag is not claimed reproduced.
Earlier unfiltered flags cannot support that claim. Divine90s includes two Booking
checkpoints, max6.38s, GUI usually .001–.003s /max .0344s. Fence-native GUI max
.0815s, tiny versus engine. **POOR responsiveness**: repeated multi-second
blocking; input/paint cannot run inside units. Heartbeats execute between units.

## Exclusive bottlenecks and event families

Fine day total **283.683s**, 401 events, 52 commits, **54 complete validations**,
**104 kernel world copies** (52 candidate/52 commit), 400 event witnesses,
401 kernel comparisons, 400 capsules, 800 output checks, 51 manifest indexes,
800 manifests. One separate Booking preparation probe adds another whole copy,
not counted by the kernel-only hook. No nested flight command gates reappear.

| Component | Exclusive s | Share | Scaling/traversal | Remedy/leverage | Risk |
| --- | ---: | ---: | --- | --- | --- |
| Event/history, ownership and transition proof | 111.096 | 39.2% | Per-event pending/history, table topology/revision maps | Exact sealed deltas; highest50 lever | High |
| Complete validation | 77.975 | 27.5% | Entire graph/retained domains each boundary | Dependency-complete incremental predicates | High |
| Flight handler residual | 27.212 | 9.6% | Includes broad pending-event lookup/minimum scans | Reuse sealed kernel selection/ID lookup | Medium |
| GC | 27.354 | 9.6% | Container/capability/copy allocation | Reduce allocation; never disable GC | Medium |
| Candidate/commit clones | 25.933 | 9.1% | Whole unchanged world twice/unit | Narrow detached changesets/overlays | High |
| Booking preparation/process | 8.473 | 3.0% | One fence, two allocation passes, probe copy | Small daily share, high worst-stall lever | High |
| Manifest/index | 3.088 | 1.1% | Existing index once/candidate + relevant lineage | Low standalone leverage | Medium |

These groups are disjoint, GC subtracted; residual/queue/notification remainder
is explicit in JSON. Every category blocks the thread today. GUI is separate.
Within proof: witness30.379s; comparison47.670s; begin10.000s; output checks16.219s;
publication2.939s; topology2.007s. Validation graph19.813s; structure residual29.677s;
Booking6.201s; fulfilment5.876s; IDs3.382s; other predicates complete the aggregate.

Full-day lifecycle **inclusive** (do not add to exclusive table): Departure200 /
42.228s /200 future Completions; Completion200 /40.351s /0 children; Booking1 /
10.276s /one next-day child. Enclosing Booking callback12.471s. Pure arithmetic
is not that entire lifecycle cost.

Small isolated production probes:

| Family | Total with entry/final gates s | Lifecycle inclusive s | Children |
| --- | ---: | ---: | --- |
| Departure | .166 | .00164 | 1 future Completion |
| Completion | .169 | .00162 | 0 |
| Payment | .0698 | .000718 | 1 anniversary |
| Market +Booking at equal UTC | .178 | .00514 Market / .0926 Booking | one successor each |
| Two-aircraft weekly +2 Departures | .470 | .03431 publication | 113 publication children +2 Completions |

These are family probes, not idle-fleet capacity claims. Contract expiry is not due
in50/day/native windows; its strict code was audited, existing lifecycle tests
are correctness evidence, not a new timing claim.

## Change footprint versus unrelated traversal

One Completion updates one aircraft/location/lifetime counters, one flight/revision,
removes its operation, adds one result/journal, changes its airline/four accounts,
archives its event and updates simulation/allocator facts. No Booking/itinerary/
airport/definition change. Departure updates flight, aircraft/operation, event/
Completion and simulation/cursors. Measured50 next pair changes two aircraft/two
flights and one result/journal; emitted changed IDs are stable authoritative IDs.
It still traverses all 6580 pending events, history and unrelated tables.

Kernel event witness deepcopies pending/history +simulation per flight.
Handler contract compares retained rows/ID unions; flight proof repeats topology.
WriteTable copies entire footprint tables for one writable row; output checks
walk protected rows/key sets twice/event. Simulation copies include all operation
revisions. Revision counters/identity alone do not establish immutability.

Fresh50 next pair **5.667s/max4.291s**; after one real day **7.292s/max5.434s**.
Flights remain6800, pending fall to6380; Bookings7819→15569, history482→883.
Containers86848→135375; entries659156→1012150; runtime pickle bytes
13765579→21339594. Growth amplifies cost without more aircraft/horizon flights.
This coupled history test does not independently isolate each variable.

## Validation classification — no predicates changed

| Invariant/caller | Current traversal | Future classification/condition |
| --- | --- | --- |
| Foreign entry, Load, Save | Complete unknown graph | **A global**: retain full types/aliases/references/domain coverage |
| JSON/aliases/fields/money/UTC | Every complete gate, all containers | **B** internal output pack +protected-entry induction; **A** arbitrary input; no blind revision trust |
| IDs/allocator/ownership | All entities/history every gate | **B/C** affected records/inverse dependencies, namespaces/index invariants; retain global uniqueness |
| Pending/history/lifecycle | Witness/comparison +domain topology/event | **C/E** sealed canonical ticket/delta could subsume duplicate scans; custom handlers strict |
| Aircraft/operations/reservations/location | Flights/results/ops, latest-result lineage | **B/C** aircraft closure and operation/interval indexes; uniqueness remains proved |
| Booking/checkpoint/itinerary/sale | All Bookings, date results/cohorts/events | **B/C** protected sources for flight writes; daily writes require complete capacity/coverage/money closure |
| Finance/journals | Source-linked records/journals | **B/C** exact balanced new journal/touched accounts/lineage; integer money and old history preserved |
| Schedule/timing/catalog/recurrence | All occurrences/definitions | **B/C** protected-source inheritance, explicit clock/weekly dependencies |
| Extra full shadow/strict oracle | Diagnostic mode | **D** intentionally expensive, retained; no production checks silently moved to debug |

Approved current contract requires full final validation/detached publication.
Replacing that requires an approved exact-preservation contract, not permission
to delete checks. Clock-only calls run entry+final full validation with no domain
write. Monotonic UTC/earliest due/proved predecessor are promising inputs, but
the entire time-dependent dependency set must be proved.

## Transactions, indexes and queue

Runtime clone already uses C pickle, safe deepcopy fallback; saves use independent
JSON. Two copies/unit duplicate unrelated records. 104 copies at starting volume
represent roughly **1.43GB** encoded traversal before growth, not measured allocated
bytes. Hundreds of smaller event witnesses are additional.

Best-fit proposal: sealed deltas/transaction overlays, read-only source capability,
detached writable rows, exact new-row JSON/aliases, atomic publication. Structural
sharing requires protected/immutable sources; simply sharing mutable dicts or
unproved revisions breaks alias/recovery/Stage2 contracts. No strategy changed.
Unknown/foreign handlers retain strict full isolation.

Maps already provide O(1) aircraft/flight/market IDs. Dated indexes cover aircraft/
schedule/OD/time; Stage2 is committed-only. Candidate manifest lookup performs
two coverage passes once/batch, rebuilt after flush/fence, never persisted or
borrowed from Stage2. At least ~797k source Booking visits follow from51×2×7819
before growth; index costs only 1.390 s. Broad speculative manifest caching is low leverage.

Flight next-event and matching-event helpers scan all pending events despite
known kernel selection. The next pair with 50 aircraft costs .13054s for two minima and .01414s
for two matches: supports sealed selection capability rather than new authority.
Selected Bookings still require current checkpoint/sale/carriage checks.

Heap itself is small: build6580 in .0323–.0453s; pop all in .00359–.00415s.
Authority insertion is dict/ID/order assignment; derived insert O(log P).
Unusual cursor collision fallback scans pending/history, not the normal hot path.
Millions of events would hurt memory/build and broad proofs. Keep bounded horizon.
Future allocation is legitimate, not causal runaway. Weekly113 case passes;
Ordinary same-UTC limit100 and processed-event limit10000 remain unchanged;
explicit Advance retains its existing configured causal limit10000.

## Booking growth and hot/cold history

Model is **already aggregate/cohort**, not individual passengers. Rows represent
cohort/desired-date/selected-flight allocations with linked itineraries.
One50 day adds **7750 Bookings+7750 itineraries**, 200 results, 201 journals,
401 history entries; pending decreases200. Booking status stays CONFIRMED after
carriage; temperature joins flight status. Before: completed42 /airborne55 /
planned7722 associated Bookings; after:376 /142 /15051. Future cohorts dominate
hot-table volume too; cold growth is not the sole issue.

Source has two checkpoints, ten market results, **2548 desired-date groups**,
2189 zero booked (not necessarily zero demand). Unsuccessful outcomes are authority.
Validation/clones/index construction revisit retained sources. Checkpoint topology
scans all events per completed checkpoint: actual loop shape O(C×(P+H)).
Shopping rebuilds active flight/inventory indexes; current-date cohort reuse scans history.
Preparation runs allocation on a detached probe; processing recomputes it.
Imported aliases were timed: two allocation/shopping/demand/index calls. Reuse
needs exact witness AND cohort-state application; cached passenger totals alone are wrong.

| Retained data | Hot simulation use | Other necessary authority |
| --- | --- | --- |
| Active/future flights/Bookings | Capacity/events/carriage/position | Operations/Bookings/full save |
| Latest result per aircraft | Position/lifetime/settlement proof | Details/history/save |
| Older results/events | Broad proofs/validation still scan | Actual historical rows/lineage/save |
| Old Bookings/itineraries/checkpoints/cohorts | Coverage/lineage, broad indexes/gates | Historical load/fare/revenue/replay/save |
| Journals | Balances, linked sale/settlement | Finance/history/save |
| Old occurrences/revisions | Protected lineage/publication reconciliation | Historical reports/revisions/save |

Derived hot-ID partitions can remove cold data from operational reads without
changing saved meaning. Physical archival/retention/split persistence needs
separate design/schema approval; no authority may be omitted/deleted here.

## Memory, GC, Python and parallelism

Quiet50 ends265.5MiB working/389.0MiB process peak; fine profile peaks411.6MiB.
These include input+active world/candidates/witnesses/verification, not index size.
Native includes Kivy/OpenGL and loaded-source fixtures. Legitimate graph growth
is56%; a day cannot certify multi-week stability or rule out leaks. Aged50
post-service collection finds54 objects but working set stays254.7MiB; it does
not prove all retained RSS is a leak or all can be returned to Windows.

GC: **27.354s /32710 collections** in fine day. Native50 180s totals16.895s,
max gen2 .140s; fence-native gen2 max .167s; Divine max individual collection
.198s. GC amplifies CPU/allocation cost, but single pauses do not explain13.51s
alone. GC is never disabled. Explicit post-service collection is outside timing,
not a claimed production improvement.

Python loops/wrappers cost CPU, but are made to repeat unrelated work. Clone is
already C-backed. Evidence favors algorithm/data architecture before a language
rewrite, interpreter switch or native extension. No dependency justified here.
A simulation thread does not remove work; GIL/state ownership complicate it.
A separate owner process could isolate painting later but adds IPC, serialization,
command order, pause/save/rebind and committed-view synchronization. Full-world
transfers would recreate the bottleneck. Neither implemented/recommended as
a substitute for locality; preserve one owner and evaluate after efficient algorithms.

## Amdahl leverage

Perfect removal of validation alone caps gain at **1.38×**; validation+world
clones **1.58×**. Removing everything else while retaining validation caps at
**3.64×**, below required ~5.84×. Removing GC alone **1.11×**. Millisecond GUI
or .5% manifest-index optimization cannot deliver Ultra. Complementary locality,
validation and transactions are required. These are theoretical bounds, not
permission to remove protections or promises of realized gains.

## Exactness baseline

- Original50 source hash:
  `6ad6c18d2ee383a26938a856195c69c59f6c5c2517e614481e4a734c62a6b52d`.
- Quiet/profile day raw hash:
  `2368617d74d6da1acaf9c166037170ce64d8cef629211ea0a5089805c20550f4`,
  identical401 ordered events. Source retains NORMAL ratio1. The same explicit
  final Normal30 selection used by Stage3F yields
  **`dadcf6f513b68409b453c9629633fe603763c2ba84af5de46bd3ed3219dd8fc0`**,
  exactly its complete day. No fields excluded; clock selections cannot be ignored.
- Four speeds at fixed50 60-game-second target and independent strict oracle:
  **`b787e6f2434f9d5cadd2d92e0bf003bf39004a4474ac6952c1fe8faceb5e3ae2`**;
  same two equal-time events /one shared commit.
- Results:
  `d6273c18448369c172c66a0d543fe3850d6ace9bbf6d53f963374cdd0bd7aabe`;
  journals:
  `3c16f283faec0770f2261e1897a919fc27a89f9264608750e21b5010f900bc3e`;
  history:
  `5647ad7e3bcf1054dee21468ca458577b7328db7456fb0c47f57dae8c014bd07`.

Tool records complete/component/deterministic-state hashes and event vectors.
Native committed-prefix snapshots validate and reload exact/paused. No timer,
proof, cache, credit, selection or clipboard enters Schema7.
All16 pacing ledgers balance. Autosave is not naturally due in current short
windows (15 active minutes/seven game days); no new throughput claim for I/O.
Focused/full save/runtime tests remain evidence for committed-only persistence,
pause/drain, autosave throttling and no offline progression. Full shadow/strict
oracle/successful-prefix replay remain required.

## Proposed implementation sequence — user approval required

Proposals, **not Approved decisions**. No gameplay redesign.

| Stage | Problem/modules | Leverage/risk | Tests/rollback | Proposed success |
| --- | --- | --- | --- | --- |
| **3G-B** Certified proof locality +canonical selection | kernel witness/comparison, candidate_ownership, flight/payment proofs, fulfilment lookups; stop broad copies/scans | ~39% proof +material handler scans; high protected/topology/alias risk | Actual footprints, deliberate corruption/first-invalid/alias/replay, caps1/2/8/64, full oracle; strict fallback | ≥75% targeted proof/scan reduction on same50/aged fixtures; no per-event full-history witness; exact authority |
| **3G-C** Dependency-complete incremental boundary/clock proof | world validators/domain closures, resolver/session owner epoch | ~27.5%, primary Divine cost; high inverse/time dependency risk | Every invariant/foreign rebind, clocks/fences/save/load, full shadow/unknown-input gates; original checker rollback | ≥80% known-owned boundary cost reduction, every prefix independently fully valid; arbitrary inputs globally gated |
| **3G-D** Narrow detached transactions | transaction ownership/serialization bridge/domain deltas | ~9% copies +GC; high rollback/reference/Stage2 risk | Retained refs/aliases, stale indexes, mixed failure prefix/save/rebind; clone-path rollback | Copy volume follows affected subgraphs, ≥80% kernel clone-byte reduction, no leaks |
| **3G-E** Cooperative atomic preparation | resolver/session/domain preparation/pure validation and pump contract | UI stall target; high cancellation/interleaving risk | Irregular budgets/partitions, pause/drain/error/load discard, no speculative views/save, complete oracle; old atomic path rollback | Ordinary p95≤50ms/max250ms; rare fence≤1s or explicit bounded preparation; no credit/outcome loss |
| **3G-F** Measured Booking reuse +derived hot/cold indexes | checkpoint/allocation/shopping, source-bound occurrence/cohort/manifest readers | Worst fence/history wall; high cohort/inventory/revenue risk | 5D witnesses/fairness/RNG/old history/multiple airlines/invalidation, rebuild oracle; original probe/index rollback | One exact transaction-local allocation computation; hot work independent of unrelated cold growth; no retention change |
| **3G-G** Recertification | existing capacity/native/oracle harnesses | Actual acceptance, not microbenchmark | Full matrix1/3/7-day escalation, save/pause/drain/autosave, native, exact hashes | 50 Ultra≥1800× sustained, recovered bounded debt/no ordinary overload; responsive callbacks/stable memory |

B leads because per-event proof/table work is50's largest component. C also
addresses small aged/clock-only cases. D supplies smaller deltas before safe
resumable E. Responsiveness E comes ahead of broad history/Booking F: yielding
only between events is insufficient. B should introduce latency gates immediately.
F is re-profiled after preceding changes, not a speculative cache project.

E requires explicit amendment to today's no-private-candidate-across-returns rule:
bounded private preparation/deltas, committed-only views, queued/validated edits,
atomic publication and discard/rebind. D cannot casually share mutable authority.
Physical archival would need a separate persistence/schema design decision.
None of these contracts is amended here.

### Proposed final targets and rationale

- Keep literal30/210/900/1800. Certify1/10/25/50 active fleets over multiple days,
  including weekly fences. Fifty Ultra budget48s/day; suggested ≥20% engineering
  margin is proposed, never a reduced gate. Hundred is stress only; larger
  bounded curve probes follow successful50, not an invented thousand-aircraft claim.
- Ordinary p95≤50ms/max250ms permits useful input/paint; rare atomic fence≤1s
  is a separate noticeable-stall ceiling. Ideal60Hz is stricter, not promised.
  Prepare larger work in bounded safe pieces, no partial authority or time dropping.
- At fixed active load, unrelated cold growth must not multiply per-event cost.
  Doubling active events should trend near2×; proposed diagnostic ≤2.5× doubling
  with controlled history, genuine affected-work deviations explained, not a theorem.
- Transient memory bounded by batch/affected rows; derived indexes by active
  windows/lifetime. Post-collection growth tracks retained authority, not callbacks.
  Multi-week/drain/rebind/navigation runs are needed for leak conclusions;
  no arbitrary RSS ceiling invented from short data.

## Tooling, verification and scope

[Profiler](../../tests/profile_runtime_forensics.py),
[Windows observer](../../tests/observe_runtime_window.ps1),
[guard tests](../../tests/test_runtime_forensics.py).
Project Python, caller-owned TEMP fixtures only; real Saves untouched.

```text
python -B -m tests.certify_runtime_capacity --fixtures <temp> --build
python -B -m tests.profile_runtime_forensics --fixture <temp>/fleet-50.json --seconds 86400 --budget 600 --quiet
python -B -m tests.profile_runtime_forensics --fixture <temp>/fleet-50.json --seconds 86400 --budget 600
python -B -m tests.profile_runtime_forensics --families
python -B -m tests.profile_runtime_forensics --fixture <temp>/fleet-50.json --queue
python -B -m tests.certify_runtime_capacity --fixtures <temp> --fleets 1,10,25,50 --mode live --pacing-seconds 20 --speeds "Normal Speed,Fast,Very Fast,Ultra" --budget 30
python -B -m tests.profile_runtime_forensics --fixture <temp>/fleet-50.json --seconds 75599 --budget 600 --quiet --snapshot <temp>/before-booking50.json
```

Windows: run observer with Fixture before-booking50.json, Python project interpreter,
Tag booking, Budget60, Callbacks20. Outputs stay TEMP; filter Unix rows between
returned started_unix/stopped_unix. OS query time, clock markers, engine time differ.

Verification on 2026-10-07, frozen diagnostic source scope:

- Seven new instrumentation guards pass: source read-only, quiet/profile whole-world
  and event-vector equality, unchanged certificate/handler identities, exact child
  count, hook/GC cleanup, derived temperature/ID changes, finite diagnostic budgets.
- Affected runtime/capacity/cooperative GUI/causal safety/ownership: 96 actual cases
  passed in167.220s; invocation also had one nonexistent module loader error.
  A subsequent seven-guard rerun passed in3.305s, with another mistaken loader name.
  Both invocation errors were corrected; actual candidate manifest lookup suite:
  **26 passed in19.525s**. Thus122 distinct affected cases passed; no source-test
  assertion failure was hidden. Actual test modules remain unchanged.
- Full clean command: python -B -m unittest discover -s tests:
  **1116 passed in1167.058s** (baseline1109, seven new). Includes full Stage1/2/3,
  save/migrations, Bookings/finance/aircraft/runtime and scheduling/GUI regressions.
- Scoped command: python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py: PASS.
- Windows observer PowerShell AST parsing: PASS. All75 affected local documentation
  links resolve; original historical status body verified byte-equivalent after
  newline normalization. git diff --check: PASS.
- Native direct Load/Ultra/committed-prefix snapshot reload and phase-filtered
  Windows/heartbeat observations PASS, with limitations and initial diagnostic
  Save-while-draining rejection retained above.
- Full source/diff self-review: no production source changes, handler identity
  substitution, validation bypass, shortened workload, schema/persistence change,
  dropped credit/events, speculative state exposure or Stage3G-B implementation.
  Proposed architecture/targets remain proposals. Artifacts/saves stay TEMP.


Only diagnostic Python/observer, guards, report, documentation index and status
change. No production/data/template/schema, handler/certificate, speed/cap/overload,
commands, retention, formulas, GUI, persistence or offline changes. Git outcomes
are reported at delivery; .venv excluded.

**PH 1.0 RUNTIME REMAINS NOT CERTIFIED. Stage 3G-A stops here.**
**Stage 3G-B requires user approval.**
