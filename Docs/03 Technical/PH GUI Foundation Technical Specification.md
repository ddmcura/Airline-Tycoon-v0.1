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
unchanged. The fresh A320-200 starter remains on its V1 compatibility path until
approved catalog specifications and a versioned modern configuration can bind it
without changing old saves or published timing witnesses.

A player can now research, acquire, schedule, publish, advance or run, inspect
flights/Bookings/finance, and save through Kivy. The terminal remains the
developer/debug frontend. Existing-plan editing, aircraft sale, cabin changes,
advanced maintenance, maps, final art, and mobile packaging remain deferred.
