# Airline Tycoon - Aircraft Operations Technical Specification

> **Status:** Approved first-pass technical direction. This document translates the approved Aircraft Operations architecture into a continuous clock, event-driven state model, handling timeline, delay propagation, Hub substitution workflow, derived-position contract, operational records, and required tests. Names and example structures are conceptual until approved in the canonical schema reference. This document does not authorize code or schema changes by itself.

## 1. Technical Purpose

Aircraft Operations executes published dated flight instances without replacing Scheduling as the source of the plan.

The technical separation is:

```text
Scheduling
    publishes the dated plan

Aircraft Operations
    opens a live execution record
    processes meaningful operational events
    tracks the physical aircraft and actual timeline
    records the final operational outcome

Airport Operations
    supplies live airport resources, movement opportunities, and queue outcomes

Passenger Service
    consumes disruption outcomes and handles affected passengers
```

The implementation must preserve one traceable identity from the scheduled dated instance through the operational result.

## 2. Stage 1 Scope

The first complete technical stage includes:

- a continuously advancing single-player simulation clock;
- pause and configurable speed controls;
- normalized UTC timestamps with airport-local display;
- a deterministic chronological event queue;
- activation of published dated flights at the start of required handling;
- an individual operational state for every aircraft;
- scheduled, estimated, and actual major timestamps;
- aircraft-dependent ground-handling activity ranges;
- concurrent handling activities and dependencies;
- boarding and calculated gate-closing milestones;
- early departure after the gate cutoff when permitted;
- delay propagation through an aircraft rotation;
- simple safe speed-recovery inputs;
- Hub-only parked-spare rotation substitution;
- cancellation as a last-resort outcome;
- time-derived aircraft position;
- completed operational history; and
- deterministic save/load and fast-forward behavior.

Stage 1 does not include detailed:

- Airport Operations queues or resource algorithms;
- taxiway, gate, stand, runway, or holding-path generation;
- weather simulation;
- crew legality;
- maintenance-fault formulas;
- passenger compensation or recovery;
- diversion behavior;
- full airline-policy interfaces; or
- worker-level ground animation.

## 3. Authoritative Simulation Clock

The simulation uses one authoritative normalized timestamp.

Conceptually:

```text
simulation_time_utc
```

Internal timestamps support seconds. Most routine player-facing schedules may display only hours and minutes.

Airport-local dates and times are derived from the authoritative UTC timestamp using airport time-zone data. Local display must never become a competing source of chronological truth.

### 3.1 Single-player clock behavior

Single-player supports conceptual states such as:

```text
PAUSED
NORMAL
FAST
FAST_FORWARD
```

Exact real-time ratios remain configuration.

When paused:

- simulation time does not advance;
- operational events do not execute;
- rendering and interface inspection may continue; and
- queued future events remain unchanged.

When the game is closed, single-player simulation time remains frozen at the saved instant. Loading resumes from that exact simulation time.

A future online mode may replace this ownership with a server clock. Aircraft Operations must consume an authoritative time source rather than assume the player always controls time.

### 3.2 Speed independence

Normal speed, fast speed, and fast-forward must process the same due events in the same order and produce the same outcome from identical state.

Game speed changes how quickly the simulation reaches timestamps. It must not change:

- event ordering;
- random outcomes;
- handling durations;
- delay causes;
- operational history; or
- financial and passenger outcomes.

## 4. Event-Driven Execution

Aircraft Operations uses meaningful scheduled events rather than per-frame or fixed-tick polling.

Example:

```text
11:20:00 HANDLING_ACTIVITY_STARTED
11:35:00 BOARDING_OPENED
11:45:00 GATE_CLOSED
11:50:30 AIRCRAFT_READY
11:54:10 OFF_BLOCK
12:03:20 TAKEOFF
13:18:00 APPROACH_STARTED
13:26:15 LANDED
13:32:40 IN_BLOCK
13:47:00 DISEMBARKATION_COMPLETED
```

An event conceptually contains:

- event identity;
- event type;
- due UTC timestamp;
- affected dated operation;
- affected aircraft when applicable;
- originating system;
- deterministic ordering key;
- payload or reference data; and
- cancellation, supersession, or revision information when needed.

Exact fields remain schema design.

### 4.1 Stable ordering

Events are ordered by:

1. due UTC timestamp;
2. event-priority category; and
3. stable deterministic tie-breaker.

A conceptual equal-time priority is:

```text
complete existing work
-> release or update occupied resources
-> update aircraft location and readiness
-> evaluate dependent operations
-> create policy decisions or notifications
-> record resulting history and settlement events
```

Airport Operations defines its internal queue behavior. Its released, cleared, waiting, or denied results enter Aircraft Operations through a stable interface and deterministic timestamp.

### 4.2 Event invalidation

When an estimate or plan changes, obsolete future events must not execute accidentally.

Implementations may cancel events explicitly or attach a revision to the operation and ignore stale events whose revision no longer matches.

Completed actual events are immutable. They cannot be invalidated by later estimate changes.

## 5. Dated Flight Activation

A dated flight exists under Scheduling before Aircraft Operations begins live execution. Booking may reserve it throughout the booking horizon.

Aircraft Operations activates the dated flight when its first required departure-handling activity is due to begin.

```text
Published dated flight
    remains future Scheduling data

First departure-handling start reached
    opens live Aircraft Operations record
```

The activation time is derived from:

- scheduled off-block departure;
- required handling package;
- planned handling duration;
- aircraft and service characteristics;
- known inbound aircraft availability; and
- any required movement to the departure gate or stand supplied later by Airport Operations.

Activation is therefore event-based rather than a universal fixed number of hours before departure.

### 5.1 Initial or parked departure

For an aircraft already parked at the departure airport, activation begins at the first required preparation activity.

### 5.2 Inbound aircraft

For a continuing rotation, the next dated flight may activate while the arriving flight remains in disembarkation. Eligible departure activities begin only when their dependencies are satisfied.

### 5.3 Missing or unavailable aircraft

If the planned aircraft cannot reach the departure Hub or airport by the required timeline, Aircraft Operations updates estimates and evaluates approved recovery options rather than creating an impossible activation.

## 6. Canonical Operational States

The top-level Stage 1 operational states are conceptually:

```text
PLANNED
DEPARTURE_PREPARATION
BOARDING
READY
TAXI_OUT
AIRBORNE
APPROACH
LANDED
TAXI_IN
AT_STAND
DISEMBARKING
COMPLETED
CANCELLED
```

Exact enum names may change during schema approval, but their meanings must remain distinct.

### 6.1 State meanings

| State | Meaning |
|---|---|
| `PLANNED` | Published instance exists but live departure handling has not started. |
| `DEPARTURE_PREPARATION` | One or more required departure-handling activities are active or waiting on dependencies. |
| `BOARDING` | Passenger boarding is open; compatible preparation may continue concurrently. |
| `READY` | Required handling is complete, doors are closed, and the aircraft is ready to leave when Airport Operations permits. |
| `TAXI_OUT` | Aircraft has left the stand and is moving or waiting under its departure movement assignment. |
| `AIRBORNE` | Aircraft has taken off and is executing its airborne segment. |
| `APPROACH` | Aircraft is in the arrival phase or waiting under an arrival opportunity supplied by Airport Operations. |
| `LANDED` | Aircraft has touched down but has not reached its stand. |
| `TAXI_IN` | Aircraft is following or waiting for its assigned arrival ground movement. |
| `AT_STAND` | Aircraft has reached the gate or stand; actual in-block arrival is recorded. |
| `DISEMBARKING` | Passenger and arrival-unloading work belonging to this leg remains active. |
| `COMPLETED` | Required arrival disembarkation and leg-owned unloading are complete. |
| `CANCELLED` | The dated operation will not operate. Cause and operational consequences are recorded. |

Waiting for clearance, congestion, maintenance, handling delay, or another cause normally annotates the current state rather than creating a separate mutually exclusive aircraft state.

Diversion is reserved for later design and is not a Stage 1 transition.

### 6.2 State-transition validation

Every transition must:

- be caused by a due event or explicit approved recovery action;
- validate the operation revision;
- preserve chronological order;
- update the aircraft's physical state where applicable;
- record an actual timestamp when the corresponding actual milestone occurs;
- update downstream estimates; and
- emit owned outcomes to connected systems.

Impossible transitions must fail visibly in development rather than silently moving the aircraft.

## 7. Flight Time Definitions

The dated operation retains these concepts:

```text
scheduled_off_block
estimated_off_block
actual_off_block

scheduled_takeoff or planned takeoff estimate when useful
estimated_takeoff
actual_takeoff

scheduled_landing or planned landing estimate when useful
estimated_landing
actual_landing

scheduled_in_block
estimated_in_block
actual_in_block
```

The public departure time is scheduled off-block. Actual departure is actual off-block.

The public arrival time is scheduled in-block. Actual arrival is actual in-block.

Takeoff and landing are separate operational events used for airborne duration, fuel, airport movement, and operational history.

### 7.1 Timestamp mutability

```text
Scheduled timestamp:
    copied from the published dated plan and never rewritten by operations

Estimated timestamp:
    recalculated whenever material information changes

Actual timestamp:
    unset until the event occurs, then written once and immutable
```

Corrections to corrupted or externally imported history require an explicit migration or administrative process, not ordinary operations.

## 8. Handling Packages

Each dated operation resolves a required handling package from its aircraft, service, airport, and operational context.

Possible packages include:

- first departure after overnight parking;
- normal intermediate turnaround;
- terminating arrival;
- same-aircraft through service;
- domestic departure;
- international departure;
- post-maintenance release;
- deadhead or positioning flight; and
- future special-service packages.

Packages select required activities and dependency rules. They do not directly replace the calculated activity timeline with one opaque total.

## 9. Handling Activities

Handling activities are timed sub-processes under the dated operation. They may be visible to the player while remaining below the top-level state machine.

Possible activities include:

- passenger disembarkation;
- baggage and cargo unloading;
- cabin cleaning;
- catering;
- fueling;
- potable-water service;
- lavatory service;
- routine inspection or minor servicing;
- baggage and cargo loading;
- passenger boarding;
- doors closing; and
- dispatch or readiness checks.

Not every operation requires every activity.

### 9.1 Arrival and departure ownership

The arriving leg owns:

- passenger disembarkation;
- arrival baggage and cargo unloading; and
- other work specifically required to finish that carried leg.

The departing leg owns:

- cleaning required for departure;
- departure fueling;
- catering for the new service;
- departure baggage and cargo loading;
- boarding; and
- departure readiness checks.

This avoids counting the same work twice.

An arriving leg may remain `DISEMBARKING` while eligible activities for the next dated leg enter `DEPARTURE_PREPARATION`. Dependencies still prevent impossible overlap.

## 10. Handling Duration Resolution

Every required activity uses aircraft- and context-dependent duration inputs.

Conceptually:

```text
activity minimum
activity normal maximum
aircraft or configuration input
handling package input
airport or handler capability input
operating-policy input
deterministic random draw
known disruption extension
```

The resolved duration must never fall below the safe minimum.

Example prototype data may resemble:

```text
A320 cleaning:     12-20 minutes
A320 fueling:      15-25 minutes
A320 baggage load: 15-28 minutes
A320 boarding:     20-35 minutes
```

These are examples, not approved balance.

### 10.1 Deterministic activity randomness

The duration draw uses stable inputs such as:

```text
save simulation seed
dated operation identity
actual aircraft identity
activity type
activity occurrence or revision
purpose-specific random stream
```

Reloading or changing game speed must not reroll the activity duration.

### 10.2 Handling policy

A future policy may conceptually choose:

```text
ECONOMY
STANDARD
EXPEDITED
```

Policy influences the duration distribution and cost or resource request. It cannot violate the safe minimum.

Exact cost, staffing, equipment, quality, and risk effects belong to Ground Handling, Finance, Airline Operating Policies, and later technical work.

## 11. Activity Dependencies and Concurrency

Handling uses a dependency graph rather than one serial list.

Conceptually:

```text
DISEMBARKATION_COMPLETE
    -> CLEANING may start
    -> some departure preparation becomes eligible

CLEANING_COMPLETE
    -> BOARDING may become eligible

FUELING and BAGGAGE_LOADING
    may overlap with other compatible work

ALL_REQUIRED_READINESS_ACTIVITIES_COMPLETE
    -> aircraft may become READY
```

Compatibility and safety rules are configurable inputs from the owning Ground Handling or Airport Operations design. Aircraft Operations consumes their permission and completion results.

### 11.1 Critical path

Earliest readiness is the completion time of the final mandatory dependency on the critical path, not the sum of every activity duration.

Whenever an activity begins late, extends, completes early within its resolved duration rules, or is blocked, Aircraft Operations recalculates:

- earliest aircraft-ready time;
- estimated off-block time;
- estimated takeoff;
- estimated landing and in-block arrival;
- the next flight's handling eligibility; and
- downstream estimated times for that physical aircraft rotation.

## 12. Boarding and Gate Cutoff

Boarding-open and gate-closing times are calculated milestones for each dated flight.

They may depend on:

- aircraft and cabin configuration;
- booked passenger count;
- boarding method and usable doors;
- gate or remote stand;
- domestic or international processing;
- airport and terminal capability;
- handler capability and policy; and
- known disruption.

The scheduled off-block time remains the target. Boarding milestones are calculated backward or forward as appropriate to support that target while respecting actual aircraft availability.

### 12.1 Late inbound effect

If the aircraft arrives late, departure activities begin from their actual earliest eligible times. The system does not pretend that handling occurred before the aircraft arrived.

Minimum safe durations remain enforced. The handling timeline shifts forward and propagates delay when the remaining scheduled buffer is insufficient.

### 12.2 Gate-closing behavior

Before the calculated gate cutoff, the flight waits for booked passengers under normal rules.

At gate closure:

- absent ordinary passengers may be offloaded;
- boarding becomes final for Stage 1;
- the operation does not repeatedly reopen boarding because later airport clearance is delayed; and
- protected connecting passengers are handled according to the connection policy supplied by Airline Operating Policies and Passenger Service.

Exceptional reopening remains future policy.

## 13. Readiness and Early Departure

The aircraft becomes `READY` only when:

- every mandatory departure activity is complete;
- boarding has closed;
- all remaining passengers are accounted for;
- doors and departure checks are complete;
- the actual aircraft is legal and available under connected systems; and
- no unresolved hard operational blocker remains.

The operation may leave before scheduled off-block time only after the calculated gate cutoff and only when Airport Operations permits stand release and departure movement.

Early actual off-block time never changes the scheduled off-block time.

## 14. Airport Operations Interface

Aircraft Operations must not implement live airport queues internally.

It requests or receives airport outcomes through conceptual interfaces such as:

```text
request gate or stand release
waiting for departure opportunity
cleared for assigned movement
runway use started
runway released
arrival opportunity assigned
holding or delay instruction received
arrival stand assigned
in-block confirmed
```

Airport Operations owns:

- gate and stand assignment;
- parking occupation;
- taxi routes and conflicts;
- departure and arrival queues;
- runway sequencing;
- holding opportunities;
- congestion;
- live throughput; and
- airport resource release.

Aircraft Operations converts those outcomes into aircraft state, estimates, actual timestamps, and delay causes.

Stage 1 may use simplified deterministic airport-duration inputs while preserving this interface boundary.

## 15. Delay Representation

Delay is derived from the difference between scheduled, estimated, and actual milestones. It is not an independent number that resets the aircraft.

Conceptually:

```text
estimated departure delay
= estimated_off_block - scheduled_off_block

actual departure delay
= actual_off_block - scheduled_off_block

actual arrival delay
= actual_in_block - scheduled_in_block
```

Early values may be negative where reporting permits.

### 15.1 Delay causes

Aircraft Operations records major delay causes and their affected interval or contribution where known.

Possible categories include:

- late inbound aircraft;
- handling;
- maintenance;
- airport congestion;
- gate or stand unavailability;
- weather;
- passenger processing;
- future crew constraints;
- connection hold; and
- knock-on operational delay.

The originating system owns the underlying cause. Aircraft Operations owns its effect on the aircraft timeline and operational record.

### 15.2 No schedule reset

If a physical aircraft remains late, all dependent operations use its actual and estimated availability. Passing midnight, advancing the date, loading a save, or reaching the next scheduled departure does not reset it to the planned timeline.

## 16. Downstream Estimate Propagation

Whenever the estimated ready or arrival time materially changes, Aircraft Operations walks the affected future rotation in chronological order.

For each later dated leg it calculates:

```text
earliest handling start
earliest ready time
estimated off-block
estimated airborne and arrival milestones
remaining schedule buffer
new propagated delay
```

Propagation stops when:

- a later schedule buffer fully absorbs the delay;
- a substitution breaks the dependency chain;
- the future assignment is revised or cancelled; or
- the materialized operational horizon ends.

This forecast updates estimates only. It does not prematurely write actual timestamps.

## 17. Speed-Based Recovery Contract

For an airborne segment, Aircraft Operations may request a cruise strategy supplied by Airline Operating Policies.

Conceptually:

```text
NORMAL_OR_ECONOMICAL
RECOVERY
```

Aircraft performance supplies permitted speed bounds. Fuel Management or aircraft performance supplies fuel consequences. Finance records resulting costs.

The operational calculation returns:

- selected safe cruise speed;
- revised estimated airborne duration;
- estimated time recovered;
- additional fuel use or cost input; and
- any aircraft-performance consequence approved later.

Recovery cannot exceed certified aircraft limits or cancel ground, traffic, weather, or handling delays.

Exact formulas remain deferred.

## 18. Hub-Only Substitution Eligibility

Substitution may begin only at an airline Hub containing a compatible aircraft currently in parked-spare state.

An ordinary Served Airport or Operating Base without Hub status cannot perform this operational substitution handoff.

The spare must be:

- physically at the Hub;
- parked and not executing another operation;
- released from maintenance and other legal restrictions;
- compatible with the route and airports;
- capable of the required range and performance;
- compatible with the permitted passenger capacity and cabin rules; and
- free of another scheduled obligation that conflicts with the takeover.

Exact compatibility tolerance and capacity-reduction handling remain policy and Passenger Service decisions.

## 19. Rotation Takeover

Substitution transfers actual operational responsibility for a continuous section of the planned rotation without changing the recurring schedule's planned aircraft.

Example:

```text
Aircraft A is delayed before reaching Hub MNL.
Aircraft B is parked spare at MNL.

At the approved replacement point:
Aircraft B takes A's next scheduled leg from MNL.
```

The rules are:

1. Aircraft A completes every actual leg before the replacement point.
2. Aircraft B begins the takeover only from the Hub where it is physically parked.
3. Aircraft B follows Aircraft A's remaining geographically continuous rotation.
4. Aircraft A reaches the Hub and parks.
5. Aircraft B continues until the assumed rotation returns to that same Hub.
6. At that Hub return, Aircraft A may resume if ready and eligible.
7. Aircraft B is released and returns to parked-spare state.

Neither aircraft chases or teleports into the other's location.

### 19.1 Temporary operational assignment

Every affected dated flight retains:

```text
scheduled aircraft = Aircraft A
actual aircraft    = Aircraft B
substitution chain or takeover identity
```

The recurring schedule remains planned on Aircraft A unless the player separately revises Scheduling.

### 19.2 Original aircraft at the Hub

When Aircraft A reaches the substitution Hub after the takeover has departed, it parks. It does not operate duplicated legs or independently continue a rotation whose next location is now occupied by Aircraft B.

It may remain available for another explicitly approved recovery action only if that action does not break the promised handback and policy rules.

The safe Stage 1 behavior is to reserve it for handback.

### 19.3 Handback

When Aircraft B returns to the substitution Hub:

- validate that Aircraft A is ready;
- validate that the next planned leg begins at that Hub;
- end the takeover assignment;
- restore Aircraft A as actual operator for following legs; and
- return Aircraft B to parked-spare state.

If Aircraft A remains unavailable, Aircraft B may continue the rotation under the same takeover until a later return to that Hub or until policy selects another valid action.

Unusual multi-Hub rotations, schedule revisions during takeover, spare maintenance, and conflicting recovery actions remain later technical cases.

## 20. Substitution Decision and Policy

The operational engine may receive one of these conceptual policy modes:

```text
OFF
NOTIFY
AUTOMATIC
```

Stage 1 must always validate physical and technical eligibility regardless of policy.

Policy may later rank multiple spares using:

- exact type or family match;
- capacity difference;
- cabin compatibility;
- operating cost;
- maintenance condition;
- future scheduled need; and
- priority of the disrupted rotation.

Exact ranking is deferred. Deterministic selection must prevent iteration-order accidents when candidates are otherwise tied.

## 21. Cancellation

Cancellation occurs only after the operation is impossible or exceeds the approved recovery policy.

Aircraft Operations records:

- cancellation timestamp;
- cancellation cause;
- state reached before cancellation;
- scheduled and actual aircraft situation;
- affected downstream aircraft rotation;
- booked passenger counts supplied by Booking; and
- emitted disruption outcome.

Passenger Service handles passenger recovery and compensation. Scheduling remains the owner of future timetable revisions. Finance settles costs and refunds.

A discussed twelve-hour maintenance recovery threshold remains configurable and unapproved as permanent balance.

Diversion is not implemented under this first-pass specification.

## 22. Movement Segments and Derived Position

Aircraft movement is represented through timed segments.

A conceptual segment contains:

- segment type;
- start UTC time;
- end UTC time or open-ended waiting state;
- start and end locations;
- assigned path reference when available;
- operation identity;
- aircraft identity; and
- revision.

Position is derived:

```text
progress
= clamp(
    (current_time - segment_start)
    / (segment_end - segment_start),
    0,
    1
  )

position = interpolate assigned path at progress
```

Waiting segments may use a fixed location. Holding segments may use repeating geometry and elapsed-time modulo the pattern duration after future approval.

The renderer may interpolate as often as needed without mutating authoritative aircraft state.

## 23. Movement-Path Interfaces

Aircraft Operations consumes, but does not authoritatively define:

- gate and stand positions;
- taxi paths;
- runway paths;
- departure and arrival routings;
- holding patterns; and
- simplified enroute display geometry.

Airport Operations or map/data systems provide these references.

Until detailed paths exist, Stage 1 may use simplified segments such as:

```text
departure airport position
-> enroute interpolated arc
-> destination airport position
```

Simplification must not remove the underlying timed-segment contract.

## 24. Aircraft Current-State Projection

Each aircraft requires one authoritative current operational projection containing or deriving:

- actual airport or airborne status;
- current dated operation;
- current top-level state;
- current movement segment;
- current handling activities;
- estimated next milestone;
- delay summary;
- substitution or takeover state; and
- next scheduled work.

Fleet, map, airport, and operational screens read projections from this state. They must not maintain independent writable copies.

Exact schema placement—aircraft record, world operations section, or linked indexes—remains schema design. There must still be one authoritative relationship.

## 25. Operational Flight Record

Every activated dated flight has one operational execution record linked to the Scheduling identity.

Conceptually it includes:

- dated flight identity;
- scheduled service identity and flight number;
- origin and destination;
- scheduled aircraft;
- actual aircraft;
- scheduled timestamps;
- current estimates;
- immutable actual timestamps as reached;
- current and final state;
- handling package and activity summaries;
- delay causes;
- substitution or takeover reference;
- passenger counts supplied by connected systems;
- major movement segments or summary;
- cancellation outcome when applicable; and
- operational revision.

It must not duplicate the full recurring schedule or become a second source of scheduled truth.

## 26. Operational History

After `COMPLETED` or `CANCELLED`, the live record is archived or compacted into durable operational history.

Permanent history retains:

- scheduled, estimated-final, and actual major times;
- planned and actual aircraft;
- origin and scheduled destination;
- final outcome;
- major delays and causes;
- substitution details;
- planned and actual handling duration;
- significant delayed activities;
- handling policy used;
- passengers carried or affected;
- block and airborne time;
- cycles and operational statistics; and
- references required by Finance, Maintenance, Reliability, and Passenger Service.

Temporary interpolation coordinates, UI progress values, and every minor handling event need not be retained permanently.

History-retention duration and aggregation remain technical balancing decisions. Data required for financial or reliability history must not disappear before consuming systems settle it.

## 27. Estimates and Notifications

Estimated times update whenever new material information changes the critical path or movement timeline.

Notifications should be emitted from meaningful state changes rather than repeated polling.

Possible notification levels include:

- informational delay update;
- policy action taken automatically;
- substitute selected;
- player approval required;
- cancellation risk; and
- cancellation confirmed.

Fast-forward pauses only when notification policy marks an unresolved event as requiring player input. If a standing policy safely resolves the event, processing continues and records or reports the action.

Exact notification UI and policy thresholds remain later work.

## 28. Save and Load

Saving must preserve enough authoritative state to resume the exact simulation moment deterministically.

Conceptually required state includes:

- simulation timestamp in UTC;
- single-player pause or speed preference;
- active aircraft operational projections;
- active dated operational records;
- current handling activities and their resolved durations;
- active movement segments;
- substitution takeover state;
- pending decisions requiring player input;
- deterministic random seed inputs or resolved outcomes; and
- future operational events or sufficient validated state to rebuild them exactly.

### 28.1 Queue persistence versus rebuild

The implementation may persist the event queue or rebuild it from active records after loading.

Whichever method is chosen must guarantee:

- no event is lost;
- no event executes twice;
- stale revisions do not execute;
- equal-time ordering remains identical; and
- loading produces the same future as uninterrupted play.

### 28.2 Closed-game behavior

Single-player loading does not calculate elapsed real-world time. The authoritative simulation timestamp resumes from the saved instant.

## 29. Fast-Forward and Catch-Up

When simulation time advances across many due events, the engine repeatedly:

1. reads the earliest due event;
2. advances authoritative simulation time to that event when appropriate;
3. validates event revision and prerequisites;
4. executes the event;
5. enqueues resulting events;
6. handles any required critical pause; and
7. continues until reaching the target time or pause condition.

It must not jump directly to the target time and approximate away intermediate dependencies.

UI rendering may skip intermediate animation while operational events still execute exactly.

## 30. Deterministic Random Streams

Operational randomness may affect:

- handling durations;
- future maintenance or disruption events after their systems are approved;
- permitted operational variation; and
- deterministic tie-breaking where appropriate.

Every random purpose uses a separated stable stream based on identifiers such as:

```text
save simulation seed
dated operation
aircraft registration
event or activity type
occurrence or revision
random-purpose identifier
```

Adding a new random draw in one activity must not reroll unrelated flights.

## 31. Performance Requirements

The engine must support thousands of aircraft and concurrent flights under accelerated time.

Required principles:

- priority-ordered event processing;
- active-flight and aircraft indexes;
- no per-frame operational mutation;
- no constant per-aircraft resource polling;
- derived map positions;
- event invalidation through stable revisions;
- bounded downstream propagation;
- compact completed history;
- level-of-detail rendering; and
- the same engine for AI and player aircraft.

Detailed visual calculations occur only for aircraft currently visible or selected. Operational events execute regardless of visibility.

## 32. Required Processing Interfaces

Aircraft Operations requires stable contracts with:

### Scheduling

- obtain published dated instance;
- obtain planned aircraft and scheduled times;
- obtain future aircraft rotation;
- receive effective-dated revisions and cancellations; and
- preserve dated-instance identity.

### Booking and Passenger Service

- obtain booked and expected passengers;
- obtain protected connection relationships;
- emit actual operational times and outcomes;
- emit missed-connection and cancellation events; and
- receive boarding-accounted or passenger-handling results.

### Fleet and Maintenance

- validate physical aircraft identity and configuration;
- obtain maintenance availability and legal release;
- update actual utilization, cycles, and hours; and
- expose current aircraft operation and location.

### Base and Hub Management

- validate airline Hub status;
- discover physically parked eligible spares; and
- validate spare parking and support relationship.

### Airport Operations

- request movement opportunities;
- receive waiting, clearance, release, and arrival outcomes;
- receive assigned paths or simplified duration inputs; and
- report aircraft resource release.

### Airline Operating Policies

- obtain handling, connection hold, speed recovery, substitution, and cancellation decisions;
- return actions taken and outcomes; and
- request player input only when policy does not resolve the situation.

## 33. Stage 1 Technical Tests

### 33.1 Clock and events

- pause freezes simulation time and events;
- closing and loading single-player does not advance time;
- UTC ordering remains correct across local time zones and date changes;
- normal speed and fast-forward produce identical results;
- equal-time events execute in deterministic order;
- stale-revision events do not execute; and
- loading does not duplicate or lose events.

### 33.2 Flight activation and states

- a published future flight remains `PLANNED` before handling activation;
- activation occurs at first required handling activity;
- only valid state transitions are accepted;
- actual timestamps write once at their real events;
- estimates may update repeatedly without rewriting schedule; and
- completion occurs after disembarkation, not merely at landing or in-block.

### 33.3 Handling

- required activities vary by handling package;
- durations remain within approved aircraft/context bounds;
- reload cannot reroll durations;
- concurrent activities use the critical path;
- dependencies prevent impossible activity starts;
- late inbound aircraft shifts actual handling forward;
- handling never compresses below safe minima;
- gate cutoff follows the calculated operation; and
- boarding remains closed after Stage 1 closure.

### 33.4 Delay propagation

- sufficient buffer absorbs delay;
- insufficient buffer propagates delay;
- downstream estimates update without writing future actual times;
- propagation stops after full recovery or substitution; and
- midnight or daily boundaries do not reset delay.

### 33.5 Substitution

- substitution fails outside an airline Hub;
- substitution fails without a physically parked compatible spare;
- the original aircraft completes every leg before replacement;
- the original parks on reaching the substitution Hub;
- the substitute takes the geographically continuous remaining rotation;
- affected flights retain planned aircraft and record actual substitute;
- the substitute continues until the rotation returns to the same Hub;
- handback occurs only when the original is ready at that Hub;
- the substitute returns to parked-spare state after handback; and
- neither aircraft teleports or duplicates a leg.

### 33.6 Movement and history

- derived position matches segment time;
- off-screen aircraft require no per-frame updates;
- viewing an aircraft midway through a segment produces the correct position;
- operational history preserves major facts; and
- temporary rendering data is not required to reconstruct business results.

### 33.7 Boundaries

- Aircraft Operations does not allocate gates or sequence runways;
- Aircraft Operations does not compensate passengers;
- Aircraft Operations does not rewrite the recurring schedule;
- Fleet views do not create a second writable aircraft state; and
- AI aircraft use the same event and physical-continuity rules.

## 34. Migration From Current Daily Tick

The current implementation resolves an entire day's scheduled flights and finances in one daily call. It does not represent the approved continuous operational model.

Migration should occur in stable stages:

1. introduce an authoritative continuous UTC simulation timestamp;
2. materialize a simple dated operational record from published schedule data;
3. execute one direct flight through deterministic gate-to-gate events;
4. preserve actual aircraft location and timestamps across save/load;
5. connect confirmed Booking batches to operation completion;
6. settle flight revenue and operating cost after actual outcomes;
7. add handling activities and downstream delay propagation;
8. add Hub-only spare rotation substitution; and
9. retire daily whole-flight resolution only after equivalent playable reporting and tests exist.

This specification does not authorize that migration yet.

## 35. Airport Operations Spillover

The following are explicitly outside Aircraft Operations technical ownership:

- gate and stand assignment;
- parking-capacity calculations;
- airport resource occupation;
- taxiway graph and pathfinding;
- departure and arrival queue algorithms;
- runway sequencing and separation;
- holding assignment;
- congestion calculation;
- live airport throughput;
- airport movement conflicts;
- airport-specific path geometry; and
- detailed diversion-airport availability.

Aircraft Operations requires interfaces to those outcomes but must not pre-empt their design.

## 36. Deferred Technical Decisions

The following remain open for implementation planning or balancing:

- exact single-player speed ratios;
- final schema names and locations;
- persisted queue versus deterministic rebuild;
- event-priority numeric values;
- exact operational activation calculation;
- handling-package data format;
- activity minimum and maximum values;
- dependency and compatibility data format;
- policy cost and duration curves;
- boarding-open and gate-cutoff formulas;
- exact downstream propagation horizon;
- speed and fuel recovery formulas;
- spare compatibility tolerances;
- substitution candidate ranking;
- exceptional multi-Hub takeover behavior;
- cancellation thresholds;
- operational history retention duration;
- map path formats;
- performance budgets; and
- diversion behavior.

These open details are not permission to restore daily whole-flight execution, teleport aircraft, perform substitution outside Hubs, or move Airport Operations mechanics into Aircraft Operations.

## 37. Final Technical Rules

```text
Aircraft Operations consumes published dated flights and preserves their
identity. Scheduling remains the source of planned times and aircraft.

The authoritative clock is continuous UTC with second-capable timestamps.
Airport-local time is a display and scheduling projection.

Single-player simulation stops while paused or closed. Normal speed and
fast-forward process the same deterministic chronological events.

A dated operation activates when its first required departure-handling activity
begins, not at one universal fixed pre-departure interval.

Top-level operational states coexist with concurrent timed handling activities.
Handling duration is aircraft- and context-dependent, deterministically random
within valid bounds, policy-influenced, and never below the safe minimum.

The arriving leg owns disembarkation and arrival unloading. The departing leg
owns departure preparation, loading, boarding, and readiness work. Adjacent
records may overlap while dependencies preserve physical reality.

Scheduled and actual departure are off-block times. Scheduled and actual arrival
are in-block times. Takeoff and landing remain separate operational timestamps.

Calculated gate cutoff governs passenger waiting. After closure, Stage 1 does
not repeatedly reopen boarding. Early off-block departure requires readiness
and Airport Operations permission.

Delay propagates through the actual physical aircraft rotation and is absorbed
only by real buffer or recovery. Dates and schedules never reset physical delay.

Substitution occurs only at an airline Hub using a compatible physically parked
spare. The original aircraft completes all legs before the replacement point
and parks at the Hub. The spare follows the remaining continuous rotation until
it returns to that Hub. The original may then resume and the substitute parks.

Aircraft motion is represented through timed segments and derived position,
not persisted per-frame coordinates.

Airport Operations owns live airport resources, queues, sequencing, and path
assignment. Passenger Service owns passenger recovery and compensation.

Operational history preserves major planned and actual facts while temporary
rendering and fine-grained live activity data may be compacted.

Save/load, fast-forward, randomness, and equal-time processing are deterministic.

The technical architecture is introduced through small, playable, tested stages.
```
