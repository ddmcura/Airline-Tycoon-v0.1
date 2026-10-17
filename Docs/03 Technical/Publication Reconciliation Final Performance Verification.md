# Publication Reconciliation — Final Performance Verification

Verification date: **2026-10-17**. Final safeguarded Candidate 1 working tree over
`120aa5f5c8d1047750cd29f4c14a5212231945de`. This is measurement only: no production,
test, schema or save-format changes; no commits or pushes. The earlier
[implementation report](Publication%20Reconciliation%20No-Op%20Optimization.md) and
[Phase 1 evidence](Engine%20Performance%20Profiling%20Phase%201.md) remain unchanged.

## Decision

**A reliable overall speedup is not established.** The publication check itself
is measurably cheaper and eliminates one whole-world copy in this fixture.
Recommend **keeping Candidate 1 provisionally**, preserving its safety admission;
do not advertise an overall speedup or treat performance acceptance as settled.
No measured regression or outcome difference justifies revision/reversion here.

The uninstrumented pair was 97.261355s original versus 94.337071s final, an observed
2.924283s / 3.01% reduction. However, reversed instrumented pairs disagree in sign,
and repeated final runs differ by 23.841955s. Noise exceeds the plausible saving.

## Fixture and controls

Reuse the exact retained Phase 1 `operating-source-1.json`, 75,758,607 bytes,
canonical SHA256
`ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0`.
Advance from `2026-10-02T03:00:00Z` through `2026-10-03T03:00:00Z`.
One A320neo, four daily passenger sectors, four services, a published Q4 plan,
368 dated flights and 42,923 initial Bookings; deterministic seed 17012026 and
`stage1-philippines-v1-starter-grant-2026-10-02` reference data. No warmup rebuild.

Each worker is a fresh Python 3.12.10 process using the existing `.venv`, the same
source load, full source validation, hash check, isolated session copy and
temporary save root. Session runtime clock is constant zero. The retained catchup
harness uses the shared facade, batch cap eight, existing 100 same-UTC generated
child / 10,000-event limits. All 13 events use strict boundaries: four dispatches,
four departures, four completions and one daily Booking checkpoint. No retries,
engine failures or unresolved same-UTC work. No other tests/benchmarks ran alongside.

The original control extracts only `_reconcile_quarterly` from HEAD using Python
AST and substitutes it in the diagnostic worker. This restores the actual original
unconditional publication reconciliation after unchanged backend reconciliation,
without invoking the new predicate or scan. Public repair code is unchanged.
Both modes otherwise execute the same current source. No disk source is patched.

Simulation timing excludes imports, fixture reading/validation/hashing, session
construction and final audits. Both modes receive the same setup. Filesystem/OS
caches and background machine load are uncontrolled; fresh process does not imply
a cold operating-system cache. Save/load is not included in these timings and was
not repeated; final-source load/resume regressions remain in the earlier evidence.

One global **720-second hard deadline**, with each worker killed and waited for at
min(205 seconds, remaining global budget); a cooperative 165-second simulation
budget supplies an additional boundary stop. All six workers completed normally,
exit zero; supervisor elapsed **670.682697s**. No deadline extension or further
experiment. The supervisor and every child have exited.

## Total simulation runtimes

Execution order is shown explicitly; times are seconds for one complete game day.

| Run | Original | Final | Instrumentation |
| --- | ---: | ---: | --- |
| 1, then 2 | 106.684090 | 89.612399 | Alias counters and boundary timers |
| 3, then 4 (final first) | 97.531917 | 113.454354 | Same counters and timers |
| Mean of profiled repetitions | 102.108004 | 101.533377 | Observed 0.56% reduction; inconclusive |
| 5, then 6 | 97.261355 | 94.337071 | No timing/count hooks |

The quiet pair guards against attributing instrumentation effects to production.
There are too few repetitions and too much variation to quantify profiler overhead:
the quiet original is 4.75% below the profiled original mean, and quiet final is
7.09% below its profiled mean. These differences mix noise/order and overhead and
must not be used as corrections. No cProfile or recursive deepcopy tracing is used.

## Measured operations

Calls are **per complete day**, confirmed in both profiled repetitions. Timings
are cumulative seconds per day, averaged over the two repetitions of each mode.

| Operation | Original calls | Final calls | Original seconds | Final seconds |
| --- | ---: | ---: | ---: | ---: |
| Public publication reconciliation, inclusive | 1 | 0 | 2.078141 | 0 |
| Publication whole-world deepcopy, inside above | 1 | 0 | 2.028453 | 0 |
| New predicate, inclusive | 0 | 1 | 0 | 0.823112 |
| Compatibility scan, inside predicate | 0 | 1 | 0 | 0.823073 |
| Predicate residual, excluding scan | 0 | 1 | 0 | 0.000039 |
| Backend whole-world deepcopy | 1 | 1 | 2.241214 | 2.130255 |
| Kernel runtime clones (13 candidates + 13 detached commits) | 26 | 26 | 37.229447 | 38.526827 |
| Booking preview runtime clone | 1 | 1 | 1.261347 | 1.242529 |
| Demand activation provider whole-world deepcopies | 4 | 4 | 9.363377 | 8.818825 |
| Booking shopping provider whole-world deepcopies | 4 | 4 | 8.367269 | 8.306112 |
| Full-world validations | 15 | 15 | 36.334425 | 36.138151 |

The new scan takes **0.766561–0.879584s**, mean **0.823073s**. The predicate
residual is about 39 microseconds, including nested timer overhead; this is not
a precision claim about pure matching cost. Original reconciliation takes
2.073610–2.082672s. Subtracting the mean predicate cost from mean original public
reconciliation gives a **component comparison of 1.255029s less work**. It is not
a demonstrated whole-day improvement, nor a forecast for other careers.

Whole-world copies total **37 original → 36 final**, one eliminated per qualifying
request here: 27 runtime clones + eight provider copies + one backend copy, with
the original's additional publication copy. Recursive/partial-object copies are
excluded. No validation gates, event transactions or detached commits are removed.

Nested timing must not be added: publication copy is inside reconciliation;
compatibility scan is inside the predicate. The tiny predicate residual is inclusive
minus its separately measured child. Other rows identify the major boundary costs;
they are not an exhaustive exclusive decomposition of total simulation time.
Counts are scoped to advancement, excluding setup and post-run audit validation.

## Outcome and source verification

All six runs pass complete-world equality and independently match Phase 1's final
canonical hash:
`f2639799ac18443c62a85dcab3e613e12adbb5627df2051b19a4367df66091a2`.
This covers event IDs/history, cursors/revisions, every Booking and financial value,
not merely selected totals. Each ends with 43,467 Bookings/itineraries (+544),
65,596 booked passengers, nine completed flights, 47 journals, 63 historical and
363 pending events. Full validation, unique settlements, balanced journals,
passenger conservation/lineage, aircraft chronology/position and
publication-before-Booking checks pass in every worker. The loaded source hash is
unchanged in all six. No new quarterly publication event falls inside this day;
boundary failures/retries are covered by existing regressions, not this timing run.

Native process peak working sets, including setup/audits, range 1079.543–1080.047
MiB original and 1045.566–1079.988 MiB final. Quiet peaks are 1080.047 / 1079.883
MiB. No reliable peak-memory improvement is established.

All **344 application/test Python source hashes** match before/after measurement.
The earlier final-source 18 focused regressions and 1,763-test discovery evidence
remain applicable; they were not rerun for this documentation/measurement-only task.
No tests were modified. Only this report and a verification update in Current
Development Status are added/edited in the repository by this verification task.
Documentation diff/whitespace and local-link checks pass.

## Evidence and next smallest measurement

External evidence directory: `%TEMP%/at-final-publication-20261017/`. It contains
`verify.py` (supervisor/worker), the extracted `original-entry.txt`, source-hash
manifest, six logs, six completed JSON audits, timing checkpoints and
`supervisor.json`. It imports the retained benchmark harnesses without modifying
them. Run command from repository: `.venv/Scripts/python.exe -B` followed by the
external `verify.py` path. Earlier Phase 1/2 raw evidence is preserved separately.

If overall performance acceptance is required, the smallest next experiment is
another quiet one-day pair in **final→original** order, under a new explicitly
bounded budget and quiet machine conditions. Pool it with this quiet pair and
report spread; if signs disagree or spread still exceeds the difference, retain
the inconclusive conclusion. Do not extend to 90 days or extrapolate a fleet gain.
That additional experiment was **not** performed under this request's deadline.
