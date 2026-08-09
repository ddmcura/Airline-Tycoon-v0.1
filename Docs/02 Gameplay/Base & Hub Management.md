# Airline Tycoon - Base & Hub Management Architecture

> **Status:** Approved architecture. This document separates aircraft operating bases from passenger-connection hubs. It defines airport roles, aircraft stationing, Hub licensing, Hub progression, connection privileges, and their system boundaries. It does not finalize airport construction, facility economics, scheduling algorithms, or balancing formulas.

## 1. Purpose and Core Philosophy

Airline Tycoon distinguishes between where an airline serves passengers, where its aircraft are stationed, and where its passengers may connect.

The defining rule is:

```text
Every Hub is an Operating Base.
Not every Operating Base is a Hub.

Bases support aircraft.
Hubs connect passengers.
```

A busy airport does not automatically become a Hub. Hub status is an airline-specific capability that the player must apply and pay for.

## 2. Airline Airport Roles

An airport may hold one of these roles for a particular airline:

| Role | Aircraft may be stationed? | Airline passenger connections? | Local operational facilities? |
|---|---:|---:|---:|
| Served Airport | No permanent home-base assignment | No | Normal turnaround services only |
| Operating Base | Yes | No | May acquire or lease parking, servicing, hangars, maintenance, fuel, and other local support |
| Hub | Yes | Yes | Includes all Base capabilities and adds Hub licensing, connecting operations, XP, levels, and Hub benefits |

These are airline-specific roles. The same airport may be a Hub for one airline, an Operating Base for another, and only a served airport for a third.

An airline may operate routes between any airports for which it holds the required access and route rights. A route does not need to begin or end at a Base or Hub.

## 3. Point-to-Point Service and Passenger Connections

An airline's non-Hub routes operate point-to-point. Merely serving two routes through the same airport does not let that airline connect passengers between its own flights there.

For example, if an airline operates:

```text
CEB <-> MNL
CEB <-> DVO
```

while CEB is not that airline's Hub, passengers may book each market independently, but they may not book DVO -> CEB -> MNL as one connecting journey with that airline.

After the airline establishes CEB as a Hub, DVO -> CEB -> MNL may become a valid same-airline connecting itinerary. Passenger Simulation still determines whether the itinerary is feasible and attractive.

Passenger Simulation may separately evaluate partnered or unpartnered changes between different airlines. An inter-airline transfer at a non-Hub does not grant either airline Hub functionality there: neither airline may use it to connect between two of its own flights unless that airline has established the airport as its Hub.

Hub status creates permission for passenger connections. It does not guarantee demand, suitable schedules, sufficient terminal capacity, or successful bookings.

## 4. Starting Airport

The player's starting airport begins as the airline's first Operating Base, not as a Hub.

At the start of the game:

- aircraft may be assigned to and stationed at the starting Base;
- aircraft schedules may include arrivals, departures, stationing, and support activity there;
- the Base provides the basic support needed for the starting operation;
- the player's initial access rights determine which routes may be acquired and operated; and
- flights remain point-to-point until the player successfully establishes a Hub.

This makes the first Hub a deliberate early progression goal rather than a free starting entitlement.

## 5. Operating Bases

An Operating Base is an airline operational location where aircraft may have their persistent home-base assignment.

Base capabilities may include, when acquired or otherwise available:

- contracted or leased aircraft parking;
- routine ground servicing;
- hangars or maintenance access;
- airline operational space;
- fuel facilities or fuel-service arrangements;
- future crew facilities; and
- other local aircraft-support infrastructure.

Base status does not permit passenger connections by itself. It also does not grant market access, route rights, airport slots, airport ownership, or physical facilities that the airline has not acquired.

The detailed Base-establishment requirements, prices, contracts, and facility packages remain future design work.

## 6. Hub Establishment

The player establishes a Hub by applying for and paying for Hub status at an existing Operating Base.

Once the defined requirements are satisfied, Hub approval should be predictable rather than governed by an unexplained random rejection. A processing or approval period may exist later, but the player should be able to understand the requirements, cost, and expected result.

Establishing Hub status does not grant:

- country or market access;
- route rights;
- airport slots;
- ownership of the airport;
- free gates, stands, terminals, hangars, or other facilities; or
- exemption from normal airport charges.

Those remain controlled by their owning systems.

## 7. Hub Cost Structure

Hub costs have three separate layers.

### 7.1 One-Time Establishment Fee

The player pays a one-time fee when converting an Operating Base into a Level 1 Hub.

The first Hub should be affordable. The establishment fee increases as the airline creates additional active Hubs, representing the growing complexity and strategic value of a wider connecting network.

The airport's size, importance, market, and local costs may also influence the fee. Exact prices and scaling formulas remain balancing work.

### 7.2 Recurring Hub Overhead

An active Hub creates recurring operational overhead separate from airport-use fees.

This overhead scales primarily with actual connecting passengers handled and may also consider Hub level and transfer-operation complexity. It represents costs such as:

- transfer and passenger-assistance staff;
- baggage-transfer handling;
- connection coordination;
- Hub administration; and
- operational space used by the connecting service.

The system should not charge directly from the theoretical number of mathematical itinerary combinations, which may become enormous without reflecting real work performed.

### 7.3 Normal Airport and Facility Costs

The airline separately pays applicable costs such as:

- landing and departure fees;
- passenger and handling charges;
- gates and aircraft stands;
- parking;
- hangars and facility leases;
- fuel and ground services; and
- other airport-use charges.

Paying for Hub status never replaces these costs.

## 8. Hub XP and Levels

Every newly established Hub begins at Level 1 and gains Hub XP through meaningful connecting operations.

Hub level represents the maturity of that airline's connecting operation at the airport. It does not represent the physical size or development level of the airport itself.

XP may be earned through activity such as:

- successfully handled connecting passengers;
- sustained Hub operations;
- completed flight movements supporting the connecting network;
- reliable passenger connections; and
- continued effective use over time.

XP should not be awarded merely for scheduling large numbers of empty flights. Progression should reward real and sustained operation rather than artificial activity.

Hub levels may eventually unlock or improve:

- connection-handling sophistication;
- minimum connection-time performance;
- management of larger or more complex connection banks;
- transfer desks and baggage capabilities;
- Hub analytics and automation;
- premium connection services; and
- other advanced connecting-network benefits.

Exact XP formulas, level count, thresholds, unlock tables, and balancing values remain future technical design.

Hub levels do not magically create runways, gates, parking, terminals, hangars, or other physical infrastructure. Those remain airport and facility concerns.

## 9. Aircraft Parking and Physical Capacity

There is no arbitrary aircraft-count limit attached directly to Base or Hub level.

Practical stationing capacity comes from physical and contracted resources:

- aircraft on the ground require compatible parking positions;
- idle and overnight aircraft need somewhere to remain;
- aircraft away on flights do not occupy Base parking while absent;
- maintenance work may require a compatible hangar or maintenance bay; and
- not every based aircraft requires its own dedicated hangar.

The intended direction is a soft capacity model where practical:

- contracted Base parking is dependable and normally cheaper;
- temporary overflow or remote parking may cost more;
- shortages may create towing, delays, or restrictions on long-term stationing; and
- a hard block occurs only when no compatible physical solution exists.

Exact parking simulation, compatibility, overflow rules, and airport capacity calculations belong to Airport Management and later technical design.

## 10. Aircraft Home-Base Assignment and Transfer

Every aircraft has an assigned home Base. Fleet Management owns this persistent relationship.

The home Base is the aircraft's normal operational anchor, not a mandatory weekly or monthly return checkpoint. Scheduling must include meaningful activity to and from the assigned Base, but an aircraft may operate extended continuous rotations away from it. Required maintenance or other Base-dependent service may be completed at any Operating Base with the correct facilities.

To reassign an aircraft, the player explicitly initiates a home-base transfer. The aircraft must physically arrive at the receiving Base through either:

- a normal scheduled revenue flight; or
- a non-revenue positioning or deadhead flight.

The transfer becomes effective when the aircraft arrives and the connected scheduling, operational, maintenance, and Base requirements are satisfied. Merely passing through the airport does not silently change the aircraft's home Base.

Detailed transfer timing, schedule migration, positioning costs, and validation rules remain Scheduling and technical-design work.

## 11. Closing or Downgrading a Hub

Removing Hub status causes the airport to lose that airline's passenger-connection privileges and Hub benefits.

Closing or downgrading a Hub should:

- stop the creation of new connecting itineraries through it;
- remove active Hub-level benefits;
- stop recurring Hub overhead after required wind-down obligations;
- preserve valid point-to-point routes;
- preserve the airport as an Operating Base if the player retains Base status;
- preserve separately owned or leased facilities subject to their contracts and costs; and
- safely handle existing connecting bookings and published schedules before closure becomes effective.

The original Hub establishment fee is a sunk cost. Restoring Hub status requires a new application and payment.

Stored Hub XP should become dormant rather than vanish immediately. A future decay or retention rule may determine how much maturity remains after a prolonged closure; the exact rule is not yet finalized.

Closing an Operating Base separately requires aircraft to be reassigned or transferred and local obligations to be resolved. Its detailed workflow remains future design.

## 12. System Boundaries

| System | Responsibility |
|---|---|
| Fleet Management | Owns individual aircraft and each aircraft's persistent home-base assignment. |
| Base Management | Owns the airline's Operating Base role, aircraft-stationing permission, local parking arrangements, and access to acquired operational support. |
| Hub Management | Owns Hub applications, Hub status, passenger-connection permission, Hub XP, Hub levels, and connecting-network benefits. |
| Market & Route Management | Owns country and market access, route rights, and airport-pair market participation. |
| Airport Management | Owns physical airport capacity, available stands, gates, terminals, runways, developable space, and airport constraints. |
| Scheduling | Owns rotations, timetables, positioning flights, aircraft-time allocation, continuity, and the aircraft's planned activity to and from its home Base. |
| Aircraft Operations | Owns each aircraft's actual location and current operational state. |
| Maintenance | Owns servicing requirements, maintenance work, facility compatibility, downtime, and return to service. |
| Passenger Simulation | Searches for, validates, evaluates, and books connecting itineraries through eligible Hubs. |
| Finance | Records Hub fees and overhead, Base and facility costs, parking, leases, services, and positioning expenses. |
| Fuel Management | Owns fuel purchasing, storage, inventory, pricing, and consumption. |

Base & Hub Management coordinates these systems but does not duplicate their source data or bypass their constraints.

## 13. Airport Expansion Spillover

Airport development is related to Bases and Hubs but belongs to the separate [`Airport Management`](./Airport%20Management.md) architecture.

Airports do not gain runways, terminals, gates, parking, hangars, fuel facilities, or other physical infrastructure from Hub levels. Each airport instead retains its historical footprint, infrastructure, available land, constraints, and future development potential.

Airport expansion is strategic placement rather than detailed manual construction. Future player-controlled development uses simple lines, boxes, templates, or anchor points, while an automatic connector handles minor taxiway, apron, gate, service, and internal-routing geometry.

Extraordinary late-game projects may include land acquisition, relocation, reclamation, demolition, redevelopment, or replacement airports. They remain expensive, slow, and unable to overcome genuinely impossible geography or aviation-safety constraints.

## 14. Fuel Infrastructure Spillover

Fuel infrastructure is a physical airport facility supporting airline operations. It does not require Hub status.

The intended responsibility split is:

- Airport Management determines whether suitable land and infrastructure are available;
- Base Management allows the airline to establish or lease a local fuel operation;
- Fuel Management owns purchasing, storage, stock, pricing, and consumption; and
- Finance records construction, lease, purchase, and operating costs.

An Operating Base may therefore support airline fuel storage without being a passenger Hub. Detailed fuel infrastructure remains a future system.

## 15. Non-Goals and Deferred Decisions

This architecture intentionally does not finalize:

- exact Base-establishment rules and costs;
- Hub prices and progressive cost formulas;
- recurring Hub-overhead formulas;
- Hub XP thresholds, level counts, or unlock tables;
- minimum connection-time calculations;
- parking, gate, terminal, or hangar capacity formulas;
- detailed facility acquisition and lease mechanics;
- airport construction or ownership mechanics;
- detailed schedule algorithms and recurrence implementation;
- exact home-base transfer and remote-operation validation;
- Hub closure wind-down timing;
- Hub XP decay or restoration formulas;
- detailed fuel infrastructure; or
- persistent schema fields and exact names.

New persistent fields must be defined in the canonical template/schema reference before code implementation.

## 16. Finalized Architecture

The following decisions should not change without redesigning Base & Hub Management:

```text
Every Hub is an Operating Base; not every Operating Base is a Hub.

Bases support and station aircraft. Hubs additionally connect passengers.

The starting airport is a Base, not a Hub.

Non-Hub to non-Hub routes are permitted when access and route rights exist,
but an airline cannot connect passengers between its own flights through a
non-Hub. An inter-airline transfer does not grant either airline Hub status.

Hub status requires an application and a one-time establishment payment.
Additional active Hubs become progressively more expensive.

Recurring Hub overhead is separate from airport fees and scales mainly with
actual connecting passengers handled and operational complexity.

Hub XP and levels represent the maturity of the airline's connecting operation,
not the airport's physical infrastructure.

Aircraft stationing is constrained by real parking and facility availability,
not an arbitrary aircraft limit tied to Hub level.

Every aircraft has a home Base. A home-base transfer requires an explicit action
and the aircraft's physical arrival through a revenue or positioning flight.

Home Base is an operational anchor with scheduled activity to and from it, not
an arbitrary weekly or monthly return requirement. Maintenance may occur at any
Operating Base with the required facility.

Removing Hub status disables passenger connections and Hub benefits while
preserving point-to-point operations and, if retained, the Operating Base.

Airport expansion and fuel infrastructure remain separate future systems.
```
