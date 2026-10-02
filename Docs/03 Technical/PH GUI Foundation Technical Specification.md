# PH 1.0 Kivy GUI Foundation

Approved implementation scope: user request, 2026-10-01. Implementation and
verification results are recorded in [Current Development Status](Current%20Development%20Status.md).

## Frontend decision and ownership

Kivy is the approved GUI framework. PH development and verification are desktop
first; layout and controls should remain suitable for later mobile and touch
adaptation. This does not authorize Android packaging or a final mobile layout.

`app.session.Stage1Session` is the application owner of the active complete
world, runtime controller, autosave cadence and save-store calls. Both
`app.terminal` and `app.gui` consume that session. The former remains a
developer/debug frontend. The GUI may read detached projections and ask the
session to perform commands; widgets, screen focus, timers and dialogs are
runtime-only presentation state and never authoritative game state. The
terminal's historical import path is a compatibility re-export, not a second
session implementation.

The Kivy event loop calls `Stage1Session.pump()` on its own thread. It does not
run a separate simulation worker. Explicit multi-event advancement may be
stepped through `begin_advance_to`, `advance_tick` and `cancel_advance`, with
one completed event boundary per callback. GUI actions are serialized by the
same owner. Runtime refresh replaces labels and lists in place; its timing is
not a simulation input. Paused load, autosave, safe snapshots, exact UTC and
event order follow the existing [save](Game%20State%20%26%20Save%20Technical%20Specification.md)
and [runtime](Continuous%20Runtime%20Technical%20Specification.md) contracts.

## Foundation surfaces

- Title: New PH Normal career, existing airline career selection with manual,
  autosave recovery and bookmark choices, and Exit.
- Game shell: airline and CEO, base, authoritative USD cash, exact UTC,
  pause/running state, and the approved 7x running mode. Pause, Resume and
  explicit Next Event, Day, Duration and UTC Target controls are available.
- Read-only fleet, dated flights/Bookings/operations, and finance pages use
  modern projections and stable IDs. Flight and fleet views page their data.
  Routine maintenance is visible as a flight cost component; no repair action
  is implied.
- Manual Save and bookmark list/create/load/delete use the existing SaveStore.
  Unsaved return, exit and bookmark load require Save, discard or cancel.

The screen shell uses touch-sized buttons, scrollable lists and controls, and
vertical composition so it does not require a permanently wide window, hover,
or right-click. This is a functional playtest layout, not final art or mobile UX.

## Boundaries and next slice

The GUI does not add or alter persistent fields, gameplay formulas, speeds,
offline progress, AI, save migration, or domain authority. The legacy Kivy
title stub and hybrid gameplay loop do not supply commands or state. The
second bounded GUI slice now supplies graphical new-aircraft purchase,
operating lease, lease-to-own, used-aircraft purchase, market research and a
list/form weekly planner. Its controls call the same modern session and domain
commands as the terminal. A draft, form or preview remains transient GUI state;
acquisition commits revalidate the original preview, and schedule save
revalidates draft legs against the current world before atomic publication.
Cabin editing, aircraft sale, route-wide fare editing, advanced maintenance,
and a map remain deferred by their owning domain contracts.

Launch with `python -m app.gui` after installing `requirements.txt` in a
Kivy-compatible Python environment. The terminal remains `python -m app.terminal`.

## First graphical gameplay action loop

The game shell adds Research, Acquire and Schedule navigation. Research shows
existing directional market projections for a selected origin. Acquire shows
current reference models, lease offers and used listings; each action collects
an authoritative delivery airport ID, presents the domain preview, and commits
only the confirmed original preview. The same domain command rejects stale or
unaffordable purchases. The GUI computes no price, demand or financial rule.

Schedule selects a parked aircraft by ID and holds a detached WeeklyDraft.
List/form controls add passenger or explicit positioning legs, choose earliest
or exact Philippine local departure, add the supported earliest return, copy
draft days, undo, and save with an optional inclusive weekly repeat end date.
The session's save_current path revalidates draft legs against the current
world and publishes atomically; the separate next-rotation command remains
available. The planner pauses the shared session when an edit begins, and
Kivy callbacks remain serialized with the runtime pump. Navigation, draft
rows, form values and dialogs never enter the canonical world or save.
Leaving or loading another career with an unpublished draft requires an
explicit discard choice before the existing world unsaved-progress guard.

Acquire now browses dynamically through current catalog manufacturers, their
models, then available new-purchase, operating-lease, lease-to-own and used
options for the selected model. Catalog names/specifications and active market
terms remain the sources; Kivy retains only navigation selection. The passenger
leg form displays the modern economy domain's USD 0.12/km neutral Suggested
Economy Fare, rounded to whole USD, with an explicit Use Suggested Fare action.
Changing endpoints refreshes the displayed reference without replacing a fare
already typed by the player. Booking's relative-offer scoring and demand remain
unchanged. The subsequently approved `STARTER_GRANT` increment now gives fresh
PH careers a configured catalog A320neo and V2 timing; saved A320-200 aircraft
and their published timing witnesses remain on the V1 compatibility path.

A player can now research, acquire, schedule, publish, advance or run, inspect
flights/Bookings/finance, and save through Kivy. The terminal remains the
developer/debug frontend. Existing-plan editing, aircraft sale, cabin changes,
advanced maintenance, maps, final art, and mobile packaging remain deferred.

## Weekly scheduling workspace and searchable airport input (2026-10-02)

The graphical Schedule view selects a parked aircraft, then shows its Monday-
Sunday PH-local week as a horizontally scrollable time grid with pinned day
labels. Green blocks are local unpublished draft legs, gray blocks are existing
published reservations, and selected draft blocks are blue. Flight labels and
details use `WeeklyDraft.week_rows()` projections for local departure and arrival;
visual placement is derived only from those projected timestamps. Week navigation,
selected blocks, clipboard, scroll position, forms and dialogs are frontend-only.

The player can add a passenger or explicit positioning leg on a selected day,
choose earliest or exact local departure, add the earliest return, select one or
more draft blocks, select/copy a full day, paste onto a weekday at a chosen
start time, and undo the whole pasted sequence. The domain `WeeklyDraft`
constructs detached relative offsets and replays every pasted leg through its
existing `add` validation on an isolated draft. The GUI revalidates the result
against the current world before accepting it. A rejected paste does not alter
the draft or world; the domain may suggest its earliest valid first-leg slot.
Only Publish Schedule commits the draft through the shared session's existing
atomic publication path. A game save cannot save an unpublished draft.

`app.gui.airport_selector` is a GUI-local searchable airport picker over the
current detached airport projection. It matches code, city and display name
case-insensitively, returning immutable airport IDs in an active career and the
curated reference code before career creation. It is used for New Game base,
Research origin/destination filter, scheduling endpoints, and acquisition
delivery. Manufacturer/model/acquisition controls are unchanged.

The existing weekly repeat-through date remains inclusive and finite in this
GUI. `WeeklyDraft` supplies a one-date end for ordinary publication or an
explicit end date for weekly repeat. The schema permits an absent recurrence
end, but this GUI does not expose a new indefinite-until-stopped workflow.
Defining that player contract, stop/retirement behavior, rolling publication
and already-booked obligations requires separate design approval. No persistent
schema field, airport record, scheduling rule or recurrence command changed in
this slice.

### Weekday row placement correction (2026-10-02)

The seven weekday controls and seven timeline rows share a Monday-derived date
sequence. Each hour header and day row uses a local Kivy `RelativeLayout`
coordinate space, so its labels and flight blocks render within that row when
the enclosing weekly workspace scrolls. The pinned day pane and time pane have
identical eight-row heights (one header plus Monday through Sunday). Selecting
a day changes the selected PH-local draft date. A row's Add Flight action
submits the persistent builder to exactly that row's PH-local date through the
same atomic `WeeklyDraft.add_weekdays()` path as the main multi-day button.
The separate Advanced single flight form remains available for explicit
positioning and service choices. Entering or changing a week brings Monday
into view after Kivy lays out the workspace.
The domain's `week_rows()` departure dates still decide which row owns each
published or draft block; no flight timing, publication, or date rule changed.

### Scheduling playtest controls (2026-10-02)

The desktop window prefers maximized, nonexclusive mode. Axis-aware GUI scroll
containers expose mouse-wheel scrolling on the vertical page, horizontal
timeline/weekday scrolling, visible bars, and touch content movement. Scheduling
date fields use a GUI calendar that returns the existing canonical local date.

The Schedule view starts on the PH-local current week and identifies its exact
Monday-Sunday range. Its persistent builder selects authoritative airport IDs,
prefills the editable Economy fare from `Stage1Session.suggested_economy_fare`,
defaults exact departure to 00:00, and offers the existing earliest mode. MWF,
TThS, Even, Odd, Daily and Clear set transient weekday checkboxes; players may
toggle them afterward. One Add Flight action submits all selected dates to the
detached `WeeklyDraft`. Optional returns use the domain's `add_return()` timing.
The domain validates the whole batch before one draft/undo change, including
past pre-departure work, position, turnaround, overlap and publication horizon.
Past days are labeled; past slots are rejected by domain authority. No past
flights or financial records are synthesized.

Copy/Paste can target several weekdays in one atomic detached edit, retaining
the copied relative offsets. Selected unpublished draft legs can be deleted
with one undo step. Their dedicated horizontal drag handle proposes a five-
minute UI slot; the normal domain planner accepts or rejects that exact time.
Rejected drops restore the original block and report the domain error. Published
reservations have no draft delete or drag control. Selection, clipboard,
checkboxes, gestures, calendar view and scroll position remain GUI-only.

The existing finite inclusive repeat-through date remains the only repeat
choice exposed by this planner. Schema 4 already permits open recurrence and
the publication API enforces a configured rolling horizon, but a player-facing indefinite
contract still needs approved stop/edit semantics and handling of already
published or booked future flights. Published cancellation likewise needs a
separate Booking/refund/journal and airline-impact design. Neither is part of
this playtest control pass.
