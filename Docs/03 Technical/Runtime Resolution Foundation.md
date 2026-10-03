# Runtime Resolution Foundation — Stage 1

Implemented scope: resolver facade and deterministic equivalence oracle.
The approved direction is bounded chronological shared-candidate resolution,
but Stage 1 retains the strict isolated event transactions described by the
[canonical schema](Stage%201%20State%20Schema.md#clock-and-event-contract).
Schema remains 7; the subordinate template and save format do not change.

## Ownership and entry points

`game.simulation.resolver` owns the shared application-facing resolution facade:

- `begin_resolution(world, target_time_utc, **kernel_options)` returns runtime-only
  `ResolutionRequest`. Its first `step()` performs the existing kernel input
  checks. Subsequent steps continue that same iterator and its cumulative limits.
- `request.step(management_changed=False)` returns `ResolutionProgress`.
  `YIELDED` means the strict kernel actually yielded after a committed event.
  Terminal status/result is the existing `ProcessingResult`: COMPLETED, STOPPED
  or BLOCKED, including unchanged diagnostics and completed/stale event IDs.
- `resolve_until(...)` synchronously drains the same request and returns the
  unchanged kernel result.
- `resolve_next_event(...)` delegates to the strict single-event command.
  It does not drain all equal-time events and retains NO_EVENT behavior.
- `request.close()` cancels remaining work without undoing commits or choosing
  a new clock mode. The caller still owns pause/fast-forward policy.

The request reports authoritative UTC, requested/unresolved target and completed/
stale counts. These are descriptions, not independent simulation authority.
No wall-time budget is introduced: the real existing event yields exercise the
cooperative abstraction. Heavy individual transactions remain non-interruptible.

The pacing controller uses `begin_resolution` and one `step` per pump.
Shared-session duration/day/UTC Advance uses the same facade; Next Event uses
`resolve_next_event`. Terminal and Kivy still consume that session. Existing
kernel commands remain strict compatibility entry points and the independent
test oracle. The facade contains no second dispatcher or gameplay engine.

Handler readiness remains the existing shared session/default controller startup
responsibility. Custom registries stay explicitly caller-owned; the facade does
not change registrations or substitute handlers.

The exclusive owner applies validated management commands between steps and
signals `management_changed=True` to refresh the kernel heap. No worker thread,
automatic retry, limit reset, changed speed, or changed overload policy is added.

## Complete boundaries

Three different concepts must remain distinct:

1. Last event committed by this request: its event ID and exact resolved UTC.
2. Current authoritative UTC and whether all pending events due through it have
   resolved.
3. Requested target, which can remain unresolved.

`request.boundary()` derives these facts on demand. Its
`current_utc_fully_resolved` is false if any pending event is due at or before
current UTC. It does not scan on every ordinary pump, change the world or establish
a persistent watermark. It assumes the existing valid, exclusively owned world.

A fully committed event snapshot is safe for save/pause/commands even if another
event at exactly the same timestamp remains pending. That snapshot is not proof
that the timestamp is fully resolved. A clock-only target completion does not
invent an event boundary. A failed event leaves the earlier committed prefix and
failed pending event intact. STOPPED and generation-limit termination may commit
an event without yielding it; progress includes that event.

Requests and their metadata never enter the saved envelope. Loading stays paused.
An interrupted request is not restored; continuation starts a new request from
the exact saved event boundary under the existing save contract.

## Oracle and identity

`tests/resolution_oracle.py` compares complete envelopes using the unchanged
kernel Next Event path, one facade request, target partitions, cooperative steps
and production SaveStore round trips in temporary directories.

Comparison includes every envelope field, including saved ui_state and metadata;
JSON object key insertion order alone is normalized. No authoritative fields,
history timestamps, journals, IDs, counters, random witnesses or clock settings
are ignored. File-wrapper real save time, serial, career/bookmark IDs and integrity
metadata are outside the world envelope, not stripped from it.

Save comparisons use current-schema paused fixtures: historical schema migration
and paused restoration are intentional behaviors, not an excuse to normalize
differences away. Tests use identical player actions at exact game-time boundaries.
Target partition invariance is tested below existing safety ceilings. Splitting a
blocked request to bypass its cumulative limits is not an equivalence guarantee.

Covered fixtures include equal-time priority/sequence/generated events, before/
at/after targets, stale and unknown handlers, failed candidates, booking capacity
contention, multiple seeds, finite/continuous recurrence, weekly publication,
departure/completion and in-flight reload, month rotation/payment, actual one-year
contract expiry, protected booked flights and matching recurrence revision actions.
Existing paced/stepped/bulk and fresh-process handler startup tests remain gates.

`python -B -m tests.profile_resolution --repeats 3` compares identical quiet and
busy worlds through strict/facade paths, with alternating order, exact output
comparison and setup/copy/hash/post-validation excluded from timing.

## Later stages and rollback

Future protected fences are DAILY_BOOKING_CHECKPOINT,
STAGE1_WEEKLY_PUBLICATION and AIRCRAFT_CONTRACT_EXPIRY. The facade records these
constraints; Stage 1 isolates every event, including custom handlers.
Before later batching, amend the isolated-candidate behavioral contract explicitly
and prove intermediate validity, prefix failure semantics and exact identity.

Rollback is caller rebinding to the unchanged strict kernel; saves need no rollback
or migration. No shared candidates, reduced validation, incremental indexes,
booking/recurrence optimization, prefix replay, background processing, map/replay
or offline progression is implemented. The future approved recovery policy
(freeze accrual, drain retained target, finish paused awaiting Resume) remains
unimplemented; current overload still pauses with retained credit.

See [runtime specification](Continuous%20Runtime%20Technical%20Specification.md),
[performance investigation](Runtime%20Advancement%20Performance%20Investigation.md)
and [current status](Current%20Development%20Status.md) for verification and limits.


## Stage 2 successor

[Runtime Trusted Reads](Runtime%20Trusted%20Reads.md) implements only session-owned
read contexts and disposable presentation lookups/pages. Resolver and kernel
transaction boundaries remain exactly as described above. Stage 3 is not implemented.
