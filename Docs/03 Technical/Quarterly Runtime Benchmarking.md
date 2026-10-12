# Quarterly Runtime Benchmarking — Stage 3G-B2 / B2.1

## Stage 3G-B2.1 — advancement investigation (2026-10-13)

Approved baseline `b2db1c71f9dcc2356ff8eac303614c417d10929a` matched HEAD,
upstream, freshly fetched origin/master and live remote master. Tracked tree/index
were clean; only `.venv/` was untracked, and stashes were empty. Repository
contracts and targeted Serena navigation governed this bounded successor.
No Schema 9, template, economics, pacing, gameplay activation or safety-budget
change is authorized or made. The B2 evidence below remains historical evidence.

### Exact reproduction and workload

Reuse the committed B2 harness and its original one-aircraft construction without
changing schedule, aircraft, demand or retained history. The earlier fixture was
temporary; rebuilding reproduces full source SHA-256
`ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0` exactly.
Construction takes **595.657s**, including **586.522s natural warmup**; publication
prepare/apply are 0.051/0.217s. Warmup completes 50 events through the original
2026-10-02T03:00:00Z target; peak process working set is **640.172 MiB**.
Construction/warmup are excluded from one-day command timings.

The audited source has **75,758,607 JSON file bytes**, 42,923 Bookings and matching
itineraries, 368 dated flights, five completed flight results, 42 journals,
50 historical events, 367 pending events, 33 retained checkpoints and 128 processed
cohorts. It has one aircraft, four daily services, one published plan and ten paid
directional connections. Runtime environment remains Windows 11 build 26200,
Python 3.12.10, i5-1035G1 / eight logical processors / 8,361,132,032 bytes RAM.

Three isolated baseline one-day commands take **102.874, 97.317, 98.452s**:
median **98.452s**, range **97.317–102.874s**. All complete exactly 13 events:
four dispatches, four departures, four completions and one daily Booking checkpoint.
All match B2's full result hash
`f2639799ac18443c62a85dcab3e613e12adbb5627df2051b19a4367df66091a2`.
Output grows to 43,467 Bookings/itineraries, nine results, 47 journals,
63 historical and 363 pending events. The small event count does not describe
all internal record traversal, copying, preview/replay or proof work.

### Complete-day profile and attribution

A separate full-day cProfile plus test-only nested exclusive timers completes
with that SAME complete-world hash and event vector. Instrumented command time is
**342.229s**, not a latency sample. cProfile records **494,646,011 calls** and
343.006s; its region additionally includes the benchmark helper's result assembly
and final digest, outside the helper's command timer. Profile totals must not
be substituted for the 98.452s quiet median. Instrumentation leaves handler
identities/registrations and all copies, gates, budgets and event outcomes intact.

| Baseline instrumented region | Calls | Inclusive seconds | Exclusive seconds |
| --- | ---: | ---: | ---: |
| Complete-world validation | 15 | 180.159 | 21.404 |
| Plain authority JSON/alias/money/UTC traversal | 15 | 65.881 | 65.881 |
| Booking validation, including retained relationships | 15 | 92.304 | 17.073 |
| Detailed retained Booking relationships | 15 | 75.169 | 75.169 |
| Imported deepcopy regions, including provider isolation/witnesses | 66,057 | 105.276 | 102.340 |
| Runtime world clone regions | 27 | 37.896 | 35.862 |
| Detached event publication | 13 | 17.470 | 0.001 |
| Booking allocation preparation | 2 | 97.550 | 2.187 |
| Booking shopping preparation | 2 | 94.849 | 1.330 |
| Scheduling supply/presence lookups | 2,966 | 0.890 | 0.633 |
| Quarterly backend reconciliation | 1 | 11.313 | 0.047 |
| Handler execution and contract checks | 13 | 101.566 | 2.372 |
| Garbage collection | 4,631 | — | 5.891 |

Exclusive timer regions subtract complete instrumented children. They may be
added within that partition; inclusive rows are nested and MUST NOT be summed.
The remainder includes clock/queue/resolver/session/other uninstrumented work.
The deepcopy region count includes small descriptor/result copies, not 66,057
whole worlds. cProfile's actual recursive deepcopy count is **44,202,636**,
57.834s self / 115.783s cumulative; it uses a different attribution boundary.

Per-handler cProfile (self / cumulative seconds): quarterly dispatch four calls
0.000 / 0.020; departure four 0.000 / 1.151; completion four 0.001 / 1.215.
These bodies exclude the kernel's following full gate and detached publication,
so they are not complete event-transaction latencies. Booking prepare/process
run once each: 0.001 / 51.239 and 0.087 / 47.921, including their nested copies
and derivations. Preview and fresh commit replay each call allocation/shopping.
Identifiable finance settlement construction runs four times, 0.000 / 0.020s;
Booking journal staging is integrated into process_daily_booking_checkpoint and
is not claimed as a separately isolated complete finance subtotal.

Fifteen complete validations are entry + thirteen strict quarterly events + final
clock-gap gate. Twenty-seven runtime clones include their candidate/commit copies
and the existing Booking preparation clone. Request startup also performs backend and
publication reconciliation once, with their existing detached source copies.
No gate is classified as redundant merely because its inputs look unchanged.

Ranked remaining costs are current full-world predicates and copying; Booking's
allocation equations and Scheduling lookups are small exclusive fractions.
Validation/copy cost depends on retained graph size and transaction count, not
only fleet or event count. This source's 42,923 retained relationships are visited
again at each of fifteen gates. Published-flight validation runs 5,520 times
(368 × 15); complete published chronology and mode checks also remain.
Checkpoint/event topology includes C × E scans; overall relationships are not
Booking × itinerary Cartesian scans. No aircraft-count scaling claim follows
from this one-aircraft profile.

### One retained candidate and contract audit

B2 explicitly sends any quarterly flight to the detailed Booking suffix, leaving
the already approved exact call-local E.2 relationship proof unused. Extend that
existing proof to explicit quarterly mode, rather than add a cache or another
Booking writer. World State owns both predicates. The caller still requires this
invocation's completed plain authority/alias proof and clean structure/checkpoint
prefix. Exact quarterly itinerary fields, null legacy schedule lineage and all six
publication-lineage values are compared with current dated-flight facts.

Every itinerary, Booking, owner, inventory revision/capacity equation, result ID,
passenger total, paid journal and source coverage is checked. Distinct flight facts
are reconstructed only within this synchronous call; flat scalar rows never escape
it. No world identity, revision, session epoch or retained immutable segment acts
as a validity token. Deep mutations are observed on the next call. Full published
flight, fixed-fare/date-horizon, operations, chronology and mode gates still run.
Unsupported or malformed facts return to the UNCHANGED ordered detailed suffix.
Legacy mode continues its existing graph eligibility and diagnostics.

A: all mandatory gates retained; no cross-gate validation reuse.
B: all candidate/commit and provider-isolation copies retained; the rejected B2
copy substitution is not revived.
C: existing Booking scalar relationship proof reused; no published-supply or
inventory authority changed.
D: every retained record still checked; no immutable-history exemption or
load-time corruption bypass.
E: queue ordering, dispatch/reconciliation, chronology, callback ownership and
all request/causal budgets unchanged.

Differential lineage tests preserve the predecessor's existing True == 1 value
equality in itinerary revision/slot comparisons; no stricter validation policy
is introduced incidentally. Published flight lineage still has its original
strict type checks. Stronger itinerary type enforcement would be a separate
correctness scope, not an unexplained optimization difference.

### Optimized measurement and verification

Three isolated optimized runs take **92.598, 91.669, 88.660s**: median
**91.669s**, range **88.660–92.598s**. Against the contemporaneous 98.452s
baseline this is **1.074× / 6.89% less command time**. B2's earlier 94.819s
is historical host variation, not the paired baseline for this new change.
All six quiet runs have identical complete-world hashes and 13-event vectors;
no envelope roots, history, journals, inventory, IDs, RNG or UI fields are excluded.

Peak working-set maxima are **1,085.203 → 1,085.754 MiB**, a 0.551-MiB / 0.05%
difference, effectively unchanged. Three-sample baseline peaks are
1,084.289/1,084.637/1,085.203 MiB; final 1,084.199/1,085.754/1,085.754 MiB.
Each process's peak is cumulative; this is not a per-graph allocation delta or
long-run memory leak certification. The bounded current-data proof is retained:
measurable time improvement without the substantial B2 copy-prototype memory penalty.

Final focused command:
`python -B -m unittest tests.test_quarterly_booking_validation tests.test_booking_lineage_optimization -v`
passes **35 tests in 75.960s**, exit 0. The first run's two overly strict new
True/1 expectations were corrected after both predicates agreed; that matrix alone
then passed in 10.762s before the final 35-test run. No production rejection policy
was changed. Final source is frozen at **329 Python SHA-256 witnesses**.

The optimized full-day diagnostic completes in **258.176s** command time,
258.877s cProfile region, with **405,546,091 calls**, the same complete world and
13-event vector. Profiler overhead is reduced by the changed call structure;
this is NOT a claimed 24.6% quiet speedup. Identical structural counters remain:
15 full gates, 27 runtime clones, 13 detached event commits, 66,057 imported
copy regions, 44,202,636 recursive deepcopy calls, two allocation/shopping
preparations, 2,966 schedule lookups and 4,631 GC observations. No guard/copy
or simulation work was removed.

| Optimized instrumented region | Calls | Inclusive seconds | Exclusive seconds |
| --- | ---: | ---: | ---: |
| Complete-world validation | 15 | 115.156 | 19.523 |
| Plain authority traversal | 15 | 58.485 | 58.485 |
| Booking validation | 15 | 36.369 | 15.053 |
| Current-data relationship graph proof | 15 | 21.316 | 21.316 |
| Imported deepcopy regions | 66,057 | 96.409 | 93.518 |
| Runtime world clone regions | 27 | 29.598 | 28.135 |
| Detached event publication | 13 | 13.852 | 0.001 |
| Booking allocation preparation | 2 | 89.645 | 2.178 |
| Booking shopping preparation | 2 | 86.974 | 1.176 |
| Scheduling supply/presence | 2,966 | 0.796 | 0.569 |
| Backend reconciliation | 1 | 10.149 | 0.037 |
| Handler/contract work | 13 | 93.135 | 2.113 |
| Garbage collection | 4,631 | — | 5.410 |

The old detailed suffix is not invoked on these valid inputs. cProfile's graph
passes (self / cumulative seconds) are itinerary 6.268/9.566, Booking ownership/
inventory 4.201/7.261 and result/journal coverage 1.862/4.264. Other pure graph
predicates and current-record checks remain. The same partition shows copying
is still about 121.653 exclusive diagnostic seconds; complete validation is
115.156 inclusive. Unchanged regions vary between runs, so the paired quiet
measurements, not individual unmodified-region deltas, establish speedup.

Finance settlement construction remains four calls, 0.000/0.017s; departure
four 0.000/1.047s; completion four 0.001/1.061s; dispatch four 0.000/0.011s.
There is no gameplay serialization inside the Advance command. The diagnostic
captures 18,903 json.dumps calls, 0.037s self / 1.706s cumulative: deterministic
fingerprints and the helper's final result digest, not disk-save latency.
Save/load is exercised for correctness; B2.1 does not claim a fresh save/load
performance improvement. Profile peaks 1,084.254/1,085.527 MiB are comparable
in magnitude to the quiet runs, not allocation-only measurements.

A smaller synthetic validation-only control varies the inseparable Booking /
itinerary / linked-result-ID counts by splitting unflown aggregate batches with
existing test tooling. This does NOT change the main audited operating fixture.
All three valid controls retain **2,996 passengers, 29,960,000 accepted fare minor
units**, one aircraft, 180 dated flights, zero results, one journal, two history
events and 184 pending events. Aircraft, published schedule, capacity/inventory,
passenger demand, account balances, checkpoint outcomes and operational chronology
remain fixed. Fresh IDs/cursors and their exact linked source-ID lists necessarily
grow with the two coupled record counts. No historical manifest is rewritten.

| Booking/itinerary count | Detailed reference full validation median [range], seconds | Optimized full validation median [range], seconds |
| ---: | --- | --- |
| 1,185 | 0.116 [0.114–0.128] | 0.108 [0.103–0.111] |
| 1,896 | 0.144 [0.142–0.150] | 0.133 [0.122–0.140] |
| 2,436 | 0.169 [0.160–0.179] | 0.152 [0.140–0.162] |

Each row alternates three reference and three optimized validations on the exact
same source and checks its complete hash remains unchanged. From 1,185 to 2,436
linked records, full validation medians grow about 1.45× reference / 1.40× optimized
for 2.06× record count; fixed structural/flight work remains. These few small
points do not prove a general asymptotic exponent, isolate aircraft scaling or
certify retained-operation/50-aircraft capacity.

Affected command:
`python -B -m unittest tests.test_quarterly_backend tests.test_quarterly_boundaries tests.test_quarterly_gui.QuarterlyKivyTests tests.test_route_establishment.RouteKivyTests -v`
passes **97 tests in 297.460s**, exit 0, including **eight native Windows Kivy
cases** for quarterly planning/publication controls and normal paid-route purchase.
Python 3.12.10 / Kivy 2.3.1 / SDL2 / Intel UHD Graphics / OpenGL 4.6 remain the
observed environment. These are actual native regression cases, not a separate
manual visual survey or large-fleet GUI capacity certificate.

Scoped compilation `python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
passes, exit 0. Profiler `--root Saves` rejects with expected exit 2 before access.
Real Saves, protected local metadata, `.venv/` and stashes remain untouched.

Final `.venv/Scripts/python.exe -B -m unittest discover -s tests -v` passes
**1,628 tests in 2,384.109s**, exit 0. All **329 source witnesses** remain unchanged
through performance and full verification. Stage 3A–3G-A, quarterly/legacy isolation,
Booking/finance/history, publication fences/retries, save/load and event/runtime
safety regressions all pass. Final exact seven-file scope, whitespace and three
changed Markdown documents' **280 local links / 65 heading targets** pass.
Generated fixtures, profiles, logs and runtime artifacts are excluded from commits.
Actual commit/push synchronization is reported at completion, not invented here.

### Legitimate work limit versus runaway and continuation

The default processed/stale ceiling is 10,000 per REQUEST. A finite queue of
10,001 already scheduled NO_OP events (no generated children) stops after exactly
10,000 commits with EVENT_LIMIT_REACHED; the final event remains pending at the
same UTC, and current_utc_fully_resolved is false. Explicit new resolution finishes
that event in its original order. This is a synthetic safety test, not airline
capacity evidence. Default same-UTC generated-child accounting remains 100;
advancing chronology resets only that causal counter, not processed work.

A quarterly two-event budget stop also preserves exact validated authority through
real SaveStore save/load; a separately explicit retry to the unchanged target matches
an uninterrupted strict control, including Bookings, finance, history and identities.
An additional inline `.venv/Scripts/python.exe -B -` diagnostic exercises the
actual Stage1Session begin_advance_to/advance_tick/save_manual/load_saved APIs.
With a lowered test-only two-event budget, five events remain pending; saved
prefix hash is `fe4d2a14fbd4f8cdb5d010b89dc2b36cf698134a31ce6970f0868e0531e59d37`.
An explicitly new Advance to the original 2027-01-02T15:00:00Z target after Load
completes and matches the uninterrupted full-world control hash
`032fecfc122cfc3830acbbbcf900182d14787e4fc7c40b3b37957a21ba0610f7`.
This smaller backend test fixture is separate from the primary performance
fixture. No production constant, source file or automatic retry path changes.

A suspended iterator/yield keeps its existing counters. A closed/terminal request
or restored save does not contain the iterator; explicit continuation creates a
new request under the existing boundary contract. No API or budget change is needed
for that explicit retry. Automatic transparent partitioning, durable fixed-entitlement
counter/target recovery or a new resume UI is not implemented or authorized here.
A runaway same-UTC generator remains distinct and blocked under existing tests.

At four sectors/aircraft/day, 50 aircraft require at least 400 departure/completion
events/day; 30/45/90-day single requests exceed 10,000 before dispatch/Booking work.
This is legitimate density, not proof of recursion or a wall-time bottleneck.
Faster execution cannot change that bound. B3 may reuse the explicit command API,
but any automatic bounded workflow needs its own authority/design decision and
must not silently renew an exhausted request.

### Exact B2.1 changed-file scope

- [World State relationship proof](../../game/world_state/booking_lineage_validation.py).
- [World State Booking proof eligibility](../../game/world_state/booking_validation.py).
- [Opt-in profiling/scaling tool](../../tests/profile_quarterly_advancement.py).
- [Differential and recovery tests](../../tests/test_quarterly_booking_validation.py).
- [This performance report](Quarterly%20Runtime%20Benchmarking.md).
- [Current Development Status](Current%20Development%20Status.md).
- [Decision Register](Decision%20Register.md), AT-058 evidence only; policy unchanged.

### Reproduction and B3 recommendation

[Test-only profiler](../../tests/profile_quarterly_advancement.py) consumes the
unchanged audited fixture from [the B2 harness](../../tests/benchmark_quarterly_runtime.py).
[Quarterly proof tests](../../tests/test_quarterly_booking_validation.py) compare
complete validation results, exact exceptions and source immutability with the
retained predecessor path, and cover strict/shared/SaveStore/retry equivalence.
Commands use the project virtual environment, caller-owned temporary outputs and
no real Saves; profiling is separate from quiet latency controls:

```text
python -B -m tests.benchmark_quarterly_runtime --root <temporary> --build --fleets 1 --setup-budget 900
python -B -m tests.profile_quarterly_advancement --root <temporary> --label baseline-day --repeats 3
python -B -m tests.profile_quarterly_advancement --root <temporary> --label baseline-profile --repeats 1 --instrument --cprofile
python -B -m tests.profile_quarterly_advancement --root <temporary> --label optimized-day --repeats 3
python -B -m tests.profile_quarterly_advancement --root <temporary> --validation-study --repeats 3
```

B2.1 does not certify representative 50-aircraft 7/45/90-day targets, normal 90×
continuous performance, offline recovery or default activation. Next investigate
remaining measured copying/whole-graph predicates on fixed operating fixtures;
any change to certified ownership, validation exemptions or copy architecture
requires a separate bounded contract decision. AT-058 B3 provenance, paused-close,
branch/cancellation/versioning and legacy rollout decisions remain open. B3/C need
separate authorization; no future behavior starts in this slice.

---


Bounded implementation and measurement, 2026-10-12. Approved baseline
`916caff51774d78d1b711d9afb54de4b3f82b9ae` matched HEAD, upstream, freshly fetched
origin/master and live remote master. Tracked tree/index were clean; `.venv/`,
local metadata and the empty stash list were preserved. Serena navigation and
repository contracts governed inspection; memories remain subordinate aids.

Authority: [AT-058 contract](Single%20Speed%2C%20Advancement%20%26%20Offline%20Progression.md),
[Schema 9](Stage%201%20State%20Schema.md),
[quarterly consumers](Quarterly%20Backend%20Consumer%20Cutover.md),
[publication](Quarterly%20Shared%20Publication.md),
[failure recovery](Quarterly%20Boundary%20Orchestration.md),
[event budgets](Runtime%20Causal%20Generation%20Accounting.md),
[save safety](Game%20State%20%26%20Save%20Technical%20Specification.md), and
[current status](Current%20Development%20Status.md).

## Environment and reproducible protocol

Windows 11 build 26200, Python 3.12.10; Intel Core i5-1035G1 @1.00GHz,
8 logical processors, 8,361,132,032 bytes physical RAM. Hardware differs from the
historical i5-10400/12-thread Ultra certification machine. Results are host-specific.
Native verification uses Kivy 2.3.1 / SDL2 / Intel UHD Graphics, OpenGL 4.6
(build 26.20.100.7926), as observed in the native regression logs.

[benchmark_quarterly_runtime.py](../../tests/benchmark_quarterly_runtime.py) is an
opt-in measurement harness, not a gameplay pathway. Temporary artifacts are excluded
from commits and real `Saves` is rejected as an output root. It uses the existing
Stage1Session begin/step/cancel APIs, unchanged handlers, strict/shared resolver and
full validation. No event is skipped, budget reset, consumer disabled or financial
outcome estimated. Cancellation happens only between completed transactions; an
individual transaction can overrun a wall-time budget. All such overruns are reported.
Reaching the target UTC alone is insufficient: completed status also requires the
engine's successful terminal result. Same-UTC pending work can remain at a budget stop.

Setup and actual advancement are distinct measurements. Early setup runs overlapped
baseline regression/other fixture setup and are diagnostic elapsed costs, not isolated
capacity measurements. cProfile measurements are diagnostics with profiling overhead
and are not substituted for latency samples. Repeated component/operating measurements
report median and range; incomplete samples are never extrapolated into completion
times or reported as passing targets. Peak process working set is cumulative within
each process, not a per-operation allocation delta.

```text
python -B -m tests.benchmark_quarterly_runtime --root <temporary directory> --build --fleets 1 --setup-budget 900
python -B -m tests.benchmark_quarterly_runtime --root <same directory> --build --fleets 10 25 50 --setup-budget 180
python -B -m tests.benchmark_quarterly_runtime --root <same directory> --components --repeats 3
python -B -m tests.benchmark_quarterly_runtime --root <same directory> --label baseline --repeats 3 --budget 30
```

## Fixture specification and setup limits

Fleet sizes 1/10/25/50 use the real PH scenario with 43 airports/1,806 directional
markets, creation UTC 2026-08-31T00:00:00Z, MNL Operating Base, configured owned
A320neo aircraft and explicitly declared test-only funding of 10^14 cash minor units.
Additional aircraft use real purchase commands. Five MNL airport pairs (DVO, CEB,
ILO, BCD, PPS) use paid atomic route commands and real expense/cash journals.

Each aircraft operates two daily return cycles, four passenger sectors/day, with
09:00/15:00 origin-local outbound starts staggered two minutes per aircraft. Domain
WeeklyDraft return/timing calculation and authoritative suggested fares produce legs.
The owning World State constructors build one private complete draft revision using
allocated service/slot identities and retained timing snapshots. This avoids hundreds
of GUI editing calls during setup; it does not bypass publication feasibility or
operational chronology. Validate the private draft, then invoke actual manual
prepare/apply for the legally eligible 2026-Q4 target, retaining four gates/two copies.
No current-quarter initial operating exception or forged publication timestamp is used.

Warmup naturally resolves through 2026-10-02T03:00:00Z. It includes September's
automatic committed skip, progressive daily directional demand, real sales/inventory,
and October operations/results/finance. Demand economics and the 365-day preference
window remain unchanged. A ready fixture must have positive Booking and completed
flight results, pass full validation, and carry a stable audit hash. Incomplete warmups
are identified separately and cannot stand in for operating-career benchmarks.

| Fleet / warmup budget | Elapsed warmup | Reached UTC | Completed events | Outcome |
| --- | ---: | --- | ---: | --- |
| 1 / 180s initial probe | 188.175s | 2026-09-21 00:00Z | 23 | Incomplete; 21 Booking checkpoints, no operational start yet |
| 1 / 600s extended probe | 625.958s | 2026-10-02 00:00Z | 47 | Incomplete target; 32 Booking checkpoints, 4 dispatches/departures/completions and real finance |
| 10 / 180s | 181.371s | 2026-09-07 00:00Z | 9 | Incomplete; 7 Booking checkpoints |
| 25 / 180s | 194.858s | 2026-09-05 00:00Z | 7 | Incomplete; 5 Booking checkpoints |
| 50 / 180s | 240.929s | 2026-09-04 00:00Z | 6 | Incomplete; 4 Booking checkpoints; single transaction exceeded budget |

Ten/25/50 setup totals, excluding no required setup work, were respectively
189.980/207.101/265.317s. These are one-run contended construction diagnostics,
not medians or per-game-day performance. The 600-second one-aircraft setup total
was 629.758s. Warmup process peaks were 637.609 MiB for that one-aircraft probe
and 529.668 MiB by the last large-fleet probe. Larger ready operating fixtures
were not fabricated after their construction budget was exhausted.

The final one-aircraft 900-second setup attempt completed: **811.238s total
construction, 798.992s natural warmup**, with 50 events through the requested
03:00Z boundary. It overlaps full regression work and is not an isolated throughput
claim. Full validation passes. The frozen operating fixture has **42,923 Bookings,
42,923 itineraries, 368 sold/materialized occurrences, five completed flights,
42 journals, 50 historical and 367 pending events**, four daily service frequencies
and ten paid directional connections. Source SHA-256:
`ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0`.
This is naturally filled future inventory, not eager publication materialization.
Warmup peak was **650.703 MiB**. Only this fleet is a ready operating fixture;
10/25/50 results remain incomplete and cannot supply qualifying advancement timings.

## Historical comparability

The [375.151-second result](Runtime%20Capacity%20Certification.md) measured baseline
`ebdfc1239cb88f2ccd12a481033f1ba236588b04`, legacy rolling-four-week scheduling,
50 A320neo aircraft, four sectors/aircraft/day, five domestic destinations, real
Booking/history/finance, and an aged mixed-phase source at 2026-09-02T03:00:00Z.
It used the production explicit session facade on the i5-10400 machine.

Its test harness remains available and documents reproduction. This B2 fixture
matches fleet/model/network frequency density where possible, but changes hardware,
calendar start, publication coverage, Booking supply/provider and operational consumer
implementation. Full-quarter future supply permits different advance sales/history;
quarterly dispatch and strict quarterly flight validation also add work. The older
legacy certification was Schema 7; current authority is Schema 9. No controlled
equivalent legacy-versus-quarterly throughput comparison was completed here.
The historical and current numbers are **not directly comparable**, and no speedup
is attributed solely to quarterly scheduling. The old Ultra gate remains superseded;
its measured result is not rewritten.

Quarterly architecture avoids eager unsold dated-row expansion and persists stable
weekly service authority with lazy operational materialization. Its additional costs
include exact published lineage, dispatch reconciliation, full published chronology
and mandatory publication preparation/fences. These architectural observations are
not a quantitative claim that total runtime is faster.

## Ranked diagnostic bottlenecks

cProfile of unchanged real initial quarterly Booking execution recorded 28,400,446
calls (24,958,503 primitive) in 29.899 profiler seconds. The 30-second request stopped
at a committed prefix at 2026-09-02 00:00Z with four events: one publication skip,
two Booking checkpoints and one marketplace rotation. It was not a completed two-day
operating benchmark. The instrumentation leaves handler identities intact.

| Path | Calls | Cumulative profiler seconds |
| --- | ---: | ---: |
| Booking allocation preparation | 4 | 21.466 |
| Deep copying (all recursive calls) | 3,256,743 | 16.576 |
| Booking shopping preparation | 4 | 16.738 |
| Active market discovery | 4 | 9.961 |
| Full-world validation | 9 | 6.366 |
| Published flight projection | 7,480 | 2.323 |
| Explicit-date supply lookup | 7,798 | 2.079 |
| Local departure conversion | 14,212 | 0.669 |
| Planned interval projection | 7,480 | 0.549 |
| Quarterly dispatch reconciliation | 1 | 0.020 |

Rows are nested and **must not be summed**. Deepcopy alone accounts for 8.073s
exclusive work; dictionary copying 2.499s exclusive and plain authority-tree validation
1.140s exclusive are also prominent. Allocation prepares an accepted preview and
fresh commit replay; activation provider isolation makes detached inputs and mutation
comparison snapshots. These safeguards are not treated as dispensable redundancy.
The initial profile does not establish long-history/50-aircraft cost fractions.

An aged-source cProfile, separate from the latency samples, stops after one
QuarterlyDispatch in 45.740s of instrumented command time. Initial quarterly
reconciliation accumulates 21.967 profiler seconds; deepcopy 21.954s; two full
validations 21.479s; detailed Booking relationships 8.743s. These nested values
must not be summed or treated as per-day timings. The large-history source makes
reconciliation copying and complete graph validation prominent, unlike the small
initial-demand profile. Those remaining costs are not eliminated by this slice.

## Existing indexes and cache choice

Scheduling's maintained QuarterlyDependencyIndex/owner tracks identity, membership,
aircraft closure and freshness for commands. Session owned-read epochs and bounded
detached page caches are already available. QuarterlySupply builds call-local market,
aircraft and service/slot lookups plus dated aliases. QuarterlyShoppingIndexes uses
lazy per-market/date entries and a 366-date publication-presence probe, independent
of inventory authority. Pinned timezone loading is already cached.

Select **A: existing lazy resolution**, retaining its existing bounded per-command
date lookup, rather than introducing a new cross-event cache. B (additional date
indexing) overlaps existing shopping indexes; C (rolling prepared horizon) and D
(full-quarter preparation) add eager work and retained memory without demonstrated
end-to-end benefit. The component horizon measurements below evaluate derived
preparation cost only, not a new authority or implementation. No 30-day window is
imposed, no occurrence table is persisted, and supply beyond a cache remains
discoverable through the original published authority up to the approved horizon.

No new cross-event cache, preparation window or authoritative inventory is added.
Existing publication, reassignment, fare, retirement, route lifecycle, load/rebind
and reconstruction tests remain required. Immutable planned descriptors remain
separate from dynamic remaining inventory, actual location/readiness, delays, cash
and outcomes. Every provider invocation observes fresh input through all retained
isolation copies and mutation checks; there is no new cache invalidation protocol.

## Implemented derived-owner lifetime improvement

Scheduling owns the published-market presence scan. Factor the existing 366-date
lazy scan into a local function. QuarterlyActivationProvider uses QuarterlySupply
plus that same scan directly; actual QuarterlyShoppingIndexes reuses the scan and
retains its shopping/date indexes. Activation no longer constructs an unused shopping
owner with an owner/lookup reference cycle. Published/retired/connection/date/horizon
filters and sorted market IDs are unchanged. No new cache or persisted field exists.

A weak-reference diagnostic with cyclic GC disabled found one activation-only shopping
owner retained until explicit collection in the baseline. The final provider constructs
zero shopping owners and releases its temporary supply without waiting for cyclic GC.
Production garbage-collection policy is unchanged. Four focused tests cover presence
agreement, lifetime, fresh retirement/unpublished facts and exact complete-world/
ProcessingResult agreement with original activation across strict/shared caps 1/2/8.

## Rejected copy prototype and memory tradeoff

Profiling also motivated a prototype reusing World State's existing internal clone at
quarterly provider input/mutation-snapshot sites. Every copy/check remained, and the
prototype produced the exact same complete-world hash and 13-event one-day workload.
The preliminary two-file prototype reduced median day time from 100.038 to 88.224s,
but peak memory rose from 1,077.180 to 1,482.348 MiB. Adding the presence refactor gave
median 87.488s (86.334–88.298), yet peak memory still reached 1,489.387 MiB, about 38%
above baseline. Faster copying did not establish an acceptable memory tradeoff on
this 8-GB host with already-incomplete large-fleet preparation.

The copy substitution is **rejected and reverted**, including its private flags and
imports. Booking shopping and Demand activation are restored byte-for-byte to the
baseline. Their existing provider-isolation copies, mutation detection, output
checks and public/legacy behavior remain. Only the Scheduling presence/lifetime
refactor is retained. The passing exploratory clone tests (56 combined, then seven
focused) and prototype timings are superseded evidence, not final source certification.
No new serialization algorithm, trusted-provider boundary or save codec is introduced.
Required full-world gates, all copies, published chronology and event budgets remain.

## Long-duration safety-budget constraint

Four sectors per aircraft/day at 50 aircraft means 200 sectors/day. Each executed
sector requires departure and completion, at least 400 processed events/day before
quarterly dispatch, Booking, finance/publication lifecycle or stale work. Thus 30 days
requires at least 12,000 processed events, 45 days at least 18,000, and 90 days at
least 36,000. These lower bounds exceed the unchanged 10,000-event request ceiling.
At 25 aircraft, 90 days also exceeds it (at least 18,000). This is a workload/count
constraint, not an inferred wall-time measurement or a reason to alter demand.

The normal/explicit same-time generation budgets remain 100/10,000 as previously
configured; request-wide processed/stale work remains 10,000. A truthful long-duration
request must return its successful committed prefix and explicit limit diagnostic
where reached. B2 does not silently partition/retry to complete a target or raise
budgets. Additional quarterly dispatch means the actual limit can occur earlier than
the departure/completion-only lower bound. Seven days at 50 aircraft is not excluded
by this lower bound, but its runtime objective still needs a qualifying measurement.
B3 recovery must preserve the fixed entitlement/target and explicit stop/retry
semantics rather than treating save/reopen as an automatic budget renewal.

## Completed one-day before/after evidence

Three isolated samples use the exact same validated 42,923-Booking source, excluding
construction/hydration from the timed session command. Baseline median **100.038s**
(range **98.951–100.843**) becomes **94.819s** (range **93.302–95.256**) with the
retained presence-only change: **1.055×**, approximately **5.22% less wall time**.
This modest result is host/workload-specific and is not a 50-aircraft capacity claim.

Every sample completes all **13 events**: four dispatches, four departures, four
completions and one daily Booking checkpoint. All six complete-world hashes agree:
`f2639799ac18443c62a85dcab3e613e12adbb5627df2051b19a4367df66091a2`.
No world root, UI root, financial field, history or deterministic cursor is excluded.
Request budgets and every mandatory transaction are retained.

Peak working-set maxima in the separate three-sample processes are baseline
**1,077.180 MiB**, final **1,077.145 MiB**; effectively unchanged, not a material
memory-reduction claim. The specific activation owner/lookup cycle is eliminated;
actual shopping indexes and overall retained-history costs remain. Faster clone
prototypes with about 38% higher peak memory were rejected, not hidden in the final
before/after comparison.

## Censored targets, save/load and component measurements

The separate one-day completion samples above use a 180-second budget. The following
grid uses 30-second budgets and fresh copies of the same source. Every row stops
at the same five-event prefix at 2026-10-02T07:00:00Z, preserving hash
`5e8fe812092438d3f21fd95778d536508d2791c887fd6f13253bd034a4c9e36f`.
These are censored prefix costs, not completed-day timings or long-horizon speedups.

| Target days | Baseline median [range], seconds | Final median [range], seconds | Status |
| --- | --- | --- | --- |
| 1 | 32.683 [31.572–34.252] | 31.007 [30.898–31.874] | INCOMPLETE_BUDGET; 5 events |
| 7 | 32.631 [31.251–32.733] | 32.965 [32.043–34.524] | INCOMPLETE_BUDGET; 5 events |
| 30 | 32.913 [32.414–32.995] | 34.398 [32.067–34.652] | INCOMPLETE_BUDGET; 5 events |
| 45 | 31.446 [31.193–32.757] | 32.809 [31.869–33.891] | INCOMPLETE_BUDGET; 5 events |
| 90 | 32.619 [31.500–33.978] | 33.066 [31.927–35.027] | INCOMPLETE_BUDGET; 5 events |

For fleets 10/25/50, all 1/7/30/45/90-day operating measurements are unavailable
because warmup did not produce ready operating fixtures. No empty/preparatory
source was substituted; no completion time or speedup is extrapolated.

| Operation, ready 1-aircraft source | Baseline median [range] | Final median [range] | Baseline/final median ratio |
| --- | --- | --- | --- |
| Save | 11.311 [11.209–11.402] | 12.343 [11.907–12.730] | 0.916× |
| Load | 9.604 [9.340–11.057] | 9.704 [9.601–9.706] | 0.990× |
| 4-offer occurrence lookup (ms) | 1.430 [1.405–1.602] | 1.378 [1.229–1.769] | 1.038× |

Save/load values are seconds; lookup values are milliseconds. All six SaveStore
round trips reproduce the full audited source hash and restore paused. These paths
are unchanged by the presence refactor: save shows a roughly 9% measured slowdown,
load/lookup differences are small, and no causal improvement is attributed to them.

| Fleet, preparatory source only | Baseline prepare/apply median, seconds | Final prepare/apply median, seconds | Final 90-date preparation median [range], seconds / rows |
| --- | --- | --- | --- |
| 1 | 0.054 / 0.322 | 0.060 / 0.282 | 0.095 [0.085–0.098] / 360 |
| 10 | 0.066 / 0.846 | 0.067 / 0.840 | 0.934 [0.911–0.945] / 3600 |
| 25 | 0.099 / 1.732 | 0.098 / 1.776 | 2.761 [2.653–2.764] / 9000 |
| 50 | 0.167 / 3.458 | 0.175 / 3.522 | 6.715 [6.412–6.887] / 18000 |

Each preparatory publication group repeats three times and produces identical
complete-world hashes. These sources have paid routes and genuine published services,
but no aged operating history; they cannot certify 50-aircraft gameplay throughput.
The 1/7/30/90-date preparation probes return respectively 4N/28N/120N/360N offers
for N aircraft and record peak process working set. They measure eager preparation
cost, not a newly implemented cache. Ninety dates are a probe window, not Q4’s
calendar length (92 days); full-quarter strategy D is not separately certified.
A full derived preparation range adds work/memory without a demonstrated operational
benefit over existing lazy date lookups. Publication transaction code is unchanged.

Additional repeated component details (seconds, median [range]); these remain
preparatory measurements, not operational capacity:

| Version / fleet | Prepare | Apply | Reconciliation | Peak process MiB |
| --- | --- | --- | --- | ---: |
| Baseline / 1 | 0.054 [0.052–0.065] | 0.322 [0.268–0.411] | 0.001 [0.001–0.008] | 34.836 |
| Baseline / 10 | 0.066 [0.057–0.075] | 0.846 [0.837–0.919] | 0.005 [0.005–0.007] | 36.863 |
| Baseline / 25 | 0.099 [0.091–0.107] | 1.732 [1.717–1.942] | 0.014 [0.013–0.015] | 40.246 |
| Baseline / 50 | 0.167 [0.152–0.167] | 3.458 [3.298–3.967] | 0.037 [0.034–0.103] | 50.180 |
| Final / 1 | 0.060 [0.046–0.081] | 0.282 [0.238–0.296] | 0.001 [0.001–0.009] | 34.785 |
| Final / 10 | 0.067 [0.062–0.082] | 0.840 [0.828–0.944] | 0.007 [0.005–0.011] | 36.957 |
| Final / 25 | 0.098 [0.098–0.105] | 1.776 [1.714–2.005] | 0.014 [0.013–0.024] | 40.543 |
| Final / 50 | 0.175 [0.158–0.180] | 3.522 [3.519–3.703] | 0.036 [0.035–0.042] | 50.098 |

| Version / fleet | 1-date preparation | 7-date preparation | 30-date preparation | 90-date preparation |
| --- | --- | --- | --- | --- |
| Baseline / 1 | 0.002 [0.001–0.051] | 0.010 [0.009–0.012] | 0.044 [0.041–0.052] | 0.126 [0.125–0.150] |
| Baseline / 10 | 0.011 [0.010–0.011] | 0.075 [0.065–0.075] | 0.312 [0.290–0.335] | 0.943 [0.938–0.965] |
| Baseline / 25 | 0.026 [0.026–0.031] | 0.207 [0.187–0.214] | 0.888 [0.876–0.905] | 2.708 [2.685–2.721] |
| Baseline / 50 | 0.119 [0.098–0.136] | 0.639 [0.631–0.653] | 2.220 [2.135–2.386] | 6.508 [6.458–6.610] |
| Final / 1 | 0.002 [0.001–0.041] | 0.006 [0.006–0.007] | 0.030 [0.030–0.032] | 0.095 [0.085–0.098] |
| Final / 10 | 0.011 [0.011–0.011] | 0.077 [0.073–0.079] | 0.311 [0.300–0.335] | 0.934 [0.911–0.945] |
| Final / 25 | 0.031 [0.026–0.033] | 0.210 [0.210–0.216] | 0.947 [0.891–1.037] | 2.761 [2.653–2.764] |
| Final / 50 | 0.076 [0.066–0.104] | 0.591 [0.568–0.610] | 2.361 [2.137–2.408] | 6.715 [6.412–6.887] |

Booking/flight workload is explicit in completed one-day samples: one real daily
Booking checkpoint and twelve dispatch/departure/completion events. The earlier
two-checkpoint cProfile gives Booking call-path duration/workload; it is not an
isolated repeated per-handler latency measurement. Per-handler operational timing
at large fleet sizes remains unavailable, alongside their incomplete setup.

## Verification scope

Baseline full discovery passed 1,612 tests in 2,746.015s with 326 unchanged Python
SHA-256 witnesses. Final focused presence tests pass four cases in 14.628s.
Final source is frozen at 327 Python witnesses, including both opt-in benchmark and
new presence tests; final full discovery passes **1,616 tests in 2,586.643s**, exit 0.
All 327 source witnesses remain unchanged throughout final verification. Native
Windows Kivy quarterly controls and the normal paid-route purchase workflow pass
in full discovery; no separate manual visual or large-fleet GUI certification is claimed.
Scoped application compilation
passes for `app game tests main.py make_snapshot.py settings.py test.py`, excluding
protected runtime/metadata directories. Final documentation links, heading targets,
exact seven-file scope and whitespace are checked before commit. The full command
was `python -B -m unittest discover -s tests -v`; focused verification was
`python -B -m unittest tests.test_quarterly_activation_presence -v`.

## B3 readiness and limitations

AT-058 remains the product contract. Offline progression, single-speed controls,
default quarterly activation and congestion are not implemented. B3 provenance,
paused-close/branch/cancellation/versioning and legacy-rollout decisions remain open
as listed there. B2 does not certify 90× live performance or near-instant catch-up.

The representative 50-aircraft 7/45/90-day objectives are not demonstrated; qualifying measurements are unavailable
where warmup remained incomplete. No passing or fabricated target result is claimed.
Prioritize Booking preparation/isolation and retained-history validation cost on fixed
real operating fixtures before adding schedule caches. Report measured alternatives
and seek bounded architecture approval if a proposed change alters ownership or
validation semantics. B3 can proceed only under its separate design/implementation
authorization; combined C activation still needs representative performance,
deterministic advancement and durable recovery certification.


## Exact changed-file scope

Historical **Stage 3G-B2** file scope follows; B2.1 scope is listed above.

- [Scheduling presence/index ownership](../../game/scheduling/quarterly_supply.py).
- [Focused presence and lifecycle tests](../../tests/test_quarterly_activation_presence.py).
- [Opt-in benchmark harness](../../tests/benchmark_quarterly_runtime.py).
- [This performance report](Quarterly%20Runtime%20Benchmarking.md).
- [Current Development Status](Current%20Development%20Status.md).
- [Decision Register](Decision%20Register.md), evidence link only; AT-058 policy unchanged.
- [Documentation index](../README.md).
