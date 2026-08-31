# Game State & Save Architecture

## Purpose

The save system preserves one complete, internally consistent Airline Tycoon world at an exact simulation moment. Loading that save must restore the same world, not reconstruct an approximation around the currently selected airline.

This document defines the architectural behavior. It does not authorize schema or game-code changes. Concrete field names must be approved against the repository's schema and naming reference before implementation.

## Core Rule

> A save is a versioned snapshot of the authoritative whole-world simulation at a safe event boundary.

The save includes the player airline, AI airlines, airports, aircraft, dated flights, bookings, finances, policies, the economy, active operations, pending events, world time, and deterministic simulation inputs.

`current_focus` is only a user-interface selection. It must never define the ownership or boundary of saved simulation state.

## Time Model

The authoritative save moment is an exact UTC simulation timestamp. Airport-facing interfaces may show local time, but persisted operational ordering uses UTC.

In single-player:

- simulation time stops while paused;
- simulation time stops while the game is closed; and
- a loaded game always opens paused.

Loading therefore performs no offline catch-up. Continuous-time systems resume only after the player unpauses.

## Safe Snapshot Boundary

A save may occur only between completed simulation-event transactions. It must represent either the complete state before an event or the complete state after it, never a partially applied event.

The simulation may briefly establish a save barrier while an in-progress event finishes. This barrier should be short and should not become a general gameplay pause.

Events with the same timestamp must retain deterministic ordering. Saving and loading must not reorder them.

## Authoritative and Derived State

### Persisted authoritative state

The save normally preserves:

- exact world time and calendar state;
- player and AI airline state;
- airports and mutable world state;
- persistent aircraft identities, condition, locations, assignments, and active operations;
- dated published flights and their scheduled, estimated, and actual facts;
- bookings, itinerary reservations, and capacity commitments;
- financial accounts, liabilities, loans, assets, and auditable transactions;
- airline operating and passenger-service policies;
- active disruptions and unresolved outcomes;
- the pending simulation-event queue;
- operation and entity revision values needed to reject stale events;
- deterministic seeds, stream positions, accumulators, or already resolved random outcomes;
- required historical records and compacted summaries; and
- immutable relationships between entities.

### Rebuilt derived state

Data that can be reproduced exactly should normally be rebuilt after loading, including:

- schedule-search indexes;
- network-reachability caches;
- candidate-itinerary caches;
- screen tables and sorting projections;
- world-map interpolation and rendered positions;
- regenerable dashboard summaries; and
- other performance caches whose contents are not simulation facts.

Derived data may be persisted later as an optional performance optimization, but it must be disposable, versioned separately where necessary, and never override authoritative facts.

## Persistent Identity

Every persistent entity uses an immutable internal identifier. This applies at least to airlines, airports, aircraft, routes or markets where represented as entities, dated flights, bookings, transactions, and simulation events.

Display values are not identities. An airline name, aircraft registration, route label, or flight number may change without breaking references or historical records.

References should use internal IDs and be validated during loading.

## Operational Event Continuity

The pending event queue is part of the authoritative snapshot. It preserves exact future work such as handling completions, boarding milestones, departures, arrivals, financial postings, and other scheduled simulation transitions.

Each event must carry enough identity and revision information to determine whether it is still valid. On load, the system validates the queue against active operations:

- stale events are rejected safely;
- duplicate required events are not created;
- missing required next events are reported or rebuilt by an explicit repair rule; and
- equal-time ordering remains deterministic.

Aircraft position is not saved as repeated per-frame coordinates. It is derived from the saved movement segment, segment times, path reference, and current simulation time.

## Determinism

Reloading an unchanged save and making no different player decision must reproduce the same resolved future outcomes.

Randomness must therefore be purpose-scoped and deterministic. Systems may persist stable seeds and stream positions, deterministic fractional accumulators, or resolved outcomes. They must not use uncontrolled process-global randomness that changes merely because a save was reloaded.

A player action after loading may intentionally create a new branch. Determinism does not require two different decisions to produce the same future.

## Versioning and Compatibility

Every save records at least:

- `save_schema_version`;
- `game_version`; and
- `reference_data_version`.

Save-schema changes use explicit, sequential migration functions. A save at version 4 is migrated through the approved 4-to-5, 5-to-6, and later steps rather than being silently reshaped through scattered fallback defaults.

Game and reference-data updates affect existing saves only through declared compatibility or migration rules. Updating source data must not silently change an owned aircraft's capacity, remove a used airport, rewrite financial history, or invalidate a booking.

If required mods, custom data, or referenced content are missing, loading stops before mutating the world and presents a clear compatibility report. The loader must not silently delete affected entities.

Unsupported newer save versions are rejected clearly. Older supported versions are migrated in memory and validated before play or an upgraded save is written.

## Durable File Writing

Saving is atomic from the player's perspective:

1. build a snapshot at a safe boundary;
2. serialize it to a temporary file;
3. validate the serialized snapshot;
4. make the prior valid save recoverable; and
5. replace the target only after every earlier step succeeds.

A crash or storage failure must not destroy the last valid copy. At least one prior valid backup is retained for recovery.

## Save Types

The initial player-facing system supports:

- named manual save slots;
- quick save;
- rotating autosaves;
- autosaves at configurable simulation-time intervals; and
- autosaves before major irreversible actions where practical.

The system must not write a full save after every simulation event. Autosave frequency is a policy and performance setting, not a simulation requirement.

## Historical Retention

Recent operational history remains detailed enough for disruption review, player reports, and debugging. Older routine history is compacted into daily and monthly summaries for aircraft, routes, airlines, airports, and finances as appropriate.

Major events remain individually recorded permanently where required. Examples include aircraft acquisition and disposal, major accidents or world events, bankruptcies, base or hub changes, and other milestone events.

Compaction must preserve:

- financial conservation and audit totals;
- lifetime statistics;
- achievements and milestone inputs;
- required reputation and reliability inputs; and
- references needed by permanent records.

Compaction is not permission to discard unresolved obligations or active operational facts.

## System Boundaries

- **Game State & Save** owns snapshot boundaries, serialization orchestration, validation, versions, migrations, backups, and restoration.
- **Simulation Clock** owns authoritative time and pause behavior.
- **Aircraft Operations** owns aircraft and operational-flight facts and produces resumable operational state.
- **Airport Operations** owns airport resources and queues and must expose their authoritative resumable state.
- **Passenger Demand and Booking** owns demand accumulators, bookings, itineraries, and capacity commitments.
- **Economy and Finance** own accounts, liabilities, assets, and transactions.
- **User Interface** owns `current_focus`, selected screens, and other optional presentation state.

Each domain defines and validates its authoritative save fragment. The save coordinator does not duplicate domain rules.

## Migration from the Current Repository

The current `game/game_state.py` JSON structure and day-oriented flow are legacy implementation inputs, not the target architecture. Migration should be staged:

1. introduce immutable IDs and a versioned snapshot envelope;
2. separate UI focus from whole-world ownership;
3. make each simulation domain expose authoritative snapshot and validation contracts;
4. add safe-boundary snapshot coordination and deterministic event persistence;
5. add explicit migration and compatibility reporting;
6. replace direct writes with atomic writes and recoverable backups; and
7. add history compaction only after detailed history is proven correct.

Legacy saves may be supported through a dedicated import migration. Normal runtime loading must not keep accumulating permanent compatibility guesses.

## Stage 1 Scope

Stage 1 establishes:

- a whole-world snapshot;
- exact UTC save time and paused load;
- immutable references;
- authoritative-versus-derived separation;
- event-queue and deterministic-random continuity;
- explicit versions and sequential migrations;
- atomic files and one recoverable prior copy;
- manual, quick, and rotating autosave behavior; and
- validation and compatibility reporting.

Advanced cloud synchronization, multiplayer server snapshots, user-editable save formats, replay recording, and final long-term compaction thresholds are deferred.

## Finalized Architecture

The approved model is a whole-world, exact-time, event-safe, deterministic, versioned snapshot. It preserves simulation facts and pending work, rebuilds disposable indexes, loads paused, fails clearly when dependencies are missing, and protects the last valid file through atomic replacement and recovery backups.

Schema 4 also retains immutable minimal flight results and the exact revision-1
fulfilment configuration witness. Its explicit migration schedules only future
eligible departures and performs no offline catch-up. A snapshot between
departure and completion contains the frozen operation, in-flight aircraft,
and pending completion event; after completion it contains the result,
settlement, terminal event history, and destination aircraft state.
