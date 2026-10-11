# Quarterly Planning and Publication GUI — Stage 3F

Bounded implementation authorized 2026-10-11, starting from
`fb2dd01b7031b34a9a49f8e23cadd65f329518e8`. HEAD, upstream, freshly fetched
origin/master and live remote master matched; tracked tree/index were clean.
Only the protected `.venv/` was untracked. Serena memories were used for navigation;
their older Stage 2 checkpoint does not override current repository evidence.

Authority: [Schema 9](Stage%201%20State%20Schema.md), the subordinate
[template](../../Data/Templates/template_reference.txt),
[quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md),
[certified commands](Quarterly%20Transaction%20Certification.md),
[readiness](Quarterly%20Publication%20Readiness.md),
[occurrence lineage](Quarterly%20Operational%20Lineage.md),
[shared publication](Quarterly%20Shared%20Publication.md),
[failure recovery](Quarterly%20Boundary%20Orchestration.md),
[isolated consumers](Quarterly%20Backend%20Consumer%20Cutover.md), and
[GUI ownership](PH%20GUI%20Foundation%20Technical%20Specification.md).
No new persistent field, schema version, save migration or simulation rule.

## Isolation and navigation

Ordinary `python -m app.gui` retains its New Game and legacy Scheduling controls.
Explicit `python -m app.gui --quarterly-dev` adds a separate **New quarterly
development career** action. Ordinary New Game remains legacy even in that process.
The session creates a private untouched new-career candidate, establishes PH
directional connections with the existing construction primitives, then invokes
Stage 3E's existing isolated enrollment. Those pre-established routes are a
development fixture, not a new player route-creation command or general activation
policy. It seeds no service, plan, booking, flight or operational occurrence.
Enrollment failure exposes no partial active world. Existing saves are not converted.

An explicitly saved quarterly career retains its existing authority after Load,
and therefore shows quarterly controls without needing a new enrollment. The mode
belongs to the career; page selection and the launch flag never choose simulation
ownership. Ordinary careers continue using their existing Booking and operations.
General quarterly activation remains Stage 3G.

The existing Operations → Scheduling page hosts the quarterly page only for an
isolated quarterly career. Fleet/Research handoffs select the same page and retain
the selected aircraft as runtime presentation context. Existing Flights, Bookings,
Finance, Fleet, acquisition, bookmarks and runtime navigation remain available.
The page uses the existing one-active-page lifecycle, scrolling and touch controls.
Actions share the existing horizontally scrollable strip, and variable text has
content-sized labels/bounded diagnostic scrolling so service rows remain visible;
there is no second ticker, worker or simulation owner.

## Planning and editing

The heading shows authoritative simulation UTC, operating quarter, eligible planning
quarter, selected quarter, UTC publication deadline, commitment status, preceding
published baseline and frequency count. Rows show flight numbers, permanent service
identities, frequency numbers, endpoints, aircraft registration, weekdays,
origin-local departure/timezone and exact USD fare. Revision numbers are freshness
facts, not primary player labels. A separate plan selector permits read-only review
of existing plans; selecting a historical or published quarter grants no edit permission.

Controls construct existing certified request types: create service, revise frequency
(including permitted aircraft/time/day/commercial facts), fare revision, add frequency,
remove frequency, explicit continuation, endpoint replacement and explicit retirement.
Aircraft, airport and weekday selectors are reused. Backend-owned input projection
resolves the existing route connection, installed capacity and currency; Scheduling
derives timing and allocates identity. Kivy calculates no demand, capacity, timing,
positioning or publication rule. Endpoint replacement uses a new service; removal
does not retire it. Retirement has explicit confirmation and retains commitments/history.
It still rejects while editable continuation remains, as the certified command requires.

Missing-plan carry-forward rows are labeled as a preview. Continue initializes the
complete editable baseline; Create also seeds that baseline through the existing
command. Direct edits of a preview explain that initialization is needed. Published
and unrelated closed quarters disable ordinary editing. Rejections show actual
code, path and message; the UI does not repair or reinterpret rejected intent.
Planning edits change the plan in memory. Save Game/bookmarks remain the distinct
disk-persistence actions. No long-term blueprint feature is implemented.

## Readiness, publication and recovery

Inspect readiness invokes the immutable Stage 3A query explicitly at its paused
completed boundary. It separately presents publication eligibility, planning
feasibility and execution readiness, including actual positioning and contract
diagnostics. Missing-plan results remain unavailable rather than inventing a proof.
Hypothetical repositioning is explained as planning only: it creates no flight or
aircraft movement. Readiness never authorizes a command.

Manual Publish pauses through the existing session/runtime drain boundary, inspects
readiness and prepares the existing Stage 3C command. Confirmation names the target,
frequency count/services on the current page, complete edited plan versus carry-forward,
informational eligibility/execution diagnostics and irreversible commitment/eligible
booking consequences. It explicitly states that fresh validation is required;
preparation does not guarantee acceptance. The message scrolls for long diagnostic
lists and places the irreversible warning before blockers, preserving every diagnostic
without hiding the commitment. Confirm invokes the exact owner-issued
preparation through apply, preserving all four full gates and both world copies.
Failure shows authoritative diagnostics and consumes no partial commitment.
No modified-data retry is implicit. Success refreshes the eligible quarter and
leaves simulation UTC and operating dates unchanged; the committed plan is locked.

The persisted Stage 3D failure is visible both in the global status and Scheduling
page, including affected quarter and structured diagnostics. Session Resume rejects
while that fence exists. The default editing view selects the genuinely fenced
unpublished target even when the normal planning target has advanced. Other selected
quarters disable GUI editing while fenced. A missing fenced plan explains that
initialization is required before readiness inspection; it never queries an unrelated
normal planning quarter. Certified
commands alone implement the narrow correction exception. Correction leaves the
fence intact. **Retry publication** processes one event through the existing kernel
reconciliation/publication engine with fresh facts; it does not clear a fence or
advance its frontier from Kivy. Unchanged failure preserves the saved obligation.
Success refreshes the normal planning context; Resume remains a player action.

## Published supply, bookings, operations and persistence

Published day browsing selects an origin-local date and pages at 32 frequencies.
Scheduling constructs applicable explicit Stage 3B references, each checked against
selected published membership and UTC-quarter applicability. The existing immutable
resolver retains both source gates and the maximum 128-reference limit. Query limits
outside 1–128 reject. No full-quarter expansion or operational materialization occurs.
Rows retain service/date/slot key, flight number, aircraft, UTC departure/arrival,
publication timestamp and exact plan/version. Existing materialized outcomes decorate
them with confirmed/locked/carried seats and operational status. Unsold published
descriptors show zero seats occupied without allocating rows/events. Finance/history
remain the existing detached session pages and their Stage 3E lineage.

GUI widgets and the headless controller never borrow world dictionaries. The session
uses its established validated owned-read epoch and bounded detached planning-page
cache. Arbitrary foreign bindings reacquire the existing full gate. Ordinary screen
refresh does not repeatedly invoke readiness, occurrence validation or full command
validation; these are explicit inspection/command actions. Read projections belong
to Scheduling, not widgets. There is no Booking365 supply union or added writer.

Manual saves, rotating autosaves, named bookmarks, world unsaved guards, pause/drain,
separate load validation and paused restoration retain their existing session paths.
A runtime-only binding counter revokes page selection, readiness, confirmation and
aircraft context on New/Load/rebind, including same-byte replacement. Active forms and
occurrence dialogs close on departure/rebind. No GUI cache, descriptor, form or
confirmation is serialized. Saved fences reconstruct from authoritative reads.

## Verification and measurements

Focused command: `.venv/Scripts/python.exe -m unittest tests.test_quarterly_gui -v`.
Final focused run: **45 PASS in 45.799s**, including **seven native Windows Kivy
cases**, Python 3.12.10 / Kivy 2.3.1 / SDL2 / OpenGL 4.6 Intel UHD Graphics.
The native cases construct real widgets, navigate, open and submit a service form,
confirm publication, preserve long blocked-confirmation diagnostics and their warning,
close stale forms after rebind and assert a usable service
viewport at 1000×720. A temporary native render at 1200×900 was visually inspected;
fixed-panel occlusion was corrected to show both services and the same compact layout
is regression-covered. This is automated native
smoke evidence, not human touch/layout acceptance or runtime capacity certification.
Initial import/test-fixture errors were corrected before the final focused run;
no domain validation or formula was weakened.

The focused tests cover isolated entry/default legacy behavior, literal quarter and
deadline, command identity/locks, diagnostic-only readiness, explicit confirmation,
failure atomicity, real automatic fence/correction/retry, paused saved recovery,
stale object revocation, bounded pure browsing, positive sold-seat/finance visibility,
no additional operational writer and native/session-only ownership. The full suite,
explicit regression group, scoped compilation and documentation checks are recorded
with final results in [Current Development Status](Current%20Development%20Status.md).
Final full discovery: **1,571 PASS in 2,311.770s**, exit 0, no failures/skips,
baseline 1,526 plus 45 new cases. All **322 source/test SHA-256 witnesses** match
before/after the frozen run. Final affected legacy GUI: **89 PASS in 243.434s**.
Commit preparation removed one extra trailing blank line in the new test file;
pre-cleanup bytes matched the freeze and its before/after ASTs are identical.
Preceding quarterly/GUI integration candidate: **293 PASS in 866.772s**; final
confirmation-only changes are covered by the focused/legacy/final full runs.
Scoped compilation, **410 local links / 67 heading targets / 8 Markdown documents**,
whitespace, exact 18-file scope and final self-review pass.
Superseded full/regression runs were stopped for fence edge cases and native layout;
only the final source freeze is eligible for completion evidence.

Run `.venv/Scripts/python.exe -m tests.profile_quarterly_gui` for the committed small
measurement harness. Three samples per operation, setup/cloning and prior publication
excluded; validation/copy work belonging to the measured operation is included.
One aircraft, one Q2 plan, two daily round-trip frequencies, zero stored flights/bookings.
Compact sorted JSON world size: **321,476 bytes** draft / **321,494 bytes** published;
no SaveStore wrapper. Native construction/refresh timings include widget work; Load
timing includes separate-candidate validation and controller refresh, not a disk Save
or native page redraw. Final-source measurements ran concurrently with full discovery
and the regression group; timings are observations under that background load.

| Operation | Median seconds | Minimum | Maximum |
| --- | ---: | ---: | ---: |
| Open native planning | 0.023195 | 0.022955 | 0.031804 |
| Cold detached service page | 0.000382 | 0.000365 | 0.000413 |
| Readiness inspection | 0.094502 | 0.086454 | 0.137660 |
| Published day, two references | 0.111787 | 0.101292 | 0.131036 |
| Fare edit and native refresh | 0.291296 | 0.271207 | 0.331317 |
| Manual prepare and confirmation apply | 0.453747 | 0.421492 | 0.534244 |
| Load and controller refresh | 0.192185 | 0.179458 | 0.194687 |

These small empty-history fixtures do not establish large-world scalability.
Full readiness/occurrence gates, command copies/chronology, source discovery,
retained aliases and existing manifest/history projections retain their real costs.
The page selector shows the latest 64 owner plans; retirement choices the latest
128 retained owner services; continuation shows a bounded 32-frequency source page.
Historical browser expansion/virtualization and larger-world UX/performance evidence
remain limitations, not permission for unrelated optimization or history pruning.

Stage 3G general activation, 3G-C capacity work, automatic positioning, new booking
economics/consumers, airport queues, long-term blueprints and unrelated marketplace
fixes remain excluded. Ordinary quarterly gameplay remains dormant.

## Exact changed-file scope

- [Schema](Stage%201%20State%20Schema.md)
- [Template mirror](../../Data/Templates/template_reference.txt)
- [This GUI contract](Quarterly%20Planning%20GUI.md)
- [Current Development Status](Current%20Development%20Status.md)
- [Decision Register](Decision%20Register.md)
- [Documentation index](../README.md)
- [Quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md)
- [GUI foundation](PH%20GUI%20Foundation%20Technical%20Specification.md)
- [Backend successor notice](Quarterly%20Backend%20Consumer%20Cutover.md)
- [Session](../../app/session.py)
- [Controller](../../app/quarterly_planning.py)
- [Kivy shell](../../app/gui/app.py)
- [Development launch entry](../../app/gui/__main__.py)
- [Quarterly page](../../app/gui/quarterly_page.py)
- [Scheduling presentation queries](../../game/scheduling/quarterly_presentation.py)
- [Isolated backend capability docstring](../../game/scheduling/quarterly_backend.py)
- [Focused tests](../../tests/test_quarterly_gui.py)
- [Measurement harness](../../tests/profile_quarterly_gui.py)
