# Stage 1 Implementation Roadmap

## Purpose

This roadmap converts the approved Airline Tycoon architecture into an implementation sequence. Its goal is a small but complete playable simulation rather than a collection of disconnected subsystems.

This remains a planning document. It does not itself authorize schema or code changes. Before each implementation milestone, concrete structures must follow `Docs/template_reference_with_rules.txt` and the approved technical specifications.

## Stage 1 Outcome

The first vertical slice must allow this complete loop:

```text
Create an airline
→ establish a base or hub
→ acquire one aircraft
→ create a directional market connection
→ publish dated flights
→ generate daily booking intentions
→ accumulate bookings on future flights
→ operate those flights through timed events
→ record revenue, expenses, and aircraft results
→ save and reload the exact world
```

Success means every arrow is backed by authoritative state and tests. A beautiful interface is not required for this milestone.

## Architectural Baseline

The vertical slice must preserve these separations:

- World Demand determines how many people want to book an airport pair.
- Booking determines whether they find and reserve an acceptable itinerary.
- Scheduling defines published future flights.
- Aircraft Operations determines what physically happens at operation time.
- Economy records money movements and obligations.
- Game State & Save preserves the whole world at an exact safe moment.
- User interfaces display and command the simulation but are not its source of truth.

No Stage 1 shortcut may collapse these into a per-flight demand calculation or a one-day financial roll.

## Repository Reconciliation

### Retain and adapt

The current repository contains useful behavior that should be preserved through focused adapters or refactoring:

- aircraft reference-data loading;
- airport reference-data loading and airport lookup;
- aircraft purchase and registration workflows;
- directional route creation concepts;
- schedule-conflict and aircraft-continuity validation;
- deadhead-planning concepts;
- currency display conversion;
- fleet, route, schedule, and financial report presentation ideas; and
- existing unit-test patterns.

These are reusable behaviors, not approval to retain every current dictionary shape.

### Replace as simulation authority

The following current mechanisms conflict with the approved architecture and must not remain authoritative:

- `current_focus` selecting the world that gets processed;
- airline names and aircraft registrations acting as primary identity;
- `game_time.current_date` as a date-only or minute-formatted string;
- pressing **Advance One Day** as the simulation clock;
- weekly aircraft schedule blocks acting as operated dated flights;
- demand stored directly on an airline route and consumed on the operating day;
- passenger counts created when a flight operates instead of booked beforehand;
- direct addition of flight profit to cash as one combined mutation;
- random daily variation from an uncontrolled random stream;
- direct JSON overwrite during saving;
- deleting the oldest autosave before proving the replacement is valid; and
- silent recursive defaults as the normal save-migration strategy.

### Keep temporarily behind compatibility boundaries

Older menu and rendering functions may continue reading a compatibility projection while the new authoritative model is introduced. Such projections must be one-way derived views. New simulation code must not write back through the old structures.

The existing daily tick may remain temporarily as a legacy test fixture, but it must not be called by the completed vertical slice.

## Target State Responsibilities

The first approved schema pass should represent the following conceptual roots. Names remain subject to the repository schema rules.

```text
world
  metadata and versions
  simulation clock
  deterministic state
  airports and mutable world conditions
  airlines
  aircraft
  markets and airline connections
  schedule definitions
  dated flights
  demand state
  bookings and itineraries
  active aircraft operations
  pending events
  financial accounts and transactions
  history

ui_state
  current focus
  selected screens and filters
```

`ui_state` may be saved for convenience, but it never defines simulation ownership.

## Identity Rules

The schema foundation must introduce immutable internal IDs before timed operations or save migration are built.

At minimum:

- airline ID is separate from airline name;
- aircraft ID is separate from registration;
- airport identity uses a stable internal or reference identifier rather than display name;
- market-direction ID represents `origin → destination` independently of an airline;
- connection or route ID represents an airline's commercial presence in that market;
- schedule-definition ID identifies the repeating plan;
- dated-flight ID identifies one published occurrence;
- booking and itinerary IDs identify capacity obligations;
- transaction ID identifies every money movement; and
- event ID plus operation revision identifies pending simulation work.

IDs must not be recycled within a save lineage.

## Milestone 0 — Protect the Existing Baseline

### Work

- Run and record the current test baseline.
- Add characterization tests for behavior that will be retained.
- Mark legacy game-state, daily-tick, demand, and save entry points clearly.
- Establish module boundaries for the new simulation without moving unrelated UI code.

### Exit criteria

- Existing passing tests remain understood.
- Known failures are documented rather than mistaken for migration regressions.
- New code can be introduced without silently switching old menus to incomplete state.

## Milestone 1 — Schema, IDs, and World Construction

### Work

- Approve the Stage 1 schema against the template rules.
- Create a versioned whole-world state envelope.
- Introduce immutable ID generation.
- Construct a new game containing the player airline and world collections.
- Move `current_focus` into UI projection state.
- Represent money with the approved precise amount strategy and explicit accounts.
- Create validation for IDs, references, ownership, and required fields.

### Exit criteria

- A new world can be created and validated.
- Renaming an airline or aircraft registration does not break references.
- The world can contain more than one airline without changing the active simulation boundary.
- No continuous simulation is required yet.

## Milestone 2 — Continuous Clock and Event Kernel

### Work

- Store an exact authoritative UTC simulation timestamp.
- Add `PAUSED`, `NORMAL`, `FAST`, and `FAST FORWARD` clock modes with configurable ratios.
- Keep single-player time frozen while paused or closed.
- Implement a deterministic priority event queue.
- Order equal-time events using a stable tie-breaker.
- Add event transaction boundaries and operation revisions.
- Allow fast-forward to process the same events without per-frame simulation.

### Exit criteria

- Tests advance time through events rather than through a day tick.
- Pausing and reloading do not advance time.
- Equal inputs produce equal event order.
- Thousands of no-op test events can be processed without render-frame polling.

## Milestone 3 — Publishing Dated Flights

### Work

- Preserve repeating schedule definitions as plans.
- Materialize dated flights only within a configured publication window.
- Preserve scheduled departure and arrival as UTC instants with local-airport presentation.
- Attach scheduled aircraft, origin, destination, capacity, fare offer, and schedule traceability.
- Prevent conflicting or physically discontinuous aircraft assignments.
- Generate deadhead or repositioning work only through explicit scheduling rules.

### Exit criteria

- One weekly schedule produces identifiable dated flights.
- Extending the publication window does not duplicate occurrences.
- Editing a future schedule follows explicit revision rules.
- A dated flight exists before demand or operations interact with it.

## Milestone 4 — Stage 1 World Demand

### Work

- Implement `OriginDailyBookingPool`.
- Calculate `RawPairScore` for the full valid destination universe.
- Normalize stable directional `DestinationPairShare` values against that universe.
- Calculate directional `BaseDailyBookers` independently of airline service.
- Apply configurable daily demand multipliers.
- Use deterministic accumulation or stochastic rounding for tiny markets.
- Process only meaningful active cohorts without scanning every future flight for every pair.

### Exit criteria

- `MNL → DVO` and `DVO → MNL` may differ.
- Opening a route does not create or renormalize underlying demand.
- A pair with no service retains potential demand but creates no booking attempt.
- Repeated runs from the same state produce the same integer cohorts.

## Milestone 5 — Booking Pipeline

### Work

- Generate one generic Economy cohort per active directional pair and date.
- Select desired future travel dates within `MAX_BOOKING_HORIZON_DAYS`.
- Build indexed direct-itinerary search first.
- Add hub-limited connecting itinerary search after direct booking is correct.
- Score price, time suitability, journey time, connections, airline signals, controlled preference, and outside option.
- Allocate aggregated batches rather than passenger objects.
- Reserve multi-leg capacity atomically.
- Redistribute overflow when a preferred choice is full.
- Let unsuccessful Stage 1 shoppers leave without automatic backlog.
- Record booking cash receipt and the corresponding unfulfilled-service obligation.

### Exit criteria

- Future flights accumulate bookings across daily cohorts.
- Capacity cannot be oversold unless a future overbooking feature explicitly allows it.
- A connecting booking either reserves every leg or none.
- A bad only option can lose to the outside option.
- Daily intent, successful bookings, and passengers flying are separate metrics.

## Milestone 6 — Aircraft Operations Vertical Slice

### Work

- Activate a dated flight at the beginning of its departure handling block.
- Model required handling activities such as cleaning, fueling, catering, baggage loading, and boarding.
- Use aircraft-dependent configurable minimum and maximum durations with deterministic variation and policy effects.
- Allow concurrent handling and calculate the critical path.
- Process gate departure, taxi out, airborne, arrival, taxi in, gate arrival, and disembarkation as events.
- Define actual departure as leaving the gate or stand.
- Define actual arrival as reaching the destination gate or stand.
- Apply delay propagation when an aircraft cannot begin its next handling block on time.
- Record passengers carried from confirmed bookings, never from operating-day demand generation.
- Keep Airport Operations responses behind a simplified Stage 1 interface.

### Exit criteria

- One aircraft completes a timed gate-to-gate operation.
- Late arrival plus handling duration delays the next leg naturally.
- Aircraft location and operational state are always physically coherent.
- Map position can be derived from segment and time without saved per-frame coordinates.

## Milestone 7 — Economy and Flight Fulfilment

### Work

- Replace combined profit mutation with auditable transactions.
- Keep ticket cash received at booking and the service obligation open.
- Recognize ticket revenue when the booked flight is fulfilled according to the approved economy rules.
- Post fuel, handling, airport, crew or simplified Stage 1 operating expenses at their proper events.
- Post onboard food, internet, and other ancillary revenue when delivered.
- Track aircraft asset carrying value separately from cash.
- Support loan accounts and repayment events at the approved simple level.
- Produce flight, route, aircraft, airline, and daily reports from actual transactions and operations.

### Exit criteria

- Cash, revenue, expense, profit, assets, and liabilities are not treated as synonyms.
- Cancelling or failing an operation cannot recognize unearned ticket revenue.
- Flight profit is a report calculated from postings, not a direct source-of-truth field.
- Financial conservation tests pass.

## Milestone 8 — Exact Save and Reload

### Work

- Capture whole-world state between completed event transactions.
- Persist the exact UTC timestamp, active operations, pending events, versions, IDs, deterministic state, bookings, and finances.
- Rebuild schedule, network, booking-search, reporting, and rendering indexes.
- Load into a separate candidate world and open paused.
- Add explicit sequential migration functions.
- Add reference-data and missing-content compatibility reports.
- Write temporary files, validate them, atomically replace targets, and retain a recovery copy.
- Add manual, quick, and rotating autosave slots without deleting the last good file first.

### Exit criteria

- Saving during a busy operational period captures either side of an event, never half of it.
- An unchanged save produces the same future after reload.
- A failed save leaves the previous file usable.
- A failed load leaves the active world unchanged.

## Milestone 9 — Integrated Playable Slice

### Work

- Connect the existing player workflows to the new command/application layer.
- Provide non-final screens or command-line views for clock control, bookings, flight status, fleet state, and finances.
- Run the full create-to-operate-to-save loop.
- Add one simple AI airline using the same world, schedule, booking, operations, and finance engines.
- Profile publication, demand, booking, event processing, and save/load independently.

### Exit criteria

- The complete Stage 1 outcome at the beginning of this document is playable.
- Player and AI flights use the same simulation rules.
- No legacy day tick participates in the new result.
- Core outcomes are reproducible through automated integration tests.

## Simplified Stage 1 Boundaries

The following are intentionally simplified while preserving future interfaces:

- one generic Economy passenger group;
- direct booking before connecting booking;
- configurable global connection-time prototypes;
- simplified Airport Operations clearance and resource responses;
- no diversion system;
- no overbooking;
- basic aircraft substitution only at bases or hubs with a compatible parked spare;
- simplified operating-expense categories where detailed providers are not yet implemented;
- basic AI decisions on strategic intervals; and
- no offline progress.

Simplification must occur inside the owning boundary. For example, a simplified airport response is acceptable; putting runway queues inside Aircraft Operations is not.

## Features Explicitly Deferred

- detailed gates, stands, taxiways, and runway queues;
- diversions and destination closure while airborne;
- detailed passenger compensation and regulatory differences;
- advanced connection-hold and substitution policies;
- overbooking, no-shows, and probabilistic retry behavior;
- Business, First, Premium Economy, and traveler-purpose segments;
- loyalty programs and deep airline preference history;
- complex staffing and ground-handler markets;
- full depreciation, overhaul, and resale-value tuning;
- sophisticated bankruptcy proceedings beyond the approved trigger concept;
- multiplayer server time;
- cloud saves and mod recovery mode; and
- final graphics and live-map detail.

## Testing Strategy

Every milestone requires unit tests for formulas and invariants, integration tests across its immediate boundaries, and deterministic replay tests where time or randomness is involved.

The critical end-to-end fixture should use a tiny world with:

- three airports;
- two directional markets;
- one player airline;
- one optional AI airline;
- one or two aircraft;
- several dated flights;
- direct and one-stop booking opportunities; and
- enough simulated days to observe booking accumulation, operation, finances, and reload.

The fixture should be small enough for exact expected results rather than statistical guesses.

## First Coding Increment

When code implementation is authorized, begin with Milestones 0 and 1 only:

1. capture the current test baseline;
2. approve the concrete Stage 1 state schema;
3. introduce immutable IDs;
4. construct and validate a versioned whole world; and
5. provide a compatibility projection for the current UI where necessary.

Do not begin by rewriting the interface or implementing aircraft animation. The first code change should establish the trustworthy state foundation required by every later system.

## Readiness Decision

The approved architecture is sufficient to begin Stage 1 implementation. Remaining deferred gameplay subjects do not block Milestones 0 through 5. Airport Operations detail will become necessary before expanding Milestone 6 beyond its simplified interface, but it does not block the initial event-driven aircraft-operation slice.
