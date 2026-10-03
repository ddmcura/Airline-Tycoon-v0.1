# Runtime Advancement Performance Investigation

Measured 2026-10-03 against live baseline `051561ad59c4c2eaf8f35ec4ddf306264732606f`
and its performance successor working tree. This report describes measured facts,
not a change in gameplay or the state schema.

## Reproduction and method

Windows desktop, Python 3.12.10, Kivy 2.3.1/SDL2/GLEW, Intel UHD Graphics 630.
Other pre-existing Python processes were left alone; wall times are observations,
not portable thresholds or statistically controlled medians. Latency runs are
separate from cProfile/copy-count runs. Construction, input cloning, hashing and
post-run validation are outside measured engine latency. Process high-water memory
includes earlier cases in that process and is not per-operation allocation peak.

The player's existing valid manual save was loaded read-only, then benchmarked
as a detached TEMP fixture: one aircraft, **718 dated flights, 525 bookings, 40
completed results**, UTC `2026-09-06T00:40:00Z`, 4,213,502 encoded bytes.
Two days required 46 events (22 departures, 22 completions, two Booking checkpoints).
The engine-only baseline completed in **119.794 s**. Thus the reported fifteen
minutes was not reproduced exactly by engine-only work; screen refresh, host load,
and different evolving state must be distinguished from this measured two-minute
engine cost. No claim that the save was corrupt or event processing was sleeping.

`tests/profile_advancement.py` uses the existing scheduling benchmark builders,
public acquisition/definition/publication APIs, real Booking/event processing,
43 authoritative airports and 1,806 directional markets. The busy starter begins
September 6 at 23:59:59 UTC, after actual event processing, with a daily A320neo
MNL–DVO return service, rolling four-week publication, 70 flights and 1,848 bookings.
Larger fixtures use existing test-only funding conventions and multiple aircraft
on this same corridor; this is a stylized throughput workload, not a whole-airline
network forecast. Fixture JSON preserves insertion order and is reused unchanged
against an archived baseline tree and the successor. All fixture/save files are
in temporary directories. No production save or reference data is modified.

```powershell
python -B -m tests.profile_advancement --fixtures <temp-directory> --fleets 1 --days 1,2,7,30 --budget 120
python -B -m tests.profile_advancement --fixtures <temp-directory> --fleets 10,25,50 --build-only
python -B -m tests.profile_advancement --fixtures <temp-directory> --fleets 10,25,50 --days 1,7,30 --budget 20
python -B -m tests.profile_advancement --fixtures <temp-directory> --case observed-save --days 2 --profile --budget 120
python -B -m tests.profile_advancement --fixtures <temp-directory> --case quiet-new --days 90,365 --budget 120
python -B -m tests.smoke_advancement --fixtures <temp-directory> --mode load --view Flights --days 2
```

Budgets cancel **between complete committed events**. `TIME_BUDGET` is a partial
run, never a completed target or a valid whole-jump speedup comparison. Instrumented
profiles can hit the same budget sooner. Event dispatch timing includes the kernel
candidate/handler/result validation/commit; different cumulative profile entries
nest and must not be summed. Tooling records exact target/actual UTC, events by type,
completed flights, full-state SHA-256, process working/high-water bytes and optional
tracemalloc allocation peaks.

## Bottlenecks established before changing code

The observed-save instrumented flight-heavy prefix processed 19 lifecycle events
in 123.374 s: **58 full validations and 76 whole-world copies**. Each lifecycle event
had kernel result validation plus redundant command common-check/manifest world
validation, and kernel copies surrounding another nested command transaction.
Full validation consumed 80.981 cumulative seconds; deepcopy 42.034. Structural
validation, recursive forbidden-field scanning, JSON compatibility and alias checks
dominated. There were 117 catalog loads; reference loading and actual flight-time
calculation were not the dominant cost in this sample.

An older recurring fixture (84 flights, 28 results, 4,251 bookings, 10.2 MB) processed
six events in 127.026 instrumented seconds. Fifteen full validations took 61.002
cumulative seconds, deepcopy 64.807. One Booking checkpoint took 30.276 seconds:
preparation 17.438, commit 12.833; allocation ran twice, shopping and active demand
resolution ran twice. The same isolated operation was repeatedly copied at nested
allocation, shopping and demand boundaries. Historical payloads were also rescanned
for JSON/alias properties already proven by the root validator.

These are substantial CPU costs. Normal 7× pacing remains ordinary runtime behavior;
explicit advancement processes events as fast as the complete-event path permits.
It does not wait for seven real-time seconds per game second. The previous GUI called
one advancement step every .2 s and could rebuild the active management view repeatedly.

## Architectural changes and invariants

- Kernel-owned isolated candidates are reused by nested flight fulfilment, Booking
  allocation/shopping/checkpoint and Model 4 active-day operations **only** for the
  existing exact internal transaction capability token. Public operations and forged
  booleans retain detached validation/transaction behavior. A failed nested operation
  raises through the owning handler and the kernel discards the candidate.
- Flight manifest/common checks reuse the enclosing validated input. The kernel
  still validates the complete handler result before publishing it, checks handler
  contracts, and makes a detached commit. Bulk input/final-target validation remains;
  each nontrivial event retains its complete result validation. No unvalidated
  multi-event commit or reduced historical validation contract was introduced.
- Booking preparation remains a separate probe, with its original witnesses and
  commit-time checks. Provider purity snapshots remain, including custom-provider
  isolation. This deliberately retains preparation/commit computation and five
  physical world clones per checkpoint rather than silently trusting provider code.
- Runtime candidate/commit/probe cloning uses an internal C standard-library object
  codec for exact primitive trees. The pickle bytes are created and consumed inside
  one private helper; **no external bytes are accepted**, no save uses this format,
  global restoration is rejected, and custom reduction is excluded from the fast
  encoder. Non-plain compatibility objects fall back to the previous deepcopy.
  Exact integer/float values, dictionary insertion order, aliases and detached
  references are preserved. A five-repeat local 4.2 MB clone microbenchmark measured
  deepcopy about .082 s, internal codec about .030 s. This trades temporary byte
  buffers for lower CPU work; it is not a memory reduction claim.
- Validator proof reuse is invocation-local: successful whole-envelope JSON/alias
  proofs suppress redundant subtree checks. Invalid input still executes the original
  diagnostics. UTC syntax memoization is bounded to 4,096 exact immutable strings;
  it caches no world, reference input or mutable outcome.
- Explicit shared-session advancement now uses the existing 10,000-event request
  ceiling as its generated-event ceiling too. Ordinary paced runtime keeps its
  100-generation budget. Both explicit ceilings remain whole-request, across GUI
  chunks; hitting either pauses visibly and requires an explicit continuation.
  This runtime safety-budget adjustment permits routine multi-aircraft horizon
  extension; it is not recurrence, schema or simulation-speed redesign.
- Kivy has a 64-event ceiling and a 15 ms yield budget checked between complete
  events; this is not a hard frame-time cap. Wall time controls
  yielding only, never simulation UTC/outcomes. The clock/status label updates in
  place; management/header rebuilding is suppressed during explicit advancement,
  with one final refresh on completion/failure. Navigation may explicitly render.
  One heavy atomic event can still block a frame; there is no worker thread.

For a single-event public `advance_next_event`, flight lifecycle work now has two
full kernel gates and two physical detached clones. In a bulk iterator its initial
input gate is shared across the request; each event retains result validation.
The complete-event transaction/rollback contract and retained-handler-reference
isolation are preserved. No persisted field, save migration, fare/demand formula,
turnaround rule, flight status, financial witness or recurrence rule changes.

## Exact equivalence and regression strategy

The busy starter input SHA-256 is
`fc4472f88f94593fae8f49f1b85640063d4ddf717415b737f2e550432934541e`.
Before/after complete states match at one, two and seven days, including event
history/order, generated identifiers, operations, bookings, finance and recurrence.
Two-day witness:
`2aa62106a7fedd3425addc98841cc84273ab6fa0639a93bca5f4c764174df8b6`.
Observed-save two-day witness:
`6306724f8ff9553ed8b87902b04ee2a499a9a059c7afdd60e0699c2032d0b468`.

`tests/test_advancement_performance.py` covers these complete witnesses, fake-clock
normal 7× vs explicit equality from identical clock configuration, paused exact
save/reload, physical copy/validation counts, forged-token rejection, late result
corruption rollback, bounded generation limits, UTC predicate compatibility,
JSON/alias rejection, detached clone accuracy, GUI batching/one final render, and
90 actual daily Booking checkpoints in a quiet valid career. Existing startup,
recurrence/revision, financial, migration and deterministic kernel tests remain gates.

## Remaining scaling limitations

Full complete-result validation and detached commits still scale with all retained
flights/bookings/cohorts/events/journals. Booking still computes its authoritative
prepare/commit plan twice and checks provider purity twice. This patch eliminates
measured redundant administrative work; it does **not** establish constant-time
history processing, thousands-of-aircraft performance, or instantaneous long
catch-up. Larger workloads and busy 90-day/year requests must be reported explicitly
when budget-limited. Future optimization should profile these retained gates and
operation-local indexes before proposing a proven batched transaction contract.
No historical records may be removed or validation weakened merely for throughput.


## Complete starter and gameplay-save measurements

Single samples in seconds, identical input fixtures; all rows here reached the exact
requested UTC and passed complete-state validation. These are engine wall times,
excluding native GUI presentation. Before/after complete-state hashes match.

| Fixture | Days | Before | After | Events / completed flights |
|---|---:|---:|---:|---:|
| Busy starter | 1 | 7.745 | 2.344 | 5 / 2 |
| Busy starter | 2 | 15.812 | 4.582 | 10 / 4 |
| Busy starter | 7 | 70.636 | 18.812 | 36 / 14 |
| Detached gameplay save | 2 | 119.794 | 31.163 | 46 / 22 |

The optimized gameplay-save profile completed all 46 events (106.439 instrumented
seconds), **48 full validations, 98 physical world clones, zero nested fulfilment
replacement commits**, one final advancement report, 44 carriage-manifest calls,
24 event creations, 97 aircraft-catalog loads. Flight dispatch cumulative times in
the uninstrumented run: completion 12.467 s, departure 12.472 s; Booking 4.969 s.
The profile's complete validation consumed 90.152 cumulative seconds; recursive
forbidden-field scanning 24.512, structure 29.934, root 28.777, Booking authority
21.026. Thus retained complete validation, not clone CPU, now dominates this sample.
Booking still prepares/commits twice (four allocation/shopping/active-demand calls
for two checkpoints). Its physical snapshots were intentionally not removed.

Working/high-water process memory for the gameplay-save case was 106.55/135.66 MB
before and 102.81/131.96 MB after (decimal MB). Busy starter one-day process
high-water rose from about 59 MB in the baseline sequence to 75.88 MB in the successor;
seven-day successor high-water 102.66 MB. Internal clone byte buffers and process
lifetime sequencing affect this measure. This is not a general memory improvement
claim; no unbounded cache of worlds or derived gameplay was introduced.


The retained field-policy scan was then measured in isolation with identical cached
UTC helpers: seven-repeat median **.07295 → .06116 s** on the gameplay-save fixture.
It now enqueues only dictionary/list children; primitive field values still receive
every original policy check. Diagnostic path/order regressions cover nested lists,
forbidden airport-code fields, float money and malformed UTC. This is traversal
optimization, not a relaxed validator contract.


Thirty-day busy-starter result: **139.458 s**, exact target
`2026-10-06T23:59:59Z`, 155 events (30 Booking checkpoints, 60 departures, 60
completions, four weekly publications, one market rotation), 60 completed flights.
Booking dispatch 40.191 s; departure 46.720; completion 47.089; weekly publication
3.314; market rotation 1.035. Working/high-water 126.94/160.78 MB. Baseline at the
120-second budget: 121.550 s, 50 events/19 completions, only
`2026-09-16T02:10:00Z`; **TIME_BUDGET**, not a completed thirty-day comparison.
The optimized thirty-day SHA-256 is
`cc9b499a15e597dc45f0ebfdf3699b75813b3971507592ab1bd2d2331760268b`.

Busy rolling 90-day and 365-day attempts were explicitly budgeted at 120 s. They
stopped at complete boundaries after 139/136 events and 54/52 completed flights,
respectively (120.893/120.056 s), reaching only October 3. Neither reached its
requested target. All partial worlds validate; these runs establish long-target
acceptance and safe cancellation, not finished long-jump performance or equivalence.
A separate quiet-career long-jump result must not be conflated with this workload.


## Scaling measurements

Input flights/bookings: 10 aircraft **700/8,825** (13.42 MB), 25 **1,750/9,488**
(15.72 MB), 50 **3,500/9,737** (18.48 MB). Setup took 15.38/33.33/71.27 s and is
excluded from advance latency. Ten-aircraft day-one budget: 120 s; other scaling
rows: 20 s. A heavy atomic event can overrun a budget before cancellation. All
partial rows below are **TIME_BUDGET**, not completed requests or speedup ratios.

| Aircraft / days | Before seconds / events | After seconds / events | After status | Booking dispatch seconds before → after | Lifecycle dispatch seconds before → after | After working / lifetime peak MB |
|---|---:|---:|---|---:|---:|---:|
| 10 / 1 | 122.514 / 22 | 61.890 / 41 | COMPLETED | 8.227 → 3.185 | 113.228 → 57.016 | 165.16 / 210.16 |
| 10 / 7 | 25.183 / 4 | 20.179 / 13 | TIME_BUDGET | 8.211 → 3.055 | 15.884 → 16.356 | 155.00 / 201.67 |
| 10 / 30 | 20.139 / 3 | 20.499 / 13 | TIME_BUDGET | 8.384 → 3.225 | 10.659 → 16.513 | 161.54 / 204.10 |
| 25 / 1 | 26.006 / 3 | 20.501 / 10 | TIME_BUDGET | 11.218 → 4.886 | 13.433 → 14.681 | 172.33 / 229.24 |
| 25 / 7 | 25.514 / 3 | 20.322 / 10 | TIME_BUDGET | 11.130 → 4.995 | 13.027 → 14.403 | 189.49 / 230.58 |
| 25 / 30 | 25.905 / 3 | 20.669 / 10 | TIME_BUDGET | 11.427 → 4.980 | 13.110 → 14.745 | 197.83 / 236.63 |
| 50 / 1 | 25.696 / 2 | 21.340 / 7 | TIME_BUDGET | 15.647 → 7.832 | 8.232 → 12.285 | 192.34 / 276.75 |
| 50 / 7 | 25.702 / 2 | 20.726 / 7 | TIME_BUDGET | 15.678 → 7.753 | 8.257 → 11.726 | 204.35 / 276.87 |
| 50 / 30 | 25.340 / 2 | 21.326 / 7 | TIME_BUDGET | 15.310 → 7.852 | 8.201 → 12.187 | 202.75 / 276.87 |

All scaling prefixes validate. Ten-aircraft day one completed 20 flights/41 events
at exact September 7 23:59:59 UTC; its baseline processed only 22 events before
the 120 s cap. For 10-aircraft 7/30-day targets the optimized prefix reached
September 7 01:40 UTC (13 events); 25 and 50 prefixes were still at their first
departure timestamp. None of those larger full targets completed under the cap.
Weekly materialization had not yet occurred in these short prefixes; the complete
starter 7/30-day runs supply actual history-bearing horizon-extension evidence.
No successful dense 50-aircraft live 7×/catch-up gate is claimed.


## Quiet long targets and aged recurrence

A valid quiet new career retains 43 airports/1,806 markets and its starter aircraft,
but has no flights/bookings. It is a low-load long-target correctness case:

| Target | Before | After | Complete after events |
|---|---|---|---:|
| 90 days | 22.706 s, COMPLETED | 12.057 s, COMPLETED | 92 |
| 365 days | 25.019 s, EVENT_GENERATION_LIMIT_REACHED | 61.384 s, COMPLETED | 377 |

Ninety-day full-state hashes match before/after, at November 30 2026 UTC, with 90
completed daily Booking checkpoints and two market rotations. Year-long optimized
advancement reaches September 1 2027 UTC with 365 checkpoints/12 rotations. The
baseline's explicit 100-generation ceiling stopped it December 7 after 100 events;
its 25-second duration is **not** a completed-year timing. The new shared-session
10,000-generation ceiling handles the complete year without skipping events.

The independently prepared aged recurring fixture (84 flights/4,251 bookings/28
results/10.23 MB, after real prior events) completes another two days in **12.189 s**:
11 events, four completed flights, two Booking checkpoints and one horizon extension.
Weekly-publication dispatch .874 s; Booking 3.177 s; departures 3.511 s; completions
3.406 s. Working/high-water 112.26/157.93 MB. The baseline evidence for this fixture
was the separate **instrumented, budget-limited** six-event 127.026-second profile;
it must not be presented as an uninstrumented whole-target speedup comparison.


## Displayed Kivy smoke and presentation measurements

Fresh processes opened maximized SDL2 windows (2560×1377). Load used title/career/
current-manual-save controls directly; no New Game was created first. Fresh-career
cases used GUI New Game and public domain scheduling/publication, starting September
1; their first service week begins September 7. These differ from the busy-starter
benchmark that begins September 6. All files remained temporary. After advancement,
Fleet/Flights/Finance/Schedule views rendered, complete worlds validated and manual
save/reload preserved exact paused authoritative bytes.

| Loaded gameplay save, Flights view, 2 days | Before | After |
|---|---:|---:|
| Wall seconds | 168.0086 | 33.0740 |
| View rebuilds | 48.0000 | 1.0000 |
| Render seconds | 36.6284 | 1.0157 |
| Header calls | 48.0000 | 1.0000 |
| Header seconds | 0.0017 | 0.0000 |
| Ticks | 47.0000 | 47.0000 |
| Longest complete tick seconds | 9.0111 | 2.7423 |
| Working / lifetime peak MB | 446.93 / 483.58 | 378.79 / 419.66 |

Both completed all 46 events/22 flights/two Booking checkpoints and produced the
same complete hash as the engine-only before/after. Header lookup itself was tiny;
expensive management projection/widget rebuilding was the presentation cost.
The exact fifteen-minute report was **not reproduced**: this native baseline was
168 s, while engine-only was 119.8 s. The evidence explains measured redundant work,
not a claim about an unobserved fifteen-minute host interval.

Fresh-career one/two/seven-day smoke observations:

| Days from creation | Wall seconds | Events / completed flights | Rebuilds | Longest tick seconds |
|---|---:|---:|---:|---:|
| 1 | 0.683 | 1 / 0 | 1 | 0.385 |
| 2 | 1.181 | 2 / 0 | 1 | 0.412 |
| 7 | 6.266 | 13 / 2 | 1 | 0.681 |

This proves programmatic functional behavior in a displayed native Windows GUI,
including direct load, actual operations/Booking, final finance projections and
exact paused save/reload. It does not prove human-level responsiveness. A loaded
history-bearing checkpoint still produced a 2.742 s tick; the 15 ms yield budget
cannot interrupt an atomic event. Heavy transaction stalls remain explicit work.


## Verification and final review

- Focused: `python -m unittest tests.test_advancement_performance
  tests.test_stage1_event_kernel tests.test_runtime_startup
  tests.test_stage1_booking_checkpoint tests.test_stage1_flight_fulfilment
  tests.test_stage1_runtime tests.test_gui_foundation -q`:
  **135 tests passed, 84.567 s**.
- Full: `python -m unittest discover -s tests`: **707 passed, 436.375 s**.
- `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`:
  exit 0. Compilation is scoped, excluding protected metadata/runtime directories.
- Displayed native smoke: fresh one/two/seven days; fresh direct Load Game/two days;
  matching full loaded-state hash, Booking/operations/finance/management views,
  exact paused save/reload. Standalone CLI also passed without external Kivy env
  setup. No production career files were changed.

Review covered domain ownership/private capability boundaries, public failure
isolation, retained-handler references, late result rollback, codec detachment,
validator diagnostics, deterministic state witnesses, explicit request limits,
GUI rendering/status separation, persistence and documentation. No schema/template,
legacy-state, demand/fare/timing/turnaround/finance/recurrence semantic changes,
worker threads, offline progress or unrelated GUI redesign. Pre-existing untracked
`.venv/` remains untouched. Remaining dense/history-bearing catch-up and atomic GUI
stalls are measured limitations; they must not be described as solved by this patch.
