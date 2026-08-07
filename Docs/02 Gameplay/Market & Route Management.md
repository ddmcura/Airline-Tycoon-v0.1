# Airline Tycoon - Market & Route Management Architecture

> **Status:** Approved architecture. This document defines the player-facing ownership, access, competition, and lifecycle rules for airline markets and routes. It does not define passenger formulas, scheduling algorithms, or detailed hub internals.

## 1. Purpose and System Boundary

Market & Route Management governs where an airline is legally and commercially allowed to operate, which airport-pair markets it controls, how it enters and develops those markets, and how it competes for passengers.

The core distinction is:

```text
Route = an owned airport-pair market and its operating rights

Flight = a scheduled aircraft movement that serves a route
```

A route is not a flight, a schedule, or a fixed block of demand. Owning a route permits the airline to serve that market, but service exists only after the required slots and a valid schedule are in place.

This document owns:

- domestic, country, and route access progression;
- route-right acquisition, retention, suspension, and forfeiture;
- airport-slot relationships at the architectural level;
- market presence and competition principles;
- the route lifecycle and strategic value of markets.

It intentionally leaves passenger generation and booking formulas to Passenger Simulation, aircraft rotations and timing rules to Scheduling, Operating Base and Hub roles to Base & Hub Management, and physical facilities to Airport Management.

## 2. Market Definition

### 2.1 Airport-pair markets

Every route is an airport-pair market, not a city-pair market.

```text
MNL-NRT is one market.
CRK-NRT is a different market.
```

Airports serving the same city may have different runway limits, fees, slots, access conditions, catchment areas, and strategic value. Those differences must remain meaningful.

### 2.2 Direction and service pattern

A route represents the airline's right to operate between its two airports. The detailed direction, frequency, timing, and aircraft assignment belong to Scheduling.

A route may connect:

- a hub to another hub;
- a hub to a non-hub airport; or
- airports that are otherwise technically and legally feasible under future network rules.

Passenger connections may occur only through Hubs. A non-Hub destination or Operating Base can be served normally, but it cannot act as a transfer point unless that airline has established it as a Hub under Base & Hub Management.

### 2.3 Derived route categories

Route categories are derived from airport and country reference data. They are not separate facts manually stored on each route unless implementation requirements later justify a cached value.

Examples include domestic, regional international, and other international categories. Any categorization logic must use the canonical airport and country data rather than ad-hoc route labels.

## 3. Access and Rights

Market entry uses distinct layers. Purchasing one layer does not silently grant the others.

### 3.1 Domestic rights

The player's starting Operating Base automatically grants domestic operating rights within that Base's country. This provides the initial market from which the airline can build its network even though the starting airport is not yet a Hub.

Domestic rights are country-specific. Opening a Base or Hub in another country does not automatically bypass that country's access rules unless a future approved access rule explicitly grants such rights.

### 3.2 Country access

Country access permits the airline to develop commercial routes involving suitable airports in that country. It is purchased separately from individual route rights.

Progression begins with the starting country's domestic access, then expands through paid regional and international country access. Later tiers may unlock cargo authority and other specialized traffic rights.

Country access is non-resellable. Money spent to obtain it is an entry cost, not an asset that can be sold back.

Country access is the route-development permission for the country. The airline does not need separate Airport Access merely to fly to each suitable airport.

### 3.3 Airport access and airport capability

Airport Access permits the airline to establish a permanent operational or commercial footprint at that airport. It may be required for:

- an Operating Base or Hub;
- airline lounges or offices;
- dedicated or contracted parking;
- hangars and maintenance facilities;
- airline fuel storage; and
- other locally controlled airline facilities.

Airport Access does not replace country access, route rights, or slots. Conversely, a normal revenue flight does not require Airport Access when the airline already has the required country access, airport-pair route right, slot or movement permission, and technical capability.

Airport operational capability is separate again. An airport must physically and regulatorily support the intended service. A domestic-only airport cannot handle an international flight until customs, immigration, security, terminal, runway, and other required capabilities exist. A future Airport Management or ownership system may allow the player to fund such a conversion.

### 3.4 Route rights

After the required country access exists, the airline must separately purchase the right to operate each airport-pair market.

Route rights are non-resellable. Permanently closing a route forfeits the right and its purchase cost. Re-entering that market later requires acquiring the route right again under the rules and price then in effect.

This separation creates two deliberate decisions:

1. whether a country is strategically worth entering; and
2. which airport-pair markets within that access area are worth owning.

### 3.5 Technical feasibility and player freedom

The game may warn the player about weak demand, high costs, poor strategic fit, or limited infrastructure, but it should not prevent the purchase of a poor route merely because the game predicts it will lose money.

A market may be acquired whenever legal access exists and its operation is technically feasible. Actual service must still satisfy constraints such as:

- aircraft range;
- airport runway requirements;
- airport restrictions;
- slot availability; and
- other aircraft or airport compatibility rules.

Players remain free to make unconventional, speculative, prestige-driven, or simply bad business decisions.

## 4. Airport Slots

Slots are operational assets distinct from country access and route rights. A route right allows entry into a market; slots provide permission to use the airports at specific operational opportunities required by a schedule.

Slots are tradable assets. The architecture must allow them to be acquired, retained, and transferred separately from route rights. Future systems may support negotiated purchases, sales, trades, leasing, or other market mechanisms.

Temporarily suspending a route does not automatically erase its ownership or associated retained assets. Detailed slot-use requirements, scarcity rules, timing, and scheduling validation belong to Airport Management and Scheduling.

## 5. Bases, Hubs, Aircraft, and Network Rules

Routes do not need to run only between hubs. Hub-to-non-hub service is a normal and necessary network pattern.

Operating Bases and Hubs have separate roles:

- aircraft are assigned to Operating Bases, whether or not those Bases are Hubs;
- an aircraft has planned activity to and from its assigned home Base without an arbitrary weekly or monthly return rule;
- passenger connections may occur only at Hubs; and
- parking, hangars, service infrastructure, and physical airport capabilities remain separate from Hub status.

These points are cross-system constraints, not definitions of Base, Hub, or scheduling internals. Base & Hub Management owns airline airport roles, stationing permission, Hub licenses, connection privileges, and Hub progression. Fleet Management owns each aircraft's home-base assignment. Airport Management owns physical capacity and facilities. Scheduling owns rotations, timing, validation, and flight construction.

## 6. Market Presence

### 6.1 Definition

Market presence represents the airline's current strength and credibility in an airport-pair market. It replaces the narrower idea of route reputation.

Market presence combines two broad qualities:

- **Awareness:** how familiar travelers are with the airline's offer in the market.
- **Operating maturity:** how established, dependable, and proven the airline's service is in that market.

The current market score is sufficient for gameplay. The architecture does not require permanent historical-stat archives for every past market state.

### 6.2 Growth and decline

Market presence grows through sustained, reliable service. Consistency matters: merely buying a right does not create mature market standing.

Presence may be boosted before launch through marketing and advertising, allowing the player to build awareness before the first flight. Pre-launch promotion should not instantly grant the operating maturity earned through actual service.

Service quality, reliability, continued operation, and relevant commercial actions may affect presence. Temporary suspension may halt growth or cause decline according to future balancing rules, but it does not erase route ownership.

### 6.3 Scope

Market presence belongs to the airport-pair market. Broader airline reputation is a separate airline-wide signal. The booking system may consider both without treating them as interchangeable.

## 7. Competition and Booking Principles

All airlines compete for a shared passenger pool. A route does not generate a private demand allocation for each airline.

Passengers compare qualifying services using booking scores appropriate to their traveler class or type. Price is a major factor, alongside:

- departure and arrival time suitability;
- airline perks and onboard or ground services;
- reliability;
- airline reputation; and
- market presence.

Different travelers may weight these factors differently. A business traveler may value timing and reliability more heavily, while a price-sensitive leisure traveler may accept a less convenient option for a lower fare.

Frequency is not an automatic scoring bonus. Additional departures are valuable when they create useful choices, better departure or arrival times, or more available capacity. Repeating poorly timed flights should not receive a reward simply because the raw frequency is higher.

Booking is capacity-aware. If the preferred service is full, passengers may choose a lower-scored qualifying alternative rather than disappearing or remaining assigned to an unavailable flight.

Detailed traveler segmentation, scoring weights, seat allocation, fallback behavior, and demand formulas belong to Passenger Simulation and Booking.

## 8. Route Value

A route's standalone profit is important but not its only source of value.

A weak standalone route may still make a positive strategic or network contribution by:

- feeding passengers into hub connections;
- making additional origin-destination journeys reachable;
- supporting aircraft utilization or network coverage;
- protecting or developing presence in a strategic market;
- enabling future expansion; or
- contributing to a broader competitive strategy.

Route reporting should therefore distinguish direct financial performance from network contribution when those supporting systems become available. The game should inform the player's decision without declaring that every individually weak route is worthless.

## 9. Route Lifecycle

The standard lifecycle is:

```text
Domestic or country access
        |
Route-right acquisition
        |
Slot acquisition
        |
Scheduling
        |
Active service
        |
Market-presence growth
        |
Expand, maintain, suspend, or close
```

### 9.1 Planned

The airline has the required access and route right but may still need slots, aircraft, or a valid schedule.

### 9.2 Active

The route has valid scheduled service. Flights compete for the shared passenger pool and sustained operation can grow market presence.

### 9.3 Suspended

A temporary closure suspends service but does not erase route ownership. The airline may retain the right and resume service later, subject to slot, schedule, and other operational rules.

### 9.4 Closed

A permanent closure relinquishes the route right. Its acquisition cost is forfeited, and the right cannot be resold. Any separately owned tradable assets, including slots, follow their own disposition rules rather than automatically inheriting the route right's treatment.

## 10. AI Fairness

AI airlines follow the same access, rights, slots, feasibility, market-presence, capacity, and passenger-competition rules as the player. They receive no hidden route, demand, booking, or operating cheats.

AI behavior may differ through explicit strategy and difficulty parameters, including:

- starting money;
- risk tolerance;
- expansion aggressiveness;
- pricing or service strategy;
- preferred network structure; and
- investment priorities.

Difficulty should change resources and decision-making behavior, not invalidate the shared simulation rules.

## 11. Future Scope: Airport Ownership

Airport ownership is approved future scope and is not part of the initial Market & Route Management implementation.

An airline or related company that owns an airport may later earn additional income from:

- landing fees;
- departure fees;
- terminal fees;
- slot transactions;
- hangar fees; and
- airport expansion or upgraded facilities.

Airport ownership must remain distinct from airline route rights. Owning an airport should not automatically grant every route or eliminate the access rules applied to airlines.

## 12. Non-Goals

This architecture intentionally does not define:

- passenger-demand formulas or traveler generation;
- booking-score formulas or numerical weights;
- itinerary search and seat-reservation algorithms;
- flight scheduling algorithms;
- weekly-rotation construction or validation;
- detailed hub licensing, facility, or capacity rules;
- detailed slot timing, allocation, or market mechanics; or
- airport-ownership implementation.

Those details belong to the systems that own them and may evolve without changing the market and route concepts defined here.

## 13. Related Systems

This system directly interacts with:

- **Passenger Demand, Booking, and Network Simulation** - owns demand, traveler types, itinerary choice, booking scores, capacity fallback, and passenger connections.
- **Scheduling** - owns the canonical future timetable, recurrence, specific planned aircraft assignments, positioning plans, effective-dated revisions, and dated flight publication.
- **Base & Hub Management** - owns Operating Base and Hub roles, aircraft-stationing permission, Hub licenses, passenger-connection privileges, and Hub progression. Physical airport infrastructure remains owned by Airport Management.
- **Fleet Management** - owns individual aircraft assets, their home-base assignment relationship, and persistent aircraft configuration. Aircraft Reference Data owns model specifications; Scheduling and other consuming systems evaluate operational feasibility.
- **Airport Management** - owns airport constraints, slot mechanics, fees, and future airport development or ownership.
- **Finance and Marketing** - own acquisition costs, route economics, advertising spend, and financial reporting.

This document defines the boundaries between those systems but intentionally does not define their internal behavior.

## 14. Finalized Architecture

The following are the core decisions that should not change without redesigning Market & Route Management:

```text
Routes are owned airport-pair markets and rights, not flights or demand.

The starting Operating Base grants domestic rights in its country; it does not
begin with Hub status.

Country access and route rights are separate, paid, and non-resellable.

Country access permits route development involving suitable airports. Airport
Access is instead required for Bases, Hubs, lounges, offices, dedicated parking,
hangars, fuel storage, and other permanent airline facilities.

Permanent closure forfeits a route right and its cost; suspension preserves ownership.

Slots are separate, tradable operational assets.

Passenger connections occur only through Hubs. Operating Bases without Hub
status remain point-to-point.

Market presence combines awareness and operating maturity.

All airlines compete for one shared passenger pool under the same rules.

Useful timing matters more than frequency for its own sake.

Strategic network contribution may justify a weak standalone route.

Players may operate poor ideas when they are legal and technically feasible.

AI airlines obey the same simulation rules and differ only through explicit parameters.
```
