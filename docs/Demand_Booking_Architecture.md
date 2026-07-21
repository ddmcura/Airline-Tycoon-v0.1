# Airline Tycoon — Passenger Demand, Booking, and Network Simulation Architecture

## 1. Purpose

The passenger simulation should model how people move through an airline network.

It should not assign fixed demand directly to individual routes.

Instead, cities generate people who want to travel. Those travelers choose destinations. The available airline network then determines whether those journeys are possible and which airline carries them.

The core principle is:

```text
Passengers create travel demand.

Routes satisfy travel demand.

Airlines compete to carry the passengers.
```

Airline Tycoon should therefore behave as a transportation network simulation rather than a traditional route-demand simulator.

---

## 2. Transportation Network Philosophy

Passengers do not begin by choosing a flight.

They begin by deciding that they want to travel.

The simulation follows this order:

```text
A city generates potential travelers
                    ↓
Travelers choose destinations
                    ↓
The network searches for possible journeys
                    ↓
Airlines compete for those travelers
                    ↓
Passengers travel
                    ↓
They later return, continue, stay, or migrate
```

As the airline network grows, more journeys become possible.

A new route can therefore create traffic on several existing routes, not only on the route that was added.

Example:

```text
Existing route:

DVO → MNL
```

A new route opens:

```text
MNL → NRT
```

This now creates a possible journey:

```text
DVO → MNL → NRT
```

The DVO–MNL route gains connecting passengers even though Davao’s population and local demand did not change.

The value came from improved network connectivity.

---

## 3. Undecided Traveler Pool

Every airport or city generates a daily pool of people who want to travel.

At this stage, they have not yet chosen destinations.

Example:

```text
DVO

↓

300 undecided travelers
```

The pool represents people who are willing or preparing to travel that day.

The simulation does not need to create 300 individual passenger objects.

It only needs to store the number of undecided travelers.

---

## 4. Role of the Original Demand Formula

The original demand formula remains part of the system.

It no longer directly generates a fixed number of passengers for a specific route.

Instead, it has two purposes.

### 4.1 Origin pool generation

The formula helps determine how many undecided travelers an origin creates.

Possible factors include:

```text
Population
Travel rate
Economic activity
Airport importance
Season
Local events
Tourism activity
Business activity
```

Example:

```text
DVO daily undecided traveler pool:

300
```

### 4.2 Destination weighting

The formula also determines the relative attractiveness of possible destinations.

Example:

```text
DVO → MNL weight: 40
DVO → CEB weight: 30
DVO → TAG weight: 10
DVO → NRT weight: 2
```

These values are not fixed passenger counts.

They are relative destination probabilities.

After normalization, the 300 undecided travelers are divided into destination batches.

Example result:

```text
126 want MNL
101 want CEB
50 want TAG
7 want NRT
16 want other destinations
```

The exact results may vary each day because destination assignment uses weighted randomization.

---

## 5. Origin–Destination Relationships

Every airport pair may have a hidden origin–destination relationship.

Example:

```text
DVO → NRT
```

The relationship may be small, but it exists.

Possible factors include:

```text
Population
Distance
Tourism appeal
Business connections
Cultural links
Diaspora
Migration patterns
Domestic travel preference
International travel preference
Seasonal activity
```

The relationship determines how likely travelers from the origin are to choose that destination.

It does not guarantee that passengers can currently reach it.

---

## 6. Reachable Destination Filtering

Before destination selection, the game determines which destinations are currently reachable from the origin.

A destination is reachable when a valid direct or connecting journey exists.

Example:

```text
DVO → MNL
MNL → NRT
```

Therefore:

```text
DVO → NRT
```

is reachable.

The destination may participate in Davao’s active destination draw.

However:

```text
MNL → NRT
```

existing by itself does not make NRT reachable from DVO.

There must be a continuous usable path from DVO to NRT.

The important distinction is:

```text
OD relationships may always exist.

Reachability determines whether they are active today.
```

An unreachable destination keeps its hidden relationship weight but does not receive active traveler batches.

When the network expands and makes the destination reachable, that weight becomes active.

---

## 7. Destination Choice Comes Before Airline Choice

Passengers first decide where they want to go.

Only afterwards do they compare available airlines and itineraries.

Example:

```text
Traveler intention:

DVO → NRT
```

Possible journeys may include:

```text
Airline A:

DVO → MNL → NRT
```

```text
Airline B:

DVO → NRT
```

```text
Airline C:

DVO → CEB → MNL → NRT
```

The destination decision belongs to the passenger.

The airline decision belongs to the booking system.

This separation prevents airlines from owning artificial demand.

---

## 8. Shared Passenger Pool

All airlines compete for the same passenger pool.

Passengers belong to the world simulation, not to a specific airline.

Incorrect model:

```text
Airline A receives 100 passengers.

Airline B separately receives another 100 passengers.
```

Correct model:

```text
Shared passenger pool:

100 travelers want DVO → NRT.
```

All qualifying airlines compete for those same 100 travelers.

Possible result:

```text
Airline A: 45
Airline B: 32
Airline C: 8
Postponed: 10
Cancelled: 5
```

This creates natural market share and airline competition.

---

## 9. Booking Engine

The booking engine searches the airline network for valid journeys.

The full flow is:

```text
Undecided traveler pool
            ↓
Destination selection
            ↓
Traveler type assignment
            ↓
Reachability check
            ↓
Itinerary search
            ↓
Airline competition
            ↓
Seat reservation
            ↓
Flight operation
            ↓
Passenger persistence
```

The booking engine may compare:

```text
Directness
Number of connections
Total travel time
Layover time
Ticket price
Airline reputation
Airline reliability
Airline style
Service quality
Passenger preferences
```

---

## 10. Itinerary Acceptance

Not every traveler accepts every possible itinerary.

A direct flight should have the highest acceptance.

Example initial behavior:

```text
Direct journey:

Almost all willing travelers consider it.
```

```text
One connection:

A smaller percentage accepts it.
```

```text
Two connections:

A much smaller percentage accepts it.
```

```text
Three or more connections:

Very few travelers accept it.
```

Possible provisional values:

```text
Direct: 100%
One connection: 70–80%
Two connections: around 50%
Three connections: very low
```

These are balancing values and should remain configurable.

---

## 11. Itinerary Score

Accepted itineraries receive a score.

Possible factors include:

```text
Directness
Travel time
Layover quality
Price
Airline reputation
Reliability
Service quality
Airline style
Traveler type
```

Example:

```text
Business traveler:

Strong preference for direct flights,
short travel time,
and reliable airlines.
```

```text
Tourist:

Stronger preference for low price,
reasonable journey time,
and destination access.
```

```text
OFW:

Strong preference for affordability,
availability,
and baggage value.
```

Different airlines can therefore attract different passenger types.

---

## 12. Airline Reputation and Style

Each airline has its own reputation and operating identity.

Possible airline styles include:

```text
Low-cost
Full-service
Regional
Premium
Hybrid
Charter
```

Examples:

### Low-cost airline

```text
Lower prices
Stronger appeal to budget travelers
Weaker appeal to premium travelers
```

### Full-service airline

```text
Higher service quality
Stronger reputation
Greater business-traveler appeal
```

### Regional airline

```text
Strong feeder access
Secondary-airport coverage
Useful hub connections
```

Airline style affects itinerary selection.

It does not determine where passengers initially want to travel.

---

## 13. Network Value Effect

Adding a route increases more than the demand on that route.

It increases the number of origin–destination journeys the network can solve.

Example network:

```text
MNL → DVO
```

Add:

```text
MNL → CEB
```

The hub becomes more connected.

Add:

```text
MNL → HKG
```

More domestic cities may now reach Hong Kong through Manila.

Add:

```text
MNL → NRT
```

More origins may now reach Japan through Manila.

This produces natural hub-and-spoke behavior.

Possible future hidden metrics include:

```text
Network Connectivity Score
Hub Reachability
Network Value
Reachable OD Pairs
```

These metrics may later influence:

```text
Airline prestige
Passenger confidence
Corporate contracts
Tourism growth
Alliance attractiveness
```

---

## 14. Tourism

International tourists may initially choose a country or major gateway rather than a complete multi-city journey.

Example:

```text
Home country:

United States
```

```text
Target country:

Philippines
```

```text
Initial gateway:

MNL
```

After arrival, the tourist later decides whether to:

```text
Visit another tourist destination
Return home
Stay longer
Travel to a nearby country
```

Possible journey:

```text
USA → MNL
```

Later:

```text
MNL → TAG
```

Later:

```text
TAG → PPS
```

Later:

```text
PPS → BKI
```

Later:

```text
BKI → USA
```

The full journey is not generated at the start.

---

## 15. Progressive Tourism

Tourists choose destinations one stop at a time.

A tourist may visit approximately two to four tourist locations, depending on trip duration and available flights.

The next destination may be chosen using:

```text
Tourism rating
Distance
Flight availability
Journey quality
Remaining stay
Season
Country preference
Regional preference
```

Tourist trips do not need to remain domestic.

A tourist visiting the Philippines may later travel to:

```text
Hong Kong
Singapore
Bangkok
Kota Kinabalu
```

when those destinations are nearby, reachable, and attractive.

---

## 16. Progressive Journeys

Multi-city journeys should not be permanently generated in advance.

Instead of creating:

```text
USA → MNL → TAG → PPS → CEB → USA
```

the game creates one committed destination at a time.

Example:

```text
Decision 1:

USA → MNL
```

After arrival:

```text
Decision 2:

MNL → TAG
```

After arrival:

```text
Decision 3:

TAG → PPS
```

After arrival:

```text
Decision 4:

PPS → USA
```

This allows the journey to respond to:

```text
New routes
Closed routes
Schedule changes
Ticket price changes
Full flights
Network disruptions
```

---

## 17. Passenger Persistence

Passengers do not disappear after reaching their destination.

They remain in the simulation as aggregated traveler groups.

Example:

```text
12 tourists

Home:
DVO

Current location:
NRT

Next decision:
10 days from now
```

The group may later:

```text
Return home
Continue to another destination
Extend its stay
Migrate
```

The game stores groups and counts rather than individual passengers.

---

## 18. Traveler Groups

A group may be represented conceptually as:

```text
Home
Current location
Traveler type
Passenger count
Arrival date
Next decision date
Remaining tourist stops
Current status
```

Example:

```text
Home: MNL
Current location: DVO
Type: Tourist
Count: 20
Next decision: Day 154
```

On Day 154, the group may split.

Example:

```text
12 return to MNL
5 continue to CEB
2 extend their stay
1 migrates to DVO
```

This produces future travel demand without creating individual passenger records.

---

## 19. Traveler Types

Initial traveler types may include:

```text
Domestic leisure
Tourist
Business
Family visit
OFW
Migrant
```

Each traveler type has different behavior.

### Tourist

Typical stay or trip duration:

```text
5 to 30 days
```

Possible behavior:

```text
Continue traveling
Return home
Extend stay
```

### Business traveler

Typical stay:

```text
1 to 3 days
```

Possible behavior:

```text
Return home
Continue to another business city
```

### OFW

Typical stay:

```text
6 months to 2 years
```

They should remain inactive until their future decision date rather than being processed every day.

### Migrant

Migrants do not automatically return.

They become residents of the destination.

---

## 20. Migration

Migration permanently changes the traveler’s home location.

Example:

```text
DVO resident migrates to NRT
```

After arrival:

```text
DVO resident pool decreases
NRT resident pool increases
```

Future travel from that person or group originates from NRT.

Migration should affect the game-world population layer rather than rewriting the original airport reference data.

---

## 21. Return Travel

Temporary travelers eventually create reverse or onward demand.

Example:

```text
MNL → DVO
```

After staying in Davao:

```text
DVO → MNL
```

This helps prevent unrealistic permanent one-way demand imbalance.

Return travel does not need to occur immediately.

Different traveler types return after different periods.

Return movement is therefore distributed across future days.

---

## 22. Demand Snowballing Through Network Growth

A larger network creates more usable journeys.

More usable journeys create more active destination choices.

More destination choices create more passengers.

More passengers strengthen feeder routes and hubs.

Example:

```text
Small network
    ↓
Few reachable OD pairs
    ↓
Limited traffic
```

```text
Expanded network
    ↓
More reachable OD pairs
    ↓
More connecting journeys
    ↓
Stronger hub traffic
```

Demand grows because the network becomes more useful, not because the game applies an arbitrary route bonus.

---

## 23. Direct Flights Naturally Win

Direct flights should usually outperform connecting alternatives.

They offer:

```text
Shorter travel time
Lower disruption risk
No layover
Higher convenience
Greater acceptance
```

However, connecting journeys remain important when:

```text
No direct route exists
The connection is much cheaper
The connecting airline has better service
The schedule is more convenient
```

This creates natural competition between nonstop and hub-based networks.

---

## 24. Aggregated Simulation

The simulation must use grouped passenger counts.

It must not create millions of individual traveler objects.

Example destination batches:

```text
54 MNL → DVO leisure travelers
17 MNL → CEB business travelers
12 MNL → NRT tourists
```

Possible airline split:

```text
20 choose Airline A
25 choose Airline B
6 postpone
3 cancel
```

After arrival, similar groups may be stored together.

This allows a living passenger simulation without excessive performance cost.

---

## 25. Two Connected Simulations

The game contains two major simulations.

### Population movement simulation

```text
People
    ↓
Want to travel
    ↓
Choose destinations
    ↓
Travel
    ↓
Stay
    ↓
Travel again
```

### Airline operations simulation

```text
Aircraft
    ↓
Routes
    ↓
Schedules
    ↓
Capacity
    ↓
Pricing
    ↓
Profit
```

The Booking Engine connects them.

The population simulation creates traveler intentions.

The airline simulation provides possible journeys.

---

## 26. Core System Architecture

```text
Demand Generator
        ↓
Destination Allocation
        ↓
Network Reachability
        ↓
Itinerary Search
        ↓
Airline Competition
        ↓
Booking and Seat Reservation
        ↓
Flight Simulation
        ↓
Passenger Persistence
        ↓
Future Travel Demand
```

Each system should have one responsibility.

### Demand Generator

Creates undecided traveler pools.

### Destination Allocation

Assigns destinations using OD weights.

### Network Reachability

Determines which destinations can currently be reached.

### Itinerary Search

Finds valid direct and connecting journeys.

### Airline Competition

Divides the shared pool among airline options.

### Booking

Reserves seats across all required legs.

### Flight Simulation

Moves confirmed passenger groups.

### Passenger Persistence

Determines future return, continuation, stay, and migration behavior.

---

## 27. Finalized Architecture

The following are core architectural decisions.

They should not change without redesigning the passenger system.

```text
Cities create undecided traveler pools.

The original demand formula determines pool size and OD weights.

Passengers choose destinations before choosing airlines.

Only reachable destinations enter the active destination draw.

Direct and connecting flights can satisfy the same destination intention.

All airlines share and compete for the same passenger pool.

Airline reputation and style affect airline choice.

Travelers are stored as grouped counts.

Passengers persist after arrival.

Tourism and multi-city travel are progressive.

Temporary travelers eventually return or continue.

Migrants transfer into the destination population.

The network creates new demand by making more journeys possible.
```

---

## 28. Values Reserved for Testing

The following values are intentionally not permanent.

They should remain configurable and be adjusted through gameplay testing.

```text
Daily travel rates
Origin pool sizes
OD formula coefficients
Distance penalties
Domestic and international modifiers
Connection acceptance percentages
Maximum allowed connections
Maximum layover times
Airline scoring weights
Price sensitivity
Reputation sensitivity
Traveler-type distribution
Tourist stop count
Tourist distance range
Stay durations
Return probabilities
Postponement behavior
Cancellation behavior
Migration rates
```

These are balancing values, not unanswered architectural questions.

---

## 29. Recommended Implementation Stages

### Phase 1 — Stateless demand and booking

```text
Generate undecided pools
Assign reachable destinations
Find direct or connecting journeys
Book seats
Remove passengers after arrival
```

Purpose:

```text
Test whether the network and booking gameplay work.
```

### Phase 2 — Return groups

```text
Store arrived traveler groups
Assign future return dates
Generate return bookings
```

Purpose:

```text
Create realistic reverse demand.
```

### Phase 3 — Passenger persistence

```text
Tourist continuation
Multi-city travel
OFW behavior
Migration
Population adjustments
```

Purpose:

```text
Create a living long-term travel simulation.
```

---

## 30. Final Philosophy

The Airline Tycoon passenger system should not ask:

```text
How much demand belongs to this route?
```

It should ask:

```text
How many people want to travel?

Where do they want to go?

Can the airline network take them there?

Which airline offers the best journey?

What do those travelers do after they arrive?
```

The final guiding principle is:

```text
Passengers own destinations.

Airlines own networks.

The booking engine connects them.
```
