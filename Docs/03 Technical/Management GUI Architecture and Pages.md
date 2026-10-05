# Management GUI Architecture and Pages — Patch 2

Approved scope and implementation: 2026-10-05. Baseline local HEAD, upstream and
live origin/master matched `c2a8bb11646bbfb9efa183665784cc3d4a7bb7e4`.
Authority remains [Stage 1 State Schema](Stage%201%20State%20Schema.md),
[GUI foundation](PH%20GUI%20Foundation%20Technical%20Specification.md),
[trusted reads](Runtime%20Trusted%20Reads.md) and owning domain specifications.
Schema remains **7**. No persistent fields, migrations or gameplay changes.

## Legacy archaeology

The tracked Kivy history at `8020b58` contains `game/gui/app.py`, an empty
`screens/dashboard.py`, and a single title-screen KV layout. ScreenManager owns
one DashboardScreen, title buttons mostly print placeholders, and no Fleet,
Research, management refresh, subpage or back implementation exists there.
The current historical launcher delegates to the modern app. No tracked/current
Snapshots directory supplies another graphical implementation.

The older terminal Fleet overview uses a table, selected aircraft detail page,
and Back to Fleet flow. Other management menus use nested loops/return. These
are useful navigation concepts, not reusable authority. They use hybrid
`game_state`, registration/name matching, direct seat/condition mutation and
legacy financial fields. None is imported or restored. The modern title/game
ScreenManager is retained; explicit sections and Fleet child details adapt the
useful overview → detail → Back concept and the approved Patch 2 requirements.

## Measured previous failure mechanisms

A fresh-career diagnostic navigating Fleet/Research/Flights/Finance/Overview
five times measured **25 content clears, 25 empty-column intervals**. Rendering
cleared the live outer scrolling column before projection calculation/widget
construction. Refresh repeated that process on a changing revision after .75 s.
It also replaced nested scrolling widgets while their effects could be active.
The sample ended at 33 widgets and one application ticker; it did **not** prove
an unbounded page/callback leak. App-level widget references could retain a
previous tree until the corresponding page was recreated.

A separate controlled Kivy 2.3.1 numeric diagnostic starts DampedScrollEffect
at value 10, bounds -100/0, velocity 200, then supplies repeated four-second
frame deltas. Its elastic integration becomes NaN; settling reproduces exactly
`ValueError: cannot convert float NaN to integer`. The same input using ordinary
ScrollEffect remains finite at -100. This establishes the long-frame spring
failure mechanism, **not the precise gesture/history of the human crash**.
Existing atomic engine stalls remain outside this patch. No production runtime
optimization or global Kivy monkey patch is introduced.

## Shell and lifecycle contract

```text
Title / career screen
Game application shell (identity, clock, existing runtime controls)
  Section navigation
    Section page navigation
      ONE active page host
        Active management page
```

Sections: Dashboard; Operations (Flights, Bookings, Scheduling); Network
(Research); Fleet (Overview, Acquire, child Aircraft Details); Finance;
Game/System (Save/Bookmarks, Return to Title, Exit). Existing gameplay actions
remain reachable. Aircraft Details is not a permanent global tab. Research and
Details navigate to the same Schedule page and existing WeeklyDraft.

Only the active page derives management rows. There are **no page refresh
timers**: one existing .2-second application tick still owns runtime pumping.
Committed header/table derivation is throttled to 1.5 s; UTC/runtime status
updates in place every pump. This changes presentation cadence only, not speed,
credit, event routing or simulation results.

Entering obtains current committed presentation before mounting. Ordinary
Fleet/Research refresh computes detached replacement rows first, keeps the
page/controls/header/viewport, and updates cells by immutable entity ID. Identical
rows do no widget/geometry work. Search, filters, deterministic sort, selected
identity and normalized scroll values are lightweight UI state. Scheduling
retains its existing draft/week/day/clipboard state. Nothing enters saves.

Leaving stops scroll velocity triggers/bounds work, releases text-input focus,
removes the page from the host and drops app-owned widget references. Re-entry
creates a page from current data plus lightweight state, not a retained live
heavy page. Section navigation scroll effects also stop when replaced. Deferred Schedule
Monday-focus callbacks are cancelled on departure and reject any detached/replaced
target tree, including callbacks already dequeued when navigation occurs.
Non-redesigned Flights/Bookings/Finance/Acquire/Saves/Schedule keep their existing
content/commands: replacement columns are built offscreen, then swapped once
into a persistent viewport. No live column is emptied before derivation.
Flights and Bookings still expose the existing combined flight/Booking results;
their actual table redesign belongs to Patch 3.

## Management table

`app.gui.management_table.ManagementTable` is a small Airline Tycoon component:
fixed page heading, search/filter/actions, fixed synchronized horizontal header,
a two-axis data viewport, and fixed footer. Only row content scrolls/pans.
Touch-sized rows/actions, mouse wheel, existing axis handling, horizontal bars
and touch panning remain available. No hover/right-click interaction is needed.

Numeric columns include Decimal distance values, avoiding lexical numeric sort.
Equal-value ties use immutable ID order. Empty/filter-zero states use a real
placeholder row and positive extent. Replacement/reorder happens synchronously
after preparation. Motion is stopped on geometry/order changes, not ordinary
cell text updates. Scroll positions persist where meaningful. Headers share
normalized horizontal position with the viewport.

App-owned AxisScrollView uses **clamped ScrollEffect**, disables elastic
overscroll on non-scrollable extents, and provides local disposal. This removes
the unstable spring behavior rather than catching/resetting NaN. No finite-value
reset or global framework patch is used. `finite()` is diagnostic/test inspection.
Small windows use horizontal panning rather than permanent desktop coordinates.
Final compact/mobile layouts and large-table virtualization remain future work.

## Fleet semantics

Columns: Hub, Airplane Name, Registration, Model, Manufacturer, Weekly Load,
Status, Details. Search matches name/registration/model/manufacturer; filters
cover home base, manufacturer, model and authoritative status; headers toggle
ASC/DESC. Details resolves stable aircraft ID, not display-name matching.

- **Hub** means the aircraft's authoritative `home_airport_id`, not an invented
  individual hub or its current position.
- **Airplane Name** is not currently modeled: displays **—**. No name field or
  rename command is invented.
- Model/manufacturer come from the aircraft configuration's versioned catalog.
  Unconfigured historical aircraft keep their model reference; unavailable
  catalog-backed manufacturer/name data is neutral, not guessed.
- Status derives from aircraft status/current airport or its real active operation.
- **Weekly Load** is passenger-seat utilization of published operational service
  in the aircraft's current **home-local Monday–Sunday week**. Denominator sums
  published capacities for PASSENGER flights in PLANNED, OPERATIONALLY_LOCKED or
  COMPLETED state. Numerator uses completed result carriage; otherwise the existing
  confirmed carriage-manifest projection with Booking-owned IDs. Connecting
  passengers count per seat-leg. Basis points = floor(numerator × 10000 /
  denominator). Display divides basis points by 100 for percent. Cancelled,
  superseded, deadhead, unpublished and inert pattern slots do not contribute.
  No applicable passenger capacity yields **—**, not a misleading zero.

The owning `game.fleet_management.management_projection` performs these detached
reads after the session acquires its existing committed ownership gate. No GUI
formula determines bookings, capacity or operation outcomes.

## Aircraft Details

Fleet child page with Back and Schedule Aircraft. Organized existing values:
registration, manufacturer/model, acquisition/ownership, home base, actual
operational route/status, Economy cabin/capacity, reference range, manufactured
date, derived age days, authoritative lifetime flight hours/cycles and service
condition, and routine maintenance policy. Contract identity/status appears when
modeled. Cargo is explicitly not modeled; no capacity/repair system is fabricated.

Current-week rows include only that aircraft's actual published dated authority,
with origin-local departure and destination-local arrival (ISO offset retained),
state and endpoints. Membership uses its home-local operational week. Inert
pattern intent is not falsely presented as operated history. No raw JSON dump.

## Research semantics and handoff

- IATA/name identify the destination of the selected directional origin.
- Distance retains the existing projection's km value.
- Base Daily Bookers is the Model 4 base directional allocation leaf, rounded
  HALF_UP to an integer **for display only**; underlying Decimal values/formulas
  remain unchanged.
- **Market Available** is the current Model 4 **destination airport availability
  boolean**. It is not unsold passengers or remaining directional demand; no
  accurate remaining-opportunity count is currently exposed by this boundary.
- **Your Seats** sums player capacity on structurally usable direct passenger
  service with departure in the inclusive current UTC → configured publication
  horizon interval. It is neither daily seats nor remaining empty seats.
- **Confirmed** sums current confirmed Booking passenger counts on those same
  services. It is neither flown passengers nor an invented market-wide total.
- Fare is the common published fare if uniform; mixed published fares say
  **Mixed fares**. With no qualifying service, the existing suggested Economy
  fare is labeled **suggested**. No fare formula is reproduced in Kivy.

Code/name search and all requested column sorts are presentation-only. The
searchable origin/destination controls retain code/city/airport-name matching.
Add Flight calls the session's route-compatibility read. Its scheduling-local
helper uses existing `planning_snapshot`/versioned eligibility, including scalar
range and approved airport timing profiles. Runway/payload restrictions are not
modeled by this approved contract; none is invented or loosened. This chooser
identifies planning candidates, not permission for any departure time/location.
Final Add/publication still validates position, timing, reservations and conflicts.

Zero candidates gives a clear message and stays in Research. One opens the
builder; multiple require selection by authoritative ID. Builder aircraft,
origin/destination and existing suggested fare are prefilled. Time, return,
recurrence and publication stay player choices. No flight is added/published by
handoff. Runtime pauses/drains through the existing boundary before edits;
changing aircraft with an unpublished draft requires explicit discard consent.

## Verification and measurements

- Affected GUI + scheduling activation/Earliest + runtime safety suites:
  **108 passed in 165.309 s**. Final management suite after self-review:
  **19 passed in 39.155 s** (includes focused-keyboard-release regression).
  The first complete run found two stale deferred Schedule focus callback errors
  (1078 tests in 1100.375 s). Lifecycle cancellation/exact target checks fix that
  issue; **51 focused scheduling/management tests passed in 73.693 s**, including
  the new pending-callback regression (20 management tests total).
- Native fresh Windows SDL2/OpenGL smoke with two purchased/granted A320neos,
  real published flights, and Normal/Fast/Very Fast: **PASS**. Fleet shows real
  airborne state; compatible chooser/builder prefill, search/filter/sort, scroll,
  refresh, repeated sections/pages and exact save/paused reload work.
- Quiet 80-navigation sample: Dashboard widget count **32 in all ten samples**;
  one mounted page, **one retained historical weak page reference**, zero page
  refresh timers, one app ticker. Median navigation **.0782 s**, maximum **.9787 s**.
  Final post-callback-fix native rerun also passed: median **.0792 s**, maximum
  **1.0311 s**, identical counts and exact save/reload. Concurrent-test sample
  had a 3.1602-s maximum; this is not a promise of smooth interaction or a capacity
  certification.
- **50 native finite table checks**, plus unit empty/populated/changed, filter-zero,
  clear, sort while scrolled, resize, long-frame velocity, navigation/focus and
  runtime-refresh cases. No blank/disappearing table or NaN exception in smoke.
  Native screenshots were inspected; unsupported font-arrow glyphs were replaced
  by readable ASC/DESC and route text in these new surfaces.
- Twelve unit navigation cycles across all sections retain constant widget counts,
  one ticker, and at most one historical Fleet weak reference; inactive pages do
  not refresh. Ordinary identical refresh keeps exact cell/viewport identities.
- Final full suite: **1079 passed in 1102.349 s**. Scoped compilation passed;
  **215 affected local documentation links** resolve; `git diff --check` passed.
  Final self-review found no authoritative schema/runtime/gameplay change, domain
  logic in Kivy, legacy authority, clipboard/save leak or unrelated redesign.
  Evidence covers the final source working tree based on the baseline above.
  All saves/screenshots/diagnostic output use TEMP, not production data.

Commands: `python -B -m unittest tests.test_management_gui`; affected command: `python -B -m unittest tests.test_management_gui tests.test_gui_foundation tests.test_gui_gameplay tests.test_gui_weekly_workspace tests.test_gui_schedule_polish tests.test_gui_cooperative_runtime tests.test_scheduling_activation tests.test_scheduling_earliest_activation tests.test_causal_generation`; `python -B -m unittest discover -s tests`;
`python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`;
`python -B -m tests.profile_management_navigation`; `git diff --check`.

## Scope and limitations

No schema/save/offline, scheduling/recurrence, demand/Booking/economy, runtime,
speed/cap/overload, aircraft sale/cabin/maintenance action or acquisition redesign.
No legacy authority, new dependencies, threading, map or Stage 3G. Stage 3F's
capacity failure remains. Patch 3 will redesign Flights/Bookings on this table
architecture. Final mobile layouts/art, very large table virtualization and
retained-history read-performance work are not claimed complete.
