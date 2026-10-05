# Scheduling Patch 4 — planning-only reposition feasibility

Approved and measured **2026-10-06**, against local HEAD, upstream and live
origin/master **0623a621835f2a8d6ca10d06f19d26b55cd42fff**.
Authority: [scheduling architecture](../01%20Core%20Simulation/Flight%20Scheduling%20Architecture.md),
[canonical Schema 7](Stage%201%20State%20Schema.md), subordinate template and
[existing acquisition compatibility](Aircraft%20Acquisition%20Technical%20Specification.md).
No persistent field, migration, timing formula or runtime change.

## Root cause and reproduction

Unpublished `WeeklyDraft.add` enforced literal incoming airport equality.
`add_weekdays` also called `_candidate` through `_commit_edited_sequence`, staging
world definitions and running real publication/continuity on discarded worlds.
Consequently an overnight gap that could physically contain repositioning still
failed. A fresh MNL-based A320neo attempting Daily DVO→MNL at 08:00 in Sep7–13
failed at its first DVO origin; even starting at DVO would leave MNL after its
first leg and fail at the next DVO origin. MWF failed identically.

The new rule applies to transient planning only: every resulting chronological
adjacency must be physically connectable. Airport inequality requires a travel
proof, not an actual movement. Add, multi-day Add, copy/paste, move/delete,
current-world revalidation, and bounded finite/continuous recurrence preview
use the same planning proof. Failed edits preserve the previous legs and undo.
Same-airport handling/overlap remains strict. After initial feasible activation,
insufficient repositioning cannot be skipped to repair an invalid later edit.

## Exact timing contract

[Planning proof](../../game/scheduling/planning_feasibility.py) uses existing
`planning_snapshot` (approved profile, aircraft configuration, catalog/scalar range,
coordinates/distance) and `timing_bounds(snapshot)[1]` (maximum reservation bounds).
No GUI travel formula, arbitrary padding or rounding buffer exists.

Let a predecessor arrive at A, with retained post-arrival allowance P; next flight
requires pre-departure allowance N, and minimum turnaround is T. If destination
already equals next origin, earliest next departure is:

`max(A + P + N, A + T)`.

If the endpoints differ, obtain hypothetical reposition maximum `(Rpre,Rblock,Rpost)`:

- reposition departure: `max(A + P + Rpre, A + T)`;
- reposition arrival: reposition departure + Rblock;
- next departure readiness: `max(reposition arrival + Rpost + N, reposition arrival + T)`.

For an already parked initial anchor, preparation starts no earlier than current
UTC; there is no invented previous landing/turnaround at current UTC. A genuine
active operation supplies its projected arrival and reservation bounds. Retained
recent actual work continues to restrict readiness. All existing future reserved
and virtual active-schedule movements stay in chronological planning queries.

V2 pre is the versioned 30-minute narrowbody/regional/turboprop or 45-minute
widebody stand turnaround; post is zero. Minimum turnaround is an independent
**maximum inequality**, not another additive allowance. V1 retains historical
critical-path pre/post handling; neither snapshot is rewritten.

A320neo example: Monday08:00 DVO→MNL arrives09:40. Hypothetical MNL→DVO can leave
10:10, arrives11:50, and aircraft is ready for DVO departure12:20. Tuesday08:00
therefore fits comfortably. A same-day DVO departure12:19:59 is rejected;
12:20:00 is accepted. Starting physically at MNL at Tuesday08:00, hypothetical
MNL→DVO departs08:30/arrives10:10; first DVO departure can be10:40. Exact seconds
survive Earliest and manual input.

PH_SCALAR_RANGE_V1 and approved airport timing profiles are checked for the
hypothetical route too. Real Twin Otter MNL→TWT / BSO→MNL legs fit individually,
but TWT→BSO reposition exceeds its scalar range and rejects the draft.
**Runway/payload performance is not modeled by the current compatibility contract**;
no false runway certification or invented restriction is supplied here.

## Initial partial week and Earliest

Elapsed preparation/flight intent remains inert and never supplies actual
position. Only a genuinely initial partial-week infeasible prefix can be omitted
in the planning proof. Actual published/booked obligations and an established
activation cannot use that exception; every full future recurrence week is checked.
Publication's original Patch1 filter is unchanged.

Earliest searches finite exact readiness and order change points, including the
next representable second after order equality, and proves each proposal through
the same resulting-plan validator. It cannot return an omitted/inert proposal.
It now may suggest a physically reachable different origin: this proves planning
feasibility, **not** permission for runtime to teleport. Patch1.1's inert-prefix
08:30:01 insertion and exact second-return tests still pass. Explicit inert
reverse-pattern construction remains separate from actual operational readiness.

Recurrence preview derives weekly local departure dates through existing pinned
local-to-UTC conversion. It is bounded by the configured 90-day planning horizon,
checks cross-day/week adjacency and allocates no definitions, flights or event IDs.
Finite Repeat Until remains inclusive; continuous recurrence is not changed.
Publication retains its existing rolling four-week materialization semantics.

## Publication/runtime boundary

A physically feasible draft with unresolved location gaps is **not executable**.
Save/Publish still calls the unchanged detached publisher, complete world validation
and literal aircraft continuity. Such publication fails atomically with an explicit
explanation that planning-only reposition does not move aircraft and actual
positioning is required. The original draft and complete live world remain intact.

The engine already supports **explicit timed DEADHEAD** legs with zero commercial
capacity and real departure/completion/cost/maintenance effects. Existing explicit
execution remains tested. Advanced Single Flight already exposes an explicit
positioning choice; the terminal also asks confirmation. Patch 4 does not insert
or reuse one automatically.
The smallest later feature is an approved planning-to-publication workflow that
materializes/asks confirmation for actual positioning legs using that mechanism,
with decisions about placement, costs, conflicts, recurrence and edits. No such
workflow or permission is inferred from this patch.

Implicit gaps create **no** passenger/deadhead occurrence, movement, Booking, demand,
revenue/expense/journal, maintenance hours/cycles, result/history, runtime event,
RNG consumption or save field. Draft/clipboard/proof/cache state is transient.

## Performance and proof boundary

`python -B -m tests.profile_planning_reposition` loads exact baseline WeeklyDraft
source read-only from Git into a private module and compares the same modern fresh
fixture, three repetitions per case. Construction is outside timing. Initial
cProfile of valid Daily+Return: .438s instrumented total; .362s in discarded
candidate/publication composition, .252s in three complete validations (nested
costs are not summed). Quiet measured results:

| Case | Before median | After median | Outcome |
| --- | ---: | ---: | --- |
| Daily DVO→MNL | .010448s | .014916s | rejected → 7 draft legs accepted |
| MWF DVO→MNL | .009589s | .010317s | rejected → 3 draft legs accepted |
| Daily MNL→DVO + Return | .106638s | .022470s | 14 draft legs accepted in both |

Draft Add no longer builds publication worlds; complete validations during the
valid Daily+Return Add fall from 3 to 0. This removes proof of an operation that
planning no longer performs; it does **not** bypass any authoritative mutation
validation. Draft construction validates its world; each real publication retains
its original validated transaction. Base movements/reference data are reused once
per builder operation, including nested Earliest, then released. Hypothetical
route bounds are cached only within a proof; no persistent/Stage2 index is added.
Normal overlap, timing/range and chronology are still checked. Large drafts and
retained history can still incur multiple finite Earliest trials; no broad
scheduling/runtime optimization or wall-clock performance SLA is claimed.

## Verification

18 new deterministic regressions cover Daily/multi-day, exact readiness/seconds,
atomic incremental reschedule/delete/paste/undo, cross-week finite/continuous
preview, real range rejection, airport-profile failure, real active operations,
published obligations, return, inert prefix and complete-world side-effect witnesses.
Older literal-location **draft** expectations are updated to the approved planning
rule; the corresponding publication rejection and actual execution assertions remain.
Structural tests retain one base projection per Add and now require zero discarded
world-validation boundaries during draft Add. Publication equivalence controls remain.

Focused scheduling/planning/recurrence/performance/GUI suites: **130 passed in 73.682 s**.
Surrounding management/GUI/event-safety suites: **62 passed in 133.421 s**.
Full `python -B -m unittest discover -s tests`: **1109 passed in 1111.512 s**.
Scoped application compilation, 226 affected local documentation links, final
diff checks and self-review pass. Production source stayed frozen throughout
the full run. See [Current Development Status](Current%20Development%20Status.md).

`python -B -m tests.smoke_planning_reposition`: fresh Windows SDL2/OpenGL app PASS.
Actual builder Daily preset accepted 7 DVO→MNL legs (.121473s domain+GUI), MWF 3;
valid gap insert accepted, invalid05:00 gap edit rejected atomically with timing
explanation; Earliest DVO10:40 and ordinary MNL→DVO return10:10 correct. Continuous
implicit publication rejected with unchanged world/draft. A literal return pair
published 2 real flights, manual save/reload exact and paused. All artifacts TEMP.
This is programmatic native verification, not a human smoothness survey.

Stop after Patch 4. No Ultra-hang investigation, runtime/pacing/schema change,
Stage3G, automatic deadhead, map, or unrelated management work.
