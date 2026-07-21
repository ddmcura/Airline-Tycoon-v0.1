# Airline Tycoon — Passenger Demand and Booking Technical Specification

> **Document Type:** Technical Specification
> **Status:** Design-ready; balancing values remain provisional
> **Purpose:** Convert the Passenger Demand, Booking, and Network Simulation architecture into implementable modules, data structures, processing steps, and testing rules.
>
> This specification must follow:
>
> * `Data/Templates/template_reference_with_rules.txt` as the source of truth for schemas.
> * `foldertree.txt` as the source of truth for module placement.
> * Existing hybrid `game_state` conventions.
> * Functions used only by this feature must remain inside the passenger simulation package.
> * Functions shared by several packages must be placed in `game/utils`.

---

# 1. Technical Principle

The system must not generate fixed daily demand directly for individual routes.

Instead, it must process passenger movement in the following order:

```text
Origin city creates an undecided traveler pool
                    ↓
Eligible destinations are identified
                    ↓
Origin–destination weights are calculated
                    ↓
Travelers are distributed into destination batches
                    ↓
Available itineraries are found
                    ↓
All airlines compete for the same batches
                    ↓
Seats are reserved across every itinerary leg
                    ↓
Flights transport booked travelers
                    ↓
Arrivals become persistent traveler groups
                    ↓
Traveler groups later return, continue, stay, or migrate
```

The original demand formula remains part of the system.

Its purpose changes from:

```text
Generate fixed route demand
```

to:

```text
Determine origin pool size and destination-pair weight
```

---

# 2. System Boundaries

The passenger simulation consists of separate subsystems.

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
Flight Execution
        ↓
Passenger Persistence
```

Each subsystem must have one clear responsibility.

## Demand Generator

Creates undecided travelers at an origin airport.

It must not:

* select an airline,
* reserve seats,
* operate flights,
* or modify aircraft.

## Destination Allocation

Assigns destinations to undecided travelers using origin–destination weights.

It must not choose an airline.

## Network Reachability

Determines whether at least one usable path exists between two airports.

It must not reserve seats.

## Itinerary Search

Produces valid direct or connecting travel options.

It must not generate travelers.

## Airline Competition

Scores available itineraries from all airlines and distributes the shared passenger batch among them.

It must not operate flights.

## Booking and Seat Reservation

Reserves capacity across every leg of a selected itinerary.

## Flight Execution

Moves confirmed passenger counts according to the schedule.

## Passenger Persistence

Stores arrived traveler groups and determines their future travel behavior.

---

# 3. Recommended Folder Structure

The current folder tree does not yet contain a dedicated passenger simulation package.

Add the following package only after updating `template_reference_with_rules.txt`.

```text
game
└── passenger_simulation
    ├── __init__.py
    ├── config.py
    ├── demand.py
    ├── destination_weights.py
    ├── reachability.py
    ├── itinerary_search.py
    ├── itinerary_scoring.py
    ├── competition.py
    ├── bookings.py
    ├── persistence.py
    ├── daily_processor.py
    └── serializers.py
```

Suggested responsibilities:

```text
config.py
    Balancing defaults and feature switches.

demand.py
    Origin travel-pool generation.

destination_weights.py
    Origin–destination pair score calculation and normalization.

reachability.py
    Cached network reachability checks.

itinerary_search.py
    Valid scheduled-path generation.

itinerary_scoring.py
    Passenger willingness and itinerary-quality scoring.

competition.py
    Shared-pool distribution among airlines.

bookings.py
    Seat reservation, booking batches, postponement, and cancellation.

persistence.py
    Visitor groups, future decisions, return travel, continuation, and migration.

daily_processor.py
    Coordinates the passenger simulation during Advance Day.

serializers.py
    Serialization and migration helpers for passenger-simulation state.
```

Functions useful to other game packages may be placed in:

```text
game/utils
```

Examples:

```text
game/utils/routes.py
    Generic route-key or route-direction helpers.

game/utils/time_utils.py
    Schedule and date calculations.

game/utils/airports.py
    Generic airport lookup and geographic-distance helpers.
```

Passenger-specific scoring and persistence logic must remain inside `game/passenger_simulation`.

---

# 4. Required Template Changes

Before implementing the new system, update:

```text
Data/Templates/template_reference_with_rules.txt
```

The template must document:

1. new airport demand fields,
2. new airline passenger-market fields,
3. global passenger-simulation state,
4. booking batches,
5. persistent traveler groups,
6. balancing configuration.

No implementation should introduce undocumented game-state keys.

---

# 5. Airport Data Additions

Existing airport fields already include useful demand inputs:

```text
population
city_type
regional_importance
hub_potential
tourism_rating
business_activity_level
luxury_travel_score
holidays
seasonal_demand
```

Additional fields may be needed.

Proposed airport schema addition:

```json
{
  "passenger_demand": {
    "base_travel_rate": 0.0,
    "domestic_travel_bias": 0.0,
    "international_travel_bias": 0.0,
    "migration_attractiveness": 0.0,
    "diaspora_links": {},
    "business_links": {},
    "tourism_source_markets": {},
    "destination_overrides": {}
  }
}
```

Example:

```json
{
  "passenger_demand": {
    "base_travel_rate": 0.002,
    "domestic_travel_bias": 1.25,
    "international_travel_bias": 0.65,
    "migration_attractiveness": 0.4,
    "diaspora_links": {
      "NRT": 1.15,
      "HKG": 1.10
    },
    "business_links": {
      "MNL": 1.30,
      "CEB": 1.10
    },
    "tourism_source_markets": {
      "US": 1.10,
      "JP": 1.25,
      "KR": 1.35
    },
    "destination_overrides": {
      "MNL": 1.20
    }
  }
}
```

These values are modifiers, not fixed passenger counts.

Missing optional modifiers must default to neutral values rather than causing errors.

---

# 6. Global Passenger-Simulation State

Add a global passenger-simulation section to `game_state`.

Proposed structure:

```json
{
  "passenger_simulation": {
    "schema_version": 1,
    "enabled": true,
    "last_processed_date": "",
    "network_revision": 0,
    "reachability_cache": {},
    "daily_market_summary": {},
    "pending_booking_batches": [],
    "persistent_traveler_groups": [],
    "metrics": {
      "travelers_generated": 0,
      "travelers_booked": 0,
      "travelers_postponed": 0,
      "travelers_cancelled": 0,
      "travelers_unreachable": 0,
      "connecting_travelers": 0
    }
  }
}
```

## Important distinction

Airline-specific passenger results belong inside the airline.

World passenger demand belongs in the global passenger-simulation section.

The shared travel pool must never be stored under one airline.

---

# 7. Airline Passenger-Market Fields

Each airline should contain fields describing its market identity.

Proposed structure:

```json
{
  "passenger_market": {
    "reputation": 50.0,
    "reliability": 50.0,
    "service_style": "full_service",
    "price_position": "standard",
    "connection_quality": 50.0,
    "market_share_history": {},
    "passengers_booked_total": 0,
    "passengers_carried_total": 0
  }
}
```

Possible `service_style` values:

```text
full_service
low_cost
regional
premium
hybrid
charter
```

These values affect itinerary selection.

They must not affect where passengers initially want to travel.

---

# 8. Daily Undecided Traveler Pool

Each origin airport creates a number of people who are considering travel that day.

They do not yet have destinations.

Conceptual formula:

```text
Daily Origin Pool
=
Population
× Base Travel Rate
× Economic Modifier
× Airport Modifier
× Seasonal Modifier
× Event Modifier
× Difficulty Modifier
```

Example:

```text
DVO population: 2,000,000
Base daily travel rate: 0.00015
Combined modifiers: 1.00

Daily undecided pool:
300 travelers
```

The exact formula and constants must remain configurable.

## Recommended implementation behavior

The result may be fractional.

Use stochastic rounding:

```text
Calculated pool: 300.72

Guaranteed travelers: 300
72% chance of one additional traveler
```

This preserves long-term averages without forcing every day to be identical.

---

# 9. Origin–Destination Pair Weight

For every eligible destination, calculate an origin–destination weight.

The weight is not a percentage until all eligible destination weights are normalized.

Conceptual formula:

```text
OD Weight
=
Destination Population Pull
× Tourism Pull
× Business Pull
× Distance Modifier
× Domestic or International Modifier
× Cultural and Diaspora Modifier
× Seasonal Modifier
× Event Modifier
× Pair Override
```

Example raw scores:

```text
DVO → MNL: 40.0
DVO → CEB: 30.0
DVO → TAG: 10.0
DVO → NRT: 2.0
```

Total:

```text
82.0
```

Normalized probabilities:

```text
DVO → MNL: 48.78%
DVO → CEB: 36.59%
DVO → TAG: 12.20%
DVO → NRT: 2.44%
```

These probabilities are recalculated from the destinations currently participating in the draw.

---

# 10. Eligible Destination Rule

A destination may participate in an origin’s active destination draw only when at least one valid itinerary can currently be offered.

A destination is eligible when:

```text
origin != destination
AND destination airport is open
AND at least one scheduled path exists
AND path satisfies connection limits
AND path satisfies timing limits
AND at least one itinerary can potentially carry passengers
```

A direct flight is not required.

Connecting itineraries are valid.

Example:

```text
DVO → MNL exists
MNL → NRT exists
```

Therefore:

```text
DVO → NRT
```

may enter Davao’s active destination pool.

## Dormant pair weights

The raw DVO–NRT relationship may exist even when no itinerary exists.

It remains dormant.

Once the network makes NRT reachable from DVO, it becomes active without requiring the OD relationship to be newly generated.

---

# 11. Important Reachability Distinction

A destination must not be considered reachable merely because some flight to that destination exists somewhere.

There must be a continuous path from the current origin.

Invalid example:

```text
MNL → NRT exists
DVO has no route reaching MNL or another NRT feeder
```

Result:

```text
DVO → NRT is not currently reachable.
```

Valid example:

```text
DVO → CEB
CEB → MNL
MNL → NRT
```

Result:

```text
DVO → NRT is technically reachable,
subject to maximum-connection and schedule rules.
```

---

# 12. Destination Allocation

The undecided origin pool is distributed among eligible destinations using weighted random allocation.

Example:

```text
DVO daily pool: 300
```

Result:

```text
126 want MNL
101 want CEB
50 want TAG
7 want NRT
16 want other reachable destinations
```

The result must be stored in aggregated batches.

Do not create one record per passenger.

Proposed batch:

```json
{
  "batch_id": "TB-YYYYMMDD-DVO-NRT-0001",
  "created_date": "YYYY-MM-DD",
  "origin": "DVO",
  "destination": "NRT",
  "traveler_type": "tourist",
  "count": 7,
  "status": "awaiting_itinerary"
}
```

---

# 13. Traveler-Type Allocation

After destination allocation, divide destination batches by traveler type.

Initial traveler types:

```text
domestic_leisure
tourist
business
family_visit
ofw
migrant
```

Traveler-type probabilities may depend on:

```text
origin airport characteristics
destination airport characteristics
same-country status
distance
business links
tourism rating
diaspora links
migration attractiveness
season
events
```

Example:

```text
DVO → MNL batch: 126
```

Possible split:

```text
Domestic leisure: 55
Business: 32
Family visit: 26
OFW-related: 8
Migration: 5
```

The system should retain batches, not individuals.

---

# 14. Itinerary Search

For every destination batch, search for valid itineraries.

An itinerary is a sequence of scheduled flight legs.

Example:

```json
{
  "origin": "DVO",
  "destination": "NRT",
  "legs": [
    {
      "flight_id": "FLIGHT-001",
      "origin": "DVO",
      "destination": "MNL",
      "airline": "Example Air"
    },
    {
      "flight_id": "FLIGHT-002",
      "origin": "MNL",
      "destination": "NRT",
      "airline": "Example Air"
    }
  ],
  "connections": 1,
  "total_travel_minutes": 420,
  "total_layover_minutes": 95
}
```

## Recommended search constraints

Initial configurable defaults:

```text
Maximum flight legs: 3
Maximum connections: 2
Minimum connection time: configurable by airport
Maximum connection time: 8 hours
Maximum total itinerary duration: route-dependent
Search horizon: configurable number of future schedule days
```

These are testing defaults, not permanent design laws.

---

# 15. Itinerary Search Algorithm

The network is time-dependent because scheduled departure and arrival times matter.

A plain airport-to-airport graph is not sufficient for final booking.

Recommended approach:

## Stage 1: Cached structural reachability

Use the route network to quickly determine whether a destination could theoretically be reached.

This cache ignores exact seat availability and may use simplified schedule data.

## Stage 2: Schedule-valid itinerary search

For active OD batches, search scheduled flights using a time-aware pathfinding process.

The search should prioritize:

```text
fewer connections
earlier arrival
shorter total duration
reasonable layovers
```

Possible implementation:

```text
priority queue / Dijkstra-style search over scheduled flight legs
```

Do not perform full schedule searches for every airport pair when no passengers were generated for that pair.

---

# 16. Network Cache

Rebuilding every OD path every game day would be wasteful.

Maintain:

```text
network_revision
```

Increment it whenever:

```text
a route opens
a route closes
a schedule is created
a schedule is removed
a schedule materially changes
an airport closes
an airline ceases operating
```

Cached reachability entries must contain the revision under which they were calculated.

Example:

```json
{
  "DVO": {
    "NRT": {
      "reachable": true,
      "minimum_legs": 2,
      "network_revision": 14
    }
  }
}
```

When the current revision differs, recalculate the relevant cache.

---

# 17. Itinerary Acceptance

Finding an itinerary does not guarantee that all passengers accept it.

A willingness modifier must be applied.

Initial configurable defaults:

```text
Direct:
1.00

One connection:
0.80

Two connections:
0.50

Three connections:
0.20
```

The initial implementation should preferably support no more than two connections.

The exact percentages must remain in `config.py`.

Example:

```text
7 DVO → NRT tourists
One-connection itinerary available
Acceptance modifier: 0.80

Expected accepting count:
5.6
```

Use stochastic rounding or binomial-style allocation rather than always rounding identically.

---

# 18. Itinerary Score

Passengers who accept connecting travel must compare available itineraries.

Conceptual score:

```text
Itinerary Score
=
Base Score
+ Directness Score
+ Schedule Score
+ Price Score
+ Airline Reputation Score
+ Reliability Score
+ Service-Style Match
- Connection Penalty
- Travel-Time Penalty
- Layover Penalty
- Overnight Penalty
```

Do not hardcode this into one unchangeable formula.

Each component should be separately configurable and visible during development debugging.

Example debug result:

```text
DVO → MNL → NRT
Airline: Example Air

Base score:                 100
One connection:             -20
Total travel time:          -8
Good layover:                +2
Price appeal:                +7
Airline reputation:          +5
Reliability:                 +4
Tourist/style match:         +3

Final score:                 93
```

---

# 19. Shared Passenger Pool

All airlines compete for the same origin–destination batch.

Never generate separate demand for each airline.

Incorrect:

```text
Player airline receives 100 DVO → NRT passengers.
AI airline separately receives another 100.
```

Correct:

```text
Shared DVO → NRT pool: 100 passengers.

All valid itineraries compete for those same 100 passengers.
```

Possible result:

```text
Airline A: 45
Airline B: 32
Airline C: 8
Postponed: 10
Cancelled: 5
```

---

# 20. Airline Competition

Every qualifying itinerary receives a score.

Passenger batches are distributed proportionally according to those scores.

Recommended initial method:

```text
Convert itinerary scores into positive choice weights.
Normalize the weights.
Allocate the passenger batch across options.
```

Possible later method:

```text
Softmax probability model
```

The initial implementation does not need a mathematically complex model.

The important design rule is:

> Better itineraries capture a greater share of the same pool.

---

# 21. Airline Style Matching

Traveler types should value airline characteristics differently.

Example tendencies:

## Tourist

Values:

```text
low price
reasonable connection count
destination access
```

## Business

Values:

```text
direct travel
short total time
high reliability
strong reputation
```

## Family Visit

Values:

```text
price
baggage allowance
reasonable connections
```

## OFW

Values:

```text
price
baggage
availability
long-haul network access
```

## Premium Tourist

Values:

```text
service quality
reputation
direct travel
premium cabin availability
```

These preferences modify itinerary scores.

They must not modify the initial OD destination desire unless there is a legitimate demand-side reason.

---

# 22. Seat Reservation Across Connections

A connecting booking must reserve every leg as one transaction.

Example:

```text
DVO → MNL → NRT
```

The booking succeeds only when sufficient capacity is available on:

```text
DVO → MNL
AND
MNL → NRT
```

## Atomic reservation rule

Do not permanently reserve the first leg unless all required legs can be reserved.

Processing:

```text
1. Check capacity on every leg.
2. Calculate the maximum bookable count.
3. Reserve that count on every leg.
4. Create one itinerary booking record.
```

Example:

```text
Passenger batch: 20

DVO → MNL available seats: 18
MNL → NRT available seats: 12

Maximum bookable:
12
```

Result:

```text
12 book the full itinerary.
8 remain unbooked.
```

---

# 23. Booking Batch Schema

Proposed booking record:

```json
{
  "booking_id": "BK-YYYYMMDD-000001",
  "source_batch_id": "TB-YYYYMMDD-DVO-NRT-0001",
  "traveler_type": "tourist",
  "home": "DVO",
  "origin": "DVO",
  "destination": "NRT",
  "count": 12,
  "airlines": ["Example Air"],
  "flight_ids": ["FLIGHT-001", "FLIGHT-002"],
  "connection_count": 1,
  "booking_date": "YYYY-MM-DD",
  "departure_date": "YYYY-MM-DD",
  "status": "confirmed"
}
```

Possible status values:

```text
awaiting_itinerary
confirmed
partially_booked
postponed
cancelled
in_transit
completed
disrupted
```

Status names must be documented in the template before use.

---

# 24. Partial Booking

A large traveler batch may be split when limited capacity exists.

Example:

```text
Batch size: 40
Bookable seats: 25
```

Result:

```text
Confirmed booking batch: 25
Unbooked remainder: 15
```

The remainder may:

```text
try another itinerary
postpone
cancel
```

Do not reduce the entire batch to the smallest available seat count without preserving the remainder.

---

# 25. Postponement

Passengers unable or unwilling to book may retry later.

Proposed fields:

```json
{
  "status": "postponed",
  "retry_date": "YYYY-MM-DD",
  "attempt_count": 1,
  "maximum_attempts": 3
}
```

Configurable behavior:

```text
Tourist:
May retry for several days.

Business:
Fewer retries because time matters more.

Family visit:
Moderate patience.

OFW:
Potentially longer booking window.
```

Exact retry counts should be tuned through testing.

---

# 26. Cancellation

A traveler group cancels when:

```text
no acceptable itinerary exists,
maximum retries are exceeded,
price is unacceptable,
journey time is unacceptable,
or the trip is no longer timely.
```

Cancellation means the group leaves the active booking system.

For v1, cancellation does not need to produce refunds unless seats were already booked.

---

# 27. Tourism Flow

International tourism should initially choose a destination country or gateway rather than generating an entire multi-stop journey.

Example:

```text
Home: USA
Target country: Philippines
Initial airport: MNL
```

After arrival, later destinations are selected progressively.

Possible journey:

```text
USA → MNL
MNL → TAG
TAG → PPS
PPS → BKI
BKI → USA
```

The complete sequence is not created in advance.

---

# 28. Tourist Stop Count

Tourists may be assigned a remaining stop allowance.

Initial configurable range:

```text
2 to 4 tourism stops
```

Proposed traveler-group fields:

```json
{
  "remaining_stops": 3,
  "target_country": "Philippines",
  "trip_start_date": "YYYY-MM-DD",
  "planned_return_by": "YYYY-MM-DD"
}
```

A tourist may return before using every stop.

The stop count is a maximum or travel tendency, not an obligation.

---

# 29. Tourist Destination Selection

When choosing another destination, consider only destinations that:

```text
have tourism appeal,
are reachable,
fit the remaining trip duration,
fit the traveler’s distance tolerance,
and have acceptable itineraries.
```

Possible weighting:

```text
Tourism Rating
× Distance Suitability
× Seasonal Appeal
× Network Reachability
× Novelty Modifier
× Country or Region Preference
```

Tourism movement does not need to remain domestic.

Nearby international destinations may participate when they meet distance and itinerary rules.

---

# 30. Traveler Persistence

After reaching a destination, travelers do not need to be stored individually.

Store aggregated groups.

Proposed schema:

```json
{
  "group_id": "TG-YYYYMMDD-000001",
  "home": "DVO",
  "current_location": "NRT",
  "traveler_type": "tourist",
  "count": 12,
  "arrival_date": "YYYY-MM-DD",
  "next_decision_date": "YYYY-MM-DD",
  "remaining_stops": 2,
  "target_country": "Japan",
  "status": "staying"
}
```

---

# 31. Return and Stay Behavior

Initial configurable ranges:

## Tourist

```text
Total trip or stay duration:
5 to 30 days
```

Possible next actions:

```text
continue to another tourist destination
return home
extend stay
```

## Business

```text
Stay duration:
1 to 3 days
```

Possible next actions:

```text
return home
continue to another business destination
```

## OFW

```text
Stay duration:
6 months to 2 years
```

They should not be processed as active daily travelers before their decision date.

## Migrant

```text
No automatic return.
```

Migration transfers population affiliation to the destination.

---

# 32. Progressive Journey Decisions

Multi-city journeys must be determined one step at a time.

Do not generate:

```text
USA → MNL → TAG → PPS → CEB → USA
```

as one permanent itinerary when the trip begins.

Instead:

```text
Decision 1:
USA → MNL

After arrival:
MNL → TAG

After arrival:
TAG → PPS

After arrival:
PPS → USA
```

Benefits:

* easier data structures,
* lower memory use,
* adapts to changing schedules,
* adapts to route closures,
* adapts to price changes,
* supports organic tourism behavior.

---

# 33. Migration

Migrants differ from temporary travelers.

On successful arrival:

```text
origin home population affiliation decreases
destination home population affiliation increases
```

Do not necessarily modify the historical real-world airport population data directly.

Recommended approach:

Maintain a game-world population adjustment layer.

Example:

```json
{
  "population_adjustments": {
    "DVO": -150,
    "NRT": 150
  }
}
```

Effective game population:

```text
Base airport population
+
Game population adjustment
```

This preserves original airport reference data.

---

# 34. Batch Splitting

A traveler group may split during decisions.

Example:

```text
20 tourists currently in MNL
```

Decision result:

```text
10 continue to TAG
6 return home
3 extend their stay
1 migrates
```

Create or update separate groups for each result.

---

# 35. Batch Merging

To prevent thousands of tiny records, merge compatible groups.

Groups may merge when these important fields match:

```text
home
current_location
traveler_type
next_decision_date
remaining_stops
target_country
status
```

Do not merge groups when their future behavior differs materially.

Provide a configurable minimum batch size or periodic compaction process.

---

# 36. Daily Processing Order

The passenger system should run as part of `advance_game_day`.

Recommended order:

```text
1. Advance or resolve scheduled flight state from the previous day.

2. Process completed arrivals.

3. Convert completed travelers into persistent groups.

4. Process persistent groups whose next_decision_date is today.

5. Generate return, continuation, or migration decisions.

6. Update network revision if routes or schedules changed.

7. Refresh invalid reachability cache entries.

8. Generate undecided traveler pools by origin.

9. Identify eligible destinations.

10. Calculate and normalize OD weights.

11. Allocate origin pools into destination batches.

12. Allocate traveler types.

13. Search valid itineraries.

14. Apply connection willingness.

15. Score all airline itineraries.

16. Distribute shared passenger batches among airlines.

17. Reserve seats atomically across itinerary legs.

18. Postpone or cancel unbooked travelers.

19. Save daily market metrics.

20. Continue with other game-day financial and operational processing.
```

The exact relationship with flight departure timing may later require sub-daily processing.

For the initial daily simulation, booking may operate against the next available schedule window.

---

# 37. Integration With Existing Game Loop

Current `game/game_loop.py` calls:

```python
advance_game_day(game_state)
```

Passenger processing should not be implemented directly in the menu loop.

Instead, `advance_game_day` should call a passenger-simulation coordinator.

Conceptual structure:

```python
def advance_game_day(game_state):
    advance_calendar_date(game_state)
    process_passenger_day(game_state)
    process_finances(game_state)
    process_maintenance(game_state)
    autosave_if_needed(game_state)
```

The actual call order must be checked against the final scheduling system.

---

# 38. Configuration

Balancing values must live in one central configuration module.

Suggested examples:

```python
MAX_CONNECTIONS = 2
MAX_FLIGHT_LEGS = 3

CONNECTION_ACCEPTANCE = {
    0: 1.00,
    1: 0.80,
    2: 0.50,
    3: 0.20,
}

TRAVELER_STAY_RANGES = {
    "tourist": (5, 30),
    "business": (1, 3),
    "ofw": (180, 730),
}

TOURIST_STOP_RANGE = (2, 4)
MAX_BOOKING_RETRIES = 3
```

These values are testing defaults.

Do not scatter them across several modules.

---

# 39. Deterministic Randomness

The simulation uses random selection, but testing must remain reproducible.

Use a seeded random-number generator.

The seed may derive from:

```text
game seed
+
current game date
+
origin airport
+
processing category
```

Example purpose:

```text
The same save and same decisions should produce the same daily passenger results.
```

Avoid global uncontrolled randomness that makes bugs impossible to reproduce.

---

# 40. Performance Rules

The system must avoid:

```text
one object per passenger
full OD pathfinding for every airport pair every day
full cache rebuilds after unrelated changes
repeated airport JSON loading during daily processing
```

Use:

```text
aggregated batches
preloaded airport indexes
network revision caching
OD-weight caching where valid
schedule-window filtering
batch merging
stochastic allocation
```

---

# 41. Suggested Processing Scale

The design should remain practical for:

```text
hundreds of airports
hundreds of daily flights
many airlines
thousands of aggregated booking and traveler groups
```

The system should process only:

```text
active origins,
reachable destinations,
generated OD batches,
and changed network sections.
```

It should not iterate over every theoretical world airport pair unless required for cache generation or development analysis.

---

# 42. Save and Load

All passenger state must serialize to JSON.

Do not store:

```text
sets
tuple dictionary keys
custom class instances
datetime objects
graph objects
```

Convert runtime caches into JSON-safe structures or rebuild them after loading.

Recommended:

```text
Persistent booking and traveler state:
Save.

Derived route graph:
Rebuild after load.

Reachability cache:
May be saved or rebuilt depending on performance.

Temporary scoring data:
Do not save.
```

---

# 43. Schema Migration

Add:

```text
passenger_simulation.schema_version
```

When future fields change, create a migration function.

Example:

```python
def migrate_passenger_simulation_state(state: dict) -> dict:
    ...
```

Loading old saves must not fail simply because passenger simulation fields are missing.

Use template-backed defaults and recursive merge behavior.

---

# 44. Development Metrics

Record enough information to balance the system.

Daily metrics should include:

```text
travelers generated by origin
travelers generated by OD pair
travelers by type
reachable vs unreachable intentions
direct vs connecting bookings
average connections
average itinerary duration
bookings by airline
load factor contribution
postponements
cancellations
unused demand
top hubs by connecting passengers
```

These metrics may be development-only initially.

---

# 45. Booking Status Screen

The existing:

```text
game/scheduling/booking_status.py
```

currently contains a placeholder.

It may later display:

```text
Flight load factors
Direct passengers
Connecting passengers
Bookings by traveler type
Unserved demand
Postponed passengers
Airline market share
Top origin–destination markets
```

The calculation logic must remain in `game/passenger_simulation`.

The scheduling screen should only read and render prepared results.

---

# 46. Testing Strategy

The following questions should be answered through controlled testing.

## Pool-size testing

Questions:

```text
Do small cities generate enough travelers?
Do large cities overwhelm capacity too quickly?
How fast should the network fill as routes are added?
```

## OD-weight testing

Questions:

```text
Do domestic pairs dominate appropriately?
Are distant international destinations too common?
Does tourism create believable flows?
```

## Connection testing

Questions:

```text
Is one connection accepted often enough?
Do two connections remain useful but unattractive?
Do direct flights gain a meaningful advantage?
```

## Competition testing

Questions:

```text
Does the cheapest airline always win?
Does reputation matter enough?
Can a premium direct flight compete against a cheap connection?
```

## Persistence testing

Questions:

```text
Do visitor pools grow without limit?
Do return travelers create believable reverse demand?
Do multi-city tourists produce useful feeder traffic?
```

---

# 47. Required Test Scenarios

## Scenario A — Single Direct Route

Network:

```text
A → D
```

Expected:

```text
A–D becomes eligible.
Nearly all willing A–D travelers consider the direct option.
No connecting passengers.
```

## Scenario B — One Connection

Network:

```text
A → B
B → D
```

Expected:

```text
A–D becomes eligible.
A percentage accepts the connection.
Both legs receive the same connecting passenger count.
```

## Scenario C — Two Connections

Network:

```text
A → B
B → C
C → D
```

Expected:

```text
A–D is reachable if within configured limits.
Demand is materially lower than with one connection.
```

## Scenario D — Direct Route Added Later

Before:

```text
A → B → D
```

After:

```text
A → D
```

Expected:

```text
Most A–D passengers shift toward the direct option.
Connecting-leg traffic declines.
Total served A–D demand may increase.
```

## Scenario E — Shared Airline Pool

Airline 1:

```text
A → D direct, expensive
```

Airline 2:

```text
A → B → D, cheap
```

Expected:

```text
The same passenger pool is split according to itinerary scores.
No duplicated airline-specific demand is created.
```

## Scenario F — Full Connecting Leg

Network:

```text
A → B has 50 seats
B → D has 10 seats
```

Batch:

```text
30 A–D travelers
```

Expected:

```text
Maximum confirmed connecting bookings: 10.
No orphan first-leg reservations.
Remaining 20 retry another option, postpone, or cancel.
```

## Scenario G — Tourist Continuation

Initial:

```text
USA → MNL tourist group
```

Expected future behavior:

```text
Some return home.
Some continue to reachable tourist destinations.
Some extend their stay.
No individual passenger records are created.
```

## Scenario H — Migration

Initial:

```text
Migrants from A to D
```

Expected:

```text
They do not create an automatic return group.
Game-world population adjustment moves from A to D.
```

---

# 48. Development Debug Output

During implementation, support optional debug output such as:

```text
Origin: DVO
Undecided pool: 300
Eligible destinations: 14

DVO → MNL
Raw weight: 40.0
Normalized chance: 31.8%
Allocated travelers: 96

DVO → NRT
Raw weight: 2.0
Normalized chance: 1.6%
Allocated travelers: 5
Available itineraries: 2
Accepted connections: 4
Booked Airline A: 3
Booked Airline B: 1
```

Debug output must be controlled by development settings and disabled in normal gameplay.

---

# 49. Initial Implementation Scope

Recommended first implementation:

```text
Origin undecided pools
OD destination weighting
Reachability
Direct and one-connection itineraries
Shared airline competition
Atomic seat reservation
Aggregated booking batches
Basic postponement
Basic arrival completion
```

Recommended later implementation:

```text
Two-connection balancing
Persistent tourist movement
Return queues
OFW behavior
Migration
AI airline strategy reactions
Complex disruption handling
Cross-airline interlining
```

This staged scope does not change the architecture.

It only controls implementation risk.

---

# 50. Decisions Already Finalized

The following are architectural decisions and should not be reopened merely because balancing values change:

1. Demand belongs to origin–destination intent, not directly to routes.

2. Every origin generates an undecided traveler pool.

3. The original demand formula contributes to origin pool size and OD pair weights.

4. Destinations are chosen through weighted random allocation.

5. Only currently reachable destinations enter the active destination draw.

6. Direct and connecting itineraries can satisfy the same OD intention.

7. Every additional connection reduces willingness.

8. Airlines share one common passenger pool.

9. Airline reputation, style, price, reliability, and schedule affect airline selection.

10. Travelers are stored as aggregated number batches, not individuals.

11. Tourism chooses its next stop progressively.

12. Tourist stops may cross borders when distance and network access make sense.

13. Tourists generally stay 5–30 days.

14. Business travelers generally stay 1–3 days.

15. OFWs generally remain 6 months–2 years before a future decision.

16. Migrants transfer into the destination’s population affiliation and do not automatically return.

17. Loyalty, alliances, codeshares, cargo, and major world-event systems remain future discussions.

---

# 51. Values Intentionally Left for Testing

The following should remain configuration values until gameplay testing provides evidence:

```text
base travel rates
exact daily pool sizes
OD-weight coefficients
distance curves
connection acceptance percentages
maximum connections
maximum layovers
search horizon
itinerary-score coefficients
airline-style preferences
booking retry limits
batch compaction thresholds
tourist distance radius
tourist stop probabilities
return-action probabilities
```

These are not unanswered architectural questions.

They are balancing parameters.

---

# 52. Definition of a Successful Prototype

The prototype is successful when the following behavior emerges:

```text
A small network begins with modest traffic.

Adding a route unlocks new origin–destination journeys.

Existing feeder flights gain connecting passengers.

A hub with more useful connections becomes busier.

Direct routes attract more passengers than inconvenient connections.

No route receives the entire theoretical world demand.

Different airlines compete for the same passengers.

Seat limits constrain whole connecting itineraries correctly.

The game remains computationally stable without individual passenger objects.
```

---

# 53. Final Technical Rule

The passenger simulation must always preserve this separation:

```text
The Demand Generator decides who wants to travel.

The Destination Allocator decides where they want to go.

The Network determines whether the journey is possible.

The Booking Engine determines how they travel.

The Airline competes to carry them.

The Flight Simulation moves them.

The Persistence Engine determines what they do next.
```

No single module should attempt to perform all of these responsibilities.
