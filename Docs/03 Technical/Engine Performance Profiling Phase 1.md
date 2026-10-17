# Engine Performance Profiling — Phase 1

Measured 2026-10-16 against `120aa5f5c8d1047750cd29f4c14a5212231945de`.
Profiling only: production, Data, schema, templates and existing harnesses are
unchanged. No optimization, commit or push. Phase 2 awaits user approval.

## Plan and measurement boundaries

Reuse the exact operating source from the [90-day baseline](90-Day%20Quarterly%20Catch-Up%20Baseline.md),
starting with a short window. Run fresh processes sequentially: uninstrumented
shared-entry baseline, instrumented shared entry, then instrumented strict entry.
Use two explicit one-day requests for the paired runs and one day for strict.
Count events and compare complete canonical world hashes at every daily boundary.
Perform final full validation and chronology/passenger/journal audits outside
advancement timing. Measure real temporary SaveStore save and load separately.

The removable [diagnostic](../../tests/profile_engine_phase1.py) reuses existing
benchmark Session construction and constrained advancement. It times imported
aliases for runtime cloning, detached commits, whole-world versus partial
deepcopy, validation and its subchecks, Booking preparation/allocation/shopping,
Demand discovery/resolution, Booking processing, handler dispatch, reconciliation
and strict/shared resolution. It keeps handler registration identities intact.
GC callbacks measure collection time without retaining engine arguments/results.
No cProfile or tracemalloc is used; native process peak working set is available.

Inclusive time contains all descendants and GC. Exclusive time subtracts nested
**instrumented** intervals and observed GC, rather than every Python call. Thus
it includes uninstrumented descendants and is not Python self time. Allocation
contains shopping, which contains Demand resolution/discovery and provider copies.
Preparation and processing each include an allocation pass. Handler dispatch
contains those Booking operations; strict event resolution also contains validation
and copying. Detached commit contains its clone. Do not sum these nested rows.
Booking processing/persistence exclusive time is a residual including writes,
witnesses and uninstrumented helpers, not a pure row-write microbenchmark.

## Configuration and control

- Windows 10 build 19045, Python 3.12.10, existing `.venv` interpreter; no regression
  tests run concurrently with the benchmarks. Other pre-existing Python processes
  were present; OS scheduling and background activity were not controlled.
- Source: temporary archive `at058-90day-87a9e734ab0f45e2abd1bdceb7242678`,
  `operating-source-1.json`, 75,758,607 bytes. Validated canonical SHA-256:
  `ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0`.
- Exact source recipe remains in the linked baseline: PH scenario, seed 17012026,
  reference `stage1-philippines-v1-starter-grant-2026-10-02`, creation
  `2026-08-31T00:00:00Z`, MNL base, integer test capital `10**14`, five paid
  bidirectional MNL pairs DVO/CEB/ILO/BCD/PPS. One A320neo operates four daily
  passenger sectors, two return cycles. Four services, one published Q4 plan,
  42,923 Bookings/itineraries, 368 dated flights, five completed flights,
  42 transactions, 50 history and 367 pending events. Natural warmup is reused,
  not repeated or charged to these timings.
- Paired advancement: `2026-10-02T03:00:00Z` to October 3 03:00Z, then October 4
  03:00Z. Strict comparison repeats only the first window from the same source.
  Each request retains 100 same-UTC generated children / 10,000 processed events,
  existing batch cap eight, all copies, gates and normal chronological handlers.
  Runtime clock input is the existing deterministic `lambda: 0`.
- Per-request cooperative measurement budget: 150 wall seconds. An independent
  supervisor enforces **540 seconds total** across workers, with per-worker hard
  ceilings 180/240/180 seconds bounded by remaining time. Hard expiry kills the
  worker even during an atomic event and discards its private state; it never
  writes an interrupted world as a resumable checkpoint. All workers exited 0;
  no cancellation, retry or timeout occurred. Worker lifetimes sum **411.478s**,
  including source loading, setup, audits and the separate save/load exercise.
- Raw evidence outside the repository: temporary directory
  `at-engine-phase1-20261016`, with `baseline`, `instrumented`, and `strict`
  JSON/log pairs plus `supervisor.json`. SaveStore roots were temporary and removed
  on exit; real player Saves were untouched. No new full 90-day run was attempted.

Reproduction from the repository, with the retained source and a fresh external
temporary output directory:

```text
.venv/Scripts/python.exe -B -m tests.profile_engine_phase1 --source <operating-source-1.json> --root <new-TEMP-directory> --deadline-seconds 540
```

## Timings and growth

| Run/window | Wall seconds | Events | Total Bookings | Added Bookings |
| --- | ---: | ---: | ---: | ---: |
| Baseline, day 1 | 74.005 | 13 | 43,467 | 544 |
| Baseline, day 2 | 72.722 | 13 | 43,935 | 468 |
| Instrumented shared entry, day 1 | 72.212 | 13 | 43,467 | 544 |
| Instrumented shared entry, day 2 | 73.620 | 13 | 43,935 | 468 |
| Instrumented strict entry, day 1 | 72.088 | 13 | 43,467 | 544 |

Paired totals: baseline **146.727s**, instrumented **145.832s**, 26 events each:
eight dispatches, eight departures, eight Completions, two Booking checkpoints.
There are **1,012 new Bookings**, 1,470 new booked passengers and ten new journals
(eight fulfilment, two Booking sale). Final booked passengers: 66,299; final total
Booking fares: 607,476,400 minor units. All targets were fully resolved.

Observed instrumented-minus-baseline difference is **-0.895s / -0.610%**. This
single pair cannot resolve profiler overhead from normal timing variation; it
does not demonstrate negative overhead or an engine speedup. No repetitions or
90-day extrapolation are claimed.

Later/early baseline time changed **-1.73%**; instrumented time changed **+1.95%**.
Instrumented full validation grew 26.459→27.400s, runtime cloning
25.111→25.396s. This is a bounded within-run comparison, not evidence establishing
the mechanism of the historical 90-day slowdown. Bookings grew 2.36% from source.
No quarterly publication or marketplace rotation occurs in these windows; their
event-handler costs remain unmeasured here.

## Major operation accounting

Two instrumented shared-entry days, seconds; average is inclusive time / calls.

| Operation | Calls | Inclusive s | Exclusive s | Average s/call |
| --- | ---: | ---: | ---: | ---: |
| Full-world validation | 30 | 53.859 | 7.611 | 1.7953 |
| Authority graph subcheck | 30 | 22.105 | 22.105 | 0.7368 |
| Booking validation subcheck | 30 | 18.924 | 5.184 | 0.6308 |
| Booking graph proof | 30 | 13.481 | 7.315 | 0.4494 |
| Itinerary graph | 30 | 6.165 | 6.164 | 0.2055 |
| Runtime candidate/preview clone | 28 | 26.005 | 24.058 | 0.9287 |
| Runtime detached commit clone | 26 | 24.502 | 22.417 | 0.9424 |
| Detached commit parent | 26 | 24.503 | 0.0004 | 0.9424 |
| Captured whole-world deepcopy | 19 | 32.898 | 26.903 | 1.7315 |
| Captured partial deepcopy | 132,440 | 0.657 | 0.638 | 0.000005 |
| Booking preparation | 2 | 17.647 | 0.049 | 8.8233 |
| Booking processing/persistence | 2 | 15.793 | 0.103 | 7.8966 |
| Booking allocation | 4 | 31.390 | 0.498 | 7.8476 |
| Booking shopping | 4 | 30.055 | 0.245 | 7.5138 |
| Demand resolution | 4 | 29.133 | 0.0001 | 7.2834 |
| Demand discovery | 4 | 28.796 | 0.984 | 7.1990 |
| Handler dispatch | 26 | 34.379 | 0.032 | 1.3223 |
| Dispatch reconciliation | 2 | 3.534 | 0.061 | 1.7670 |
| Strict event execution | 26 | 130.801 | 0.965 | 5.0308 |
| Shared resolver step | 28 | 144.651 | 1.454 | 5.1661 |
| GC callbacks | 9,330 | 11.572* | 11.572 | 0.0012 |

*GC callback durations are separately accumulated, already contained in parent
inclusive times and removed from parent exclusive times. They are not additional
elapsed time. Raw GC records store exclusive duration rather than an inclusive key.

Coverage limitation: the first shared window's hook snapshot preceded the lazy
import of publication reconciliation, missing that one whole-world deepcopy.
Day 1 captures nine; day 2 captures ten. Source accounting identifies eight
provider-isolation copies plus backend and publication reconciliation per day;
**19 is the measured count, not a claim of only 19 executed copies**. The missing
interval remains in parent residual time. This also affects the deepcopy early/
later comparison (15.806→17.092s), so that change is not a like-for-like growth
measurement. The final diagnostic preloads that module; the strict worker already
uses the preload and extra publication-reconciliation hook. No shared run was
repeated to conceal or fill the gap. Other late aliases are not guaranteed covered.

Strict day 1 records 15 full validations / 26.715s, 14 candidate/preview clones /
13.121s, 13 commit clones / 11.921s and ten whole-world deepcopies / 17.115s.
Publication reconciliation is 1.619s inclusive / 0.029s exclusive. Counts reconcile
with 13 events plus one Booking preview clone, and entry/event/final-clock gates.

All 26 shared-entry events execute through `SharedResolutionRequest._strict_one`;
there are **zero shared batches and zero shared transitions**. Strict-only and
shared-entry timings are therefore different orchestration around strict domain
transactions, not a comparison of successful certified shared event execution.
Strict day 1 is 0.124s faster than instrumented shared day 1; this single noisy
pair, with the stated coverage difference, establishes no shared-path benefit.

## Memory and separate persistence

Native lifetime peak working set: baseline **1,094.098 MiB**, instrumented
**1,093.523 MiB**, strict **1,082.594 MiB**. Instrumented daily peaks are
1,082.035→1,093.523 MiB. These include source parse, retained source, input copying,
audits and (for instrumented) save/load; they are neither isolated allocation
peaks nor proof of a leak. No meaningful memory difference is established.

After the instrumented second day, actual SaveStore manual save took **8.480s**
and load **7.043s**, total **15.523s**, outside advancement and without timing hooks.
Each includes its own normal engine validation/copy work. The surrounding equality
hashes are outside those two timers. Exact full-world equality and paused restoration
passed. No post-load advancement or exhaustive save-failure fault campaign was run.

## Findings and next step

The top three measured non-overlapping operation families, inclusive of their
internal GC, are full-world validation **53.859s (36.9%)**, runtime whole-world
cloning **50.507s (34.6%)**, and captured additional whole-world deepcopy
**32.898s (22.6%, incomplete coverage)**. These three family totals can be compared;
their nested rows above cannot be added again. Within validation, the authority
graph subcheck alone consumes 22.105s exclusive. Booking's large inclusive cost
mostly nests provider copies and other preparation work; its processing residual
does not support a claim that writing Booking rows is the dominant cost.

Recommended first **design** target: the whole-world transaction copying pipeline.
The two captured copying families account for **83.405s**, about 57.2% of the
instrumented run, before the missed copy. Explore whether repeated candidate,
preview and detached-commit copies can safely be consolidated under explicit
ownership and rollback proofs. This is a hypothesis for Phase 2, not demonstrated
removability or an approved implementation. The prior
[provider-isolation trial](Quarterly%20Runtime%20Benchmarking.md#stage-3g-b26--provider-isolation-trial-rejected-on-safety-2026-10-13)
failed safety: these measurements do not justify simply deleting those copies.
Full-world graph validation is the next measured target. No projected speedup is
certified and all existing safety guarantees remain required.

## Verification and files

Both daily paired full-world hashes match, including all event IDs/history,
Booking/financial totals and ordering. Strict day 1 also matches:

- Day 1: `f2639799ac18443c62a85dcab3e613e12adbb5627df2051b19a4367df66091a2`.
- Day 2: `3e820205999669362cd323d618bd36e53ef137f7445283b174e7091772316943`.

Every worker's source hash remains unchanged. Final full-world validation,
passenger/lineage conservation, aircraft chronology/location, unique settlements
and balanced journals pass. Save/load is exact and paused. This is evidence for
the measured scenario, not exhaustive proof of every possible instrumented path.

`.venv/Scripts/python.exe -B -m unittest tests.test_engine_phase1_profile tests.test_quarterly_catchup_benchmark -v`
passes **12 tests / 20.772s**, exit 0. New checks cover nested interval subtraction,
return/argument identity, exception propagation and stack cleanup. Existing checks
cover budget/prefix safety, unchanged caps, deterministic construction, partition
equivalence, temporary saves and real publication-before-equal-UTC-Booking.

Scoped `.venv/Scripts/python.exe -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
passes, exit 0. Tracked production/reference comparison against HEAD and
`git diff --check` pass. No full gameplay suite was run for this isolated diagnostic.

Added files: the removable diagnostic, its
[three accounting tests](../../tests/test_engine_phase1_profile.py), and this report.
[Current Development Status](Current%20Development%20Status.md) receives the current
evidence summary. Pre-existing untracked `.venv/` is preserved. No staging,
commit, push, engine optimization or later roadmap implementation occurred.
