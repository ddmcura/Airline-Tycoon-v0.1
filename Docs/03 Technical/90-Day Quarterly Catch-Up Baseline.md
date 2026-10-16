# AT-058 — 90-Day Quarterly Catch-Up Baseline

Measurement only, 2026-10-16, production baseline
`5f70abd51a822bc99295011cee1d5abc35756569`. Results below distinguish a completed
90-day workload from a cancelled, valid committed prefix. No production optimization,
offline entitlement, pacing, schema/template change or default activation is included.

Authority: [Schema 9](Stage%201%20State%20Schema.md),
[AT-058 runtime contract](Single%20Speed%2C%20Advancement%20%26%20Offline%20Progression.md),
[existing benchmarking protocol](Quarterly%20Runtime%20Benchmarking.md),
[save contract](Game%20State%20%26%20Save%20Technical%20Specification.md).

## Preflight and environment

Master HEAD, upstream, freshly fetched origin/master and live remote master matched
the baseline, divergence 0/0. The tracked tree/index were clean. Existing untracked
`.venv/` and stash `On master: Preserve unfinished Stage 2; restore Stage 1 baseline`
were preserved. No protected tooling content or player Saves was accessed. Serena
was not exposed among the session's available tools; targeted source searches were
used instead. This limitation is explicit rather than a claim of Serena inspection.

Actual desktop: Windows 10 build 19045, Python 3.12.10 from the existing virtual environment; Intel Core
i5-10400 @ 2.90 GHz, six physical cores / twelve logical processors;
17,018,118,144 bytes physical memory. The qualified sample ran in a fresh
process without regression tests or instrumented profiling concurrently.
Process peak working set includes construction/loading and input copies; it is
not an isolated allocation delta or a memory-leak certification.

## Exact fixture and measurement construction

The [harness](../../tests/benchmark_quarterly_catchup.py) reuses the
[existing constructor](../../tests/benchmark_quarterly_runtime.py), with an optional
return immediately after real manual publication, followed by the same exact natural
warmup under the required limits. The default historical build path remains unchanged.
The recipe supports the requested fleet parameter; only the one-aircraft career
was constructed and measured. Its deterministic inputs are:

- The PH scenario's normal 43 airports, 1,806 directional markets, demand and
  simulation seed `17012026`, reference version
  `stage1-philippines-v1-starter-grant-2026-10-02`,
  configuration, changing only creation UTC to `2026-08-31T00:00:00Z`; MNL base.
- The granted A320neo plus real purchase-command acquisitions to 1/10/25/50
  aircraft. Explicit test capital is `10**14` integer cash minor units.
- Five paid bidirectional MNL pairs: DVO, CEB, ILO, BCD, PPS. Ten directional
  connections and five real route establishment expense/cash journals.
- Four daily passenger sectors per aircraft, two out-and-return cycles. For
  zero-based sorted aircraft index `i` and cycle `c` in `{0,1}`, destination is
  `(DVO, CEB, ILO, BCD, PPS)[(i+c)%5]`; outbound prototype is
  `2026-10-01T01:00:00Z + 6*c hours + 2*i minutes`. WeeklyDraft calculates the
  physical return, retained planning times and suggested directional fares.
- One Q4 revision containing four separately allocated service/slot identities
  per aircraft, all seven weekdays, origin-local times/fold zero, actual aircraft
  capacity and frozen planning timing. Full validation and real Manual Publish
  prepare/apply run with their existing gates/copies. There is no forged publication.

Natural warmup advances August 31 through `2026-10-02T03:00:00Z`. It includes
September 1's committed Q4 publication skip, progressive Booking, real departures,
Completions and settlement. An operating source must reach that exact target,
pass full validation and contain positive Bookings and finalized flights. Warmup
cost is separately disclosed and is not a catch-up timing. Incomplete warmup is
never silently promoted to a qualifying fixture.

The measured request starts from that operating source and targets
`2026-12-31T03:00:00Z`, exactly 7,776,000 game seconds / 90 days. It requires
December 1's actual Q1 carry-forward publication before same-UTC Booking. It
crosses the October/November/December operating calendar without treating 90 days
as a calendar quarter. This is an early operating-career baseline, not aged-career
certification. An initial August 31 new-career exploratory probe is excluded from
these results because its timing included the warmup; it also overlaps harness
verification after that fixture-design error was identified.

Construction/publication and Session input cloning/rebinding occur outside the
simulation timer. The timer includes begin/step/cancel, domain processing, validation,
copies and lightweight progress output approximately once per minute. No validation
or copies are disabled. The harness uses existing Session advancement and resolver;
its test-only resolver adapter constrains **100 same-UTC generated children** and
**10,000 processed/stale events**. This is necessary because the existing Session
passes 10,000 as its generated-event allowance. No production value is changed.
Counters survive every yield. The benchmark uses twelve explicit seven-day targets
and one final six-day target, summing all thirteen requests. Each must return success
with its UTC fully resolved before the next request starts. Every request retains
both safety limits; any engine failure stops that workload without automatic retry.
The user authorized multiple bounded measurement requests. This is a test-only
measurement workflow, not production/offline continuation or a raised event budget.
One large 50-aircraft 90-day request would exceed 10,000 processed events at the
declared flight density even before Booking and dispatch are counted.

The qualified one-aircraft run used `--budget 0 --setup-budget 0`: no wall-time cancellation.
An optional positive budget cancels only between completed events; one atomic event
may overrun. Such cancellation is a measurement resource stop, not an engine safety
failure or a completed timing. No performance acceptance threshold is inferred
from a budget or from AT-058's aspirational objectives.

## Reproduction and evidence

Run from the repository with the existing Python environment, replacing `<TEMP>`
with a new temporary directory outside the repository. Player Saves and all
repository subdirectories are rejected as artifact roots.

```text
.venv/Scripts/python.exe -B -m tests.benchmark_quarterly_catchup --root <TEMP> --fleet 1 --budget 0 --setup-budget 0
```

Each source has a complete canonical SHA-256 digest and a construction audit.
Each result records UTC, complete-world hash, event vector, exact diagnostic,
same-UTC resolution flag, process peak, fixture time, correctness and separate
save/load time. Final checkpoints use temporary SaveStore locations, exact full-world
digest comparison and paused restoration. Generated sources, checkpoints
and JSON evidence remain temporary artifacts and are not committed. No new profile
was collected. The 10/25/50-aircraft runs and timing repetitions were not started;
the user's later stop instruction supersedes the earlier unrestricted-duration request.

## Results

Only the one-aircraft workload was measured. **90 days completed**, from
`2026-10-02T03:00:00Z` through `2026-12-31T03:00:00Z`, with every request target
fully resolved. No 10/25/50-aircraft results, variability range or larger-fleet
completion estimate is claimed.

| Fleet | Game days | Request wall seconds | Completed requests | Processed events | Peak working set MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 90 | 8,312.608 | 13 | 1,173 | 1,946.008 |
| 10 | Not run | — | — | — | — |
| 25 | Not run | — | — | — | — |
| 50 | Not run | — | — | — | — |

Request wall time is **2h 18m 32.608s**, summed from unrounded samples. The complete
request-loop timer is **8,312.623s**, including inter-request progress logging.
Construction/publication is **1.711s** and natural warmup **356.179s**, separately
measured; their sum is **357.890s**. Post-warmup audit/serialization and initial
Session binding are outside those component timers and the advancement timer.
Final exact paused save/load plus its validation/hash checks is **54.599s**;
including the raw evidence checkpoint write it is **56.044s**. These are additional
costs, not hidden inside the simulation timing.

The process started at `2026-10-16T03:13:51.5271600Z`. The last live memory sample
was `05:39:29.7754575Z`, an observed process-duration lower bound of **8,738.248s**
(approximately 2h 25m 38s), including setup and audits. An auxiliary .NET exit-time
query returned null after exit, so exact process-exit duration is unavailable;
this does not invalidate the monotonic advancement timers. The process has exited.

| Request | Resolved target UTC | Wall seconds | Events | Lifetime peak MiB |
| --- | --- | ---: | ---: | ---: |
| 1 | 2026-10-09 03:00Z | 357.322 | 91 | 825.023 |
| 2 | 2026-10-16 03:00Z | 395.682 | 91 | 898.914 |
| 3 | 2026-10-23 03:00Z | 429.850 | 91 | 947.074 |
| 4 | 2026-10-30 03:00Z | 463.120 | 91 | 995.309 |
| 5 | 2026-11-06 03:00Z | 499.016 | 92 | 1,045.465 |
| 6 | 2026-11-13 03:00Z | 566.420 | 91 | 1,096.520 |
| 7 | 2026-11-20 03:00Z | 570.919 | 91 | 1,147.215 |
| 8 | 2026-11-27 03:00Z | 596.702 | 91 | 1,199.758 |
| 9 | 2026-12-04 03:00Z | 676.793 | 93 | 1,319.688 |
| 10 | 2026-12-11 03:00Z | 799.345 | 91 | 1,501.938 |
| 11 | 2026-12-18 03:00Z | 968.203 | 91 | 1,689.898 |
| 12 | 2026-12-25 03:00Z | 969.440 | 91 | 1,823.895 |
| 13 | 2026-12-31 03:00Z | 1,019.796 | 78 | 1,946.008 |

Requests 1–12 are seven days each; request 13 is six days. All have zero stale
events, failures, safety stops and retries. Event totals are **360 dispatches,
360 departures, 360 Completions, 90 daily Booking checkpoints, two marketplace
rotations and one quarterly publication**. The December 1 event published Q1;
September's earlier Q4 committed skip belongs to warmup, not catch-up.

At `2026-10-16T05:38:29.2734871Z`, just after the final request boundary during
audit, current working set was **807,772,160 bytes / 770.352 MiB**. The final live
sample was **1,319,215,104 bytes / 1,258.102 MiB**. Native process peak was
**2,040,537,088 bytes / 1,946.008 MiB**, including setup and all activity through
that point; audit sampling did not observe a higher process peak. The sampler ran
once per second only near the end, after the stop request. There is no live current
process memory after exit, and no isolated allocation or leak diagnosis is claimed.

## Correctness and preserved evidence

Full World State validation passed at the operating source and final checkpoint.
Additional checks passed for unique occurrence/operation/settlement ownership,
balanced journals, source-Booking passenger counts, actual aircraft locations,
continuous physical chains and exact paused SaveStore round-trip equality.
The real-engine harness boundary test separately observes Q2 publication before
equal-UTC Booking; final authority retains published Q4/Q1 supply and exact lineage.

Catch-up added **46,659 Bookings/itineraries**, **69,613 booked passengers**,
**360 flight results/settlements**, **69,840 carried passengers**, **360 dated rows**
and **413 journals** (360 fulfilment, 53 nonempty Booking sale journals). Ninety
Booking events do not imply ninety sale journals. Final totals are 89,582 Bookings
and itineraries, 728 dated flights, 365 results, 455 journals, 1,223 historical and
367 pending events. All pending work is beyond the resolved target. Total booked
passengers are 134,442; 70,810 have flown and 63,632 remain outstanding.

Complete final world SHA-256:
`a5f579d32d08d136a0ada4d0e2d04aae68c485a3fbfe865a442620530e74218e`.
Operating source SHA-256:
`ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0`, exactly matching
the historical deterministic fixture. Source file is 75,758,607 bytes; final raw
world checkpoint is 219,983,453 bytes. Neither is a player save.

Raw measurements remain in the local temporary directory
`at058-90day-87a9e734ab0f45e2abd1bdceb7242678`: `operating-source-1.json`,
`operating-setup-1.json`, `quiet-1-0.json`, `quiet-1-0.log`,
`quiet-1-0-checkpoint.json`, `stop-memory.ndjson`, `process-start.json`, and the
excluded `exploratory-1.json`/checkpoint plus initial-source/setup artifacts.
The excluded new-career probe took 1,803.309s, reached October 27 02:40Z
(57.111 days from August 31), processed 375 events and passed its final checks;
it is not a repetition or an operating-career 90-day measurement.

## Stop handling, bottleneck evidence and next step

The user requested a stop during request 11. A long agent monitoring call streamed
progress but delayed processing those messages; requests 12 and 13 began before
the agent regained control. The stop was consequently late. Actual termination
was the fully resolved request-13 boundary, followed only by required audits and
verification. This is a measurement-control failure, not an engine safety failure;
it is not concealed by relabeling the endpoint as request 11. No larger fleet,
repeat, new profiler run or optimization was started. Future monitoring must return
control frequently enough to handle stop messages before another request begins.

Measured facts: seven-day requests with the same 91-event vector grew from
357.322s to 969.440s; retained Booking/itinerary rows increased from 42,923 to
89,582 and lifetime peak working set from 825.023 MiB at request 1 to 1,946.008 MiB.
The last resource sample reports 8,682.625 process CPU seconds over at least
8,738.248 observed wall seconds, consistent with a CPU-bound run. These observations
do not by themselves assign time to Booking, flight bodies, copying or validation,
or establish a memory leak. No fresh profiling was started after the stop instruction.

Available **historical** profiling on the identical 42,923-row source is in the
[B2.4 report](Quarterly%20Runtime%20Benchmarking.md#measured-bottlenecks-and-repeated-work-audit):
exclusive copy regions total 125.417s; full validation is 115.501s inclusive of its
children. Booking allocation/shopping exclusive times are 0.998/1.493s; four flight
Departure/Completion bodies total 0.881/0.943s cumulative, excluding their outer
transactions. Those are instrumented older-run values, **not attribution percentages
for this new 90-day run**; overlapping inclusive categories must not be summed.
They identify copying/whole-graph validation as established earlier costs, rather
than proving Booking equations or flight bodies dominate this measurement.
Retained graph growth contributing to the rising request times is a hypothesis
supported by that earlier profile, not a fresh causal profile.

This desktop result does **not support practical interactive 90-day catch-up**:
one aircraft alone takes over two hours of engine/Session work plus checkpoint
costs. No quantitative certification threshold is invented, and no larger-fleet
timing is extrapolated. The next AT-058 step is review of this baseline, explicit
latency/memory acceptance bounds, responsive measurement stop control and the
separate exhausted-cap recovery finding below. Any new investigation or
implementation slice requires scope approval. No automatic Booking batching,
rejected B-series restart, offline implementation or activation is recommended here.

## Harness correctness finding during preparation

The new harness's first forced two-event-cap / repeated save-load continuation test
did **not** match an uninterrupted control. Using the existing small quarterly
backend fixture, natural warmup to `2027-01-02T00:00:00Z`, and target
`2027-01-02T07:00:00Z`, control hash was
`bdb1e2eaf81bbdb2f57df5d99a4764fdd3185c34c5c2d9b68fcca9560b09ebbf`;
capped/reloaded hash was
`c398d026b7ff393ac17994d100757ad7b15f8026eecba28b48b63056efa4f918`.
The event allocator/cursor increased by one, an additional historical event existed,
and an active operation's completion event ID shifted from event 193 to 194.
This is an observed full-world difference under a deliberately lowered test cap,
not a measured failure at the real 10,000 limit or a diagnosed production cause.
No production fix, event normalization or weakened equality oracle is introduced.

The retained harness instead resolves explicit bounded targets completely. Its
small real-engine multi-request test uses fully resolved two-hour targets over a
seven-hour interval, retains the real 100/10,000 limits, and requires the exact
complete-world digest to match uninterrupted execution. This passes. Existing
causal-limit and quarterly validation/retry tests also pass. That proof does not
certify arbitrary exhausted-cap recovery, which remains a separate limitation.

## Verification and scope

On 2026-10-16 against the baseline plus these harness/docs changes:

- `.venv/Scripts/python.exe -B -m unittest tests.test_quarterly_catchup_benchmark -v`
  — **9 tests / 20.613s**, exit 0. Includes exact fixture reconstruction, paid rights,
  temporary-root guards, unchanged 100/10,000 limits, incomplete-warmup rejection,
  exact warmup/timer separation, bounded/uninterrupted equality, real Q2
  publication-before-Booking, physical/conservation/finance checks and SaveStore.
- Earlier affected harness/causal/quarterly validation command
  `.venv/Scripts/python.exe -B -m unittest tests.test_quarterly_catchup_benchmark tests.test_causal_generation tests.test_quarterly_booking_validation -v`
  passed **40 tests / 162.760s** before the final two harness test additions.
  Subsequent final harness verification above covers its final scope. No full
  gameplay suite was repeated for this production-unchanged measurement.
- `.venv/Scripts/python.exe -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
  — exit 0. CLI `--help` also passed, exit 0.
- Independent evidence-file decoding reproduced the final canonical world hash
  and counted **1,223 COMPLETED / zero STALE** historical events. Twelve preserved
  raw files have size/SHA-256 entries in temporary `evidence-manifest.json`.

New boundary-test preparation initially used an invalid late current-quarter
publication stamp. World validation rejected the fixture before simulation;
the final test uses an explicit unpublished eligible Q2 plan and genuine March 1
publication. No validation rule was changed to accommodate it. Unused optional
profiling paths were removed from the new harness after the stop; the measured
advancement loop and production engine are unchanged.

Production/reference/schema/template/instruction comparison to the baseline passed.
Documentation link/heading/fence checks and final whitespace/scope review are
recorded in Current Development Status. No schema/template, ownership, economics,
runtime, offline, GUI or default activation change is made. The six-file change
scope is the new harness/test/report, the existing builder's opt-in source return,
the benchmarking report link and Status. Generated evidence and `.venv/` are excluded
from staging; the pre-existing stash is preserved. Commit/push outcomes are reported
only after their actual completion.
