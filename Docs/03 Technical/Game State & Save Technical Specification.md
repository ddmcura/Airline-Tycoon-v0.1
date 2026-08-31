# Game State & Save Technical Specification

## Status and Authority

This specification translates the approved Game State & Save architecture into implementation requirements. It remains a documentation contract only. It does not itself approve edits to schemas, templates, serialization code, or game systems.

Concrete names and structures must follow the repository's authoritative template and naming rules when implementation begins.

## Required Properties

An implementation is conformant only if it provides:

- a whole-world snapshot at an exact UTC simulation timestamp;
- a completed-event transaction boundary;
- immutable entity references;
- deterministic continuation after reload;
- explicit schema, game, and reference-data versions;
- sequential migrations;
- atomic file replacement and recovery;
- strict validation before restored state becomes playable; and
- clear failure for incompatible or incomplete content.

## Conceptual Snapshot Envelope

The serialized save requires a top-level envelope conceptually containing:

```text
SaveEnvelope
  metadata
    save_schema_version
    game_version
    reference_data_version
    save_id
    slot_id
    created_at_real_utc
    simulation_time_utc
    save_kind
    content_dependencies
  deterministic_state
  world_state
  domain_snapshots
  pending_events
  history
  integrity
```

This is a responsibility map, not an approved field schema. The final representation may divide data differently provided no responsibility is lost.

`save_kind` distinguishes manual, quick, autosave, and recovery copies without changing simulation semantics.

## Snapshot Coordination

### Transaction barrier

Simulation events execute as transactions. The coordinator may begin a snapshot only when no event transaction is partially applied.

Required sequence:

1. receive a save request;
2. prevent the next event transaction from starting;
3. allow the current transaction, if any, to complete;
4. capture the authoritative simulation timestamp and event-order cursor;
5. request immutable snapshot fragments from every domain;
6. release the simulation barrier after the in-memory snapshot is coherent; and
7. serialize and validate the captured snapshot independently of continued play where safe.

If snapshot capture fails, no target save is replaced. An event handler must not call the file writer halfway through its own mutation.

### Domain snapshot contract

Each authoritative domain must expose the conceptual operations:

```text
capture_snapshot(snapshot_context)
validate_snapshot(fragment, validation_context)
restore_snapshot(fragment, restore_context)
rebuild_derived_state(restore_context)
```

Restore operations must not begin live simulation. Loading remains paused until all domains restore, cross-reference validation succeeds, and derived data is rebuilt.

## Immutable IDs and References

Persistent IDs must be stable, unique within their entity type, and never recycled inside a save lineage. Serialized relationships use these IDs rather than mutable display strings.

Minimum identity coverage:

- airline ID;
- airport ID;
- aircraft ID;
- dated-flight ID;
- booking and itinerary ID;
- financial transaction ID;
- route or market ID if stored as a persistent entity; and
- event ID.

An operation revision or equivalent generation value accompanies mutable scheduled work. When an operation is rescheduled, cancelled, or replaced, older queued events can be recognized as stale without reusing identity.

## Time Representation

All authoritative timestamps are unambiguous UTC instants. Local airport time is a calculated presentation and schedule-authoring view using the relevant airport time-zone rules.

The snapshot stores the exact simulation instant, not only a date. Duration values use an explicit unit and must not depend on frame rate or real-world elapsed time while the game is closed.

On successful load:

```text
simulation_time = saved_simulation_time_utc
clock_state = PAUSED
offline_elapsed_time_applied = 0
```

## Event Queue Serialization

Every pending event must contain enough data to determine:

- its immutable event identity;
- event type;
- due UTC timestamp;
- deterministic equal-time ordering key;
- owning entity or operation identity;
- expected operation revision;
- payload or stable references needed to execute; and
- cancellation, invalidation, or dependency information where required.

The queue itself is authoritative. On load it is validated against domain state.

Validation must detect:

- an event whose owner does not exist;
- an event with an obsolete operation revision;
- duplicate non-repeatable events;
- a required active operation with no next event;
- an event due before the saved event-order cursor without an explicit recovery rule; and
- invalid equal-time ordering data.

Automatic repair is allowed only through an explicit, deterministic, versioned rule. Otherwise loading fails with a diagnostic report.

## Deterministic Randomness

Random outcomes must be reproducible by purpose. A deterministic input should include the save/world seed plus stable domain inputs such as entity ID, game date or event ID, and random-purpose key.

Stateful random streams must persist their stream identity and position. Stateless keyed draws need not persist generated values if they reproduce exactly. Once an outcome becomes an authoritative fact, the resolved outcome should be stored rather than rerolled.

Examples include:

- tiny-demand stochastic rounding;
- handling-duration variation;
- passenger-choice allocation ties;
- operational disruption draws; and
- AI decisions whose result has already been committed.

Changing render frequency, opening a screen, rebuilding a cache, or loading the save must not consume simulation randomness.

## Authoritative Domain Contents

### World and clock

- exact simulation timestamp and calendar rules;
- world seed and deterministic cursors;
- mutable global conditions and active world events; and
- simulation configuration that affects outcomes.

### Airlines and policies

- player and AI airline identities and state;
- licenses, bases, hubs, network commitments, and owned assets;
- operating, substitution, connection, disruption, and compensation policies; and
- AI strategic state required for deterministic continuation.

### Aircraft and operations

- persistent aircraft condition, location, assignment, and ownership;
- active movement or handling segment and its start/end times;
- scheduled and actual aircraft relationships;
- dated-flight scheduled, estimated, actual, state, cause, and outcome facts;
- substitutions and unresolved recovery state; and
- airport resource or queue references supplied by Airport Operations.

### Passenger demand and booking

- demand accumulators required for correct long-term averages;
- confirmed bookings and itinerary legs;
- atomic multi-leg capacity commitments;
- unresolved passenger-service cases; and
- market and awareness state that is an actual mutable simulation fact.

Purely calculated base-demand tables may be rebuilt only when their input versions guarantee identical results.

### Economy and finance

- cash and financial accounts;
- assets, carrying values, liabilities, and loans;
- booking receipts and unfulfilled-service obligations;
- auditable transactions and their immutable references; and
- unresolved postings or settlements.

Loading and history compaction must preserve financial conservation.

## Derived-State Rebuild

After authoritative restoration and before play is enabled, rebuild derived data in dependency order. A suitable conceptual order is:

1. entity lookup tables;
2. schedule indexes;
3. airport and airline network indexes;
4. capacity and itinerary-search indexes;
5. reachability and candidate-pattern caches;
6. reporting aggregates not loaded as authoritative history; and
7. UI projections and map interpolation.

Rebuild functions must be deterministic and side-effect free with respect to authoritative state. They must not post transactions, generate passengers, advance time, or consume random draws.

## Load Pipeline

The loader follows this order:

1. read the requested file without mutating the active game;
2. verify file integrity and parse the envelope;
3. reject an unsupported newer schema version;
4. inspect required content, mod, game, and reference-data versions;
5. produce a compatibility report;
6. run explicit sequential migrations in memory when supported;
7. validate domain structures and cross-entity references;
8. validate financial invariants and the pending event queue;
9. construct a separate candidate world;
10. restore authoritative domain state;
11. rebuild derived indexes and projections;
12. run final whole-world validation;
13. set the clock to the saved instant and `PAUSED`; and
14. replace the active world only after all prior steps succeed.

A failure leaves the current menu or active world intact and gives the player a useful report. Partial restore is prohibited.

## Migration Pipeline

Migrations are explicit transformations between adjacent schema versions:

```text
migrate_v1_to_v2
migrate_v2_to_v3
migrate_v3_to_v4
```

Each migration must:

- declare its source and target versions;
- be deterministic and testable;
- preserve immutable IDs or map them explicitly;
- document any unavoidable semantic change;
- validate its output;
- avoid reading mutable live game state; and
- never overwrite the original save during migration.

Defaults introduced by a migration belong inside that migration. Normal deserialization must not silently invent missing authoritative fields.

Legacy unversioned saves may enter through one clearly identified import path. They are not evidence that all future loaders should accept arbitrary shapes.

## Reference Data and Mods

The snapshot records the reference-data version and an inventory of required external content with stable identifiers and compatibility information.

Before migration or restore, the loader reports:

- missing required content;
- incompatible content versions;
- unknown persistent entity types;
- reference records removed or changed incompatibly; and
- whether an approved migration exists.

Missing content is a blocking error by default. The system must not replace a missing aircraft with another model, remove bookings, or delete an airport silently. A future recovery mode would require its own explicit design and player confirmation.

## Atomic Write and Recovery

The file-write algorithm is:

1. serialize the coherent in-memory snapshot to a temporary file in the target storage location;
2. flush the file according to the platform's durability capabilities;
3. read and validate the temporary file, including integrity metadata;
4. preserve the existing valid target as the recovery copy;
5. atomically replace or rename the validated temporary file to the target; and
6. update slot metadata only after replacement succeeds.

At least one previous valid save is retained. Rotation must never delete the only known-good copy before the new snapshot validates.

Integrity metadata should detect truncation and accidental corruption. It is not a security boundary and need not make save files tamper-proof unless that becomes a separate requirement.

## Slots and Autosaves

The storage layer supports:

- user-named manual slots;
- one quick-save lineage;
- a configurable rotating autosave set; and
- a recovery copy associated with each actively replaced target.

Autosave triggers include configurable simulation-time intervals and approved major irreversible actions. Multiple triggers close together should coalesce into one pending save request where appropriate.

Autosaves occur only at a safe boundary. An autosave request must not interrupt and persist half an aircraft-operation, booking, or financial transaction.

## Historical Compaction

History retention uses age tiers:

```text
recent period       -> detailed records
older routine data  -> daily summaries
long-term routine   -> monthly summaries
major events        -> permanent individual records
```

Exact retention durations remain configurable and require performance testing.

Before deleting source detail, a compaction transaction must:

1. calculate summaries;
2. verify counts and conserved totals against the source records;
3. preserve lifetime aggregates and required references;
4. commit the summaries; and
5. remove eligible detail only after successful validation.

Unresolved operations, bookings, claims, liabilities, investigations, or other live references are ineligible for compaction.

## Validation Requirements

Whole-world validation includes at least:

- unique immutable IDs;
- resolvable required references;
- valid ownership and location relationships;
- no aircraft assigned to physically incompatible simultaneous states;
- capacity commitments consistent with bookings;
- active operations consistent with their next events;
- UTC timestamps and valid chronological relationships;
- balanced or otherwise conserved financial transactions;
- supported versions and complete dependencies; and
- derived rebuilds that do not alter authoritative facts.

Validation errors should identify the domain, entity ID, violated rule, and whether recovery is possible.

## Failure Handling

Saving failures keep the previous valid target and report that the new save was not committed. Loading failures never replace the active world.

The player-facing report should distinguish:

- corrupt or incomplete file;
- unsupported newer save;
- failed migration;
- missing mod or custom content;
- incompatible reference data;
- invalid cross-reference;
- broken event continuity; and
- failed financial or domain invariant.

## Performance Expectations

Snapshot work should scale with authoritative state, not rendered objects. Coordinate interpolation, UI tables, and search caches should not inflate save size merely because they are currently visible.

Serialization may occur from an immutable captured snapshot after the short simulation barrier is released. Implementation must control memory use and must not allow live mutations to leak into that captured snapshot.

Load performance should be measured separately for parsing, migration, validation, restoration, and cache rebuild so bottlenecks remain visible.

## Required Tests

### Round-trip tests

- save and load each supported domain;
- preserve exact UTC simulation time;
- preserve immutable references;
- restore pending operations and bookings; and
- rebuild derived caches without changing authoritative data.

### Determinism tests

- run from a save twice with no different decisions and compare outcomes;
- verify equal-time event ordering;
- verify random stream continuity;
- verify pause/close adds no simulation time; and
- verify rendering and screen access consume no simulation randomness.

### Transaction tests

- request saves during aircraft, booking, and financial events;
- prove snapshots occur wholly before or after each event;
- interrupt temporary-file writing and retain the old valid save; and
- fail validation without replacing the target.

### Migration tests

- migrate every supported version through every sequential step;
- validate original files remain unchanged;
- reject unsupported newer versions;
- report missing dependencies; and
- verify migration defaults are explicit and stable.

### History tests

- compare detailed totals with compacted summaries;
- preserve financial conservation and lifetime statistics;
- retain permanent major events; and
- refuse to compact referenced or unresolved records.

### Scale tests

- whole worlds containing many AI airlines;
- thousands or tens of thousands of aircraft and dated flights;
- large booking and transaction histories;
- dense pending event queues; and
- accelerated-time autosave requests.

## Implementation Sequence

1. Approve the schema and identity strategy using the repository template rules.
2. Add the versioned envelope and dedicated legacy import path.
3. Separate UI focus from authoritative whole-world state.
4. Define domain snapshot, validation, and restore contracts.
5. Establish deterministic time, event, and random-state persistence.
6. Implement candidate-world loading and derived-cache rebuilds.
7. Implement atomic writing, recovery copies, slots, and autosave rotation.
8. Add sequential migrations and dependency compatibility reports.
9. Add tested history compaction after the detailed model is stable.

No step should silently reinterpret existing game data merely to make a file load.

## Deferred Decisions

The following remain outside the first implementation pass:

- exact file format and compression choice;
- cloud synchronization and cross-device conflict resolution;
- multiplayer authoritative-server persistence;
- replay or rewind support;
- save encryption or anti-tamper requirements;
- final retention durations and autosave counts;
- user-approved recovery for permanently missing mods; and
- background-save memory and threading optimizations beyond the safe snapshot contract.

## Acceptance Summary

The Stage 1 save system is complete when a large whole world can be saved at a safe exact-time boundary, written without risking the previous valid file, loaded paused into a separately validated candidate world, and continued deterministically with all operational, passenger, and financial commitments intact.

Schema 4 validation additionally requires one-to-one topology among every
Milestone 6 completed flight, its immutable result, its single
`FLIGHT_FULFILMENT` settlement, paid/zero-fare Booking partitions, original
ticket-sale transactions, revision witnesses, and departure/completion event
history. Active operations exist only for `OPERATIONALLY_LOCKED` flights and
retain the exact frozen manifest. Event failure leaves the event pending and
all allocators unchanged.
