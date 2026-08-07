# Airline Tycoon - Fleet Management Architecture

> **Status:** Approved architecture. This document defines aircraft as individual airline assets and establishes Fleet Management's ownership boundaries. It does not define scheduling, active operations, maintenance simulation, passenger simulation, or detailed finance rules.

## 1. Purpose and Core Philosophy

Every aircraft in Airline Tycoon is an individual operational and business asset, not a quantity in an inventory.

Buying:

```text
10 x A320
```

creates ten separate aircraft. Each aircraft has its own identity, registration, lifecycle, home Base, configuration, and connected operational information.

Fleet Management is the player's central management and overview layer for every aircraft the airline owns or controls.

The defining responsibility is:

```text
Fleet Management: This aircraft exists and belongs to or is controlled by the airline.
Scheduling:       This is what the aircraft is scheduled to do.
Operations:       This is what the aircraft is currently doing.
Maintenance:      This is its maintenance and condition state.
Finance:          This is how the aircraft performs financially.
```

Fleet Management may display information from connected systems without taking ownership of their internal logic.

## 2. Fleet Management Responsibilities

Fleet Management owns:

- individual aircraft identity;
- fleet inventory and overview;
- aircraft registration;
- acquisition of delivered aircraft into the fleet;
- disposal of aircraft from the fleet;
- aircraft organization, filtering, and grouping;
- the aircraft-to-home-base assignment relationship;
- persistent individual-aircraft configuration, including cabin layout;
- basic aircraft asset information; and
- player-facing entry points to related aircraft information.

Fleet Management may display, but does not own:

- current operational phase from Aircraft Operations;
- scheduled flights and rotations from Scheduling;
- current location derived from Aircraft Operations;
- maintenance condition and service requirements from Maintenance;
- revenue, costs, and profitability from Finance;
- utilization and lifetime operational statistics;
- route usage derived from the aircraft's schedule; and
- delivery, lease, or contract information supplied by the relevant acquisition system.

This allows the Fleet interface to serve as a complete aircraft dashboard without turning Fleet Management into the owner of every system represented there.

## 3. Individual Aircraft Identity

Aircraft of the same model remain separate assets. Each delivered aircraft must receive its own persistent identity and registration rather than being represented by a model count.

An individual aircraft may differ from others of the same model through facts such as:

- registration;
- ownership or control arrangement;
- home Base;
- cabin configuration;
- age;
- acquisition and delivery information;
- maintenance state;
- schedule and utilization; and
- financial performance.

The exact persistent schema must be established in the canonical template reference before code implementation. This architecture approves the concepts, not new ad-hoc `game_state` field names.

## 4. System Boundaries

| System | Responsibility |
|---|---|
| Fleet Management | Establishes that the individual aircraft exists in the airline's controlled fleet and owns its persistent fleet identity, organization, home-base relationship, and configuration. |
| Aircraft Market / Acquisition | Supplies aircraft offers, availability, prices, sellers, lessors, delivery terms, and contract options. |
| Finance | Validates and records purchases, sales, leases, reconfiguration costs, and other aircraft-related financial transactions. |
| Aircraft Reference Data | Defines aircraft-model specifications such as physical limits, capacity constraints, range, dimensions, and performance data. |
| Base & Hub Management | Determines whether an airport is a valid Operating Base or Hub and which capabilities are available there. |
| Scheduling | Assigns scheduled flights and rotations, allocates aircraft time, and validates timetable and rotation feasibility. |
| Aircraft Operations | Tracks what the aircraft is currently doing and where it is currently located. |
| Maintenance | Owns condition, checks, service requirements, maintenance history, downtime, and return-to-service rules. |
| Passenger Simulation | Uses the aircraft's resulting cabin products and available seat capacity when booking passengers. |

Fleet Management coordinates acquisition, entry into service, reassignment, reconfiguration, and disposal through these systems. It does not independently invent market prices, deduct money, validate schedules, calculate performance feasibility, or bypass maintenance and operational constraints.

## 5. Aircraft Acquisition

Aircraft may eventually enter the fleet through:

- new-aircraft purchase;
- used-aircraft purchase;
- leasing;
- rent-to-own or similar future contracts; and
- other acquisition methods approved later.

Regardless of acquisition source, every delivered aircraft becomes an individual fleet asset. A multiple-aircraft order must create separate delivered aircraft rather than one aircraft record with a quantity.

Fleet Management owns the aircraft's entry into the controlled fleet. Aircraft offers, purchase prices, financing, lease contracts, order backlogs, and delivery timing remain the responsibility of their future owning systems.

## 6. Aircraft Disposal

Fleet Management provides the player-facing disposal workflow, but disposal is a coordinated lifecycle action rather than an unconditional deletion.

Before an aircraft can leave the fleet, connected systems may need to confirm that it:

- is not currently operating a flight;
- has no unresolved schedule or rotation assignment;
- is not undergoing maintenance;
- satisfies ownership, lease, or contract restrictions; and
- can be financially settled correctly.

The exact resale-value formula, depreciation rules, contract settlement, and aircraft-market behavior remain future Finance and Aircraft Market work.

## 7. Home-Base Assignment

Each aircraft has an assigned home Base. An Operating Base does not need to be a passenger-connection Hub.

Fleet Management owns the persistent aircraft-to-home-base relationship, while the connected systems enforce its meaning:

- Base & Hub Management determines whether the airport is a valid Operating Base and what support it provides.
- Scheduling ensures the aircraft's rotation begins at and eventually returns to its assigned home Base.
- Aircraft Operations tracks the aircraft's actual current location.
- Maintenance determines whether required servicing is available or must be planned elsewhere.

An aircraft does not need to return to its home Base after every flight. It may operate a multi-leg rotation as long as the finalized Scheduling rules are satisfied.

Reassigning an aircraft to another Base must be coordinated with its schedule, actual location, maintenance needs, and the receiving Base's capabilities. The aircraft must physically arrive through a scheduled revenue flight or a positioning flight before the explicit transfer becomes effective. Detailed validation belongs to Base & Hub Management, Scheduling, and later technical design.

## 8. Schedule-Derived Route Usage

The legacy `assigned_routes` field is not part of the approved modern architecture.

An aircraft's route usage should be derived from its scheduled flights or rotation. Fleet Management may display the routes or markets an aircraft is expected to serve, but it must not maintain a competing route-assignment list.

This preserves one source of truth and prevents Fleet records from disagreeing with Scheduling.

## 9. Operational State and Availability

Legacy aircraft statuses such as:

- `Idle`;
- `Flying`; and
- `Boarding`

are not owned by Fleet Management and are not approved as the final aircraft-state model.

Aircraft Operations owns actual operational phases. Maintenance, delivery, scheduling, and contracts may also affect whether an aircraft is available for use.

Fleet Management may present a unified status or availability summary assembled from those systems. It must not maintain an independent operational status that can contradict them.

The final operational phases and availability-calculation rules belong to their respective future architecture documents.

## 10. Cabin Configuration

Cabin configuration is a persistent property of each individual aircraft and may be managed through Fleet Management.

Connected responsibilities remain separate:

- Aircraft Reference Data defines the aircraft model's physical limits and permitted configuration constraints.
- Passenger Simulation uses the resulting cabin products and available capacities.
- Finance records configuration and reconfiguration costs.
- Scheduling, Maintenance, or Aircraft Operations may enforce required downtime and location constraints.

The detailed seat-layout schema, product definitions, cost formulas, and reconfiguration workflow remain future work.

## 11. Scaling to Large Fleets

The same individual-aircraft model must remain usable from the player's first aircraft through fleets containing hundreds of aircraft.

Early-game Fleet Management can emphasize individual aircraft. As the airline grows, the management layer should support:

- filtering and sorting;
- fleet groups;
- aircraft-model views;
- home-base views;
- bulk actions where appropriate;
- optional automation and delegation; and
- fleet-level performance summaries.

These tools organize individual aircraft; they do not replace them with abstract quantities. Every aircraft remains a real underlying asset with its own lifecycle and connected state.

## 12. Non-Goals and Deferred Decisions

This architecture intentionally does not finalize:

- operational flight phases;
- availability-calculation rules;
- schedule structures or rotation algorithms;
- maintenance formulas, checks, and intervals;
- aircraft-market offer generation;
- resale values and depreciation;
- lease contracts, financing, or payment rules;
- delivery lead times and order backlogs;
- aircraft performance and compatibility calculations;
- the persistent aircraft schema and exact field names;
- detailed cabin-reconfiguration mechanics; or
- detailed fleet-group automation.

Those decisions belong to their owning systems and must follow the schema-first development process when implemented.

## 13. Finalized Architecture

The following decisions should not change without redesigning Fleet Management:

```text
Every aircraft is an individual asset, never merely a quantity.

Fleet Management owns aircraft existence in the controlled fleet, identity,
organization, home-base assignment, persistent configuration, acquisition into
the fleet, and disposal from the fleet.

Scheduling owns what the aircraft is scheduled to do.

Aircraft Operations owns what it is currently doing and where it is.

Maintenance owns condition, service requirements, and downtime.

Fleet may display connected information without owning its source logic.

Route usage is derived from the schedule; there is no competing
Fleet-owned assigned_routes list.

Fleet does not own vague operational statuses such as Idle, Flying, or Boarding.

The individual-aircraft model remains intact even when large-fleet tools,
bulk actions, and automation are added.
```
