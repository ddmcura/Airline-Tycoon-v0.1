# PH 1.0 Step 4 — Continuous Runtime

Original runtime scope: user request, 2026-09-17. Named PH speed redesign
approved and implemented 2026-10-03. Implementation and
verification status are recorded separately in
[Current Development Status](Current%20Development%20Status.md).

## Authority and scope

This increment implements the existing [PH step 4](Stage%201%20Implementation%20Roadmap.md#philippines-10-release-sequence)
and [Aircraft Operations clock contract](../01%20Core%20Simulation/Aircraft%20Operations%20Technical%20Specification.md#3-authoritative-simulation-clock).
It preserves the canonical [schema](Stage%201%20State%20Schema.md#clock-and-event-contract),
the clock fields introduced in schema 5 (current saves remain schema 7), domain ownership, event order and complete-event transactions.
No new persistent field or migration is introduced.

The original increment approved continued simulation during management navigation,
current-world validation of edits without automatic pause, retained credit during
ordinary delays, suspension exclusion, and a historical 50-aircraft literal-7× gate.
The 2026-10-03 redesign supersedes that player rate with the named ladder below.
Disk persistence, offline progression, AI, leasing, used aircraft, formula changes, graphics and broad kernel redesign remain outside this increment.

## Clock and pacing

Normal Speed = **30 game days / 24 real hours**, or 30 literal game seconds
per real second. `game.simulation.speeds` centrally defines this baseline and
the named relative ladder:

| Player speed | Relative multiplier | Literal ratio | Real seconds per game day |
| --- | ---: | ---: | ---: |
| Normal Speed | 1 | 30 | 2880 (48 minutes) |
| Fast | 7 | 210 | 411.428571… (about 6m 51s) |
| Very Fast | 30 | 900 | 96 |
| Ultra | 60 | 1800 | 48 |

New/loaded sessions start paused with Normal Speed selected in runtime-only
controller state. Explicit Resume writes the selected **literal** ratio to the
existing `configuration.clock_ratios.NORMAL` and enters NORMAL. Named GUI speed
buttons select and run; Pause retains the selected name for Resume in the open
session. A controller can select a rate while paused without starting. Switching
samples elapsed active time at the old ratio before changing rates, retains
fractional credit and complete-event iterator limits, and refreshes its queue
at the next boundary. `/resume` retains the open terminal session's selection.
Generic kernel FAST is separate from the player label Fast.

Saved ratios remain literal, including old 1/7 values. Loading does not rewrite
configuration, migrate saves or infer player selection from a saved number.
The next explicit Resume uses Normal Speed (30), never saved-ratio × 30.
Loading any current-speed snapshot similarly restores paused, without credit,
with Normal Speed selected. No new schema field/version is needed.

`game.simulation.pacing.RuntimeController` converts monotonic **active uptime**
to integer simulation-nanosecond credit using the configured literal ratio. Only whole
simulation seconds become explicit kernel targets. Fractional credit, last clock sample,
the active iterator, diagnostics and backlog timers are runtime-only objects.

Windows uses `QueryUnbiasedInterruptTime`, which excludes suspension. Ordinary
CPU delays and input waiting count as active uptime; suspension and closed-game
time do not. Unsupported active-clock platforms fail explicitly rather than
substitute a suspension-inclusive clock. Tests inject their own active clock.

Pause retains already-earned credit and pending iterator work. Paused elapsed
time adds none. Resume continues that work without resetting its processing
limits. An explicit manual jump replaces the automatic pacing target and its
credit; it ends paused. Close stops the controller and releases its iterator.

## Runtime handler initialization

The shared application session and standalone default pacing controller explicitly
call `game.simulation.handlers.initialize_runtime_handlers` before runtime use.
The idempotent initializer binds/verifies the complete built-in set: NO_OP,
flight departure/completion, daily Booking checkpoint, aircraft marketplace
rotation/payment/expiry, and weekly schedule publication. Conflicting built-in
bindings fail visibly; an explicitly supplied custom registry stays caller-owned.
Domain modules retain direct-import registration compatibility. Frontend navigation,
New Game, and incidental imports are not responsible for runtime readiness.

This is runtime-only initialization: saves persist events and payloads, never
handler callables. A directly loaded validated career gets the same handlers as
a new career without save rewriting, migration or skipped checkpoints. See
[Current Development Status](Current%20Development%20Status.md) for fresh-process
regression and displayed Load Game smoke evidence.

## Exclusive ownership and event boundaries

The terminal/application thread is the sole owner of world mutation. A bounded
input-only worker reads terminal lines; it receives no world or session reference.
The owner polls input between transactions and applies management commands
serially. The event queue still sorts by due UTC, priority, persisted sequence
and event ID. Input requests take effect at the next available completed boundary,
never at a retrospectively inferred wall-clock timestamp.

`iter_events_through` is a cooperative form of the existing processing loop.
It yields only after complete transactions; `process_events_through` drains the
same loop synchronously. The iterator retains the original target, event count
and generated-event count across yields. A validated management mutation signals
it to validate the current world and rebuild its disposable queue before continuing.
No event-limit reset occurs merely because the terminal received input.

Handler failures and processing limits pause visibly and require explicit
Resume/retry. Failed candidates remain uncommitted and pending; earlier completed
events remain committed. An event-requested pause is honored. SIGINT in the live
terminal requests cancellation; it does not interrupt a dictionary commit.

## Management and advancement

Selectable continuous runtime is the intended normal player progression path.
Explicit Advance remains a secondary player/debugging tool, with unchanged semantics.

`/pause`, `/resume` and `/status` are available at each management prompt.
Clock/status is visible while waiting for live input. Navigation never changes
the clock mode. Existing injected text-stream scripts remain synchronous and
deterministic; tests of live waiting use an injected input source and fake clock.

Purchases retain the exact original preview fingerprint and successful-command
replay rules. A stale quote rejects without mutation and reports that it must be
reviewed again. It is never silently replaced and purchased using old confirmation.
The player can explicitly pause for a stable quote; the UI never does so itself.

Weekly drafts remain detached. The original strict `WeeklyDraft.save` contract
is unchanged. The terminal uses `save_current`, which recreates the explicit legs
against a detached current world, rechecks timing, location, capacity, chronology,
continuity, conflicts and publication, and commits only the fully validated result.
It never shifts a departure or adds positioning implicitly. Failed revalidation
preserves both the live world and draft; success preserves intervening history.

Next Event still executes exactly one event. Day, Duration and UTC target use
the same fast-forward mode and event-processing loop, with cooperative input
checks between transactions, and always finish paused. `/pause` or Ctrl+C stops
bulk advancement at a completed boundary. Other live input during bulk processing
is rejected visibly; management mutations cannot interleave with that explicit
command. No event is skipped to reach a target faster.

## Performance and safety

The original literal-7× measurements below are historical acceptance evidence,
not proof of sustainable 30/210/900/1800× operation. Current named-speed smoke
results and limitations are recorded in Current Development Status.

The architecture's thousands-of-aircraft objective remains intact. This bounded
milestone requires measured 7x operation on the representative 50-aircraft PH
workload; 1- and 10-aircraft fixtures provide comparison. Larger or denser runs
may expose future work but do not authorize a scalability redesign.

`tests/profile_ph_runtime.py` constructs the full 43-airport/1,806-market world,
uses test-only funding and real acquisition/planning commands, and operates
staggered daily return pairs across five destinations. Booking, demand, departure,
completion and finance all use production handlers. It reports construction cost,
processing throughput, transaction latency, peak process working set, event-history
growth and serialized size. Its unpaced processing capacity is **not** by itself
a claim of successful live 7x pacing.

Acceptance accounts both authoritative seconds already committed and retained
simulation credit. Their sum divided by active uptime must sustain exactly 7x;
raw authoritative time is also reported because atomic transactions can leave it
temporarily behind at a sample boundary. Passing additionally requires that the
representative busy boundary recover without overload or monotonically growing
credit. This treatment does not forgive or discard backlog: every credited second
remains due and overload still pauses visibly if the threshold below is sustained.

The controller uses a 120-active-second backlog threshold (converted into game
credit using the current literal rate) with a
30-active-second grace period. Credit above that threshold must persist throughout
the grace period before a visible overload pause. Credit is retained. The measured
maximum transaction in the 50-aircraft capacity fixture is recorded in Current
Development Status. A transaction below the threshold is not made interruptible
and does not alone establish the separate 7x performance gate.

No validation, historical data or gameplay formula may be removed to meet a
performance target. Report architectural bottlenecks and unresolved acceptance
failures explicitly.

## Verification

Required evidence includes fake-clock fractional pacing, pause/resume, suspension
exclusion, closure, management while running, stale previews, current-world draft
validation, full-world paced/stepped/bulk equivalence with real PH events,
equal-time order, failures, limits across yields, cancellation and serialization
exclusion. Existing migrations, historical witnesses and domain regressions remain
mandatory, followed by the complete suite, scoped compilation and documentation
link/diff checks. Performance claims require actual measurements and host details.


## Explicit advancement performance boundary (2026-10-03)

Explicit shared-session catch-up retains the same chronological kernel and complete
handler result gates as ordinary processing. Kernel-owned candidates are reused by
nested domain operations using the exact private transaction capability; direct
public commands retain independent validated boundaries. Input, handler-contract,
complete-result and detached-commit guarantees remain. Runtime primitive-tree
cloning is internal only and does not alter JSON save encoding or accept external
object-codec bytes.

The explicit request's generated-event ceiling is 10,000, matching its existing
10,000 processed-event ceiling. Both accumulate across cooperative yields and
pause visibly when exhausted. Ordinary paced runtime keeps its 100-generation
budget and 7× behavior. Kivy may consume a bounded chunk of complete events without
rendering each one; it refreshes management projections at completion, with clock
status in place during work. UI pacing never decides authoritative simulation time.

See [Runtime Advancement Performance Investigation](Runtime%20Advancement%20Performance%20Investigation.md)
for before/after measurements, exact replay witnesses and unresolved history-scaling
limits. An expensive single transaction still blocks a frame; this is not a promise
of instantaneous long jumps or large-airline catch-up.


## Resolver foundation — Stage 1

Application/runtime resolution now goes through
`game.simulation.resolver.begin_resolution`, `resolve_until` and
`resolve_next_event`. These delegate to the existing strict kernel. Ordinary
handlers retain isolated candidates, complete validation and detached commits;
existing NO_OP/stale lifecycle paths also remain unchanged. Pacing, overload,
pause and explicit Advance behavior remain unchanged.

See [Runtime Resolution Foundation](Runtime%20Resolution%20Foundation.md) for
the runtime-only progress model, complete-event versus fully-resolved timestamp
distinction, exact-world oracle, protected future fences and staged rollback.
No shared multi-event transaction or performance optimization is introduced.


## Trusted reads — Stage 2

Session-owned Fleet/Flights/Finance reuse the validated ownership epoch rather
than revalidating unchanged authority for each screen. Runtime-only immutable
booking/event ID lookups and at most eight bounded detached page values are
discarded on commits, revisions, clock changes and world replacement. Public
arbitrary-world projections retain full gates. Every authoritative event still
uses the unchanged isolated candidate, full result validation and detached commit.
See [Runtime Trusted Reads](Runtime%20Trusted%20Reads.md) for exact ownership,
source/invalidation/persistence contracts, measurements and deferred handler work.
No Stage 3 or overload recovery is implemented.


## Shared candidate infrastructure — Stage 3A

The [canonical transaction amendment](Stage%201%20State%20Schema.md#clock-and-event-contract)
and [Stage 3A infrastructure](Runtime%20Shared%20Candidate%20Infrastructure.md)
permit explicit test/debug opt-in bounded candidates. Complete validation still
runs after every candidate event. Production session, explicit Advance and normal
pacing remain strict; no runtime policy, speed, save restriction, overload recovery,
handler gameplay or player-visible GUI change is introduced. Certification of
Payment/Departure/Completion and multi-event pumping belong to later slices.
