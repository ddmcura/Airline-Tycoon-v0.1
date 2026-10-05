# Scheduling Patch 1.1 — Earliest Available and initial activation

Implemented **2026-10-05**, against local HEAD, upstream and live origin/master
**8d91bd6ed135d5b8f574b76cf993f44405ac9a78**. Authority remains the
[scheduling architecture](../01%20Core%20Simulation/Flight%20Scheduling%20Architecture.md),
[canonical schema](Stage%201%20State%20Schema.md), and subordinate template.
Schema remains **7**. No persisted field, save, turnaround, recurrence, gameplay,
runtime, speed, GUI layout or unrelated screen change.

## Measured divergence

Fresh PH world: **2026-09-01T00:00:00Z / Tuesday 08:00 Asia/Manila**.
Starter A320neo is physically parked at MNL; no dated flights or active operations.
Explicit draft **06:00 MNL→CEB** is elapsed pattern intent: UTC departure
Aug31 22:00, arrival Aug31 23:15 (PH07:15), preparation Aug31 21:30. It is
not an applicable previous operational flight and cannot supply location.

Baseline `WeeklyDraft.earliest(MNL,DVO,not_before=Sep1 00:00Z)` incorrectly
classified the request as pattern-only because `floor - preparation < now`.
Its raw-pattern walk consumed the inert MNL→CEB leg, assigned location CEB,
and raised `REPOSITIONING_REQUIRED`; **no earliest timestamp was returned**.
Manual **08:30 PH /00:30Z** passed Add and publication. Publication's Patch 1
activation correctly started from actual MNL, whereas Earliest used phantom CEB.
With a midnight PH lower bound, baseline could instead return an inert midnight
slot. A lower bound is not permission to invent a past operational occurrence.

MNL→DVO retained maximum timing is `(pre, block, post) = (1800,6000,0)` seconds.
With no applicable operational predecessor, preparation can begin at current
00:00Z; off-block is **00:30Z /08:30 PH**, in-block **02:10Z /10:10 PH**;
return earliest **02:40Z /10:40 PH**. Preparation/turnaround equality is legal.

## Candidate-dependent activation and exact seconds

A second reproduction adds **08:30 CEB→DVO** and **11:00 DVO→MNL** to the
inert 06:00 prefix. Both future legs are initially infeasible from actual MNL.
Simply using the existing filtered sequence is insufficient: inserting a new
operational leg changes the first activation point and hence the successor
sequence that publication must validate.

- New MNL→DVO at **08:30:00** shares the preparation/departure boundary with
  CEB→DVO. Publication rejects the now-strict incompatible CEB leg.
- At **08:30:01**, CEB→DVO remains before initial activation and is skipped.
  The new flight arrives DVO **10:10:01**; the existing DVO→MNL departure at
  **11:00** has preparation **10:30**, so the strict successor is feasible.
- The corrected earliest is exactly **2026-09-01T00:30:01Z**. Equivalent manual
  `08:30:01` is accepted. A separately tested return after an outbound at
  08:30:01 is **10:40:01**; rounding that to 10:40:00 is rejected.

This is **not** microsecond or GUI minute rounding. Canonical UTC is whole seconds;
airport-local conversion is the existing pinned Asia/Manila UTC+8 path. Builder
and single-insert callbacks pass Earliest's canonical UTC directly to Add, without
formatting it back to HH:MM. No GUI rounding or general +1-minute buffer was added.
The one-second candidate after equality is the next representable timestamp at
a measured strict ordering boundary, not extra turnaround or arbitrary padding.

## Narrow correction and validation ownership

- `earliest` uses operational state for all public requests, clamping the lower
  bound to `now + authoritative preparation`. Only the existing private explicit
  inert-return path uses pattern-only planning. Explicit past-time pattern entry
  remains supported; past intent never operates.
- When draft prototypes establish an initial partial-week window, scheduling-local
  `_earliest_initial_activation` searches ordered exact reservation change points.
  It includes preparation/order, reservation end, minimum-turnaround, and fit-before
  bounds, plus their next whole-second successor for strict comparisons. Between
  these points the ordering and relevant availability inequalities cannot change.
- Every proposal must itself survive the **same** operational activation filter.
  A shallow detached draft wrapper with its own leg list/undo list submits through
  existing `add`, then existing detached `_candidate` publication and world validation.
  A returned proposal is proven against its own successor sequence. Trial authority
  is discarded; no query changes the draft, undo history, IDs, RNG or live world.
- Ordinary Earliest gap search is retained outside elapsed draft intent; no extra
  whole-world publication trial is added to ordinary future-week planning. Existing
  genuine location/conflict validation remains strict. No deadhead is generated.
- Query validation uses the existing one-off draft context; selected repeat/continuous
  publication still validates its complete recurrence independently. Earliest cannot
  guarantee a later user edit or a different recurrence mode will be valid.

All logic stays in `game/scheduling/weekly.py`. Kivy collects inputs and consumes
canonical results. No GUI/domain duplicate formula or new utility/cache/schema.

## Measurements and verification

Three-run query medians on the same host, exact baseline method loaded from Git:

| Reproduction | Baseline | Corrected |
|---|---|---|
| Inert 06:00 prefix, lower bound 08:00 | false rejection, .003636 s | 08:30, .083198 s |
| Prefix plus incompatible 08:30 and feasible successor 11:00 | false rejection, .003600 s | 08:30:01, .144499 s |

The additional time proves valid publication rather than returning a fast error;
no baseline speedup is claimed. Search is finite over reservation boundaries,
not every second or repeated calendar expansion. Large partial drafts may require
multiple detached validation trials; broad scheduling performance work is deferred.

Eleven regressions: nine domain tests in `test_scheduling_earliest_activation.py`
and two actual GUI callback tests in `test_gui_schedule_polish.py`. Coverage includes
single/multi-day, exact and second boundaries, manual equivalence, candidate-dependent
activation, atomic rejection, strict incompatible origins, no retroactive effects,
query immutability and no implicit deadhead. Patch 1's full next-week/strict continuity
tests remain intact.

Focused command: `python -B -m unittest tests.test_scheduling_earliest_activation
tests.test_scheduling_activation tests.test_stage1_weekly_planner
tests.test_scheduling_recurrence tests.test_scheduling_performance
tests.test_gui_schedule_polish tests.test_gui_weekly_workspace`:
**112 passed in 81.289 s**.

Native fresh-process Windows SDL2/OpenGL Kivy smoke PASS: build the inert prefix,
submit Earliest + Return for Sep1/Sep2 through the persistent builder (**.494 s**),
publish four real flights, process four results, exact manual save/paused reload;
fresh second career exercises the single-insert callback and retains **08:30:01**
through validated publication. Temporary save roots only. Programmatic native
verification does not establish human-level smoothness.

Full `python -B -m unittest discover -s tests`: **1048 passed in 993.514 s**,
final production source frozen throughout. Scoped `compileall` over
`app game tests main.py make_snapshot.py settings.py test.py`, 33 affected local
documentation links, `git diff --check` and complete diff/self-review pass.
No unresolved in-scope finding. Current Development Status records this scope.
No Patch 2 or runtime scalability work begins here.
