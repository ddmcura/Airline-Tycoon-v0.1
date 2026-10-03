# Scheduling Performance Investigation

Measured 2026-10-03 with Python 3.12.10, Kivy 2.3.1, Windows SDL2/GLEW on
Intel UHD Graphics 630. Before revision: `35ee9b70dd80ebe4eee527e41019c8d14db44ed0`,
verified against live `origin/master` before work. After: the scheduling
performance working-tree successor. These are local measurements, not latency
SLAs or claims of human playtest approval.

## Method and reproduction

`tests/profile_scheduling.py` is opt-in tooling, outside unittest discovery.
It creates modern PH careers and uses public scheduling/acquisition/event APIs;
no production data or saves change. Multi-aircraft fixtures receive explicitly
test-only capital, following the existing runtime benchmark convention.

```powershell
$env:KIVY_NO_FILELOG='1'
$env:KIVY_NO_ARGS='1'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m tests.profile_scheduling --fixtures "$env:TEMP/at-scheduling-profile" --repeats 3 --profile --gui
python -m tests.profile_scheduling --fixtures "$env:TEMP/at-scheduling-profile" --cases draft-daily-return,weekly-publish-560,recurrence-history --repeats 1 --allocations
python -m tests.smoke_scheduling_performance --output "$env:TEMP/at-scheduling-smoke"
```

Use the SAME fixture directory before/after. Setup, input cloning, post-operation
validation, and hashing are outside timed operations. Reported latency is the
median of three uninstrumented repetitions. cProfile/call counting and Python
allocation tracing run separate repeats; their overhead is excluded. Windows
working set/process high-water readings are also reported, with their limitations.
All 18 before/after fixture and complete result SHA-256 witnesses matched exactly,
including event IDs/order, schedule revisions, bookings, and financial history.

Initial measurements preceded edits. The final Before run additionally used a
read-only archive of the exact baseline's `app`, `game`, `Data`, `tests`,
`settings.py`, and `main.py` in a temporary directory with the identical harness;
this permits direct reproduction after optimization without changing checkout.
The final Before and After benchmark processes ran sequentially.

Outbound-only repeated MNL-DVO cases have an existing **unpublished reciprocal
return definition**. A daily outbound starting at MNL otherwise cannot legally
reuse the same aircraft from MNL on subsequent days. Return cases create both
legs against a fresh starter A320neo. Dates are September 7-13 at 08:00 origin
local; existing-world Add uses 14:00 around the existing morning pair. These
fixtures preserve position and turnaround rules rather than bypassing them.

Prepared-publisher cases use one/two/five aircraft with two daily MNL-DVO legs
and increasing horizons. The separate **weekly-publish-560** case measures the
actual `WeeklyDraft.save_current` path: 140 weekly MNL-CRK draft legs (ten legal
short round trips/day), finite Repeat Until November 1, and 560 dated occurrences
in the initial rolling window. The discarded continuity preview is measured too.
This distinguishes an efficient prepared publisher from expensive definition
staging in the real application workflow.

The recurrence fixture was produced by real demand, booking, flight-operation,
and settlement events through September 20 15:59:59 UTC. It contains 84 flights,
28 completed results, 4,251 bookings and 10,234,473 canonical JSON bytes. The
next event is the September 21 base-local Monday horizon extension. No fake
history, past flights, or arbitrary distant recurrence end dates were introduced.

## Bottlenecks and changes

1. **Nested definition transactions dominated Add and Publish.** WeeklyDraft
   staged each occurrence through the public single-definition command, which
   validated/copy-committed the entire world twice per definition. Daily + Return
   performed 14 commands: 33 full validations and 34 explicit envelope copies.
   With 560 existing flights this became 9.04 s. The realistic 560-flight Publish
   staged 140 definitions: 286 validations, 289 envelope copies and 990 catalog
   loads. In its separate cProfile run, 57.53 of 74.64 s accumulated inside
   definition commands; validation accumulated 48.18 s and copying 16.94 s.
   Cumulative hotspots overlap; these instrumented seconds are not table latency.

   **Change:** shared private definition/revision staging mutates one detached
   scheduling candidate. Public single-command APIs retain their input/result
   validation and atomic copy/commit. WeeklyDraft validates the complete definition
   batch, reconciles inside that candidate, validates the completed result, and
   independently validates its discarded cyclic-continuity preview. No intermediate
   definition is committed to live authority. Save still revalidates current world
   and timing before atomically replacing authority.

2. **Lifecycle/event lookup was quadratic.** Fulfilment validation scanned every
   pending/history event for each flight (and repeated scans for completed results).
   Departure reconciliation similarly rescanned the growing queue per flight.
   **Change:** build operation-local indexes once. Exact owner/type/due/revision,
   payload, duplicate and completion checks remain intact, in the same traversal
   order. Stable new-flight sorting, event priority/ID allocation, booking protection
   and continuity checks are unchanged. Known occurrence keys are likewise built
   once per publication operation rather than once per definition.

3. **Every draft leg repeatedly reconstructed identical base movements and loaded
   pinned reference catalogs.** Daily + Return made 21 movement checks and 121
   catalog loads. **Change:** reuse the immutable detached base movement projection
   and validated reference profile/catalogs for ONE Add/revalidation batch. Each
   check merges current draft legs afresh and still validates range, configuration,
   exact time, reservation overlap, turnaround and projected aircraft position.
   The operation context is removed in `finally`; no global cache, cross-command
   stale snapshot, persisted field, or GUI timing authority was added. Capacity is
   validated once per candidate where passenger legs require it.

4. **Nested publication inside recurrence duplicated the kernel transaction.**
   The weekly handler called a public publisher inside the kernel's already
   detached complete-event candidate. **Change:** a private token-guarded event
   publication path uses the same reconciler inside the kernel candidate. Kernel
   input/full-result validation, handler contract checks and copy/commit remain;
   rejection discards the entire event. It still extends only opted-in schedules
   within current week + four future weeks, with finite ends/revision boundaries
   and existing booked/published protection preserved.

5. **GUI rebuilt Schedule before AND after Add.** Rendering reconstructed timing
   for every block and validated the whole world just to display one aircraft.
   **Change:** one refresh after a successful/rejected builder batch; display uses
   retained reservation bounds rather than recalculated performance. The session
   supplies a fresh detached row for its already validated owned aircraft, analogous
   to its existing bounded header. Public fleet projections still validate arbitrary
   external envelopes. Both paths share the same row construction. UI rendering
   performs no scheduling mutation or authority validation bypass.

The publisher creates dated flights, revisions/IDs and departure events; it does
not allocate bookings or initialize financial journals. Those remain future
simulation-event work. Financial/historical validation cost is included whenever
world validation runs. Turnaround calculations themselves were not a dominant
hotspot and their formulas are unchanged. Sorting and the complete continuity
checks remain authoritative; the prepared publisher already had a proper batch
transaction, so small raw publication timings change little.

## Before -> After

### Draft Add

| Scenario | Before (s) | After (s) | Speedup |
|---|---:|---:|---:|
| draft-single | 0.2634 | 0.1162 | 2.3x |
| draft-single-return | 0.3434 | 0.1209 | 2.8x |
| draft-mwf | 0.4307 | 0.1223 | 3.5x |
| draft-mwf-return | 0.7153 | 0.1255 | 5.7x |
| draft-daily | 0.7766 | 0.1339 | 5.8x |
| draft-daily-return | 1.4110 | 0.1424 | 9.9x |

### Prepared authoritative bulk publication

| Scenario | Before (s) | After (s) | Speedup |
|---|---:|---:|---:|
| publish-10 | 0.0732 | 0.0753 | 1.0x |
| publish-50 | 0.0870 | 0.0895 | 1.0x |
| publish-100 | 0.1055 | 0.1045 | 1.0x |
| publish-250 | 0.1640 | 0.1604 | 1.0x |
| publish-560 | 0.3222 | 0.2496 | 1.3x |

### Application, history and GUI

| Scenario | Before (s) | After (s) | Speedup |
|---|---:|---:|---:|
| weekly-publish-560 | 17.7416 | 1.1149 | 15.9x |
| draft-existing-560 | 9.0413 | 0.7309 | 12.4x |
| save-draft-existing-560 | 8.9846 | 0.9085 | 9.9x |
| recurrence-history | 4.1914 | 2.0453 | 2.0x |
| gui-fresh | 1.8615 | 0.3000 | 6.2x |
| gui-existing-560 | 10.9426 | 1.0204 | 10.7x |
| gui-render-existing-560 | 0.4957 | 0.0994 | 5.0x |

GUI Add includes current-world revalidation and presentation; domain Add does not.
Render-only uses the SAME populated week/world/draft without mutation. Widget
construction is bounded to the selected aircraft/week, not all 560 flights.
A render-only repeat had an isolated 0.57 s outlier; the median is 0.0994 s.

## Boundary and operation counts

| Operation | Full validations before -> after | Envelope copy calls before -> after |
|---|---:|---:|
| Daily + Return Add | 33 -> 3 | 34 -> 2 |
| Weekly Publish creating 560 | 286 -> 4 | 289 -> 5 |
| Daily + Return Add with 560 existing | 33 -> 3 | 34 -> 2 |
| Save draft with 560 existing | 34 -> 4 | 37 -> 5 |
| Weekly event with real history | 4 -> 2 | 4 -> 2 |
| GUI Add with 560 existing | 36 -> 4 | 35 -> 3 |
| Render selected populated week | 1 -> 0 | 0 -> 0 |

Copy counts instrument explicit imported `deepcopy(envelope)` calls. Detached
`deepcopy(WeeklyDraft)` calls are reported separately: one for domain Add and two
for GUI Add, before and after; they also contain a detached base world. Counts
exclude recursive scalar/container copier calls. They are structural evidence,
not a statement that every allocation is an envelope copy.

Daily + Return still performs 21 per-leg/earliest movement checks, but expands the
immutable base once per batch. With 560 existing flights, schedule expansions
fall 258 -> 58. Catalog loads fall 121 -> 8 for fresh Add and 990 -> 9 for large
weekly Publish. GUI Add rebuilds/header refreshes fall 2 -> 1; with 560 flights
widget constructions fall 278 -> 160. Render-only still builds 160 widgets but
catalog loads/snapshot reconstruction fall 58/28 -> 0/0. Thus the gain is not from
hiding work on a worker thread or skipping required occurrences.

## Memory

Separate untimed `tracemalloc` repeats measured Python allocation high-water
marks DURING the operation (setup excluded). They produced the same state hashes.
The allocation runs overlapped verification work; their latency samples are not
used in the performance tables.

| Operation | Before peak (MiB) | After peak (MiB) |
|---|---:|---:|
| draft-daily-return | 3.35 | 2.42 |
| weekly-publish-560 | 16.44 | 13.25 |
| recurrence-history | 39.02 | 27.52 |

Allocation volume falls much more than peak resident size: copies formerly
happened repeatedly, not all simultaneously. The candidate, complete validation,
and discarded continuity preview still need memory. Recurrence's final retained
state is necessarily almost the same: roughly 11.6-11.8 MiB of Python allocations
in this trace. It contains all authoritative bookings/history rather than dropping
history for speed. Serialized input size for the historical case is about 9.76 MiB.

Windows process working/high-water readings are supplementary. They include
fixture setup, native Kivy/OpenGL allocations, allocator retention and accumulated
smoke/benchmark widgets, so they are not exclusive transaction peaks. Python
tracing also excludes native GPU allocations. This pass proves reduced bounded
Python allocation costs, not an arbitrary-airline memory ceiling or leak audit.


## Correctness, Kivy smoke and verification

New deterministic structural gates cover constant batch validation counts,
one base projection per Add operation, operation-context cleanup, exact equality
against composed public definition commands for one-off/finite/continuous modes,
last-day atomic conflict rejection and undo, invalid timing/input-world rejection,
one lifecycle-history scan with duplicate-event rejection, kernel ownership token,
retained display timing, detached owned-aircraft projection equality, one builder
refresh on success/failure, and publication feedback/exit guards.

The publication confirmation now paints a modal notice before dispatching ONE
serialized domain command on a subsequent Kivy frame. The clock is paused and
pending publication blocks advancement/exit; shutdown cancels an unstarted
callback. The notice contains no authoritative state. It does not chunk an atomic
publication, introduce a worker, or change simulation pacing.

Verification on this working-tree source scope:

- Focused affected suite: **199 tests passed in 173.093 s** (including the 12 new
  structural performance regressions).
- `python -m unittest discover -s tests`: **690 tests passed in 540.498 s**.
- Required application-scope compilation and `git diff --check` passed.

The displayed native Kivy smoke used temporary fresh careers and the actual SDL2
window/event loop. The window was maximized at 2560x1377 without exclusive
fullscreen. Daily outbound and Daily + Return creation/publication passed. Ten
legal daily short round trips produced 140 draft legs and **560 published flights**.
The actual publication command plus GUI refresh took **1.3518 s**; the approximately
4 ms callback submission was not counted as publication latency. Navigation away
and back, selection/protected published-flight details, scrolling, and all seven
weekday rows were exercised. A settled native-window screenshot confirmed the
rendered timeline; the protected-flight details modal was visible in that capture.

Cooperative session advancement extended the rolling horizon **560 -> 700**.
Save/load produced exact validated state and paused restoration. Further advancement
completed the first real round trip (two results), followed by Fleet/Flights/Finance/
Schedule inspection and another exact validated save/load. This dense short-route
smoke had no bookings; the separate historical benchmark included 4,251 actual
bookings and completed/settled results.

The measured extension smoke step took 11.2206 s including preceding demand/event
work and save/load verification; it is not the isolated weekly-event timing in the
table. Maximum heartbeat gap was **4.4976 s** during combined domain validation,
view inspection and save/load checks. Large complete transactions still occupy the
single event loop. Programmatic displayed smoke establishes functional behavior,
not human-level Windows responsiveness or a guaranteed frame budget.

## Remaining scaling limits

- Complete world validation and copy/commit still grow with bookings, financial
  witnesses and retained history. Recurrence's remaining CPU hotspots are these
  kernel boundaries, not expansion of all historical dates. The historical fixture
  still takes about 2.05 s for one weekly event; it is not instantaneous.
- The publisher scans existing occurrence/booking collections and sorts future
  continuity chains once per operation. Old revisions are visited, but date
  materialization starts at the bounded current window, never at the first
  historical schedule date. No extra years of future flights are generated.
- Weekly display still constructs a movement projection through the configured
  scheduling horizon before filtering to the visible week. Dense weeks create
  proportionally more widgets. No speculative persistent cache or widget
  virtualization was introduced; the measured render-only improvement was 5x.
- Individual complete-event work can block the event loop. A publication notice
  communicates larger commands; this pass does not claim arbitrary large-history
  simulation events meet a frame budget. Further incremental validation/history
  partitioning would need separate compatibility and deterministic-witness work.
- Other management screens retain their existing validated projections. Their
  redesign/performance, acquisition, research/economy changes, fleet actions,
  cancellation/refunds, maps, and new recurrence contracts are outside this pass.
