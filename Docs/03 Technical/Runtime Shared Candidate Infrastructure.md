# Runtime Shared Candidate Infrastructure — Stage 3A

Approved implementation slice, 2026-10-04. Baseline:
`1682c0b3c47a8a102da2d2ee2ffb172ea237ea29`, verified against live origin/master.
The [canonical event contract](Stage%201%20State%20Schema.md#clock-and-event-contract)
prevails over this implementation description. Schema remains **7**.

## Scope and defaults

Strict execution remains the production default and independent reference.
Session, terminal, explicit Advance, pacing and Kivy do not opt into shared work.
Stage 3B–3F, domain certification, reduced validation, multi-event pacing, recovery,
threads, formula changes and history compaction are not implemented.

`begin_resolution(..., shared=True, shadow=False, max_batch_events=8,
execution_state=...)` opts into the infrastructure request. Every candidate event
still receives complete world validation; final validation and a detached commit
follow. There is no validate-at-end-only switch. Arbitrary stop callbacks select
the unchanged strict request. Count bounds, not wall time, bound Stage 3A work.

## Callable-bound contracts

`game.simulation.execution_contracts` defines frozen STRICT/SHARED/FENCE metadata:
actual callable, contract version, proof description, replay eligibility, supported
schemas and shadow-only fixture status. Registration has no public certification
argument. Unknown/custom registrations default strict; stale metadata for another
callable is ignored. The shared startup initializer binds all seven domain handlers
to their strict/fence metadata without relying on GUI imports.

| Built-in | Stage 3A classification |
| --- | --- |
| Exact kernel NO_OP | SHARED infrastructure probe; full per-event validation |
| Contract Payment | STRICT, not certified |
| Flight Departure / Completion | STRICT, not certified |
| Aircraft Market Rotation | STRICT |
| Daily Booking checkpoint / weekly publication / contract expiry | FENCE |

The implementation additionally rejects non-NO_OP production shared contracts.
Private deterministic synthetic fixtures may exercise shared machinery only in
full shadow mode. They are test proof tools, not production domain certificates.

Future certification requires a precise write footprint, every affected validator
invariant and indirect dependant, local transition checks, reference/callback
restrictions, unchanged-state proof and intermediate equivalence to full validation.
A descriptive receipt or final matching hash alone cannot grant certification.

## Candidate, queue and boundaries

`SharedResolutionRequest` shares the facade's progress/boundary model. A candidate
is a local variable inside one step; the request retains no candidate between
returns. It holds only runtime counters, committed IDs and an authoritative-source
heap. Canonical selection remains `(UTC, priority, sequence, ID)` and generated
events enter the candidate heap after each lifecycle transition, before selecting
the next event. No static event sequence is preselected.

At count cap, fence/uncertified/custom/unknown/stale work, target or event-requested
pause, the valid eligible prefix flushes. The next strict event executes on a later
step, after that commit. Request-wide total/generated ceilings do not reset across
flushes or management refreshes. The generation ceiling retains the generating
event's commit and leaves the next event pending. Stale applicability is checked
before unknown-handler dispatch, preserving existing lifecycle behavior.

`boundary_requested=True` yields unchanged authority before starting more work.
Intervening validated management commands still require `management_changed=True`.
Owner-thread/exclusive-world rules remain; callbacks never receive the candidate.
Equal-time pending events can remain at a validated save/command boundary;
`current_utc_fully_resolved` remains false until due work is exhausted.

## Shared machinery and before-event evidence

Both strict and candidate paths invoke the same private kernel handler/lifecycle
primitive. Strict input/result validation and detached commits remain independently
callable. Candidate contract witnesses deep-copy simulation facts and protected
pending/history records plus the event allocator scalar; they do not copy the
entire world per event or compare a candidate against itself. These conservative
witnesses still scan/copy event history and are a remaining scaling cost.

## Failure, shadow and rollback

Handler, contract, intermediate/final validation or optimizer exceptions discard
private work. Recovery reselects each attempted event canonically through the
strict executor, committing its successful prefix and stopping at its first failure
with the original strict diagnostics. Speculative IDs/revisions/counters are not
published or charged twice. Final failure replays the whole attempted bounded
segment, not merely its last event.

If strict replay succeeds through the attempted segment, the request returns
`OPTIMIZER_DIVERGENCE`, with no innocent failing gameplay event ID. The valid strict
world is retained and the supplied runtime-only `SharedExecutionState` is disabled.
The request stops; its owner applies normal blocked/pause policy. Reuse that latch
for subsequent opt-in requests to remain strict. No automatic continuation or
session/global mutable optimization switch is introduced. Production runtime
cannot encounter this path because it does not opt in.

Optional shadow mode runs strict Next Event against a separate reference candidate
and compares complete envelopes after EVERY transition and before final publication.
It reuses the existing handlers/kernel rather than another gameplay engine. Shadow
duplicates work and is for tests/debug certification, not normal gameplay. Unapproved
strict handlers execute once, without shadow replay or duplicate external effects.
Certified shared handlers must have no external/deferred effects or retained refs.

Disable/rebind shared requests to the strict facade for rollback. No save migration.

## Owned reads, persistence and runtime

Stage 2 indexes/pages stay attached to committed authority. They are never passed
to handlers. Detached root-preserving commits invalidate their existing subtree/
revision witnesses; an owning session boundary rebinds, while foreign reads require
the existing full gate. Private candidates do not refresh/publish read epochs.

Saves include no candidate, heap, counters, metadata, proof, disable latch, diagnostic
or derived indexes. Existing saves/load/migrations remain unchanged and paused.
Manual save/bookmark/load during explicit Advance still reject. Normal autosave,
pause, exit and overload-credit behavior are unchanged. No uncommitted candidate
survives a cooperative return to a frontend.

## Verification and measurements

Focused regressions and exact gameplay oracle cover the infrastructure, intermediate
invalidity, strict prefixes, divergence, custom identity, retained refs, equal-time
and generated events, limits, save/load and Stage 2 ownership. Verification results
are recorded in [Current Development Status](Current%20Development%20Status.md).

Opt-in tooling:

```powershell
python -B -m tests.profile_shared_candidate --repeats 5 --events 64
```

It measures in-memory NO_OP and strict synthetic fallback fixtures, with setup/
equality/post-validation outside timings. Instrumented validation/whole-world clone/
commit/witness counts and tracemalloc are separate from latency samples. This is
infrastructure overhead evidence, not flight-engine improvement, sustainable Ultra,
human GUI responsiveness or 50-aircraft certification. Stage 3A intentionally pays
intermediate full gates and conservative witnesses; domain throughput work waits
for the separately approved certification slices.
