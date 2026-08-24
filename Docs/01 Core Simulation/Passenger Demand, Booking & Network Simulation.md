# Airline Tycoon - Passenger Demand, Booking & Network Simulation Architecture

> **Status:** Approved architecture. This document defines potential passenger demand, market discovery, route awareness, booking accumulation, itinerary choice, capacity-aware competition, direct and connecting journeys, and the staged path toward deeper passenger behavior. It does not finalize formulas, persistent schema fields, technical algorithms, marketing mechanics, loyalty progression, compensation values, or cargo behavior.

## 1. Purpose and Core Philosophy

Passenger simulation connects the world's desire to travel with the airline services that can satisfy it.

The defining rules are:

```text
Airport pairs have hidden travel potential.

Scheduled itineraries activate that potential for booking.

All airlines compete for the same passengers.

Passengers choose complete journeys, not isolated route records.
```

An airline does not receive private demand merely because it owns a route. Route ownership permits market participation; Scheduling must publish usable dated flights before passengers can book.

The system should reward useful networks, good schedules, appropriate prices, reliable operations, and informed commercial decisions without requiring individual passenger simulation or unnecessary realism.

## 2. Core Demand Concepts

The architecture distinguishes four concepts that must not be collapsed into one route-demand number.

| Concept | Meaning |
|---|---|
| Base Daily Bookers | The stable baseline number of new daily booking intentions for a directional airport pair. |
| Researched Demand | The airline's imperfect estimate of that hidden potential. |
| Addressable Demand | The portion that could reasonably consider the currently published itineraries. |
| Booked Demand | Passengers who selected an itinerary and reserved capacity. |

This distinction allows a market to be promising before service exists without creating waiting passenger records for every theoretical airport pair.

### 2.1 Directional airport-pair potential

Potential demand belongs to a directional origin-destination relationship. `DVO -> NRT` may differ from `NRT -> DVO` because each origin produces different travel behavior. The Stage 1 demand model resolves that potential into a stable `BaseDailyBookers` value: the normal daily number of new people at the origin who decide to seek a future journey to that destination.

The hidden score may eventually consider inputs such as:

- origin population and travel activity;
- destination attractiveness;
- distance;
- business, cultural, family, diaspora, and tourism relationships;
- domestic and international travel tendencies;
- season, holidays, and world events; and
- other data-driven market factors.

`BaseDailyBookers` is not passengers assigned to a flight, passengers flying today, a backlog, or demand created by a route. It is a directional daily booking-intention baseline. Exact inputs, normalization, coefficients, and balancing values are defined as configurable prototypes in the technical specification.

The first playable stage may use a simplified score and neutral values for advanced seasonality or events. That simplification must remain replaceable without changing the architectural distinction between potential and bookings.

### 2.2 No itinerary, no active booking demand

A hidden potential score may exist even when no service is available. However, the Booking Engine does not spawn active passengers for an origin-destination journey unless at least one valid dated itinerary is available within the applicable booking horizon.

```text
Hidden DVO -> NRT potential exists
                +
No valid published itinerary
                =
No active DVO -> NRT booking demand
```

When Scheduling publishes a valid itinerary, today's new booking cohort may enter Booking, select a desired future travel date, and evaluate the available services. A failed cohort does not automatically carry into tomorrow; tomorrow receives a newly generated cohort from the same baseline and that day's modifiers.

The network therefore activates travel potential; it does not invent a separate market for each route or airline.

### 2.3 Shared market pool

All qualifying airlines and itineraries compete for the same directional market. Adding another flight or airline does not duplicate the underlying pool.

Additional service can still increase the addressable portion of the market by providing:

- more useful departure or arrival times;
- more capacity;
- a direct alternative;
- a better price or product;
- a newly feasible Hub connection; or
- a more attractive or reliable journey.

This is improved market coverage, not a private demand bonus.

## 3. Market Research and Player Knowledge

Potential demand is hidden information. The player may enter a market because it appears commercially logical, but should not automatically know its exact size.

Research reveals an estimated range rather than a guaranteed result. For example:

```text
Estimated weekly DVO -> NRT market: 900-1,400 passengers
Confidence: Low
```

Deeper and more expensive research narrows the estimate. Research quality may later improve through:

- staff and department capability;
- player progression or perks;
- purchased market reports or data services;
- dedicated research technology;
- marketing or commercial-management capability; and
- the airline's own operating and booking history.

Actual market experience should eventually provide better forecasts than an initial external estimate.

Research and marketing have different responsibilities:

```text
Research tells the airline about passengers.

Marketing tells passengers about the airline's service.
```

Research reveals information. It does not create demand, increase awareness, reserve capacity, or guarantee profitability. Exact research tools, prices, confidence calculations, unlocks, staff effects, and interface belong to future Market Research, Marketing, progression, and technical design.

## 4. Route Awareness

A published service has market awareness. Even when an itinerary exists and its underlying market is strong, passengers do not automatically know that the service has launched.

Awareness may grow through:

- advertising and launch campaigns;
- continued scheduled operation;
- route age and operating history;
- passengers previously carried;
- word of mouth;
- broader airline recognition; and
- relevant market presence.

A sufficiently strong marketing campaign may raise awareness close to 100 percent from launch. Without marketing, awareness grows progressively as the service becomes established.

Awareness controls how much of the potential market discovers the service. It does not guarantee bookings. A fully known itinerary may still perform poorly because of price, timing, duration, connections, reliability, cabin product, or competition.

Market & Route Management owns airport-pair market presence. Marketing owns campaigns and advertising actions. Passenger Simulation consumes the resulting awareness when determining addressable demand and passenger choice.

Exact awareness formulas, decay, campaign reach, costs, and progression remain future Marketing and technical work.

## 5. Booking Horizon and Accumulation

Booking occurs against dated flight instances published by Scheduling. Passengers must never reserve seats directly against an abstract route right or infinite recurrence rule.

Bookings accumulate over the period between publication and departure:

```text
Dated itinerary is published
            -> passengers discover it
            -> bookings accumulate
            -> capacity becomes progressively reserved
            -> flight departs
```

Publishing farther in advance normally provides more daily cohorts with an opportunity to select the flight. A flight published shortly before departure may receive incomplete bookings even in a strong market. Stage 1 uses a rolling daily booking pipeline with a configurable hard maximum horizon of 365 days, not a fixed cumulative fill curve. Future passenger groups may use narrower preferred lead-time distributions within that maximum.

The booking and schedule-publication horizons may be configurable. Their exact lengths and booking-curve formulas are balancing and technical decisions.

Once a booking is confirmed:

- it reserves capacity on the selected dated flight or flights;
- later bookings see the reduced availability;
- its fare is normally locked; and
- later price changes normally affect only new bookings.

Flexible fares, voluntary changes, cancellations, refunds, and other exceptions remain later design work.

## 6. Passenger Scope and Future Groups

Stage 1 uses one generic Economy passenger group and one configurable choice profile. This isolates the demand and booking pipeline before cabin classes, fare families, and traveler purposes add more variables.

Later phases may divide the same pair demand into groups such as price-sensitive Economy, balanced Economy, Economy Comfort or Premium Economy, Business, First Class, tourists, business travelers, family visitors, overseas workers, students, or migrants. Those groups may use different choice weights and preferred booking lead times without replacing the underlying `BaseDailyBookers` model.

## 7. Itinerary Eligibility

An itinerary is an ordered sequence of dated passenger-flight instances that can carry a traveler from the intended origin to the intended destination.

A candidate itinerary must satisfy all applicable rules, including:

- every leg is published and bookable;
- airports and services are available on the travel date;
- departure, arrival, and connection times form a continuous journey;
- minimum and maximum transfer rules are satisfied;
- route rights and airline service rules permit every leg;
- airport capability, curfews, and other restrictions do not invalidate the plan;
- required Hub or inter-airline transfer rules are satisfied;
- sufficient appropriate capacity can be reserved; and
- the total journey is not rejected as unreasonable under the configured search limits.

Scheduling supplies dated flights and published times. Airport Management supplies airport conditions and physical constraints. Base & Hub Management supplies airline-specific connection permission. Passenger Simulation discovers and evaluates the itinerary.

The permanent architecture permits journeys of any reasonable length that satisfy the rules. The first implementation may limit the number of flights or connections searched to keep the system playable, understandable, and computationally stable.

## 8. Hubs, Airline Changes, and Connections

### 8.1 Same-airline connections

An airline may intentionally connect passengers between two of its own flights only at one of that airline's established Hubs.

Serving two routes through a normal Served Airport or Operating Base does not create same-airline connection functionality there.

Hub status grants permission to form the connection. It does not guarantee suitable times, enough capacity, acceptable journey quality, adequate transfer infrastructure, or successful bookings.

### 8.2 Multi-airline journeys

Passengers may combine services from different airlines. This allows airlines to feed passengers into one another's networks even when they are competitors.

For example:

```text
DVO -> MNL -> TPE     Dabudhi Air
TPE -> NRT            Japan Air
```

Dabudhi Air may connect its own flights at MNL if MNL is its Hub. The passenger may then change airlines at TPE for the final flight.

An airline change at a non-Hub does not grant either airline Hub functionality. It is an inter-airline transfer between separately valid services.

### 8.3 Unpartnered self-connections

Airlines without a partnership may still form an unprotected self-connection from the passenger's perspective.

Such a journey is less attractive because the passenger may need to:

- collect and recheck baggage;
- check in again;
- pass through additional security, immigration, or terminal transfers;
- allow a longer connection time;
- manage separate tickets; and
- accept the risk that one airline will not protect the onward journey if another airline causes a disruption.

Every additional airline change creates another attractiveness penalty and potential failure point.

### 8.4 Partnered connections

Future interline agreements, codeshares, and alliances may provide coordinated booking, baggage transfer, protected connections, rebooking, or compensation.

Protection depends on the actual agreement and ticket arrangement. Not every partnership automatically provides identical benefits.

For partnered itineraries, Booking may reserve all required legs as one protected transaction. For an unpartnered self-connection, the game may process the journey together internally for efficiency, but its passenger-facing rights and disruption risk remain those of separate bookings.

Detailed partnership types, commercial settlement, codeshare display, alliance benefits, and disruption obligations belong to future Partnership and Alliance architecture.

## 9. Itinerary and Product Choice

Passengers evaluate the complete journey and available cabin or fare product. They do not choose an airline in isolation and then receive an arbitrary seat.

Choice may consider:

- total fare;
- departure and arrival timing;
- total journey duration;
- directness and number of flights;
- layover duration and transfer difficulty;
- number of airline changes;
- protected versus unprotected connections;
- available cabin and fare product;
- airline reputation;
- demonstrated reliability;
- service quality;
- route awareness and relevant market presence;
- traveler-group preferences; and
- future loyalty preference.

Airport quality is not an independent universal choice score. Airport conditions affect the airline product through real consequences such as congestion, delays, transfer feasibility, handling, ground access, fees, and available facilities.

Each acceptable itinerary and product receives a passenger-group-appropriate score. The highest score should normally receive the largest share, but it does not automatically take the entire market. Inferior but acceptable alternatives may still attract passengers.

Technical feasibility does not guarantee acceptance. Extreme prices, poor timing, excessive connections, unreliable service, or difficult self-transfers may activate only a small portion of the hidden market potential.

Exact scoring factors, weights, randomness, score conversion, and fare-product behavior remain configurable technical and balancing work.

## 10. Capacity, Fallback, and Unmet Demand

Booking is capacity-aware. A passenger cannot remain assigned to a full flight.

When the preferred itinerary or product lacks capacity, Booking should:

1. attempt another acceptable product or itinerary when appropriate;
2. reserve the available capacity for successful bookings;
3. allow the remaining Stage 1 cohort to choose the outside option and leave the active booking process.

A connecting booking must have capacity on every required leg. Protected partnered itineraries reserve all legs as one transaction. The initial system must not partially confirm a protected journey and strand its remaining legs.

Stage 1 does not automatically carry unsuccessful passengers into tomorrow. Future traveler types may deliberately retry or postpone according to explicit probabilities; they must not create an automatic booking backlog.

The system should expose useful aggregate outcomes such as:

- potential and researched demand;
- addressable demand;
- bookings by itinerary and airline;
- direct and connecting passengers;
- passengers lost to poor awareness or unacceptable service;
- spilled passengers caused by full capacity;
- outside-option or otherwise unsuccessful booking intentions.

These are aggregated simulation and forecasting measures, not persistent objects for every unsuccessful traveler.

## 11. Booking Records and Flight Operation

Bookings are stored as aggregated batches rather than individual passenger objects. A batch may conceptually describe a count sharing the same relevant properties, such as:

```text
18 balanced travelers
Economy product
DVO -> MNL -> NRT
Booked on the same dated itinerary
```

Exact batch fields and schema belong to the future technical specification.

Booking confirmation and passenger carriage are distinct events:

- Booking reserves capacity and records the commercial commitment.
- Aircraft Operations determines whether each flight actually operates and when.
- Passenger handling resolves the consequences of changes or disruption.
- Finance records fares, refunds, compensation, and settlement.

A booked passenger is counted as carried only after the applicable flight operation succeeds.

## 12. Schedule Changes and Disruption

Changing or cancelling a published flight must not silently delete its bookings.

When an airline-caused schedule change affects a booking, the booking remains recorded and enters the applicable passenger-handling process. Possible outcomes may include:

- acceptance of the revised itinerary;
- rebooking on another service;
- rebooking through a partner;
- refund;
- accommodation or other care; and
- compensation.

For missed connections:

- the operating airline handles its own protected same-airline journey according to the applicable rules;
- a partnered journey receives only the protection established by its agreement and ticket arrangement; and
- an unprotected self-connection normally provides no automatic protection from the onward airline.

Airline fault, airport disruption, weather, passenger fault, and extraordinary events may create different responsibilities. Exact fault rules, reaccommodation priority, compensation, refunds, and settlement are deferred to Passenger Service, Partnerships, Economy, Finance, and technical design.

## 13. Reputation, Reliability, and Loyalty

Passenger choice should increasingly reflect actual airline behavior.

Reliability is not permanently determined by a fixed airline label. Repeated on-time operation, cancellations, delays, baggage performance, service delivery, and disruption handling may improve or damage the signals consumed by Booking.

Airline style may summarize a commercial product, but should not create an unexplained choice bonus that overrides the measurable fare, schedule, cabin, service, and reliability offered.

Loyalty is earned mainly after passengers actually travel. Good service, reliability, and disruption handling may strengthen it; poor experiences may weaken it.

Loyalty modifies future passenger choice but does not guarantee a booking when the loyal airline offers an unreasonable itinerary.

Detailed loyalty groups, progression, rewards, frequent-flyer programs, decay, and switching belong to the future Loyalty system. Passenger Simulation only consumes the resulting preference input.

The first implementation does not require persistent individual flyers. Future loyalty may operate through aggregated customer groups or market-level signals.

## 14. Future Overbooking

The first booking implementation must not confirm more passengers than the physical sellable capacity of the dated flight.

Overbooking is preserved as a future airline-controlled commercial policy. Possible policies may range from disabled or conservative to aggressive, with later custom limits.

The future system may use historical cancellation and no-show behavior to sell above physical capacity. If fewer passengers appear than booked, the airline benefits from improved seat use. If too many appear, the airline must manage consequences such as:

- volunteers;
- denied boarding;
- rebooking;
- refunds or compensation;
- accommodation;
- missed onward connections; and
- reputation and loyalty damage.

Overbooking should therefore be a revenue-versus-risk decision, not an automatic bonus. No-show behavior, oversell limits, denied-boarding priority, compensation, and financial formulas remain future Booking, Passenger Service, Economy, and technical design.

## 15. Staged Implementation

The complete architecture is a destination, not a requirement for the first playable passenger system.

### Stage 1 - Rolling Economy booking

The smallest complete stage may:

- calculate directional `BaseDailyBookers` from a normalized full-world destination universe;
- generate a new generic Economy booking-intention cohort each day;
- activate booking attempts only when usable future service exists;
- use a configurable 365-day hard maximum booking horizon;
- assign desired future travel dates and search around them;
- apply basic awareness;
- use one configurable Economy scoring profile;
- score fare, timing, duration, connections, reliability, reputation, Market Presence, random preference, and the outside option;
- reserve capacity in aggregated batches;
- support direct and approved connecting itineraries with atomic multi-leg capacity reservation;
- redistribute a capacity-constrained batch among remaining choices; and
- separately report daily booking intent, successful bookings, and passengers flying.

This may evolve from the current directional route-demand implementation without requiring the final system to preserve route-owned demand as its permanent source of truth.

### Stage 2 - Hub network booking

Add:

- same-airline one-connection itineraries through established Hubs;
- time-valid connection discovery;
- reservation across every leg;
- direct-versus-connecting choice; and
- Hub and feeder reporting.

### Stage 3 - Multi-airline journeys and commercial depth

Add progressively:

- unpartnered self-connections;
- airline-change penalties and longer transfer requirements;
- partnership-dependent protected connections;
- deeper research and awareness behavior;
- richer booking curves and fare products;
- schedule-change and disruption handling; and
- demonstrated reliability and aggregate loyalty inputs.

### Later stages

Later systems may add:

- more complex itineraries;
- detailed traveler purposes;
- persistent visitor and return groups;
- tourism continuation;
- migration and population effects;
- alliances and codeshares;
- overbooking, cancellations, and no-shows;
- detailed passenger rights and compensation;
- world events and deeper seasonality; and
- alternative airports and metropolitan catchments.

Every stage must remain small, stable, understandable, and playable.

## 16. System Boundaries

| System | Responsibility |
|---|---|
| Passenger Demand & Network Simulation | Owns potential demand concepts, traveler groups, addressable demand, itinerary evaluation, passenger choice, capacity fallback, and aggregate unmet demand. |
| Booking | Owns daily booking cohorts, desired travel dates, reservation batches, capacity consumption, confirmation state, the outside option, and future deliberate retry behavior. |
| Scheduling | Owns canonical services, planned aircraft assignments, publication, dated flight instances, booking availability, and schedule-change events. |
| Aircraft Operations | Owns actual flight execution, actual times, delays, cancellations, substitutions, and completed carriage. |
| Market & Route Management | Owns airport-pair markets, access, route rights, lifecycle, market presence, and participation. |
| Base & Hub Management | Owns airline-specific Hub status, connection permission, Hub progression, and connecting-operation benefits. |
| Airport Management | Owns airport conditions, physical constraints, transfer infrastructure, congestion, facilities, fees, ground-access opportunities, and airport-caused operational effects. |
| Fleet Management | Owns aircraft assets and persistent cabin configuration; Booking consumes the resulting sellable products and capacity. |
| Marketing | Owns advertising actions, campaigns, spend, and commercial awareness effects. |
| Market Research | Owns research actions, costs, confidence, information quality, and player-facing estimates. |
| Reputation and Reliability | Own the airline-wide or service-derived signals created by actual commercial and operational performance. |
| Loyalty | Owns future learned passenger preferences and loyalty progression; Booking consumes the resulting choice input. |
| Partnerships and Alliances | Own commercial agreements, interline protection, codeshares, through-booking rights, baggage handling, and partner obligations. |
| Passenger Service | Owns future reaccommodation, care, denied boarding, and passenger-handling policy. |
| Economy and Finance | Own economic conditions, fare settlement, refunds, compensation, revenue, costs, and financial reporting. |
| Tourism and Dynamic World | Supply future destination appeal, seasons, holidays, events, and persistent travel behavior. |
| AI Competition | Chooses AI routes, schedules, fares, products, marketing, research, and commercial policies under the same passenger rules. |
| Cargo | Owns future freight demand, products, booking, capacity, transfers, and operations. |

Passenger Simulation coordinates these inputs but must not duplicate their authoritative state.

## 17. Preserved Spillover

The following decisions must be preserved for later documents rather than silently lost:

- **Passenger Demand Technical Specification:** `BaseDailyBookers`, daily cohort generation, future-date selection, itinerary-search algorithms, caches, batch schemas, capacity transactions, deterministic randomness, processing order, serialization, migration, metrics, and tests.
- **Economy:** macroeconomic demand conditions, difficulty effects, inflation, fare economics, refunds, and compensation values.
- **Marketing and Market Research:** awareness growth and decay, campaign reach, research tools, cost, confidence, staff, perks, and progression.
- **Passenger Service:** voluntary changes, flexible tickets, cancellations, no-shows, standby, denied boarding, reaccommodation, care, and passenger rights.
- **Loyalty:** repeat-customer groups, experience effects, frequent-flyer programs, rewards, decay, and switching.
- **Tourism and Dynamic World:** trip purposes, visitor stays, progressive journeys, returns, migration, holidays, seasons, and events.
- **Partnerships and Alliances:** interline agreements, codeshares, through-ticketing, baggage transfer, protection, and commercial settlement.
- **AI Competition:** research, forecasting, marketing, network, schedule, price, partnership, and overbooking strategy using the same information and simulation rules as the player.
- **Cargo:** freight-specific generation, routing, products, handling, payload, capacity, booking, and economics. Cargo may reuse generic time-dependent network infrastructure but is not governed by passenger behavior.

## 18. Non-Goals and Deferred Decisions

This architecture intentionally does not finalize:

- potential-demand formulas or coefficients;
- future passenger-specific preferred lead-time distributions;
- traveler-group shares or scoring weights;
- awareness formulas, decay, campaign costs, or research confidence;
- itinerary search limits or pathfinding algorithms;
- exact minimum and maximum connection times;
- partnership types or settlement;
- persistent schemas or field names;
- batch splitting and merging algorithms;
- detailed fare families, upgrades, downgrades, or flexible tickets;
- refunds, compensation, passenger rights, or fault formulas;
- loyalty mechanics;
- overbooking, cancellation, and no-show mechanics;
- persistent tourism, return, or migration behavior;
- alternative-airport and catchment substitution;
- detailed seasonality or world events; or
- cargo simulation.

New persistent fields must be defined in the canonical template/schema reference before code implementation.

## 19. Finalized Architecture

The following decisions should not change without redesigning Passenger Demand, Booking & Network Simulation:

```text
Every directional airport pair has hidden demand-side potential. Stage 1 resolves
it into BaseDailyBookers: the stable baseline number of new daily booking
intentions for that pair, not passengers flying or assigned to a flight.

No valid published dated itinerary means no active booking demand. Publishing
a usable itinerary activates potential during its booking period.

All airlines and itineraries compete for one shared market. Flights do not
create private or duplicated passenger pools.

Potential demand, researched estimates, addressable demand, and confirmed
bookings are separate concepts.

Research reveals imperfect market information. Marketing creates awareness.
Neither guarantees bookings.

New cohorts enter Booking every day and search future dated flight instances
within the hard booking horizon. Repeated cohorts create rolling accumulation.
Unsuccessful Stage 1 cohorts do not automatically carry into the next day.

The first passenger model uses one generic Economy group. Cabin classes,
choice segments, traveler purposes, and persistent traveler lives are later layers.

Passengers evaluate the complete itinerary and cabin or fare product. Better
options win larger shares, but acceptable alternatives may still be chosen.

An airline connects between its own flights only through its own Hubs.
Passengers may also change airlines through partnered or unpartnered journeys.

Unpartnered self-connections are less attractive, require more transfer time,
and normally lack onward protection. Partner protection depends on the actual
agreement and ticket arrangement.

Airport quality is not an independent universal choice score. Airport
conditions influence bookings through access, operations, cost, feasibility,
transfer quality, and reliability.

Full preferred services cause redistribution to other acceptable options.
Unsuccessful Stage 1 bookers leave through the outside option without forming
an automatic backlog; deliberate probabilistic retries are future behavior.

Bookings use aggregated passenger batches. A booking is not counted as carried
until the applicable flight operation succeeds.

Schedule changes preserve affected bookings and initiate passenger handling;
they do not silently erase commercial commitments.

Reliability is earned through actual operations. Future loyalty modifies
choice but does not guarantee an unreasonable booking.

Initial booking cannot exceed physical capacity. Overbooking is a deferred
airline-controlled revenue-versus-risk policy.

The architecture is implemented through stable playable stages. Technical
formulas, schemas, algorithms, and future-system mechanics are designed later.
```

## Milestone 4.5A implementation boundary (2026-08-20)

The implemented demand runtime now retains compact per-origin full-universe
normalization facts and reconstructs exact directional Model 3 projections on
demand. This representation does not change hidden potential, and unserved
destinations remain in normalization.

Direct active-market discovery is exposed through a rebuildable provider
boundary over usable published dated passenger service in an explicit horizon.
Its result selects sparse current-day work only; it neither creates nor
renormalizes demand. Route rights or connections without service do not
activate, while remaining capacity does not deactivate a published market.
Connecting-pattern discovery and Booking horizon policy remain unimplemented
provider extensions for Milestone 5.

The current `processed_cohorts` collection remains transitional Demand-owned
continuation authority. The approved future transition is an atomic
Demand-to-Booking daily transaction with a Booking-owned checkpoint and sparse
outcome metrics. No such state is added in Milestone 4.5A; checkpoint creation,
marker migration, equivalent no-reroll proof, history compaction, and marker
removal are deferred to Milestone 5.

## Milestone 4.5B-1 architecture boundary

Model 4 introduces an authority hierarchy between the origin pool and airport
destinations:

```text
OriginDailyBookingPool
    -> versioned travel-scope envelope
    -> country allocation inside international scopes
    -> pure region aggregation
    -> country-local airport allocation
```

The schema foundation identifies regions and countries with immutable IDs,
maps airports to country IDs, and records whether an airport participates in
the later demand allocator. A region is only a grouping and aggregation result;
it cannot own a competing demand formula. The versioned Alpha V1 travel-scope
profile is `6500` domestic, `2500` home-region international, and `1000`
rest-of-world international basis points. Complete country overrides are keyed
by immutable country ID. Neutral country attractiveness and relationship values
are `10000`.

This is a safe staged boundary, not Model 4 activation. Schema-2 worlds continue
to calculate Model 3 exactly. Historical and newly produced Model 3 cohorts use
a versioned wrapper without changing the V1 payload or fingerprint material.
No Model 4 revision context or cohort may be active, and no production command
can switch the demand model to 4. Service, airline, route, schedule, capacity,
pack lifecycle, player ownership, and UI focus never affect normalization.

4.5B-2 implements the numerical scope/country/airport derivation and atomic
Model 3-to-4 activation. 4.5B-3 owns pack materialization and lifecycle. Booking,
capacity commitments, connections, operations, finance, save/reload, and
compaction remain outside this increment.

## Milestone 4.5B-2 architecture boundary

Model 4 now implements the hierarchy above as one demand-owned, service-neutral
derivation. Atomic activation is explicit and revision-checked; it never occurs
during migration, validation, loading, or ordinary Model 3 work. Every current
Model 4 revision owns one fingerprinted context pinning model, configuration,
travel-scope, universe date, market-pack, multiplier bounds, and input witness.

The origin pool is first conserved across the exact 6500/2500/1000 prototype
envelope. International scopes allocate to effective countries by population,
quantized centroid distance, attractiveness, and relationship. Regions merely
sum country results. Country amounts then allocate locally by airport
population, distance, and destination type. Unavailable airports and countries
without materialized airports stay latent, so changing service, schedules,
capacity, UI focus, or pack status cannot renormalize hidden potential.

Historical Model 3 markers and new Model 4 markers coexist in the same
market/date keyspace and are reused according to their stored contract. Only
prospective active markets create Model 4 intent. The exposed active-day result
is the future Booking boundary's input, not Booking state: it contains exact
baselines, multipliers, revisions, active IDs, and resolved integer intent but
does not choose itineraries, reserve capacity, or post money.

4.5B-3 still owns global airport-pack data and the complete materialization,
enable, disable, and re-enable lifecycle. Milestone 5 still owns Booking
checkpoints, desired travel dates, itinerary choice, and reservations.
