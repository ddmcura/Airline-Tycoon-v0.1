# Airline Tycoon - Passenger Demand Technical Specification

> **Status:** Approved Stage 1 technical direction. This document translates the approved Passenger Demand, Booking & Network Simulation architecture into formulas, processing rules, performance requirements, and testable behavior for the first generic Economy implementation. Numerical coefficients are configurable prototype values, not permanent balance. This document does not authorize code or schema changes by itself.

## 1. Purpose and Technical Rule

Stage 1 must keep five different quantities separate:

```text
World Demand
    asks: How many new people want to book A -> B today?

Booking Engine
    asks: Can they find an acceptable future journey?

Airline Competition
    asks: Which available itinerary do they choose?

Capacity
    asks: How many actually secure seats?

Flight Simulation
    asks: Who actually travels on the operating day?
```

The implementation must never collapse these into one per-flight or airline-owned route-demand calculation.

The primary Stage 1 demand output is:

```text
BaseDailyBookers(origin -> destination)
```

This is the stable baseline number of **new daily future-trip booking intentions** for one directional airport pair.

It is not:

- passengers assigned to a specific flight;
- passengers flying today;
- passengers generated because a route exists;
- successful bookings;
- a booking backlog; or
- a value owned separately by each airline.

## 2. Stage 1 Scope

Stage 1 includes:

- directional airport-pair demand;
- a world-level `BaseDailyBookers` baseline;
- one generic Economy passenger group;
- rolling daily booking cohorts;
- desired future travel dates;
- a configurable hard booking horizon;
- direct and approved connecting itinerary search;
- one configurable Economy choice profile;
- an outside option;
- aggregated batch allocation;
- atomic multi-leg reservations;
- deterministic randomness;
- indexed and cached network processing; and
- separate booking-intent, successful-booking, and flown-passenger metrics.

Stage 1 does not include:

- Business, First, or Premium Economy demand;
- detailed traveler purposes;
- individual passenger objects;
- automatic retry or backlog behavior;
- loyalty mechanics;
- overbooking, cancellations, or no-shows;
- detailed tourism, business, diaspora, or migration relationships;
- detailed seasonality or world events;
- permanent balancing coefficients; or
- Cargo.

## 3. Directional Demand Pipeline

For every valid directional pair `o -> d`:

```text
OriginDailyBookingPool(o)
= OriginPopulation(o)
  x DailyBookerRate(o)

DestinationPairShare(o -> d)
= RawPairScore(o -> d)
  / SUM(RawPairScore(o -> every valid world destination))

BaseDailyBookers(o -> d)
= OriginDailyBookingPool(o)
  x DestinationPairShare(o -> d)

ActualDailyBookers(o -> d, today)
= BaseDailyBookers(o -> d)
  x DailyDemandMultiplier(o, d, today)
```

Only after `ActualDailyBookers` is calculated does the system check for a valid future itinerary.

## 4. Origin Daily Booking Pool

The origin pool represents how many residents or locally generated travelers enter the future-trip booking market on an ordinary game day.

```text
OriginDailyBookingPool(o)
= OriginPopulation(o)
  x DailyBookerRate(o)
```

Example:

```text
MNL population        = 15,000,000
DailyBookerRate       = 0.0002
Origin booking pool   = 3,000 new booking intentions per day
```

`DailyBookerRate` must be configurable. Stage 1 may use one global prototype value or a small table by city or airport type.

Future origin-side modifiers may include:

- city type;
- economic strength;
- historical era;
- travel culture;
- airport accessibility;
- population changes;
- business activity; and
- tourism-source strength.

These are extension points, not Stage 1 implementation requirements.

## 5. Destination Pair Share

`DestinationPairShare(o -> d)` is the hidden fraction of the origin's daily booking market that wants destination `d`.

It exists whether or not any route, airline, or schedule currently serves the pair.

### 5.1 Raw pair score

Stage 1 calculates:

```text
RawPairScore(o -> d)
= PopulationPull(d)
  x DistanceWeight(o, d)
  x DestinationTypeWeight(d)
  x GeographyWeight(o, d)
  x RelationshipWeight(o, d)
```

All components must be positive, configurable, and independently testable.

### 5.2 Population pull

Prototype:

```text
PopulationPull(d)
= sqrt(DestinationPopulation(d) / 1,000,000)
```

This softened curve allows larger destinations to attract more travelers without linear megacity dominance.

Zero or missing population requires an explicit data fallback defined by configuration or validation. It must not silently cause invalid arithmetic.

### 5.3 Distance weight

Prototype:

```text
DistanceWeight(o, d)
= 1 / (1 + DistanceKm(o, d) / DistanceScaleKm)

DistanceScaleKm = 2,000
```

Nearby destinations receive stronger ordinary travel while long-haul markets remain possible. Stage 1 should not apply a large hard minimum floor. Testing may later justify a small floor or another curve.

### 5.4 Destination-type weight

Prototype configuration:

| Destination type | Weight |
|---|---:|
| Mega / Global City | 1.40 |
| Capital / Major City | 1.25 |
| Major Regional City | 1.10 |
| Normal City | 1.00 |
| Small Regional City | 0.80 |
| Minor City | 0.65 |

These are test values. The airport/city data source must define how a destination maps to a type before implementation.

Tourism-heavy destinations may later receive dedicated tourism inputs rather than having tourism hidden inside this generic type weight.

### 5.5 Geography weight

Prototype:

| Pair geography | Weight |
|---|---:|
| Same country | 1.25 |
| Different country | 1.00 |

The values remain configurable. Later regional, border, island, visa, or political effects must be added deliberately rather than embedded invisibly.

### 5.6 Relationship weight

Stage 1 uses:

```text
RelationshipWeight(o, d) = 1.0
```

Future phases may add tourism links, business ties, diaspora, culture, family and worker flows, migration, historical traffic, or regional relationships.

## 6. Full-World Normalization

For each origin, normalize against every valid destination in the represented world:

```text
DestinationPairShare(o -> d)
= RawPairScore(o -> d)
  / SUM(RawPairScore(o -> every valid destination))
```

The denominator must not be limited to:

- purchased routes;
- reachable destinations;
- scheduled destinations;
- destinations served by the player;
- destinations served by any airline; or
- destinations currently inside the booking horizon.

This preserves a stable pair share when the airline network changes. Opening `MNL -> NRT` must not automatically reduce `MNL -> DVO` merely because NRT became reachable.

Pair shares change only when demand-side inputs or the valid represented world change. A deliberate data expansion may therefore create a new demand-model revision and recalculate shares; ordinary route and schedule changes must not.

### 6.1 Valid destination universe

A valid destination must be a represented commercial destination eligible for passenger-demand calculation under current world-data rules. It excludes the origin itself and any location deliberately excluded from passenger markets.

The exact data validation rule belongs to Airport/Data documentation. The demand system consumes the validated universe.

### 6.2 Normalization invariant

For every origin with at least one valid destination:

```text
SUM(DestinationPairShare(o -> d)) = 1.0
```

Floating-point tolerance must be defined in tests.

## 7. Base Daily Bookers

After normalization:

```text
BaseDailyBookers(o -> d)
= OriginDailyBookingPool(o)
  x DestinationPairShare(o -> d)
```

Example:

```text
OriginDailyBookingPool(MNL)          = 3,000
DestinationPairShare(MNL -> DVO)     = 0.02
BaseDailyBookers(MNL -> DVO)         = 60
```

The baseline is directional and world-owned:

```text
BaseDailyBookers(MNL -> DVO)
!= BaseDailyBookers(DVO -> MNL)
```

An airline route may display or cache a forecast projection, but it must not become the authoritative owner of a separate copy of this demand.

## 8. Actual Daily Bookers

Each game day applies demand-side conditions:

```text
ActualDailyBookers(o -> d, today)
= BaseDailyBookers(o -> d)
  x DailyDemandMultiplier(o, d, today)
```

Possible current or future multiplier sources include:

- holidays;
- seasonality;
- advertising and market-development campaigns;
- tourism boosts;
- economic conditions;
- local, regional, or world events;
- airline or market buffs; and
- government or regional effects.

Example:

```text
BaseDailyBookers       = 60
Holiday                = 1.50
Advertising            = 1.20
Tourism event          = 1.40

ActualDailyBookers
= 60 x 1.50 x 1.20 x 1.40
= 151.2 before integer resolution
```

Large stacked results are architecturally valid. Configuration may later define caps, additive groups, diminishing returns, or stacking categories after balancing tests.

The same commercial effect must not accidentally be counted both as a demand multiplier and as an itinerary-choice input unless the owning design explicitly gives it both responsibilities. For example, route advertising may increase market activity, service awareness, or both, but each effect must be named and configured separately.

## 9. Fractional and Tiny Pair Demand

`BaseDailyBookers` and `ActualDailyBookers` may be fractional.

Example:

```text
BaseDailyBookers = 0.03 per day
```

The system must not create fractional passenger objects or process a zero-value batch every day.

Use either:

- deterministic seeded stochastic rounding; or
- a deterministic fractional accumulator.

The chosen method must preserve the long-run expected value. For example, `0.03` should resolve to approximately one booking intention every 33 days.

### 9.1 Seed requirements

Randomness must be derived from stable inputs such as:

```text
save simulation seed
origin airport
destination airport
cohort creation date
purpose-specific random stream identifier
```

Reloading the same unchanged save must not reroll the cohort.

## 10. Demand Before Network Availability

No flight, route, schedule, airline, capacity, or reachability input may appear in the `BaseDailyBookers` formula.

Required processing order:

```text
Resolve BaseDailyBookers
        -> apply today's demand factors
        -> resolve ActualDailyBookers integer batch
        -> check for usable future service
        -> if service exists, enter Booking
        -> otherwise, no booking attempt
```

If no itinerary exists, the baseline remains intact. The day's unsuccessful opportunity is not saved as a waiting batch in Stage 1.

## 11. Rolling Daily Booking Cohorts

Stage 1 does not use a fixed cumulative booking curve as its core generator.

Every game day creates a new cohort for each pair whose integer-resolved `ActualDailyBookers` is positive and for which a potentially usable future itinerary exists.

Example:

```text
MNL -> DVO
Generic Economy
Cohort creation date: 12 March 1960
Count: 60
```

The cohort:

1. selects or is allocated a desired future travel date;
2. searches acceptable itineraries around that date;
3. scores the candidates and outside option;
4. reserves capacity for successful choices; and
5. exits daily processing.

Repeated new cohorts naturally create booking accumulation on future flights.

### 11.1 No automatic carry-forward

If a cohort contains 60 bookers and only 45 confirm:

```text
Successful bookings = 45
Unsuccessful today  = 15
```

The 15 do not automatically join tomorrow's cohort. Tomorrow independently generates:

```text
BaseDailyBookers x tomorrow's demand multiplier
```

Future passenger types may retry or postpone using explicit probabilities and state. Such behavior must be introduced deliberately and must not become an implicit backlog.

## 12. Booking Horizon and Desired Travel Date

Stage 1 defines:

```text
MAX_BOOKING_HORIZON_DAYS = 365
```

This is a configurable hard maximum.

A cohort created on `today` may search only dated flights satisfying:

```text
today <= departure_date <= today + MAX_BOOKING_HORIZON_DAYS
```

The system first selects a desired future travel date using a configurable generic Economy lead-time distribution. It then searches within a configurable tolerance around that date.

The exact Stage 1 lead-time distribution and date tolerance remain prototype balancing values, but they must:

- produce rolling accumulation across future departures;
- avoid sending every cohort to the earliest available flight;
- avoid uniform selection across all 365 days unless testing supports it;
- respect schedule availability; and
- never exceed the global hard maximum.

Future passenger groups may have different preferred lead times while sharing the same hard maximum.

## 13. Stage 1 Itinerary Eligibility

Stage 1 itinerary search reads dated flight instances published by Scheduling.

A candidate must satisfy:

- departure occurs within the permitted desired-date search window;
- every leg is a published passenger service;
- origin, destination, and leg order form a continuous journey;
- all connection times are valid;
- same-airline transfers occur only through that airline's Hubs;
- any supported inter-airline transfer follows the approved self-connect or partnership rules;
- the number of connections does not exceed the configured hard limit;
- applicable airport, route, and schedule constraints are valid; and
- capacity can potentially be reserved on every leg.

Frequency receives no direct scoring bonus. More frequency helps only by offering more suitable travel dates, departure times, arrival times, journey durations, or capacity.

## 14. Schedule Indexes and Network Caches

The Booking Engine must not scan every future flight for every directional pair and cohort.

At minimum, the schedule lookup layer must support indexed access by:

- origin airport;
- departure date or date range;
- destination airport;
- airline when required; and
- Hub or connection eligibility when required.

Recommended conceptual indexes include:

```text
departures_by_origin_and_date
direct_services_by_pair_and_date
hub_departures_by_airline_origin_and_date
capacity_by_dated_flight_and_product
```

Exact runtime structures remain an implementation choice as long as their behavior and invalidation are testable.

### 14.1 Structural reachability cache

A structural cache may answer whether a direct or permitted connecting pattern could exist without scanning exact flights repeatedly.

It must not itself confirm bookability. Final booking still validates dated schedules, times, rules, and capacity.

### 14.2 Candidate itinerary-pattern cache

Repeated searches may cache candidate patterns such as:

```text
DVO -> MNL -> NRT
airline transfer pattern
eligible Hub relationships
```

The cache stores reusable structure, not permanently valid dated reservations.

### 14.3 Network revision invalidation

Route, schedule, Hub, partnership, airport-availability, or other structural changes increment the appropriate network revision and invalidate affected reachability or candidate-pattern caches.

Demand-side input changes use a separate demand-model revision. A schedule edit must not unnecessarily recalculate full-world destination shares.

## 15. Stage 1 Economy Choice Score

Stage 1 uses one configurable generic Economy scoring profile.

Candidate factors may include:

- fare or price;
- departure-time suitability;
- arrival-time suitability;
- difference from desired travel date;
- total journey time;
- number and difficulty of connections;
- number of airline changes;
- partnered protection versus self-connection;
- airline reliability;
- airline reputation;
- Market Presence and directional route awareness;
- future product or perk inputs;
- deterministic random preference; and
- the outside option.

A conceptual linear utility is acceptable for the prototype:

```text
Utility(i)
= w_price       x PriceScore(i)
  + w_departure x DepartureSuitability(i)
  + w_arrival   x ArrivalSuitability(i)
  + w_date      x DesiredDateSuitability(i)
  + w_duration  x JourneyDurationScore(i)
  + w_connection x ConnectionScore(i)
  + w_reliability x ReliabilityScore(i)
  + w_reputation  x ReputationScore(i)
  + w_presence    x MarketPresenceScore(i)
  + RandomPreference(i)
```

All component scores should use documented ranges before weights are tuned. Exact transformations and weights remain prototype values.

### 15.1 Outside option

The choice set always includes an outside option representing rejection of the available travel choices.

Possible reasons include:

- unacceptable fare;
- unsuitable date or time;
- excessive journey duration;
- too many or poor connections;
- insufficient capacity;
- another travel mode;
- changed plans; or
- no acceptable service.

A terrible itinerary must not receive the entire cohort merely because it is the only airline option.

## 16. Batch Choice Allocation

Do not simulate each traveler independently.

For a cohort count `N`, convert candidate utilities into non-negative choice weights using a configurable choice function. A softmax-style prototype is acceptable:

```text
ChoiceWeight(i) = exp(Utility(i) / Temperature)

PassengerShare(i)
= ChoiceWeight(i)
  / SUM(ChoiceWeight(all itineraries and outside option))
```

Then allocate integer batch counts using deterministic rounding that preserves the cohort total.

Example:

```text
Cohort = 60

Airline A = 42% -> 25
Airline B = 35% -> 21
Airline C = 18% -> 11
Outside   =  5% ->  3
```

The allocation method must avoid airline-order bias. Changing dictionary or iteration order must not change market results.

## 17. Capacity and Redistribution

Capacity belongs to dated flight instances and sellable products.

If 25 passengers select Airline A but only 10 seats remain:

```text
Confirm 10 on Airline A
Unallocated remainder = 15
```

The remainder is rescored or redistributed across the remaining capacity-bearing options and the outside option.

Redistribution continues until:

- all bookers confirm;
- all acceptable capacity is exhausted;
- only the outside option remains; or
- a configured iteration safety limit is reached.

Stage 1 does not carry the final unsuccessful remainder into tomorrow.

## 18. Atomic Connecting Reservations

A connecting batch must reserve every leg as one transaction.

Example:

```text
DVO -> MNL capacity = 20
MNL -> NRT capacity = 13
Requested batch     = 20

Maximum confirmed connecting batch = 13
```

The remaining seven must not receive orphan first-leg reservations.

Required behavior:

1. determine the minimum compatible remaining capacity across all legs;
2. reserve no more than that amount;
3. commit all leg reservations together;
4. roll back the entire reservation if any leg commit fails; and
5. return the unconfirmed remainder to capacity redistribution.

Partnered protection and unpartnered self-connection rules affect choice and passenger rights, but they do not permit orphan capacity reservations.

## 19. Required Daily Processing Order

The passenger pipeline should run in a deterministic order coordinated with Scheduling and Aircraft Operations.

Conceptual order:

1. resolve completed or disrupted prior operations under their owning systems;
2. apply effective-dated schedule, Hub, partnership, and network changes;
3. update network revisions and invalidate affected caches;
4. update demand-model revisions only when demand-side inputs changed;
5. obtain or calculate `BaseDailyBookers` for relevant directional pairs;
6. apply today's demand multipliers;
7. resolve fractional `ActualDailyBookers` into integer batch counts;
8. discard zero batches without itinerary work;
9. perform a cheap reachability or service-availability check;
10. assign desired travel dates within the horizon;
11. search dated direct and permitted connecting itineraries;
12. calculate utilities including the outside option;
13. allocate aggregated batches;
14. reserve capacity atomically;
15. redistribute capacity-constrained remainders;
16. record successful and unsuccessful booking metrics; and
17. persist confirmed booking batches and updated capacity.

The final code-level call order must remain consistent with the canonical scheduling and operational lifecycle.

## 20. World Scale and Active Pair Processing

Full-world normalization does not require running itinerary search for every pair every day.

The system may precompute or cache demand-side shares, then process daily booking cohorts only for pairs that pass cheap activation checks, such as:

- positive integer-resolved daily bookers; and
- at least one potentially usable future direct or permitted connecting service.

This preserves dormant pair demand without performing expensive booking work for unavailable journeys.

The engine must avoid:

```text
every origin
x every destination
x every future flight
x every airline
```

inside the daily booking loop.

## 21. Conceptual State and Ownership

Exact persistent schema fields require separate approval in the canonical template reference. The technical model nevertheless distinguishes:

### World demand state or derived cache

- demand-model revision;
- origin booking-pool inputs;
- normalized directional pair shares;
- `BaseDailyBookers` values or reproducible derivation inputs;
- fractional accumulators when that method is selected; and
- deterministic simulation seed inputs.

### Booking state

- confirmed aggregated booking batches;
- dated itinerary and leg references;
- booked product and fare;
- booked passenger count;
- booking date;
- travel date;
- protection or self-connect status where relevant; and
- reservation status.

### Derived runtime state

- schedule indexes;
- structural reachability;
- candidate itinerary patterns;
- remaining dated-flight capacity; and
- score calculation scratch data.

Derived caches should be rebuildable after loading unless persistence provides a demonstrated performance benefit and robust revision validation.

## 22. Metrics

The system must keep these measures distinct:

| Metric | Meaning |
|---|---|
| Daily Booking Intent | New `ActualDailyBookers` generated today. |
| Daily Successful Bookings | Seats newly reserved today for future flights. |
| Daily Unsuccessful Intent | Today's cohort members who selected or ended in the outside option. |
| Daily Passengers Flying | Previously booked passengers carried on flights operating today. |

Additional useful Stage 1 metrics include:

- base daily bookers by directional pair;
- booking conversion rate;
- direct versus connecting bookings;
- bookings by airline and itinerary;
- passengers lost to capacity;
- passengers rejecting available service;
- average booking lead time;
- load already booked by days before departure;
- cache hits and itinerary-search counts; and
- top connecting Hubs by confirmed passenger legs.

## 23. Configuration

Prototype values belong in configuration rather than scattered constants.

Conceptual configuration includes:

```text
daily_booker_rate_default
daily_booker_rate_by_city_type
distance_scale_km = 2000
destination_type_weights
same_country_weight = 1.25
international_weight = 1.00
relationship_weight_default = 1.00
max_booking_horizon_days = 365
desired_date_distribution
desired_date_tolerance_days
max_connections_stage_1
minimum_and_maximum_connection_rules
economy_choice_weights
outside_option_utility
choice_temperature
random_variation_parameters
allocation_iteration_limit
```

Changing balancing configuration may require a demand-model version or save migration depending on whether affected values are stored or derived.

## 24. Determinism and Random Streams

Randomness may influence:

- fractional cohort resolution;
- daily demand variation;
- desired travel dates;
- itinerary preference noise; and
- integer batch allocation ties.

Each purpose should use a stable, separated random stream so adding a new random decision does not silently reroll unrelated outcomes.

Seeds should incorporate the save simulation seed and stable domain identifiers. Tests must verify that:

- the same save and inputs produce the same results;
- reload does not reroll demand;
- changing one pair does not reroll unrelated pairs; and
- iteration order does not alter allocation.

## 25. Required Stage 1 Tests

### 25.1 Formula and normalization

- directional pairs can produce different baselines;
- destination shares sum to one for each origin;
- shares use the full valid destination universe;
- adding a scheduled route does not change pair shares;
- softened population pull behaves as specified;
- distance weight declines without a large hard floor;
- domestic geography weight applies correctly; and
- relationship weight remains neutral in Stage 1.

### 25.2 Daily cohorts

- `BaseDailyBookers` remains stable when schedules change;
- daily modifiers change `ActualDailyBookers`, not the baseline;
- tiny fractional markets preserve their long-run average;
- reload does not reroll a cohort;
- no service creates no booking attempt; and
- unsuccessful bookers do not carry into tomorrow automatically.

### 25.3 Booking horizon and dates

- no search exceeds 365 days;
- desired dates remain inside the hard horizon;
- repeated daily cohorts accumulate on future flights;
- booking intent, successful booking, and flying metrics remain separate; and
- flights are not all filled by the earliest cohort merely because they exist.

### 25.4 Choice and competition

- all airlines compete for one shared cohort;
- frequency has no direct bonus;
- useful timing can make an additional flight attractive;
- the outside option can beat a terrible itinerary;
- a new competitor affects new bookings but not confirmed bookings;
- allocation preserves the original cohort total; and
- iteration order does not change results.

### 25.5 Capacity and connections

- direct bookings cannot exceed remaining capacity;
- full preferred service redistributes the remainder;
- connecting capacity equals the minimum available capacity across legs;
- an atomic failure leaves no orphan reservation;
- same-airline connections require the airline's Hub;
- inter-airline transfers obey the approved transfer rules; and
- connection limits prevent uncontrolled search.

### 25.6 Performance

- schedule indexes avoid full-list scans for each cohort;
- unchanged caches are reused;
- relevant network changes invalidate affected caches;
- schedule changes do not rebuild demand-side normalization unnecessarily; and
- representative world and timetable sizes remain within the agreed processing budget.

## 26. Migration From the Current Playable Model

The current implementation stores directional `base_daily_demand` on airline route records and allocates passengers during the daily flight tick. That remains historical implementation input, not the final ownership model.

A future code migration should proceed in stable stages:

1. introduce world-level directional `BaseDailyBookers` calculation and tests;
2. keep existing daily flight allocation available behind a compatibility boundary;
3. introduce dated booking capacity and rolling cohorts for direct Economy service;
4. switch flight-day passengers to confirmed booking batches;
5. add approved connecting search and atomic reservations;
6. remove obsolete route-owned authority only after saves and reports migrate safely.

This document does not authorize that code migration yet.

## 27. Deferred Technical Decisions

The following remain deliberately open until implementation planning or testing requires them:

- exact `DailyBookerRate` values and city-type table;
- missing-population fallback;
- exact destination-type mapping;
- demand-multiplier stacking and caps;
- stochastic rounding versus fractional accumulators;
- generic Economy lead-time distribution;
- desired-date tolerance;
- Stage 1 maximum connection count;
- exact connection-time formulas;
- score transformations and weights;
- outside-option calibration;
- choice temperature and allocation rounding;
- persistent schema fields;
- cache data structures and invalidation granularity;
- save-migration mechanics;
- processing performance budget; and
- exact report and interface presentation.

These are not permission to replace the approved model with per-flight demand, route-owned demand, or reachable-only normalization.

## 28. Final Stage 1 Rules

```text
BaseDailyBookers is the stable directional baseline number of new people who
decide each day to seek a future trip from one airport to another.

OriginDailyBookingPool equals origin population times DailyBookerRate.

DestinationPairShare equals a pair's RawPairScore divided by the score sum for
the full valid destination universe, whether or not those destinations are
reachable, served, scheduled, or known to the player.

RawPairScore initially uses softened population pull, distance weight,
destination type, geography, and a neutral relationship weight.

ActualDailyBookers equals BaseDailyBookers times the current day's configurable
demand modifiers.

Demand is calculated before network availability. Routes and schedules do not
create or renormalize the underlying pair demand.

Every day creates a new generic Economy booking cohort. Failed Stage 1 bookers
do not automatically carry into tomorrow.

The global hard maximum booking horizon is configurable and begins at 365 days.
The rolling daily cohort pipeline replaces a fixed cumulative fill curve.

Passenger cohorts select desired future dates, score dated itineraries and the
outside option, and reserve available capacity in aggregated batches.

Frequency receives no direct bonus. It helps only by providing useful timing,
dates, connections, or capacity.

Connecting reservations are atomic across all legs. No orphan leg reservation
may be created.

All randomness is deterministic for the save, pair, date, and random purpose.

The engine uses schedule indexes, reachability and itinerary-pattern caches,
Hub-limited search, hard connection limits, and network-revision invalidation.

Daily booking intent, successful bookings, and passengers flying are separate
metrics and must never be treated as the same number.
```

## 29. Milestone 4 implementation reconciliation (2026-08-20)

The authoritative implementation is `game.demand`; persistent fields and
numeric representations are defined by the canonical Stage 1 State Schema.

The approved formula in Sections 3 through 7 supersedes the legacy
`game.economy.demand` pair-local calculation. The legacy function remains for
the current CLI and its characterization tests: it uses a 0.004 origin travel
rate, a capped destination-share estimate, and a linear distance floor. The
authoritative model retains 0.004 as the prototype `daily_booker_rate_ppm` but
uses square-root population pull, `1 / (1 + distance / 2000)`, configured
destination and geography weights, a neutral relationship weight, and the full
eligible denominator. Therefore the legacy `102` example is deliberately not
an authoritative full-universe expectation. In a two-airport represented world
the sole destination share is one and the 1,230,000-person origin pool is 4,920.

Stage 1 pair validity is revision-pinned. Both endpoints must be explicitly
passenger-demand eligible, have positive integer population, finite in-range
microdegree coordinates, a stable country reference, a supported destination
type, and be active on `demand_state.universe_date`. `active_from_date` is the
first active date and `active_until_date` is the first inactive date. The same
airport is never its own destination. Missing inputs make a reference
ineligible unless a caller explicitly claims eligibility, in which case
validation rejects the incomplete record. Unserved and unreachable airports
remain eligible. Bundled reference importance maps as follows:

| Reference classification | Demand destination type |
|---|---|
| `global` or `mega` | `MEGA_GLOBAL_CITY` |
| `major` | `CAPITAL_MAJOR_CITY` |
| `regional` + `large` | `MAJOR_REGIONAL_CITY` |
| `regional` + `medium` | `NORMAL_CITY` |
| `regional` + `small` | `SMALL_REGIONAL_CITY` |
| `minor` | `MINOR_CITY` |

Daily multipliers are integer basis points. The supported canonical composition
order is date/season, holiday, world, and explicitly supplied other demand-side
effect. Each missing category is neutral `10000`; values outside the configured
inclusive zero-to-`100000` prototype range, negative values, floats, booleans,
unknown categories, and malformed structures are rejected before mutation.
Composition multiplies all four integer factors exactly and then performs one
50-digit Decimal division by `10000^4`; it does not round between categories.
The persisted diagnostic composite is half-even rounded to integer parts per
million. Price, advertising, reputation, market presence, schedules, perks,
and capacity are not Milestone 4 demand multipliers.

The selected tiny-market policy is stateless deterministic fractional
resolution named `KEYED_SHA256_FRACTION_V1`. It always retains the integer part
and compares a purpose-keyed SHA-256 draw against the exact fractional
threshold. Inputs include world seed, immutable market ID, cohort date, model
version, configuration version, and canonical multipliers. The applied demand
revision is stored on the cohort but is not a draw input, so an airport-only or
universe revision changes the mathematical threshold without rerolling every
existing pair's independent sample. A 256-bit draw is rejection-sampled before
reduction to the exact Decimal denominator; a rejected draw retries with a
fixed domain separator and unsigned counter, so modulo bias is not introduced.
It therefore preserves long-run expected value without a mutable accumulator,
processing-order dependency, or reload reroll. The resolved result and one
market/date marker are persisted; repeated processing returns that result even
if a caller later supplies different modifiers. A versioned canonical-JSON
SHA-256 resolution fingerprint covers the world seed and stored marker
contents, so validation detects silent edits even when an older revision can no
longer be reconstructed.

Airport inputs, directional-market identity, demand/configuration versions,
universe date, rounding policy, and resolved cohorts are persistent authority.
Origin pools, rounded great-circle distance, raw scores, exact-sum shares,
baselines, source fingerprints, and indexes are reproducible derived values.
The stored input fingerprint is instead a continuation-critical authoritative
validation witness, even though its bytes are reproducible: it makes a direct
edit distinguishable from an approved revision after reload. It uses SHA-256
over version-tagged canonical UTF-8 JSON with sorted keys, compact separators,
escaped non-ASCII text, and rejection of non-finite or non-JSON values. A demand
revision commits configuration/reference changes atomically and invalidates a
runtime cache by revision/fingerprint mismatch without deleting prior cohort
outcomes or immutable market identities.

Fixed-precision share residual is assigned to the largest raw score, with an
immutable-ID tie break, rather than the last iterated pair. A sole valid
destination intentionally receives the complete origin pool. An origin with no
valid destination creates no pair and does not carry or redistribute the unused
pool.
Closed pair identities remain for history and are reused after an explicit
reopening revision.

Processed markers grow as directional pairs times processed days and remain in
Milestone 4 to prevent historical rerolls. Cohort dates on either side of the
pinned universe date are permitted; eligibility still uses the revision-pinned
universe. Compaction requires a later schema that preserves an equivalent
continuation proof.

The public API provides `calculate_world_demand`,
`recalculate_origin_demand`, `calculate_origin_daily_booking_pool`,
`calculate_raw_pair_score`, `get_base_daily_bookers`,
`compose_daily_multipliers`, `resolve_daily_cohort`,
`resolve_world_daily_cohorts`, `rebuild_demand_indexes`, and
`revise_demand_model`. Full construction is O(eligible airports squared),
unchanged reuse fingerprints reference/market authority, and the whole-world
daily command is O(eligible directional pairs). No demand path multiplies this
work by airlines,
schedules, or future flights.

Desired travel dates, service activation, itinerary search, the outside option,
choice and competition, capacity reservation, booking records and receipts, and
unsuccessful-intent handling remain Milestone 5 work.

## 30. Milestone 4.5A compact-demand reconciliation

Milestone 4.5A preserves the Section 3 through 10 formula pipeline exactly but
changes its rebuildable runtime representation. Initialization retains one
compact normalization summary per eligible origin: `OriginDailyBookingPool`,
the score denominator over the complete eligible destination universe, the
committed residual destination, and its exact conserved share. A requested
directional pair recalculates the same quantized distance and `RawPairScore` and
then derives its share and `BaseDailyBookers` on demand. The residual pair uses
the retained exact residual. This avoids materializing a rich demand object for
every directional pair while keeping all finite Decimal values and identities
exactly equal to the committed Model 3 implementation.

Unserved destinations still contribute to normalization. Schedule publication,
route rights, connections, fare, capacity availability, and network changes do
not enter the compact summary, its source witness, or any Model 3 formula.

Milestone 4.5A also implements the cheap activation step described in Sections
10 and 20. The default runtime provider returns directional market IDs for
usable direct published passenger occurrences inside an explicit inclusive UTC
window. It excludes deadheads, cancelled or superseded occurrences, malformed
traceability, and unusable or out-of-window service. It does not inspect
remaining capacity, because a full flight must still enter Booking's future
capacity fallback/outside-option decision. Connections or route rights without
a dated passenger occurrence do not activate work. Both endpoints must remain
eligible in the revision-pinned demand universe. IDs are deduplicated and sorted
by immutable market identity.

Activation is a runtime work-selection result, never demand authority. The
provider interface allows Milestone 5 to union direct service with separately
approved connecting-pattern discovery and apply Booking-owned horizon rules.
No connecting provider, itinerary search, desired-date selection, reservation,
outcome metric, or Booking state is implemented here.

The new active daily entry point is deliberately prospective: it resolves only
the current simulation date. Publishing service cannot backfill missed days,
and deactivation does not delete an already resolved marker. The pre-existing
pair and whole-world cohort commands remain compatibility behavior.

`processed_cohorts` therefore remains transitional Demand-owned authority in
Milestone 4.5A. The approved Milestone 5 direction is to commit demand intent
and Booking processing atomically under a Booking-owned daily checkpoint with
sparse outcome metrics. The persistent schema, marker migration, historical
continuation proof, and removal or compaction of `processed_cohorts` are all
deferred to that milestone.

## 31. Milestone 4.5B-1 travel-scope and compatibility foundation

Model 4 will refine the pipeline after `OriginDailyBookingPool` through a
versioned origin-country travel-scope envelope. The only canonical scopes are
`DOMESTIC`, `HOME_REGION_INTERNATIONAL`, and
`REST_OF_WORLD_INTERNATIONAL`. Policy
`ORIGIN_COUNTRY_TRAVEL_SCOPE_ENVELOPE_V1` uses one Alpha V1 default profile of
`6500`, `2500`, and `1000` basis points respectively, with optional complete
immutable-country-ID overrides. Every profile is non-negative integer basis
points summing to `10000`. Country attractiveness and relationship prototype
defaults are neutral `10000`.

Region is a pure sum of its member-country results. It owns no independent
formula, pool, coefficient, or randomness. Country and region identities are
immutable internal IDs; external codes and names are reference/display
attributes. Airline, player, route, service, schedule, pack status, capacity,
and `current_focus` do not enter scope or country normalization.

This increment supplies schema and migration authority only. A schema-1 world
is fully validated before an explicit migration consumes an approved snapshot.
The detached candidate adds region/country records and allocator namespaces,
maps every airport explicitly to `country_id`, records
`demand_allocation_member`, installs versioned empty market-pack and
travel-scope configuration, and is fully validated before atomic replacement.
Ambiguous, missing, malformed, non-JSON, or fingerprint-corrupt input is a
structured failure with no source mutation.

Schema 2 keeps Model 3 active. Existing V1 markers are wrapped as
`MODEL3_PROCESSED_COHORT_V1` with their payload unchanged. New Model 3 markers
use the same wrapper. The wrapper is excluded from the existing
`STAGE1_DEMAND_COHORT_SHA256_JSON_V1` input, so historical witnesses and
outcomes remain byte-identical and no historical configuration metadata is
invented. The single keyspace remains `<market_id>@<YYYY-MM-DD>`.

`MODEL4_TRAVEL_SCOPE_COHORT_V1`, its V2 witness contract, and versioned Model 4
revision-context fields are defined for validation, but they cannot become
active in 4.5B-1. While `demand.model_version` is 3,
`model3_terminal_demand_revision` is null, the Model 4 context collection is
empty, and any Model 4 cohort or attempted model-version change is rejected.
The first context and terminal Model 3 revision belong to the later atomic
4.5B-2 activation.

Travel-scope numerical allocation, country gravity, region aggregation amounts,
country-local airport allocation, and Model 4 cohort creation are implemented
by 4.5B-2 as specified below. Pack materialization and
enable/disable/re-enable lifecycle are deferred
to 4.5B-3. Booking checkpoints, reservations, connections, operations, finance,
save/reload orchestration, and history compaction remain deferred to their
approved later milestones.

## 32. Milestone 4.5B-2 Model 4 numerical reconciliation

Model 4 is entered only through `activate_model4(envelope,
expected_revision=...)`. The command validates the source, gives any custom
activation provider a detached candidate, requires complete schema-2 country
population/centroid and airport-membership inputs, records Model 3's terminal
revision, increments once, creates and fingerprints the current revision
context, derives and validates the complete candidate, and then commits. Every
rejection leaves the source byte-equivalent. Repeated activation is invalid.

For origin country `h` in region `r`, the domestic scope contains `h`, the
home-region-international scope contains effective countries in `r` except
`h`, and rest-of-world contains effective countries outside `r`. Effectiveness
uses the context's pinned universe date and does not consult pack status. The
configured non-negative three-scope weights total exactly 10000. Scope amounts
use the fixed 50-digit context; the greatest-weight scope receives the exact
pool-minus-other-scopes residual, with canonical scope code as tie-breaker.
Empty international scope amounts remain latent.

Domestic allocation assigns the complete domestic amount to `h`. Each
international scope scores its countries as:

```text
sqrt(country population / 1000000)
* 1 / (1 + centroid distance km / distance_scale_km)
* demand_attractiveness_bps / 10000
* relationship_weight_bps / 10000
```

Coordinates are authoritative integer microdegrees. Haversine trigonometry is
the only binary-float calculation and its result is half-even quantized to
0.001 km before Decimal use. Each scope conserves exactly; the greatest raw
score receives the residual and greatest immutable country ID breaks exact
ties. Region amounts are exact country sums and never affect allocation.

Inside a country, every allocation-member airport other than the origin uses
`sqrt(airport population / 1000000)`, the committed rational airport-distance
weight, and committed destination-type weight. Country population, centroid,
geography, attractiveness, and relationship are not repeated. The greatest
airport score receives the residual with greatest immutable airport ID as the
tie-breaker. Closed, unavailable, and pack-disabled members retain latent
leaves. Countries without member airports and scopes without countries retain
their complete latent amounts. The destination leaf of a materialized
directional market is its exact `BaseDailyBookers`.

Model 4 indexes are runtime-only compact reconstruction summaries. Their
source witness covers lineage, demand revision, Model 4 input fingerprint,
market identities, and index contract. Projections for origin, scope, country,
region, airport, latent totals, and pair baseline/share are detached.

One processed-cohort keyspace remains. Resolution validates authority and
checks the market/date key before derivation, then dispatches reuse by wrapper
contract. V1 Model 3 payload bytes and fingerprints never change. New Model 4
markers reference their revision context, use
`MODEL4_TRAVEL_SCOPE_COHORT_V1` and
`STAGE1_DEMAND_COHORT_SHA256_JSON_V2`, and use a keyed draw covering the stable
model/configuration/travel-scope/universe versions, market, date, multipliers,
world seed, and purpose. Mutable revision, pack status, UI, route, schedule,
fare, and capacity are excluded. Whole-world marker creation is rejected for
active Model 4; current-day active-service processing remains the only creation
path.

## 33. Milestone 4.5B-3 market-pack lifecycle and prospective activation

The atomic `materialize_country_pack`, `disable_country_pack`, and
`enable_country_pack` boundaries validate a detached candidate before commit.
Materialization requires expected pack and demand revisions; status transitions
require the expected pack revision. Rejection retains byte-equivalent source
authority and no caller-owned mutable references.

A country without materialized airports remains latent in its existing country
amount. First materialization preserves that amount and all pre-existing
country, leaf, pair, cohort, and entity identities while distributing the
amount only across its new allocation members. Pure disable/re-enable never
unloads authority and changes neither demand revision nor demand-input witness.

The separate pack witness covers configuration version and revision, statuses,
references and versions, status dates, catalog IDs, and catalog mappings. Pack
status, airport availability, schedules, flights, fares, capacity, airlines,
and UI focus are excluded from Model 4 normalization and its input witness.

Current-day work requires enabled and operationally available origin and
destination endpoints, an existing directional market, and traceable direct
published passenger service. Remaining seats are irrelevant. Custom providers
receive detached state; mutation, failure, malformed output, and unknown or
unavailable markets reject the complete command. Historical markers remain
valid, and materialization or re-enable creates no backlog.

Milestone 5 remains responsible for Booking checkpoints, desired travel dates,
itinerary search, reservations, capacity commitment, unsuccessful-shopping
metrics, passenger operations, finance, and marker migration or compaction.

## 34. Milestone 5A Booking schema and compatibility boundary

Schema 3 adds the strict `STAGE1_BOOKING_CONFIGURATION_V1` authority without
changing any demand formula, cohort, revision context, market-pack witness, or
active-market behavior. Its approved V1 horizon is 365 UTC dates, desired-date
tolerance is ±3 dates, and its inclusive lead-time buckets are `0` at 500 bps,
`1..6` at 1500, `7..29` at 3500, `30..89` at 3000, and `90..365` at 1500.
Ranges must cover the configured horizon exactly and weights total 10000.

The Booking-only fingerprint excludes demand/cohorts, pack state, airports,
markets, fares, schedules, flights, capacity, airlines, finance, and UI. The V1
choice-policy boundary reserves fare and schedule only; absent quality signals
are neutral, deterministic ranks are restricted to integer residuals and exact
ties, and mixed-currency competition is unsupported. 5A defines no score
transforms or weights.

`world_state.booking_state` begins at revision zero with no checkpoints. A
strict checkpoint pins Booking configuration, demand, and market-pack revisions
and owns strict market results, Booking IDs, and transaction IDs. No bootstrap
checkpoint is created because Booking recurrence/event ownership belongs to 5D.
Schema-2 placeholder Booking/itinerary payloads are compatibility-wrapped and
byte-preserved. Schema 2 defined no canonical Booking-status vocabulary, so
compatibility topology remains traceable but does not establish confirmed
capacity consumption. Desired-date allocation, shopping, choice, reservation,
production records, and finance remain 5B–5D.
