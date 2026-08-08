# Airline Tycoon - Flight Scheduling Architecture

> **Status:** Approved architecture. This document defines how the airline plans passenger services, assigns aircraft, validates future movements, publishes dated flights, and exposes the timetable to Booking and Aircraft Operations. It does not define persistent schema fields, passenger-choice formulas, live operational recovery algorithms, airport-construction mechanics, or maintenance formulas.

## 1. Purpose and Design Principle

Scheduling turns purchased route rights, available aircraft, airport opportunities, and player strategy into a feasible future timetable.

The central rule is:

```text
The player schedules services on specific aircraft, but the public service
and its flight number are not permanently owned by that physical aircraft.
```

The planned aircraft proves that the timetable can be flown. Another compatible aircraft may operate a dated occurrence without changing the passenger-facing service.

Scheduling must remain strategic without becoming repetitive clerical work. The player should be able to construct individual movements precisely, then use repetition, copying, offsets, templates, and forecasts to scale the same underlying system.

## 2. Canonical Schedule Model

Schedule information must have one canonical representation. Aircraft, route, airport, flight-number, and timetable screens are projections of the same schedule data, not separately maintained copies.

The architecture distinguishes four related concepts:

| Concept | Example | Purpose |
|---|---|---|
| Scheduled Service | `DB001`, MNL to DVO, 08:00 | Passenger-facing timetable identity |
| Planned Aircraft Assignment | RP-C1234 | Aircraft expected to cover the occurrence |
| Dated Flight Instance | `DB001` on 18 August | Concrete future occurrence available to Booking and Operations |
| Substitute Aircraft | RP-C5678 | Compatible replacement used without renaming the service |

The player's aircraft schedule and the public timetable therefore describe different views of one plan:

- the aircraft view shows the continuous work planned for a specific aircraft;
- the service view shows what passengers can book;
- the route view shows all service in an airport-pair market;
- the airport view shows planned arrivals and departures; and
- the dated instance is the unit Aircraft Operations eventually executes.

No subsystem should create a competing route schedule or aircraft schedule that can disagree with the canonical plan.

## 3. Planning Horizon and Recurrence

Scheduling is not limited to a seven-day aircraft rotation. A week is a convenient recurrence pattern, not a simulation boundary.

The player may create:

- a one-time future flight;
- a service on selected weekdays;
- a weekly repeating pattern;
- a pattern repeated a chosen number of times;
- a service repeated until a selected date;
- a service repeated indefinitely until revised or retired; and
- future seasonal or otherwise date-bounded timetable replacements.

An indefinite recurrence rule does not require the game to store infinite flights. Scheduling materializes dated flight instances only as far ahead as required by the active planning and booking horizons, then extends them as time advances.

The booking horizon and instance-generation horizon may differ as an implementation choice, but Booking can sell only dated instances that Scheduling has made available.

## 4. Schedule Lifecycle

Schedules support at least these architectural states:

- **Draft:** editable and allowed to contain unresolved warnings or conflicts;
- **Active:** validated, published, and eligible to generate bookable dated instances; and
- **Retired or Archived:** no longer generates new instances but remains available for history and reporting.

Editing an active schedule creates a pending revision. It does not silently rewrite already operated flights or immediately delete future bookings.

Every activation or replacement has an effective date. Flights before that date retain their existing plan. Removing or materially changing a future booked instance initiates a schedule-change or cancellation event for the systems responsible for passenger handling, refunds, rebooking, and financial settlement.

Seasonal scheduling uses the same model: a future timetable becomes effective for a defined period and may later be replaced by another. Detailed seasonal automation remains future work.

## 5. Aircraft-Specific Planning

The player constructs continuous time blocks for specific aircraft. Scheduling must know the planned aircraft for every dated occurrence before activation.

This provides:

- a concrete, understandable aircraft plan;
- aircraft utilization and ground-time visibility;
- physical continuity validation;
- maintenance and availability checks; and
- a basis for automatic substitution when live operations differ from the plan.

Routes do not belong to one aircraft. Multiple aircraft may operate the same route at different times, and the aircraft used for a recurring service may differ between dates without changing the public service identity.

Specific planned assignment does not prevent player-friendly automation. Tools may populate compatible aircraft automatically, but the resulting activated schedule must still contain explicit planned assignments that can be inspected and validated.

## 6. Continuous Aircraft Movement

An aircraft may fly any continuous multi-leg chain for which the airline has the required rights and the aircraft is technically compatible.

For example:

```text
MNL -> DVO -> SYD -> DVO -> CEB -> SYD -> CEB -> MNL
```

The next scheduled movement must begin where the aircraft's preceding movement ends. Scheduling hard-blocks impossible geography, overlaps, and plans in which the aircraft cannot physically reach the next origin in time.

An aircraft is not required to return to its home Base at the end of a calendar week or after an arbitrary number of days. Its plan must instead:

- contain scheduled activity to and from its assigned home Base;
- remain geographically and chronologically continuous;
- reach a Base with the required facility before maintenance or Base-dependent service becomes due; and
- avoid leaving the aircraft unable to perform its next planned obligation.

The maintenance-capable Base does not need to be the aircraft's assigned home Base. Extended operation away from the home Base may create future crew, logistics, parking, or support costs, but it is not prohibited by an arbitrary periodic-return rule.

## 7. Revenue Services and Positioning Flights

Scheduling supports both:

- **revenue flights**, which carry passengers and serve an acquired route; and
- **positioning or deadhead flights**, which move an aircraft without ticket revenue.

A deadhead:

- carries no passengers;
- earns no ticket revenue;
- incurs fuel, crew, airport, slot, parking, and other applicable operating costs;
- must satisfy aircraft range and airport compatibility;
- requires the general legal and physical ability to operate at its endpoints; and
- does not require a passenger route right for that airport pair.

When a plan strands an aircraft away from its next required origin or support location, Scheduling must:

1. warn the player;
2. propose a feasible positioning movement where possible;
3. show its timing, slots, fuel, crew, parking, and expected cost consequences; and
4. require the player to approve that movement or repair the schedule.

The initial design requires manual confirmation. The game must not secretly insert a money-losing positioning flight. Optional automatic positioning may be considered later.

## 8. Time, Dates, and Time Zones

The player schedules each movement using the local date and time at the relevant airport, matching normal airline timetables.

The simulation normalizes the timeline internally, preferably using UTC plus canonical airport time-zone data. It must correctly handle:

- different origin and destination time zones;
- overnight flights;
- local date changes;
- daylight-saving transitions where applicable; and
- crossings of the International Date Line.

The interface must clearly distinguish local dates and times so that a technically valid schedule is also understandable to the player.

## 9. Flight and Ground Activity

The player always chooses the scheduled departure time of a leg. The game calculates the earliest feasible arrival and next departure using the aircraft, route, airport, and available services.

The complete planned activity may include:

1. boarding and departure preparation;
2. pushback and taxi-out;
3. flight;
4. landing and taxi-in;
5. deplaning;
6. turnaround and servicing; and
7. preparation for the next boarding event.

Strict aviation block time normally runs from leaving the departure stand to reaching the arrival stand. Boarding, deplaning, and turnaround remain separate schedule activities even if the interface groups them into a convenient player-facing planning block.

Minimum turnaround depends on factors owned by connected systems, including:

- aircraft type and configuration;
- airport and stand arrangements;
- service type;
- unlocked or contracted ground services;
- required cleaning, catering, fueling, or baggage work; and
- maintenance or special servicing.

The game proposes the earliest feasible next departure. The player may accept it or add custom ground time. Additional ground time may improve resilience or connections but also reduces utilization and may incur parking fees.

Impossible durations and sub-minimum activity times are hard-blocked at activation rather than accepted as intentional delay risk.

## 10. Access and Route Validation

Every revenue leg requires:

- the airline license appropriate to the operation;
- the required country access;
- an acquired route right for the specific airport pair;
- airports capable of handling the intended service;
- required scheduled-movement opportunities or slots; and
- a compatible aircraft and continuous aircraft plan.

Owning MNL-DVO does not authorize DVO-CEB. Every commercial airport pair requires its own route right under Market & Route Management.

Country access allows route development involving suitable airports in that country. Separate Airport Access is not required merely to fly to an airport. Airport Access instead permits a permanent airline footprint and facilities such as a Base, Hub, lounge, office, dedicated parking, hangar, or fuel storage.

A real-world domestic-only airport cannot accept international service until Airport Management determines that it has the required customs, immigration, security, terminal, and physical capability. The airline's international license and country access do not override missing airport capability.

## 11. Airport Times, Capacity, and Slots

The published timetable uses exact local scheduled arrival and departure times.

Airport capacity may be evaluated internally using time buckets, but the player does not acquire a vague passenger-facing time window in place of an exact schedule. The architectural behavior is:

- unconstrained airports normally approve feasible requested times;
- facilitated airports may warn about congestion or recommend adjustments;
- coordinated or congested airports require an allocated slot;
- an unavailable requested time may produce nearby alternatives; and
- activation requires all mandatory slots or equivalent movement permissions.

Every applicable scheduled arrival and departure consumes airport capacity. Drafts may preserve unresolved slot conflicts for experimentation, but an active schedule must be valid.

Airport Management owns physical and declared capacity, slot supply, scarcity, and allocation rules. Scheduling requests and assigns the required opportunities to exact planned movements.

Live traffic, weather, runway configuration, air-traffic control, taxiway constraints, and stand availability may reduce actual throughput after the schedule is published. Those effects belong to Aircraft Operations and Airport Operations and do not rewrite the original scheduled time.

## 12. Activation Validation

Before activation, Scheduling validates the complete affected aircraft plan and every generated occurrence within the validation horizon.

Activation is blocked when:

- one aircraft is assigned to overlapping movements;
- an aircraft cannot reach the next origin;
- the preceding arrival and required ground activity do not fit before departure;
- aircraft range or airport compatibility is insufficient;
- the airport cannot physically or regulatorily support the service;
- a required slot or movement opportunity is unavailable;
- a revenue leg lacks its required license, country access, or route right;
- planned maintenance or another known unavailability conflicts with the assignment;
- required servicing cannot be reached before it becomes due; or
- a recurrence creates an invalid boundary between consecutive occurrences.

Warnings that do not make the plan impossible may remain advisory. The validation interface should explain the cause, highlight affected blocks, and offer useful alternatives where possible rather than only rejecting the plan.

## 13. Flight Numbers and Service Identity

The game automatically assigns passenger-facing flight numbers to scheduled services.

A flight number identifies the timetable service, not the physical aircraft. The same flight number may therefore be operated by different compatible aircraft on different dates.

When copied or generated schedule blocks match the same route, scheduled departure time, direction, and recurrence or service pattern, Scheduling may recognize them as occurrences of the same service and reuse its flight number.

Opposite directions normally use different flight numbers. A materially different timetable service receives a different number even when it serves the same route.

If two aircraft operate genuinely separate departures on the same route at the same scheduled time and date, each occurrence must remain distinguishable through different flight numbers or a future explicitly designed section-flight system.

Deadheads use internal movement identifiers rather than normal passenger-facing flight numbers. Every dated revenue or positioning instance also has its own unique internal identity.

The exact airline code format, numbering ranges, reuse policy, and section-flight rules remain technical design work.

## 14. Aircraft Substitution

The activated schedule retains its planned aircraft assignment. If that aircraft is delayed, under maintenance, or otherwise unavailable, Aircraft Operations may substitute another aircraft without changing the flight number or public timetable.

The substitute must:

- be physically present and available at the required airport;
- fit the remaining timeline;
- satisfy range and airport compatibility;
- provide an acceptable cabin and capacity under future passenger-handling rules;
- satisfy maintenance and operational restrictions; and
- not create a conflict in its own assigned work.

Substitution handles a dated operational occurrence. It does not permanently rewrite the recurring schedule unless the player explicitly revises the plan.

Detailed recovery priority, automatic reassignment, passenger reaccommodation, and downstream rotation repair belong to Aircraft Operations and future disruption-management design.

## 15. Booking and Dated Flight Generation

Scheduling generates or publishes dated flight instances within the future booking horizon. Booking reads those instances; it does not book passengers directly against an abstract infinite recurrence rule.

Each dated instance preserves its scheduled service, exact local and normalized times, planned aircraft or capacity information, route, and operational identity.

When a pending revision becomes effective:

- instances before the effective boundary remain governed by the prior plan;
- new instances follow the replacement plan; and
- affected booked instances initiate the appropriate change or cancellation workflow rather than silently disappearing.

Scheduling owns timetable publication and change events. Passenger Service, Booking, and Finance own the resulting passenger choices, reaccommodation, refunds, compensation, and settlement rules.

## 16. Hub Connections

Scheduling publishes flight times but does not manually create or save every possible passenger connection.

Passenger Simulation discovers a connection dynamically when:

- the transfer airport is an active Hub for the airline;
- the inbound and outbound dated instances form a physically valid sequence;
- the layover meets the applicable minimum and maximum connection times;
- route, capacity, and passenger rules permit the itinerary; and
- the itinerary is attractive enough to be considered by the booking model.

Minimum connection time may reflect the airport's physical baseline, terminal arrangements, the airline's Hub level, transfer facilities, baggage capability, and operational quality. Maximum connection time prevents unreasonable itineraries unless a future passenger type intentionally accepts a long layover.

Connections appear or disappear as the timetable changes. Scheduling supplies the plan; Base & Hub Management supplies connection permission; Passenger Simulation owns itinerary search and evaluation.

## 17. Planned Versus Actual Operations

Scheduling owns what should happen. Aircraft Operations owns what actually happens.

The simulation preserves scheduled and actual times separately. A delayed departure, traffic queue, diversion, cancellation, or substitute aircraft does not overwrite the original timetable.

When delayed, the airline may later use an operational policy that asks pilots to recover time by increasing cruise speed within the aircraft's safe envelope. Such recovery:

- consumes additional fuel;
- may increase operating cost or stress;
- can recover only physically available time;
- never exceeds approved aircraft limits; and
- cannot erase taxi, runway, weather, air-traffic, or ground-handling constraints.

Scheduling exposes planned buffers and consequences. Aircraft Operations owns the actual recovery decision, execution, and result.

## 18. Player-Friendly Scheduling Tools

Ease of use is an architectural requirement, especially as the airline grows.

Scheduling should support or anticipate:

- automatic earliest-next-departure placement;
- copy and paste;
- selected-day recurrence;
- repeat until a date or indefinitely;
- queue a pattern a chosen number of times;
- bulk scheduling with time offsets;
- duplication across compatible aircraft;
- automatic population of explicit planned aircraft assignments;
- conflict highlighting and nearby-time suggestions;
- positioning-flight proposals;
- reusable schedule and rotation templates;
- seasonal replacements;
- activation previews;
- undo and pending revisions; and
- future optimization or delegated scheduling.

These tools manipulate the same canonical schedule records underneath. Convenience features must not create an alternate simplified schedule model.

## 19. Forecasts and Decision Support

The player should not need to schedule blindly. The scheduling interface may display forecasts such as:

- estimated direct demand;
- estimated connecting demand at eligible Hubs;
- expected load factor;
- estimated revenue and operating cost;
- break-even load;
- likely spilled or unmet demand;
- competition and existing frequency;
- aircraft-capacity suitability;
- aircraft utilization and parking time; and
- effects on Hub connection banks.

Scheduling presents these metrics but does not own their formulas. Demand, Passenger Simulation, Competition, Finance, Fleet, Airport, and Hub systems supply the underlying estimates.

Forecasts are decision support, not guarantees. Players remain free to activate strategically unusual or commercially poor schedules when they are legal and operationally feasible.

## 20. System Boundaries

| System | Responsibility |
|---|---|
| Scheduling | Owns the canonical future timetable, recurrence, planned aircraft assignments, positioning plans, activation validation, effective dates, and dated-instance publication. |
| Fleet Management | Owns aircraft identity, configuration, and persistent home-base assignment; displays schedule-derived utilization without duplicating it. |
| Market & Route Management | Owns licenses and country access at the architectural boundary, specific airport-pair route rights, and route lifecycle. |
| Base & Hub Management | Owns Operating Base and Hub roles, stationing permission, local support access, and passenger-connection permission. |
| Airport Management | Owns airport capability, physical capacity, declared movement capacity, slots, stands, restrictions, and fees. |
| Aircraft Operations | Owns actual aircraft location, live execution, delays, substitutions, cancellations, recovery, and actual times. |
| Maintenance | Owns servicing requirements, due limits, facility compatibility, planned downtime, and release to service. |
| Passenger Simulation and Booking | Owns itinerary discovery, connection validation, passenger choice, reservations, and capacity consumption. |
| Finance | Owns operating costs, parking costs, slot and airport charges, revenue, refunds, and financial settlement. |
| Crew Management | Future owner of crew legality, assignments, positioning, duty limits, and availability. |

Scheduling coordinates constraints from these systems without taking ownership of their underlying source data or formulas.

## 21. Deferred Technical and Balancing Decisions

This architecture intentionally does not finalize:

- persistent schedule schema and exact field names;
- instance-generation and booking-horizon lengths;
- recurrence storage format;
- capacity-bucket duration;
- slot prices, allocation, trading, or use-it-or-lose-it rules;
- exact taxi, flight, turnaround, and service-time formulas;
- maintenance intervals and due-limit calculations;
- automatic substitution and disruption-recovery algorithms;
- flight-number format, ranges, reuse, or section-flight behavior;
- forecast formulas or confidence presentation;
- passenger cancellation, refund, and reaccommodation rules;
- crew planning and duty-time rules;
- detailed seasonal automation; or
- speed-based delay-recovery formulas.

Any new persistent fields must first be defined in the canonical template/schema reference before code implementation.

## 22. Preserved Spillover

The following approved directions belong to future owning documents:

- **Airport Management:** exact-time scheduling opportunities and slots, capacity forecasts derived from airport infrastructure and expected traffic, facilitated and coordinated airports, international-capability conversion, stands, taxiways, congestion, and the future airport-specific ATC engine. See [`Airport Management`](../02%20Gameplay/Airport%20Management.md).
- **Aircraft Operations:** actual flight phases, traffic delay, cancellations, substitutions, disruption recovery, and speed-based delay compensation.
- **Maintenance:** service types, due thresholds, capable facilities, planned downtime, and maintenance recovery.
- **Passenger Simulation and Booking:** booking horizons, connection search, minimum and maximum layovers, passenger response to timetable changes, and reaccommodation.
- **Finance:** positioning costs, parking charges, slot costs, cancellation settlement, and schedule forecasts.
- **Crew Management:** crew coverage, duty legality, positioning, and remote-operation consequences.

These directions are preserved but are not prematurely specified here.

## 23. Finalized Architecture

The following decisions should not change without redesigning Scheduling:

```text
Schedule data has one canonical representation. Aircraft, route, airport, and
timetable displays are views of that same plan, not competing copies.

The player plans explicit time blocks on specific aircraft. The public flight
number belongs to the scheduled service, so another compatible aircraft may
operate a dated occurrence without renaming it.

Scheduling is not limited to one week. Weekly patterns are recurrence tools,
and dated instances are generated only as far into the future as needed.

Aircraft plans must be geographically and chronologically continuous. They
need activity to and from their assigned home Base but no arbitrary weekly or
monthly return. Maintenance may occur at any capable Operating Base.

Revenue legs require the appropriate license, country access, airport-pair
route right, airport capability, slots, compatible aircraft, and feasible plan.

Country access permits route development at suitable airports. Airport Access
is instead required for a permanent airline footprint and facilities.

Positioning flights carry no passengers or revenue, cost money, and require
explicit player confirmation before they are added.

The player chooses exact local departure times. The game normalizes time
internally, calculates the earliest feasible continuation, and hard-blocks
impossible schedules.

Drafts may contain conflicts. Activation requires a feasible plan. Changes to
active schedules use effective-dated revisions and do not silently erase
operated flights or booked passengers.

Scheduling publishes dated flight instances. Booking reads them, Passenger
Simulation discovers valid Hub connections, and Aircraft Operations records
what actually happens without rewriting the planned timetable.

Scalable scheduling tools and decision forecasts are architectural requirements,
not optional polish reserved only for small-airline workflows.
```
