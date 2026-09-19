# PH 1.0 Step 4 — Continuous Runtime

Approved implementation scope: user request, 2026-09-17. Implementation and
verification status are recorded separately in
[Current Development Status](Current%20Development%20Status.md).

## Authority and scope

This increment implements the existing [PH step 4](Stage%201%20Implementation%20Roadmap.md#philippines-10-release-sequence)
and [Aircraft Operations clock contract](../01%20Core%20Simulation/Aircraft%20Operations%20Technical%20Specification.md#3-authoritative-simulation-clock).
It preserves the canonical [schema](Stage%201%20State%20Schema.md#clock-and-event-contract),
schema version 5, domain ownership, event order and complete-event transactions.
No new persistent field or migration is introduced.

The player explicitly approved continued simulation during management navigation,
current-world validation of edits without automatic pause, retained credit during
ordinary delays, suspension exclusion, and a measured 50-aircraft 7x acceptance gate.
Disk persistence, offline progression, AI, leasing, used aircraft, extra speeds,
formula changes, graphics and broad kernel redesign remain outside this increment.

## Clock and pacing

New sessions start paused. `/resume` sets the existing NORMAL ratio to 7 and
enters NORMAL; `/pause` enters PAUSED. FAST remains a generic kernel capability
and is not exposed as an additional terminal speed.

`game.simulation.pacing.RuntimeController` converts monotonic **active uptime**
to integer simulation-nanosecond credit at exactly 7:1. Only whole simulation
seconds become explicit kernel targets. Fractional credit, last clock sample,
the active iterator, diagnostics and backlog timers are runtime-only objects.

Windows uses `QueryUnbiasedInterruptTime`, which excludes suspension. Ordinary
CPU delays and input waiting count as active uptime; suspension and closed-game
time do not. Unsupported active-clock platforms fail explicitly rather than
substitute a suspension-inclusive clock. Tests inject their own active clock.

Pause retains already-earned credit and pending iterator work. Paused elapsed
time adds none. Resume continues that work without resetting its processing
limits. An explicit manual jump replaces the automatic pacing target and its
credit; it ends paused. Close stops the controller and releases its iterator.

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

The controller uses a 120-active-second backlog threshold with a
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
