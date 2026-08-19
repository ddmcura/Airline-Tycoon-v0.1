# Airline Tycoon - Aircraft Operations Architecture

> **Status:** Approved architecture. This document defines how published dated flights become live aircraft operations, how individual aircraft move through continuous simulation time, how operational stages and delays are represented, and how airline recovery policies affect execution. It does not finalize persistent schema fields, event-queue implementation, timing formulas, Airport Operations mechanics, passenger compensation, diversion behavior, or detailed maintenance and crew rules.

## 1. Purpose and Core Separation

Aircraft Operations turns the published airline plan into physical operational reality.

```text
Scheduling defines what the airline planned.

Aircraft Operations defines what actually happens to the aircraft.

Airport Operations controls live airport resources and movement opportunities.

Passenger Service handles affected passengers after disruption.
```

Aircraft Operations executes the dated flight instance published by Scheduling. It must preserve traceability to that instance rather than create an unrelated competing flight identity.

Aircraft Operations reports operational outcomes. It does not independently invent refunds, compensation, passenger-rights rules, airport queues, or financial settlement.

## 2. Continuous Simulation Time

Single-player game time advances continuously rather than depending permanently on an `Advance Day` action.

The player should eventually have controls such as:

```text
PAUSED
NORMAL
FAST
FAST FORWARD
```

A possible prototype pace is approximately one game day per five real-time minutes, but exact speed ratios remain balancing and interface work.

Published dated flights become live operations as simulation time reaches their required preparation and execution events. The architecture must also remain compatible with a future online mode governed by a continuously running server clock.

The current daily-tick implementation is a playable legacy stage, not the final operational architecture. Migration to continuous time must occur through stable playable stages.

## 3. Individual Aircraft and Physical Continuity

Every aircraft remains an individual persistent asset identified by its registration or equivalent unique identity.

For example:

```text
RP-C1234
```

Aircraft Operations owns or provides the aircraft's:

- current operational phase;
- current airport, stand, movement segment, or airborne state;
- current dated flight or positioning operation;
- actual operational timeline;
- physical location or time-derived position;
- delay state and major delay causes;
- actual aircraft assignment to an operation; and
- completed operational history supplied to connected systems.

The aircraft's future schedule remains owned by Scheduling. Maintenance state remains owned by Maintenance. Fleet Management presents these connected facts but must not maintain a conflicting operational status.

Aircraft may never teleport to satisfy a schedule, substitution, Base transfer, diversion recovery, or maintenance requirement.

## 4. Planned, Estimated, and Actual Flight Information

A dated flight preserves the original published plan alongside changing estimates and final actual results.

At architecture level, the system distinguishes:

```text
scheduled off-block departure
estimated off-block departure
actual off-block departure

scheduled in-block arrival
estimated in-block arrival
actual landing
actual in-block arrival

scheduled aircraft
actual aircraft

operational state
delay and major delay causes
final outcome
```

Exact persistent names remain schema work.

### 4.1 Departure and arrival definitions

The public scheduled departure and actual departure are gate-or-stand events:

```text
Departure = aircraft leaves its gate or stand for the flight.
```

Takeoff is a separate operational event after taxi-out and runway clearance.

The public scheduled arrival and actual arrival are also gate-or-stand events:

```text
Arrival = aircraft reaches its destination gate or stand.
```

Landing is a separate operational event before taxi-in.

This preserves realistic block-time behavior: taxi-out and taxi-in are part of the gate-to-gate operation, while airborne time remains separately measurable.

Delays, substitutions, cancellations, and other outcomes never overwrite the published scheduled information.

## 5. Operational Lifecycle

The player should see meaningful stages rather than only `Scheduled`, `Flying`, and `Completed`.

A conceptual lifecycle is:

```text
Scheduled
-> Positioning to gate or stand when required
-> At gate / turnaround
-> Boarding
-> Ready
-> Taxi out / waiting for departure clearance
-> Airborne
-> Approach / waiting for arrival clearance
-> Landed
-> Taxi in
-> At gate or stand
-> Deplaning / next turnaround
-> Completed or prepared for the next operation
```

These are player-facing concepts, not finalized enum or schema names.

A broad top-level phase such as `TURNAROUND` may contain several concurrent underlying activities. The game does not need to promote every cleaning, baggage, catering, or fueling activity into a separate top-level aircraft state.

Cancellation is a terminal operational outcome. Diversion is preserved as a future outcome but is not designed in this document.

## 6. Turnaround and Handling Timeline

Ground activities have real durations and may be affected by:

- aircraft type and size;
- booked and carried passenger count;
- baggage volume;
- domestic or international processing;
- airport capability;
- Base or Hub support capability;
- handling quality;
- airline operating strategy and policies;
- staffing in a future Crew or Ground Handling system;
- gate, remote stand, and boarding method; and
- disruption.

Many activities occur concurrently.

For example:

```text
Cleaning: 18 minutes
Baggage:  24 minutes
Catering: 15 minutes
Fuel:     20 minutes
```

The turnaround is therefore governed by required dependencies and the critical path, not automatically by adding every activity duration together.

Aircraft Operations coordinates the aircraft's readiness timeline. The systems that own handling, fuel, maintenance, passengers, crew, facilities, and airport resources supply their requirements and completion events.

Exact activity graphs, formulas, service contracts, resource constraints, and airport handling mechanics remain technical work and Airport Operations or Ground Handling spillover.

## 7. Boarding, Gate Cutoff, and Early Departure

Scheduled departure is the planned off-block time. Boarding must begin early enough for the aircraft to be ready to leave the gate or stand at that time.

Boarding-open and gate-closing milestones are calculated for the dated operation. They may depend on:

- aircraft size and type;
- passenger count;
- boarding method and available doors;
- gate versus remote stand;
- domestic or international processing;
- airport and terminal capability;
- handling quality; and
- future assistance, staffing, or disruption conditions.

Values such as boarding 30 minutes before departure and closing the gate 15 minutes before departure are believable examples, not universal permanent rules.

### 7.1 Default passenger-waiting rule

Before the calculated gate-closing time, the flight waits for booked passengers who have not yet reported or boarded.

At the gate cutoff, absent ordinary passengers may be offloaded under the applicable passenger and airline rules.

After the gate cutoff, an early off-block departure is allowed only when:

- all remaining passengers are accounted for or boarded;
- protected connecting passengers have been handled according to policy;
- required turnaround and departure activities are complete;
- the aircraft is operationally ready; and
- Airport Operations permits gate or stand release and departure movement.

Early departure changes the actual time but never rewrites the published schedule.

## 8. Connection-Hold Policy

Connections are passenger itineraries, not promises that one aircraft operates every leg.

For example:

```text
Flight 101: DVO -> MNL on Aircraft A
Flight 202: MNL -> NRT on Aircraft B
```

Booking owns the itinerary. Aircraft Operations executes each leg independently and reports its outcome.

The safe default is:

```text
Hold for Connections = OFF
```

The outbound flight waits normally until its scheduled departure while its gate remains open. At scheduled departure, it does not automatically hold beyond the timetable for late inbound connecting passengers.

A future airline policy may authorize a hold. Any hold:

- requires Airport Operations to permit continued gate or stand occupation;
- creates real delay;
- may disrupt the aircraft's later rotation; and
- may protect some passengers while harming others.

The minimum and maximum connection windows used to construct itineraries belong to Passenger Booking. The current prototype direction of a one-hour minimum and twelve-hour maximum remains Passenger technical configuration rather than Aircraft Operations ownership.

## 9. Missed Connections Boundary

Aircraft Operations reports the actual times and events that caused a connection to succeed or fail.

Passenger Service determines recovery. It searches real later services and uses only actual remaining capacity. It must not invent recovery seats.

If no viable recovery service exists, Passenger Service applies the relevant airline policy, partnership protection, refund, care, and compensation rules. Finance, Loyalty, and Reputation consume those outcomes through their own boundaries.

## 10. Delay and Physical Propagation

Delays are normal operational outcomes and propagate according to physical reality.

A delayed aircraft does not reset to its original planned position merely because the next scheduled departure time arrives.

For example:

```text
Scheduled arrival:   10:00
Actual arrival:      10:35
Required turnaround: 45 minutes
Earliest ready:      11:20
```

If the next departure is at 12:00, the planned buffer absorbs the delay. If it is at 11:00, the next operation begins late because the aircraft cannot be ready before 11:20.

This makes utilization and schedule buffer strategic decisions.

Aircraft Operations should retain major delay causes rather than one unexplained total. Possible causes include late inbound aircraft, maintenance, handling, airport congestion, weather, gate or stand availability, passenger processing, future crew constraints, and knock-on delay.

Ownership of the cause remains with the system that produced it. Aircraft Operations records its effect on the aircraft timeline.

## 11. Speed-Based Recovery

An airline may recover part of an airborne delay by using a faster cruise strategy:

```text
normal or economical cruise
< recovery cruise
<= aircraft permitted maximum
```

Recovery speed:

- remains within the aircraft's certified and safe envelope;
- increases fuel use and operating cost;
- cannot guarantee full recovery;
- cannot erase taxi, runway, weather, traffic, or ground-handling constraints; and
- may later be selected through airline operating policy.

Exact speed, fuel, cost, wear, and recovery formulas remain technical and balancing work.

## 12. Aircraft Substitution

Substitution is a physical rotation-recovery action, not a permanent schedule rewrite.

The scheduled flight keeps its service identity and planned aircraft. The dated operation records the substitute as its actual aircraft.

### 12.1 Spare-aircraft requirement

Automatic or player-directed substitution begins with a compatible spare aircraft physically parked at one of the airline's Hubs. An Operating Base without Hub status does not provide operational substitution handoff under this architecture.

The substitute must satisfy applicable requirements such as:

- range and performance;
- airport and runway compatibility;
- maintenance and operational availability;
- cabin and capacity rules; and
- absence of an incompatible obligation of its own.

Substitution may not summon an aircraft from another location.

### 12.2 Rotation takeover and handback

The delayed aircraft completes every leg before the replacement point. When it reaches the substitution Hub, it parks rather than attempting to chase its departed rotation.

The parked spare takes over the affected aircraft's remaining rotation from that Hub. It continues the rotation through every physically continuous leg until that rotation returns to the same Hub.

At that Hub return, the original aircraft may resume its intended rotation if it is ready and eligible. The substitute is then released and returns to parked-spare status.

The original and substitute registrations therefore exchange operational roles temporarily without rewriting the recurring schedule or teleporting either aircraft. Detailed compatibility, readiness, priority, and exceptional handback cases remain technical work.

## 13. Substitution Policy

Substitution should eventually be governed by airline policy rather than requiring approval for every routine disruption.

Possible future settings include:

```text
Automatic Aircraft Substitution:
OFF
NOTIFY
AUTOMATIC
```

Policies may later control spare priority, larger or smaller substitutes, capacity reduction, protected flights, and acceptable disruption to the substitute's own work.

Stage 1 should preserve the policy boundary without building the complete rule editor.

## 14. Cancellation

Cancellation is a last-resort operational failure.

The intended recovery order is:

```text
delay
-> absorb or recover where possible
-> substitute when a compatible spare is available
-> use another approved operational recovery
-> cancel only when operation remains impossible or unreasonable
```

Possible causes include:

- an aircraft maintenance condition that prevents operation;
- no compatible substitute within the permitted recovery window;
- airport closure;
- severe weather or another world event;
- a legal or physical restriction; or
- another event that makes the operation impossible.

A twelve-hour maintenance-recovery threshold has been discussed as a prototype only. Exact thresholds remain configurable technical and policy decisions.

Aircraft Operations records the cancellation, time, cause, aircraft state, and resulting operational consequences. Passenger Service owns rebooking, care, refunds, and compensation.

## 15. Diversion Spillover

Diversion is a legitimate future operational outcome, but its behavior is not approved in this architecture pass.

This document therefore does not decide:

- diversion-airport selection;
- airborne fuel and weather decision rules;
- passenger handling after diversion;
- continuation or recovery flights;
- aircraft and crew repositioning; or
- effects on the remaining rotation.

The architecture must preserve an extension point for diversion without prematurely implementing it. Airport Operations owns which airports and movement opportunities are physically available; Aircraft Operations will later own the resulting aircraft outcome under an approved diversion design.

## 16. Airline Operating Policies

Airline Operating Policies are a first-class future gameplay system consumed by Aircraft Operations.

Policy families may include:

- connection protection;
- aircraft substitution;
- delay and speed recovery;
- spare-aircraft use;
- cancellation thresholds;
- disruption handling;
- passenger compensation through Passenger Service; and
- future diversion preferences.

The purpose is to let a growing airline operate according to the player's strategy without interrupting the player for every routine decision.

Until a full policy system exists, Aircraft Operations uses explicit safe defaults, including:

```text
Hold for Connections: OFF
Automatic Substitution: OFF or NOTIFY
Speed Recovery: normal/economical
Cancellation: last resort
```

Exact policy names, unlocks, interfaces, and rule evaluation belong to a future Airline Operating Policies document and technical design.

## 17. Operational Events and Continuous Execution

Aircraft Operations must be event-driven rather than frame-driven.

Meaningful future transitions may resemble:

```text
12:08 TAXI_OUT
12:16 AIRBORNE
13:38 APPROACH
13:46 LANDED
13:52 AT_STAND
```

The simulation processes due operational events when simulation time reaches them. It must not update every aircraft every rendered frame or repeatedly poll every aircraft for resource availability.

Airport queues also use event-driven interfaces. Aircraft Operations needs to understand outcomes such as:

```text
waiting
cleared
using assigned movement opportunity
released
```

Queue ordering, gate assignment, stand occupation, runway sequencing, taxi conflicts, and airport throughput belong to Airport Operations.

Exact event-queue data structures, persistence, catch-up processing, and deterministic ordering remain technical design.

## 18. Time-Derived Position

Aircraft position should normally be derived from its assigned movement segment:

```text
progress
= (current simulation time - segment start)
  / (segment end - segment start)

position = point along assigned path at progress
```

The source of truth is the operational segment, its timing, and assigned path—not tiny coordinate updates persisted every second.

If an off-screen aircraft is taxiing from 14:04 to 14:11, the game stores that timed segment. If the player opens the airport view at 14:07, the renderer derives the correct position for 14:07.

Holding patterns may use the same time-derived approach with repeating geometry and elapsed time.

## 19. Movement-Path Ownership

Aircraft Operations owns the aircraft's current assigned movement segment and its progress through time.

It consumes movement opportunities and path geometry supplied by the appropriate system:

- Airport Operations owns airport taxi, gate, stand, runway, holding, arrival, and departure movement assignments;
- world or map infrastructure may supply simplified enroute display paths; and
- the renderer interpolates visible position and level of detail.

Aircraft Operations must not assume that aircraft have no physical position. It also must not define a full SimAirport-style taxi graph inside this document.

Exact node, segment, curve, and path-file formats remain Airport Operations, map-data, and technical spillover.

## 20. Player-Facing Operations and Live Map

The player primarily manages operations through the headquarters environment and its computer, tablet, phone, reports, and related interfaces.

Management views may show:

- live flight status;
- aircraft status and current phase;
- scheduled, estimated, and actual times;
- delays and major causes;
- substitutions and cancellations;
- booking and passenger outcomes supplied by connected systems; and
- operational history and reliability.

The game does not require detailed visual animation of individual cleaners, baggage workers, caterers, or fuel staff.

### 20.1 Live aircraft map

At world level, aircraft appear as moving icons. Useful filters may show the player's airline, one selected AI airline, aircraft associated with a Hub, or active aircraft only.

The map should not display every route line by default.

When an aircraft is selected, the view may show its relevant operational path, including departure, enroute, approach, holding, landing, and taxi movement where data and zoom allow.

### 20.2 Route view separation

The route or network view represents business connections with simple airport-to-airport lines. The live map represents physical aircraft.

These should remain distinct views rather than one permanent spaghetti visualization.

### 20.3 Level of detail

Rendering detail depends on context:

```text
World: simple moving aircraft icon
Regional or selected flight: selected path and major phases
Airport zoom: assigned ground and runway movement when available
```

The operational state exists even when it is not rendered.

## 21. Operational History and Reliability Inputs

Completed dated flights retain a final operational record sufficient for history, reporting, reliability, finance, maintenance, and passenger consequences.

The retained record should conceptually include:

- original scheduled service and dated-instance identity;
- scheduled, estimated, and actual major times;
- scheduled and actual aircraft;
- scheduled origin and destination;
- final operational outcome;
- major delay causes;
- substitution or cancellation information;
- passengers carried as supplied by Booking and operation completion;
- operating and airborne duration; and
- major operational events needed for audit or reporting.

Fine-grained rendered coordinates and temporary interpolation data do not need permanent historical retention.

Actual performance supplies future airline reliability and reputation inputs. Aircraft Operations records facts; Reputation, Passenger Simulation, Loyalty, and related systems determine their commercial effects.

Exact history-retention duration, aggregation, archival, and save-size strategy remain technical decisions.

## 22. Scaling and AI Parity

The architecture must scale to thousands of aircraft and concurrent flights, many AI airlines, and accelerated simulation time.

Required principles include:

- event-driven execution;
- time-derived positions;
- no per-aircraft render-frame simulation;
- no constant resource polling;
- level-of-detail rendering;
- detailed visual work only for visible or selected aircraft;
- indexed operational events and active flights; and
- deterministic processing when simulation time advances rapidly.

AI airlines use the same Aircraft Operations engine and physical rules as the player. AI strategic decisions occur at meaningful triggers or slower management intervals rather than every simulation tick.

## 23. Stable Implementation Stages

The complete architecture must be introduced through stable playable stages.

### Stage 1 - Dated gate-to-gate execution

The first complete stage may provide:

- a continuous simulation clock with pause and speed controls;
- activation of published dated flights;
- individual aircraft location and chronological continuity;
- scheduled, estimated, and actual off-block and in-block times;
- simplified preparation, boarding, airborne, arrival, and completion events;
- aircraft-dependent handling milestones using simple configured durations;
- delay propagation through the aircraft's rotation;
- completed operational records; and
- simplified time-derived live-map movement.

### Stage 2 - Recovery and richer ground activity

Add one connected layer at a time, such as:

- concurrent turnaround activities;
- speed-based recovery;
- Hub-only parked-spare substitution with physical rotation takeover and handback;
- cancellation and cause reporting;
- richer operational views; and
- reliability statistics.

### Later stages

Later development may add:

- more advanced substitution across unusual or multi-Hub rotations;
- detailed operating-policy automation;
- Airport Operations queues, gates, stands, runways, and taxi paths;
- deeper weather, crew, maintenance, and handling integration;
- holding and richer arrival/departure paths;
- passenger disruption workflows through Passenger Service;
- diversion after separate approval; and
- online continuous-clock operation.

No stage should become a collection of half-built operational systems.

## 24. System Boundaries

| System | Responsibility |
|---|---|
| Aircraft Operations | Owns actual aircraft execution, current operational phase, physical continuity, actual assignment, time-derived location, delay propagation, recovery execution, substitution outcomes, cancellation outcomes, and operational history. |
| Scheduling | Owns the canonical future timetable, dated flight publication, scheduled times, planned aircraft, effective-dated revisions, and planned buffers. |
| Airport Management | Owns airport capability, physical infrastructure, restrictions, facilities, forecast capacity, and strategic airport state. |
| Airport Operations / ATC | Owns live gates, stands, parking, queues, runway sequencing, taxi movement, holding or clearance opportunities, congestion, and actual airport events. |
| Fleet Management | Owns aircraft assets, identity, configuration, home Base, lifecycle presentation, and fleet-management views. |
| Maintenance | Owns maintenance requirements, inspections, faults, legality, downtime, facilities, and release to service. |
| Booking | Owns booked itineraries, reservations, expected passenger counts, connection relationships, and sellable capacity. |
| Passenger Service | Owns missed-connection recovery, rebooking, care, refunds, compensation, and stranded-passenger handling. |
| Base & Hub Management | Owns Base and Hub roles, aircraft-stationing permission, connection privileges, Hub progression, and local airline support relationships. |
| Ground Handling | Future owner of handling staff, contracts, equipment, work execution, and detailed service performance. |
| Fuel Management | Owns fuel purchasing, inventory, availability, uplift, prices, and consumption inputs. |
| Crew Management | Future owner of crew assignment, legality, duty limits, availability, and positioning. |
| Airline Operating Policies | Future owner of player-defined recovery, holding, substitution, cancellation, compensation, and related standing strategies. |
| Finance | Owns fuel and operating costs, airport charges, refunds, compensation, disruption costs, and financial settlement. |
| Reputation, Reliability, and Loyalty | Consume actual operational facts and passenger handling to calculate future commercial effects. |
| Map and Rendering | Own visual interpolation, icons, filters, camera level of detail, and presentation of assigned paths. |

Aircraft Operations coordinates these inputs but must not duplicate their authoritative state.

## 25. Preserved Spillover

The following must be preserved for later documents rather than decided here:

- **Aircraft Operations Technical Specification:** exact state machine, activation window, event ordering, continuous-clock processing, formulas, deterministic catch-up, data structures, persistence, save migration, history retention, tests, and performance budgets.
- **Airport Operations:** gates, stands, parking, runway and taxiway queues, sequencing, clearance, holding assignment, movement paths, congestion, airport capacity, and physical resource occupation.
- **Airline Operating Policies:** policy interfaces, automation levels, thresholds, priorities, permissions, and player progression.
- **Ground Handling:** detailed turnaround activities, concurrency, dependencies, staff, equipment, contracts, service quality, and delay causes.
- **Maintenance:** fault generation, legal dispatch, deferred defects, repair, release, and maintenance-driven recovery thresholds.
- **Passenger Service:** connection protection, reaccommodation, recovery capacity, refunds, compensation, care, and passenger fault.
- **Crew Management:** assignments, duty legality, delays, positioning, and substitution effects.
- **Finance:** fuel premiums, recovery costs, cancellation costs, and disruption settlement.
- **Map and Data:** airport path geometry, enroute paths, holding geometry, coordinate systems, and rendering assets.
- **Diversions:** selection, execution, passenger consequences, continuation, recovery, repositioning, and remaining-rotation effects.

## 26. Non-Goals and Deferred Decisions

This architecture intentionally does not finalize:

- exact simulation speed ratios;
- exact operational-state names or enum values;
- persistent schema fields;
- event-queue implementation;
- flight activation timing;
- handling-duration formulas or tables;
- detailed turnaround dependency graphs;
- exact boarding-open and gate-closing formulas;
- connection-hold limits;
- speed and fuel recovery formulas;
- substitution scoring, handback, and repositioning algorithms;
- cancellation thresholds;
- diversion behavior;
- airport queue, gate, stand, parking, runway, taxi, or holding mechanics;
- path-data formats;
- operating-policy interfaces;
- detailed history retention and archival;
- crew, maintenance, weather, or ground-handling formulas; or
- passenger recovery and compensation.

New persistent fields must be approved in the canonical template/schema reference before code implementation.

## 27. Finalized Architecture

The following decisions should not change without redesigning Aircraft Operations:

```text
Scheduling owns the plan. Aircraft Operations owns actual aircraft execution.
Airport Operations owns live airport resources and movement opportunities.

Game time advances continuously and Aircraft Operations is event-driven rather
than dependent on Advance Day or per-frame aircraft updates.

Every aircraft remains an individual persistent asset with physical location,
operational state, actual timeline, and continuous rotation consequences.

Scheduled departure and actual departure are off-block gate-or-stand times.
Takeoff is separate. Scheduled and actual arrival are in-block gate-or-stand
times. Landing is separate.

The operational lifecycle exposes meaningful preparation, boarding, taxi,
airborne, arrival, and turnaround stages without requiring worker-level visuals.

Ground services have real, often concurrent durations. Aircraft-dependent
handling milestones determine boarding and gate-closing times.

Before gate closure the operation waits for booked passengers. After the
calculated cutoff, absent ordinary passengers may be offloaded and early
departure is allowed only when the aircraft is ready and the airport permits it.

Hold for Connections defaults to OFF. Holding beyond schedule requires a future
airline policy and Airport Operations permission, and creates real delay.

Delays propagate according to physical aircraft readiness. Schedule buffer may
absorb delay; the timetable never resets an unavailable aircraft.

Safe speed recovery may trade additional fuel and cost for time but cannot
override aircraft limits or ground and airport constraints.

Substitution uses a compatible spare aircraft physically parked at an airline
Hub. The delayed aircraft finishes every leg before the replacement point and
parks at that Hub. The spare assumes the remaining continuous rotation until it
returns to the same Hub, where the original may resume and the substitute parks.
Neither aircraft may teleport or ignore its actual location.

Cancellation is a last resort after reasonable delay and recovery attempts.
Aircraft Operations records the outcome; Passenger Service owns recovery and
compensation.

Diversion remains explicitly deferred.

Aircraft movement and holding positions are derived from timed path segments.
Off-screen aircraft do not require continuous visual processing.

Operational history retains major planned and actual facts while temporary
rendering coordinates remain derived and disposable.

Airline Operating Policies become a future first-class management system.
Aircraft Operations consumes policies and uses safe defaults until they exist.

AI and player aircraft use the same operational engine and physical rules.

The architecture is introduced through small, stable, playable stages.
```
