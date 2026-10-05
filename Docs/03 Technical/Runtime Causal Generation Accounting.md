# Runtime Causal Generation Accounting — Patch 1.2B

Implementation and measurement: 2026-10-05. Verified baseline local HEAD,
upstream and live origin/master:
`947de8a1a47f2b57cfc37e2fd1a95b716b4c48b8`.

Authority: [Stage 1 State Schema](Stage%201%20State%20Schema.md#clock-and-event-contract),
[Continuous Runtime](Continuous%20Runtime%20Technical%20Specification.md), and
[Shared Candidate Infrastructure](Runtime%20Shared%20Candidate%20Infrastructure.md).
This is a bounded safety correctness patch, not Stage 3G or a capacity optimization.

## Measured cause

A valid two-A320neo airline operating four daily MNL–CEB round trips per aircraft
(16 sectors/day) reaches Monday 2026-09-21 00:00 PH / 2026-09-20 16:00 UTC.
Weekly publication adds 112 unique departures and one next-publication event.
All 113 children are strictly later than the root and outside its current target.
The old request-wide allocation counter exceeded 100 and stopped before two
already-due departures. No duplicate, recursion or non-advancing timestamp exists.
One aircraft with eight daily MNL–CRK round trips reproduces the same fanout.
Fixtures use real acquisition, public weekly drafts/publication and 19 preceding
Booking checkpoints. No fabricated funds, history or aircraft movement.
Patch 1/1.1 activation behavior is not the cause.

## Exact accounting contract

- The generated-event ceiling counts **new children due at their generating
  parent's exact whole-second UTC**. This is the current causal boundary.
- The count accumulates at that UTC across all events, shared cap-eight flushes,
  strict/fence interleaving and cooperative returns in the same request.
- Processing an event at a different UTC resets the causal count. A child due
  later than its parent is future pending work and is not charged, even when
  it lies inside the finite processing target. No arbitrary window or handler
  exception is used.
- Reaching the ceiling stops only when pending work still exists at that same
  UTC. The generating event's complete transaction remains committed, the next
  event remains pending, and explicit retry begins a new request/budget.
- Default generated ceiling remains **100**; explicit Advance retains its
  existing configured **10,000**. Request-wide processed/stale ceiling remains
  **10,000**, including advancing chains. No ceiling is raised.
- All children enter the queue in existing `(UTC, priority, sequence, ID)` order.
  No event, target, elapsed time or pacing credit is discarded.

`kernel._causal_generation_accounting` and `_causal_generation_limit` own this
simulation-local generic policy. The strict iterator and shared request use
identical helpers. Shared candidates maintain speculative local counters; only
successful commits update the request counters. Generated children already
processed inside a batch have their immutable due time read from history.
Recovery discards speculative counts and reconstructs accounting from the
strictly committed prefix. No lineage, counter, index or cache becomes saved
world authority. Existing transition proofs/full validation/detachment remain.

## Before / after reproduction

Same frozen two-aircraft input, production shared resolver cap eight/default
100, finite target at publication UTC. Three-run median engine wall time; setup
and cloning excluded. Baseline class loaded from verified Git source, using
unchanged transaction/proof helpers. No benchmark changes production files.

| Measurement | Before | After |
|---|---:|---:|
| Status | BLOCKED: EVENT_GENERATION_LIMIT_REACHED | COMPLETED |
| Completed events | 1 publication | 1 publication + 2 departures |
| New publication children | 112 departures + 1 weekly | same 113 |
| Total dated flights | 560 | 560 |
| Future pending departures | 558 | 558 |
| Total pending events | 563 | 563 |
| Median wall seconds | 0.2061 | 0.4948 |

Times represent different completed work, **not a speedup comparison**. The
post-change path resolves the previously blocked due work and creates two
completion events. Every publication child remains pending and unique; next
publication is 2026-09-27 16:00 UTC. No runaway queue growth occurs.

## Regression evidence

`tests/test_causal_generation.py`: **11 passed in 48.264 s**. Covers:

- one/two-aircraft real publication fanout, due departures, generated completions,
  future child retention/uniqueness and next weekly boundary;
- arbitrary future fanout (also later processed inside the target), mixed future
  and same-time generation, and chronological budget reset;
- direct and indirect same-time loops stopping at 100; explicit retry preserves
  the next child and advances another exact successful prefix;
- advancing generators still hitting the processed-event limit;
- strict/shared full-world and ProcessingResult equality, synthetic shadow caps
  1/2/8 and mixed strict/shared boundaries;
- Booking/market/payment successors, exact finance settlement, saved authority,
  no saved counters, Normal/Fast/Very Fast outcomes and exact credit retention.

Affected infrastructure/kernel/resolver/runtime: **133 passed in 120.576 s**.
Scheduling activation/Earliest/recurrence, Payment/Flight certification, candidate
ownership and GUI scheduling polish: **159 passed in 346.318 s**.
Verification commands use the project Python 3.12 environment:

```text
python -B -m unittest tests.test_causal_generation
python -B -m unittest tests.test_shared_candidate tests.test_stage1_event_kernel tests.test_simulation_resolver tests.test_stage1_runtime
python -B -m unittest tests.test_scheduling_activation tests.test_scheduling_earliest_activation tests.test_scheduling_recurrence tests.test_payment_certification tests.test_flight_certification tests.test_candidate_ownership tests.test_gui_schedule_polish
python -B -m unittest discover -s tests
python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py
git diff --check
```

Full suite: **1059 passed in 1050.849 s**, production source/tests frozen during
the run. Scoped application compilation, **67 affected local documentation links**,
`git diff --check` and complete self-review pass. No expected authoritative
gameplay result changes. Final evidence is also in
[Current Development Status](Current%20Development%20Status.md).

## Native Windows Kivy evidence

Fresh process, real SDL2/OpenGL application/event loop, direct TEMP save Load
paused at zero debt. Two-aircraft fixture crosses weekly publication at Normal,
Fast and Very Fast: 112 new future departures retained, two active operations,
no diagnostic. Maximum measured session pump callback **0.2484 s**. Resume
continues to 16:15 UTC, pause/drain, manual save and exact paused reload validate
with zero restored credit. All artifacts/saves are TEMP, not production data.
Programmatic smoke establishes correct native execution, not human smoothness
or sustained larger-airline capacity.

## Preserved boundaries and remaining limitations

Schema **7**, persistence encoding, recurrence/horizon, gameplay formulas, RNG,
clock ordering, certification identities, fences, cap eight, speed ratios,
autosave policy, overload/credit and no-offline-progression policy are unchanged.
No GUI/domain scheduling behavior or additional handler certification is added.
Template/schema documentation clarifies runtime policy only; no persistent field.

Protection remains after a complete event: it cannot preempt an infinite or
expensive handler before return. Legitimate large work can still exhaust the
separate processed-event ceiling and require explicit continuation. Same-time
fanout deliberately remains protected. This patch does not resolve the measured
Stage 3F scalability failure and does not authorize another runtime stage.
