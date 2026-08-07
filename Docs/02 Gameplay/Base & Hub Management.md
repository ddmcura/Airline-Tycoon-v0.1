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

Non-Hub routes operate point-to-point. Merely serving two routes through the same airport does not create a valid connecting itinerary.

For example, if an airline operates:

```text
CEB <-> MNL
CEB <-> DVO
```

while CEB is not that airline's Hub, passengers may book each market independently, but they may not book DVO -> CEB -> MNL as one connecting journey with that airline.

After the airline establishes CEB as a Hub, DVO -> CEB -> MNL may become a valid connecting itinerary. Passenger Simulation still determines whether the itinerary is feasible and attractive.

Hub status creates permission for passenger connections. It does not guarantee demand, suitable schedules, sufficient terminal capacity, or successful bookings.

## 4. Starting Airport

The player's starting airport begins as the airline's first Operating Base, not as a Hub.

At the start of the game:

- aircraft may be assigned to and stationed at the starting Base;
- aircraft rotations may originate and finish there;
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

Scheduling must eventually ensure that an aircraft's rotation begins from and returns to its assigned home Base according to the finalized rotation period and rules. The aircraft does not need to return after every individual flight.

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
| Scheduling | Owns rotations, timetables, positioning flights, aircraft-time allocation, and compliance with home-base return rules. |
| Aircraft Operations | Owns each aircraft's actual location and current operational state. |
| Maintenance | Owns servicing requirements, maintenance work, facility compatibility, downtime, and return to service. |
| Passenger Simulation | Searches for, validates, evaluates, and books connecting itineraries through eligible Hubs. |
| Finance | Records Hub fees and overhead, Base and facility costs, parking, leases, services, and positioning expenses. |
| Fuel Management | Owns fuel purchasing, storage, inventory, pricing, and consumption. |

Base & Hub Management coordinates these systems but does not duplicate their source data or bypass their constraints.

## 13. Airport Expansion Spillover

Airport development is related to Bases and Hubs but remains a separate future Airport Management / Airport Ownership system.

The approved direction is that airports should not simply gain physical infrastructure from Hub levels. Instead, each airport may have its own:

- developed area and existing infrastructure;
- available expansion land;
- surrounding-development, terrain, and environmental constraints;
- maximum practical footprint;
- runways and runway-upgrade potential;
- terminals, gates, and remote stands;
- parking and maintenance areas;
- fuel and cargo infrastructure; and
- other future airport assets.

Airports should behave like location-specific development sandboxes with different boundaries. Some may expand easily, while constrained airports may have little normal expansion potential.

Future late-game projects may allow extraordinary expansion through government agreements or airport ownership, including land acquisition, relocation compensation, utility or road relocation, reclamation, demolition, redevelopment, or replacement-airport construction. Such projects should be expensive, slow, and unable to overcome genuinely impossible safety or geographic constraints.

These are preserved architecture directions, not finalized construction mechanics.

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
- schedule and rotation algorithms;
- exact home-base transfer validation;
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
but passengers cannot connect through a non-Hub.

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

Removing Hub status disables passenger connections and Hub benefits while
preserving point-to-point operations and, if retained, the Operating Base.

Airport expansion and fuel infrastructure remain separate future systems.
```
