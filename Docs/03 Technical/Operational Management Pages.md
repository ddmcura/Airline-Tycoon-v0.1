# Operational Management Pages — Patch 3

Approved scope: 2026-10-05. Baseline local HEAD, upstream and live origin/master
matched `548b83c5384edfb8d3f7e1beb380a0541cf1dd03`.
Authority: [canonical Schema 7](Stage%201%20State%20Schema.md),
[GUI foundation](PH%20GUI%20Foundation%20Technical%20Specification.md),
[management lifecycle](Management%20GUI%20Architecture%20and%20Pages.md),
[trusted reads](Runtime%20Trusted%20Reads.md). No persistent field or template change.

## Data audit and semantics

- Weekly schedule revisions describe intended patterns. They do not constitute
  operated flights. Neither page reads patterns or manufactures occurrences.
- `dated_flights` are actual published occurrence authority, with immutable IDs,
  directional endpoints, scheduled UTC, capacity, fare and state. Cancelled or
  superseded retained occurrences can appear in Flights with their actual state.
- `active_aircraft_operations` freezes departure, actual aircraft and source
  Booking IDs. Its manifest is locked, not an estimate of future bookings.
- `flight_results` retains actual timestamps, actual aircraft, carried passengers
  and recognized revenue. Completed views use this retained result, never today's
  pattern or a freshly inferred historical Booking outcome.
- Bookings are aggregate/cohort records linked through itineraries. The existing
  carriage-manifest function owns confirmed counts, compatibility and lineage.
  There is no individual-passenger model or new booking/economy algorithm.

Flights includes block intervals touching the selected day in the airline's first
authoritative base-airport zone, the same base used by the session's operational
local clock. Overnight airborne/completed arrivals remain visible on the arrival
day, including an arrival exactly at midnight. Bookings assigns each occurrence
exactly once by its base-local departure date. Today/Current
Week derive from committed game UTC; computer date is not consulted. Weeks start
Monday. Departure displays origin-local time and arrival destination-local time,
including date and UTC offset; sorting uses UTC. Results use retained actual
arrival/departure, active flights use frozen actual departure plus scheduled
arrival, upcoming occurrences use scheduled times. Current PH actual times match
scheduled times; no delay or estimated-time system is invented.

Past dates show only retained dated occurrence/result authority, with explicit
states: an overdue planned occurrence is not called completed. Current dates mix
completed, airborne and published upcoming rows. Future dates show only published
occurrences. Unpublished/past inert pattern slots never appear as flown history.
Dates beyond publication or missing retained history show an empty state, not a
reconstructed plan. Completed monetary display is result revenue; future rows
have no fabricated result revenue. Fare is the occurrence's offer, not an average
of paid/zero-fare accepted Booking batches.

## Flights page

[FlightsPage](../../app/gui/operations_pages.py) uses the existing ManagementTable:
Previous Day / Today / Next Day and the existing DatePicker; fixed controls,
aircraft/origin/destination/status filters, search by registration/model/airport/ID,
chronological default, deterministic sorting, and scrollable compact occurrences.
Distinct aircraft/overlapping departures occupy separate rows. Immutable IDs own
relationships; registration filtering is presentation only. Date, query, filters,
sort and scroll are lightweight retained state. No schedule editor/cancellation.

## Directional Booking matrix

Only owned published passenger service markets (including retained completed
service) enter the selector. Origin/destination IDs remain distinct in each
ordered pair: MNL → DVO and DVO → MNL are different queries. No service produces
an explicit empty market selector and a neutral seven-day matrix.

Previous / Current / Next Week retain a base-local Monday week. Rows represent
Monday through Sunday, in calendar order; headers do not sort days by passenger
load. Weekday/date search can narrow visible rows without altering the week.
Columns represent origin-local departure time, with #1/#2/etc. when simultaneous
occurrences need separate cells. Ordinals are immutable-ID order within each
hub-local day/time slot; they are not new persisted service identities or flight
numbers. Every occupied cell retains the full occurrence ID and shows registration.
Opposite directions and same-time occurrences are never aggregated together.

Cell quantities:

- **CONFIRMED:** existing validated confirmed carriage-manifest passenger count
  for an upcoming passenger occurrence, including approved compatibility data.
- **LOCKED:** that manifest read through departure-frozen source Booking IDs,
  for an airborne operationally locked flight.
- **CARRIED:** retained completed-result passenger count. Historical cells never
  pretend they still represent future confirmed sales.
- **Capacity:** authoritative passenger capacity offered on that occurrence.
- **Load:** `passengers * 10000 // capacity` basis points, displayed as a percent;
  zero capacity is neutral. This is derived display, not a booking formula.
- **—:** no applicable published passenger occurrence or no applicable denominator.
  Cancelled/superseded and non-passenger occurrences do not create Booking cells.

The existing table gains optional variable row height, static matrix headers,
dynamic service-column replacement and a pinned first column. The fixed day rail
uses the existing AxisScrollView, synchronizing normalized vertical position and
matching row heights with the data viewport. Service header/body synchronize
horizontal position as before. Day labels remain visible while service columns
pan. Empty→populated and changed service shapes prepare data before synchronous
replacement; positive extents, stopped motion and disposal remain mandatory.
Ordinary value refresh reuses exact cells/controls/viewports.

## Read/lifecycle boundaries and scale

[Owned reads](../../app/owned_reads.py) lazily reuse the existing dated-flight and
operations/Booking-ID indexes within the existing committed epoch. Selected day/
week/OD queries create only matching presentation records, using the existing
bounded eight-query encoded/detached-return cache. No whole-world cloning or
validation per row, no candidate index, no persisted cache. Session mutation,
clock/world replacement and load retain the existing invalidation boundary.

The existing app shell mounts one active page, refreshes only that page using
its existing 1.5-second presentation cadence, and disposes it on navigation.
No new page timer, app shell, runtime loop or scrolling implementation. Selected
date/OD/week/filter/sort/scroll never enters a save. Simulation continues through
the unchanged serialized session/runtime; GUI refresh cannot move authority ahead.

Index rebuilding and matching an airline's retained occurrences still scale with
history once per epoch. Very large day tables/many service columns are not
virtualized. Those are later measured read/UI scaling boundaries, not addressed
by a runtime/history redesign here. The small smoke timings do not certify large
fleets, human smoothness or Stage 3F capacity.

## Verification

Commands use the project Python environment with KIVY_NO_ARGS/KIVY_NO_FILELOG:

- `python -B -m unittest tests.test_operations_gui tests.test_management_gui tests.test_gui_foundation tests.test_gui_gameplay tests.test_gui_weekly_workspace tests.test_scheduling_activation tests.test_scheduling_earliest_activation tests.test_causal_generation`
- `python -B -m unittest discover -s tests`
- `python -B -m tests.profile_operations_gui`
- `python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
- affected local documentation-link validation; `git diff --check`.

Final affected suites: **96 passed in 160.574 s**, including 12 new operational
GUI regressions. Final full suite: **1091 passed in 1130.769 s**. Scoped
compilation, 76 local documentation links and `git diff --check` passed. Native final: **PASS**, 80 navigations / 40 finite checks,
Dashboard count 32 in all ten samples, one ticker and no page refresh timers.
Measured entry/refresh times (seconds):

| Measure | Median | Maximum |
| --- | ---: | ---: |
| Flights entry | .2226 | .3509 |
| Bookings entry | .0396 | .2359 |
| Flights forced warm refresh | .000272 | .000323 |
| Bookings forced warm refresh | .000454 | .000633 |
| Navigation across sections | .0396 | .5292 |

Refresh timings exclude separately timed runtime pumping and synchronous large
Advance; they do not promise engine/fence responsiveness. Complete-suite and final
static/link results are recorded in [Current Development Status](Current%20Development%20Status.md).
Smoke uses two authoritative acquired/granted A320neos, four daily round trips
each on two operational days: 32 published sectors, including overnight legs, both OD directions, duplicate
departure slots, real Booking checkpoints, flight transitions and settlement.
Fresh native Windows SDL2 runs Normal/Fast/Very Fast, 80 navigations, visible
refreshes, horizontal/vertical scrolling, a narrower resized desktop window and
exact paused save/reload. All saves/screenshots/output are TEMP, never production.
Screenshot review justified taller matrix cells and the pinned weekday rail.

## Full-run fixture diagnostic

The first complete run executed 1090 tests in 1132.028 s with one new navigation
count assertion failure. It sampled the entire ScreenManager before explicitly
settling title→game startup. A controlled diagnostic measures 39 widgets while
both title/game are mounted and 32 after transition; three isolated eight-cycle
runs stayed at 32 throughout. The stress fixture now finishes only that startup
transition before measurement, retaining exact constant-count, single-page and
save/equality assertions. Production transitions/navigation are unchanged; native
smoke exercises the real transition. Final suite results are recorded in status.

## Completion boundary

Patch 3 completes this management-GUI slice after verification. Next step is
**human playtesting**, not another automatic milestone. No map, cancellation/
refunds, individual passengers, new formulas, aircraft sale/configuration/actions,
legacy restoration, mobile packaging, virtualization/history redesign or Stage 3G.
Schema 7, save meaning, authoritative UTC, runtime pacing and scheduling remain.
