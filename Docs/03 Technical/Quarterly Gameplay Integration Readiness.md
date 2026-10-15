# Quarterly Gameplay Integration Readiness — Stage 3G-C Assessment

Stage 3G-D successor (2026-10-15): the separately approved guarded paid-route
development start is implemented; [status and verification](Current%20Development%20Status.md#quarterly-stage-3g-d--paid-development-start-2026-10-15)
record the resulting integration coverage. Free-route entry descriptions and
approval requests below describe the assessed baseline. Default activation and
AT-058 runtime/offline/combined certification remain outstanding.

Assessed **2026-10-15** against `67e5e3855219ad99123d29f47e448a7738369fce`.
**Default activation: not ready.** Most quarterly gameplay already exists. The
remaining release gates are runtime/offline integration and combined certification,
plus a realistic new-career entry rather than promotion of the free-route fixture.
This assessment does not complete the roadmap's Stage 3G-C certification.

## Evidence and authority

HEAD, upstream, freshly fetched origin/master, FETCH_HEAD and live remote master
matched the baseline; divergence 0/0. Tracked tree/index were clean; untracked
`.venv/` was preserved and stashes were empty. Initial fetch could not write
FETCH_HEAD in the sandbox; escalated `git fetch origin master` succeeded.
Serena activated this repository with its Python language server; installed
`get_symbols_overview` and `find_symbol` inspected Session, runtime, persistence
and domain code. No Serena REPL was assumed or used; protected tooling files
were not inspected.

Authority reviewed: [Schema 9](Stage%201%20State%20Schema.md),
[template mirror](../../Data/Templates/template_reference.txt),
[placement reference](../../Data/Templates/foldertree.txt),
[status](Current%20Development%20Status.md), [decisions](Decision%20Register.md),
[roadmap](Stage%201%20Implementation%20Roadmap.md),
[simplification audit](PH%201.0%20Architecture%20Simplification%20Audit.md),
[quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md),
[publication](Quarterly%20Shared%20Publication.md),
[boundary recovery](Quarterly%20Boundary%20Orchestration.md),
[Booking cutover](Quarterly%20Backend%20Consumer%20Cutover.md),
[GUI](Quarterly%20Planning%20GUI.md),
[paid routes](Paid%20Bidirectional%20Route%20Establishment.md),
[runtime](Continuous%20Runtime%20Technical%20Specification.md),
[AT-058 successor](Single%20Speed%2C%20Advancement%20%26%20Offline%20Progression.md),
and [save architecture](Game%20State%20%26%20Save%20Architecture.md) /
[specification](Game%20State%20%26%20Save%20Technical%20Specification.md).
Historical checkpoint statements are read with their successor annotations.

## Current implementation matrix

A = available through the ordinary app; B = development creation only;
C = backend without GUI; D = absent; E = unresolved product choice.
A for quarterly features below means an explicitly saved quarterly career loaded
in the ordinary app, **not** ordinary New Game enrollment. Code and test bodies
were inspected; tests were not freshly executed for this documentation-only task.

| Capability | Status and actual evidence |
| --- | --- |
| Normal PH New Game | A, legacy authority. `AirlineTycoonApp.create_new_game` → `Stage1Session.new_game` → `create_stage1_new_game`; no quarterly marker. `test_default_new_game_remains_legacy` in [GUI tests](../../tests/test_quarterly_gui.py). |
| Quarterly career creation/development entry | B. `new_quarterly_development_game` builds a private candidate, seeds all PH directional connections, then calls `enable_quarterly_backend_for_testing`. Empty services/plans/operations, but free routes. Flag and separate button tests enforce isolation. A normal player quarterly bootstrap is D. |
| Quarterly GUI and weekly services | A after quarterly Load; B new entry. [Page](../../app/gui/quarterly_page.py), [controller](../../app/quarterly_planning.py), Session and Scheduling commands expose create/edit/fare/frequency/continue/remove/replace/retire, readiness and bounded published-day browsing. GUI tests exercise identity, locks, freshness and rebind. |
| Manual publication | A in quarterly careers. `PublishQuarterlyPlan('MANUAL', ...)` uses owner-issued prepare/apply and confirmation; locks the revision without advancing UTC. [Publication tests](../../tests/test_quarterly_publication.py) and GUI confirmation/atomic-failure tests. |
| Automatic publication | Implemented backend, active in enrolled quarterly careers, with GUI correction/retry. Calendar boundary handler, carry-forward/committed skip and publication-before-Booking barrier; durable failure stops progress. [Boundary tests](../../tests/test_quarterly_boundaries.py) cover equal-UTC ordering, missing events, correction, repeated failure and saved fences. This is not a missing automatic-publish button. |
| Route-rights purchase/closure | A in quarterly careers through Research, with quote/confirmation, bidirectional payment, safe closure and paid reopening. [Commands](../../game/route_management/establishment.py), Session, `research_manage_route`; [route tests](../../tests/test_route_establishment.py) include normal loaded GUI, no-connection paid start and publication closure blockers. |
| Published-only Booking | Implemented and active in quarterly careers. [Checkpoint](../../game/booking/checkpoint.py) / allocation select `QuarterlySupply` by mode; drafts are excluded, no legacy supply union. [Backend tests](../../tests/test_quarterly_backend.py) cover absolute lead weights, horizon, terminal missing supply, lineage and directional demand. |
| Aircraft positioning/fulfilment | Explicit timed DEADHEAD is implemented and selectable in the quarterly GUI; actual location, chronology and contract checks remain mandatory. Dispatch and [fulfilment](../../game/aircraft_operations/fulfilment.py) produce operations/results/finance. Backend tests cover deadhead movement, rejected hypothetical positioning and exactly-once settlement. Automatic/inferred repositioning is D and unnecessary for activation. |
| Save/load/recovery | A, including quarterly saves. [SaveStore](../../game/world_state/persistence.py) preserves complete worlds/previous valid files and validates separate candidates; Session rebind restores mode and paused runtime. GUI/backend/boundary/route tests cover sold/locked/completed work, fences, missing dispatch and exact replay. No legacy conversion. |
| Pause/resume/Advance | A in both modes through existing runtime and GUI. [Pacing](../../game/simulation/pacing.py), Session, cooperative resolver and `show_advance` provide named speeds, Next Event, One day, duration and UTC target. [Speed tests](../../tests/test_player_speeds.py), [cooperative tests](../../tests/test_cooperative_runtime.py), [GUI barriers](../../tests/test_gui_cooperative_runtime.py). |
| AT-058 runtime/offline | D: current [speeds](../../game/simulation/speeds.py) are 30/210/900/1800×; standard 90×, capped offline claims/provenance/recovery and revised controls are not implemented. E: affected offline lifecycle/storage/rollout decisions remain open. |

No essential planning/publication/route operation was found in category C needing
a new GUI wrapper. Automatic publication is deliberately engine-driven. Foreign
country-access purchase and long-term blueprints are D, outside this PH activation
scope. Absence of those features does not invalidate domestic gameplay.

## Normal New Game activation trace

1. [GUI launcher](../../app/gui/__main__.py) removes `--quarterly-dev` before Kivy
   parsing. App defaults `quarterly_development=False`; its main menu adds the
   separate development button only when enabled. Ordinary New Game stays legacy
   even with the flag. Direct development callbacks also reject without it.
2. [App](../../app/gui/app.py) `show_new_game(development=False)` collects names
   and home base; `create_new_game` invokes Session `new_game` then `_enter_game`.
   There is no player career-mode selector. Legacy `game/new_game.py` is not this
   PH GUI entry path.
3. [Session](../../app/session.py) delegates authoritative construction to
   [stage1_scenario](../../game/world_state/stage1_scenario.py). The constructor
   establishes the PH reference markets, Normal/USD scenario, starter aircraft,
   empty Booking bootstrap and Schema 9 quarterly foundation roots. Empty roots
   do not activate quarterly consumers.
4. Development creation additionally seeds `_connection` for every market and
   enrolls the untouched candidate. The backend rejects processed/operational or
   elapsed careers. The authoritative distinction is existing optional
   `simulation.operational_authority = QUARTERLY_BACKEND_V1`; absence means legacy.
5. Session `quarterly_career` reads that marker. `show_view('Schedule')` selects
   QuarterlyPage or legacy scheduling; Research/Fleet handoffs follow that same
   career authority. UI focus and the process flag do not select simulation mode.
6. `load_saved` obtains a separate validated candidate from SaveStore, binds a
   fresh runtime/read epoch, and revokes old preparations/context. The saved marker
   determines screens even without the development flag; Load never enrolls.

Boundary coverage includes GUI tests `test_development_button_and_default_button_are_separate`,
`test_entry_unavailable_without_flag`, `test_ordinary_save_cannot_be_converted_on_load`,
and backend tests for untouched legacy, existing-career enrollment rejection,
legacy writer rejection and mode-preserving Session Load.

**Smallest eventual activation seam:** a Session-owned detached new-career
construction/enrollment path, called from GUI creation only after release gates.
It must omit the development connection-seeding loop. Changing the launch flag,
screen routing or empty foundation initialization alone is not activation.
No seam is changed by this assessment.

## Verified blockers and limits

| Kind | Finding and implication |
| --- | --- |
| Correctness/release safety | AT-058 requires deduplicated offline entitlement, fixed-target recovery, complete boundaries and session exclusion. That implementation is absent. Existing paused Load is correct for its present contract, not proof of future offline safety. No newly reproduced gameplay defect is claimed. |
| Missing player entry | Normal New Game cannot create quarterly careers. The development fixture grants free connections and is unsuitable as the normal paid-route start. Route purchase GUI/backend already exist; do not rebuild them. |
| Incomplete approved functionality | 90× single-speed behavior, primary Advance presentation and capped offline integration remain required by AT-058. Duration/UTC advancement already works; convenient 7/30/90-day actions are presentation work, not a missing engine. |
| Explicit decisions | Paused-close entitlement, cancellation/abandonment/older branches, crash receipts, precision/residuals, receipt/checkpoint schema/storage portability, autosave/exit-failure UX and legacy rollout remain unresolved in AT-058. Decide before affected implementation. |
| Development guards | Intentional flag, separate Session method, untouched-source enrollment checks and legacy defaults. Remove only the appropriate creation guard after combined certification; preserve old-save authority. |
| Performance/certification | Representative aged quarterly 90× performance and combined Advance/offline/save/failure certification have not passed. Strict gates/copies and request budgets remain. Historical Ultra failure is not the current mandatory gate; B3D rejected its tested local Completion boundary, not quarterly gameplay itself. No 90× or large-fleet certification is claimed here. |

Congestion, AI, multiplayer, airport queues, automatic positioning, connecting
itineraries, history redesign and an engine rewrite are not prerequisites.
Do not restart B-series optimization experiments from this report.

## Recommended next implementation slice

**Make the existing guarded quarterly development New Game a realistic paid-route
start, and certify its complete first-service workflow.** This closes the concrete
new-career integration gap while mandatory runtime gates remain outstanding. It
does not make quarterly careers the ordinary default or complete Stage 3G-C.

Player behavior: with `--quarterly-dev`, choose the separate quarterly career action,
enter names/base and start paused with the existing cash/starter aircraft but no
free route connections. Use existing Research confirmation to buy a domestic pair;
plan a physically executable passenger return chain or explicit deadhead, inspect
readiness, confirm Manual Publish, advance through existing controls, inspect
Booking/operations/finance, save and reopen paused in the ordinary app. New Game
without that separate action retains legacy behavior.

Reuse `Stage1Session.new_quarterly_development_game`, `create_stage1_new_game`,
the existing isolated backend enrollment, route quote/apply, QuarterlyPlanningController,
QuarterlyPage and current fulfilment/persistence. Remove only fixture route seeding
from this entry; free-route fixtures may remain explicit test setup. Keep world
construction/validation in World State and domain operations in their current
packages. No new abstraction or authoritative field is needed.

Save/load: retain Schema 9 marker, receipts, plan lineage and boundary obligations;
no migration or reinterpretation. Existing saved free-route development careers
remain valid and incur no retroactive charge. Legacy saves and ordinary creation
retain their current meanings. GUI selections/confirmations stay runtime-only.

Required future tests: update the development-entry assertion that currently
expects seeded connections; retain all flag/default/load isolation tests. Extend
existing route/quarterly GUI/backend tests with the actual new-entry workflow,
cancelled/stale purchase, failed enrollment preserving the active session,
publication rejection without real positioning, successful return/deadhead chain,
sold/departed/completed save replay and failed-boundary correction/retry. Use
temporary save roots, never player Saves. Run affected suites, full
`python -m unittest discover -s tests` because shared Session behavior changes,
and the repository's explicit scoped compile command. No tests are changed or run
by this assessment.

Risks/rollback: route-free starts expose unmet route/continuity prerequisites that
the fixture masked. Stop rollout for free rights, duplicated charges, changed
legacy worlds, lost saved obligations, aliasing/partial candidate exposure or replay
mismatch. Revert only the new-entry change; do not rewrite existing saves. Current
runtime overload/budget stops stay visible and are not bypassed for this workflow.

Exclusions: default activation, mode switching/converting careers, runtime pacing,
offline provenance, performance certification/optimization, new route economics,
automatic repositioning, schema/template changes and later roadmap behavior.

## Acceptance criteria and open approvals

1. Only the explicit guarded quarterly entry creates a route-free quarterly world;
   ordinary New Game remains legacy, including when launched with the flag.
2. Existing Research buys both directions with exactly one correct journal; cancel,
   stale intent and failure change no authority. Draft/published obligations block closure.
3. First-service GUI planning/publication uses existing validated commands; published
   supply alone sells, actual flight execution settles once, and no hypothetical
   positioning or full-quarter materialization is introduced.
4. Save/load at prepublication, sold, active/completed and fenced boundaries preserves
   exact authority and resumes only explicitly. Old quarterly/legacy careers retain meaning.
5. Required regressions pass; default activation remains disabled and performance
   evidence is described at its actual workload/revision scope.

User approval is needed for this bounded replacement of the development fixture
policy; it is a proposal, not an approved milestone. Later approval must resolve
the AT-058 choices above and define representative performance acceptance before
runtime/offline implementation and combined certification. Activating ordinary
New Game requires separate explicit scope approval after those gates; this report
neither waives them nor changes roadmap order.

## Assessment verification

Source/test inspection and documentation checks only; no fresh gameplay suite,
benchmark, native GUI playtest or compile run. Previous implementation evidence
remains dated in Current Development Status. Only this report, status, Decision
Register and Docs index are changed. Link/heading/whitespace and protected-scope
checks are recorded in status; commit/push outcomes are reported at delivery.
