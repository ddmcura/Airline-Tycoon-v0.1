# Scheduling initial partial-week activation and expansion hang

Approved targeted Patch 1, **2026-10-05**. Baseline local HEAD, upstream and live
origin/master verified at **3b524084cc0ea24e69a9505a1ac31e4a5fd5126a**.
Authority: [scheduling architecture](../01%20Core%20Simulation/Flight%20Scheduling%20Architecture.md),
[canonical schema](Stage%201%20State%20Schema.md) and its subordinate template.
Schema stays **7**; no persistent fields, template, migration or save change.
No Stage 3 runtime, speed, gameplay/economy or unrelated GUI change.

## Two distinct measured defects

1. `_expand_schedule` had a `continue` inside its calendar-date loop for a new
   rolling-policy occurrence whose preparation precedes current UTC. That branch
   bypassed `current += timedelta(days=1)`. For a fresh PH career at Sep1 00:00 UTC
   /08:00 PH, an 08:00 departure has 07:30 preparation. Expansion rebuilt the same
   occurrence forever, before continuity checking or publication could finish.
   `timing_bounds` is cheap arithmetic; the date cursor, not that formula, caused
   the Not Responding behavior. A bounded diagnostic stopped after **5001 record
   calls /10000 timing calls**, one expansion, zero completed continuity passes.
2. Weekly draft movement reasoning included elapsed intent as though it were
   operating. A 07:30 prototype still notionally in flight could change projected
   location and reserve time even though it never flew. Conversely, future
   departures from an incompatible origin were rejected immediately, without
   considering initial partial-week activation. Publication also demanded a
   continuous chain beginning with the first future prototype, even when its
   omitted predecessor never operated.
   A separate isolated baseline probe confirms the phantom-position case:
   07:30 MNL ->CEB inert intent followed by 10:00 MNL ->DVO returns
   `REPOSITIONING_REQUIRED` despite authoritative aircraft location MNL and
   **zero dated flights**. The inert prototype, not an actual operation, supplied
   the erroneous projected destination.

The defects share the elapsed-intent boundary but have separate causes. Fixing
the loop alone does not fix position/activation; no asynchronous callback hides it.

## Exact behavioral correction and ownership

- Expansion conditionally excludes elapsed preparation without bypassing calendar
  progression. Constant preparation duration is computed once per revision.
- Scheduling-local `activation.py` derives home-local week boundaries, actual or
  projected readiness, and an initial operational sequence. It owns no world and
  stores no persistent marker/cache. Aircraft/active-flight authority supplies
  position; maximum retained timing/reservations and configured turnaround supply
  availability. Elapsed draft intent never supplies either.
- Only unpublished first revisions with rolling policy, starting in the current
  home-local week and containing elapsed intent, can omit an infeasible initial
  prefix. Actual selected weekdays are inspected, not an arbitrary effective date.
  The scan ends at the first feasible occurrence, a protected committed occurrence,
  an already-materialized activation boundary, or the next week.
- Publisher filters proposed new occurrences before IDs/events are allocated.
  Existing IDs, Bookings, reservations, results and journals are never deleted to
  activate a pattern. Normal publication continuity and complete-world validation
  remain authoritative after filtering; failed transactions remain atomic.
- Weekly Add/earliest/return and virtual base-movement projections use the same
  scheduling rule. An inert outbound's Return Flight remains pattern intent with
  ordinary authoritative spacing, rather than inventing a real aircraft arrival.
  Full recurrence/cyclic validation still occurs on the discarded horizon preview.
- First materialized dated authority prevents re-entering the initial exception;
  subsequent weeks and revisions remain strict. The weekly definition itself is
  unchanged, so skipped occurrences reappear normally in the next complete week.

## Reproduction and before/after evidence

All measurements use the same fresh modern PH career, starter A320neo, configured
**90-day** validation horizon, current week plus four future publication weeks,
and no production saves/data. The calendar actually starts **Tuesday Sep1 2026**;
Monday 08:00 is separately covered through a naturally advanced idle career.

The five-leg Tuesday pattern:

| PH departure | Origin -> destination | Initial partial week |
| --- | --- | --- |
| 06:00 | MNL -> CEB | Elapsed/inert |
| 08:30 | CEB -> DVO | Incompatible initial prefix, omitted |
| 11:00 | DVO -> MNL | Incompatible initial prefix, omitted |
| 14:00 | MNL -> DVO | First feasible activation |
| 16:30 | DVO -> MNL | Ordinary strict continuation |

The next Tuesday operates all five legs. Publication creates **22 dated flights**:
two this week plus five in each of four future weeks. No deadhead, retroactive
Booking, financial entry, maintenance, result or history is manufactured.

Repeatable tool: `python -B -m tests.profile_initial_activation` (three samples).
Before measurements load the two scheduling modules from the exact baseline in
an isolated process, leaving the working tree untouched; identical fixture/API
and counting wrappers. The diagnostic guard stops a non-progressing baseline
after 5000 records, rather than hanging indefinitely.

| Case | Before | After median Add | After median continuous publication |
| --- | --- | ---: | ---: |
| 08:00 outbound + return | Never completes; bounded stop at .181 s | .081 s | .120 s |
| Five-leg partial chain | Rejected at second leg; .089 s to rejection | .417 s for all five | .133 s |

The baseline cutoff is **not** a completion time or a speedup denominator. The
five-leg before/after outcomes intentionally differ: incorrect rejection versus
complete valid activation.

Counter evidence (counts span initial and discarded preview passes, not unique
live flights):

| Case / phase | Expansion calls | Occurrence-record calls | Timing calls in publisher | Expanded records before activation | Continuity passes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Boundary / baseline stalled Add | 1 | 5001 | 10000 | Never returns | 0 |
| Boundary / fixed Add | 4 | 12 | 16 | 2 | 2 |
| Boundary / fixed publication | 4 | 44 | 72 | 34 | 2 |
| Five legs / fixed Add total | 30 | 90 | 123 | 20 | 10 |
| Five legs / fixed publication | 10 | 110 | 182 | 88 | 2 |

Location/availability filtering visits a bounded ordered sequence; each normal
continuity pass checks the resulting proposed future aircraft chain. Counter
scope is publisher calls, not every timing call made by validation or the GUI.
The configured-horizon preview is validated and discarded, never committed.

## Native Kivy and regression evidence

Fresh-process Windows SDL2/GLEW smoke uses the actual persistent Schedule Builder:
new PH career -> five Add commands -> continuous publication -> real advancement
through today's pair -> manual save/exact paused reload. **PASS**. Per-Add
domain+GUI times **.190/.158/.161/.209/.227 s**, publication **.151 s**.
Today has two flights, next Tuesday five, total 22; two real results after
advancement. No GUI architecture or widget implementation changed. This is
programmatic event-loop verification, not a human smoothness survey.

Thirteen deterministic regressions cover inert position/effects/RNG, skipped
prefix, first feasible origin, strict post-activation location/turnaround and
atomic rejection, next-week full operations, no deadhead, no-elapsed strictness,
future-week strictness, repeat publication after activation, genuine airborne
projected arrival/readiness, Monday/midnight boundary and bounded expansion.
Tests assert deterministic structural bounds rather than host-time thresholds.

Focused scheduling/planning/publication/performance/GUI/suggestions/continuity
suite: **109 passed in 72.869 s**. Scoped compilation and diff checks pass.
Full `python -B -m unittest discover -s tests`: **1037 passed in 1003.867 s**,
baseline 1024 plus thirteen regressions. Production source stayed frozen during
the run. `python -B -m compileall -q app game tests main.py make_snapshot.py
settings.py test.py` passes; **31 affected local documentation links** pass.
Full diff/self-review finds no unresolved in-scope issue. Generated saves/logs
remain TEMP; pre-existing untracked `.venv/` is neither changed nor staged.

## Limits and self-review

This does not make an invalid full weekly pattern valid. Continuity, reserved
blocks, turnaround and required explicit positioning remain strict once activated
and in full subsequent weeks. Initial prefix omission cannot repair a later
conflict or alter published/booked obligations. Established patterns/replacement
revisions do not restart this exception. No automatic positioning is supplied.
The existing bounded horizon and complete preview remain; general large-airline
runtime capacity is still NOT CERTIFIED under Stage 3F and is not optimized here.
No Fleet/Research/Bookings/map/legacy or Stage 3G implementation is included.
