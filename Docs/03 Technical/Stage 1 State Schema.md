# Stage 1 State Schema

## Status and scope

This is the canonical concrete persistent-state schema for Stage 1 Milestones 0
through 4. It supersedes the hybrid `game_state` example in
`Docs/template_reference_with_rules.txt` for new authoritative code. The hybrid
shape remains a compatibility-only legacy structure until later milestones
migrate the CLI and saved games.

Milestone 1 constructs and validates this in-memory, JSON-compatible envelope.
Milestone 2 adds authoritative clock advancement and generic event execution.
Milestone 3 adds repeating schedule definitions and bounded publication of
dated flights. Milestone 4 adds world-owned directional passenger demand and
idempotent daily intent resolution. Exact file writing, loading, migrations,
booking, aircraft operations, and transaction posting are not implemented.

## Representation rules

- Field names are `snake_case`.
- Authoritative collections are dictionaries keyed by immutable internal ID.
- The record's primary ID field must equal its collection key; other `*_id`
  fields are foreign keys.
- Display names, IATA codes, registrations, route labels, and flight numbers are
  mutable/display data and are never authoritative foreign keys.
- Foreign keys always use `*_id` or `*_ids` fields.
- UTC timestamps use canonical second-resolution `YYYY-MM-DDTHH:MM:SSZ` text.
- Authoritative money uses signed integer `*_minor` values in the currency's
  minor unit. Binary floating-point values are invalid. Stage 1 accepts
  two-decimal input at construction and stores only integers thereafter.
- Runtime indexes and UI projections are not stored under `world_state`.
- Empty collections reserve ownership boundaries; they do not enable later
  milestone behavior.

## Envelope version 1

```text
stage_1_envelope
├── metadata                                      # authoritative
│   ├── save_schema_version: 1
│   ├── game_version: string
│   ├── reference_data_version: string
│   ├── lineage_id: string
│   └── world_created_at_utc: UTC timestamp
├── simulation                                    # authoritative
│   ├── time_utc: UTC timestamp
│   ├── clock_state: "PAUSED"|"NORMAL"|"FAST"|"FAST_FORWARD"
│   ├── event_order_cursor: next non-negative event sequence
│   ├── fast_forward
│   │   └── target_time_utc: UTC timestamp or null
│   ├── operation_revisions: {owner entity ID: non-negative integer}
│   └── configuration
│       ├── difficulty: string
│       ├── scheduling
│       │   ├── publication_horizon_days: positive integer
│       │   └── minimum_turnaround_seconds: non-negative integer
│       ├── demand
│       │   ├── model_version: 3
│       │   ├── configuration_version: non-empty string
│       │   ├── revision: positive integer
│       │   ├── daily_booker_rate_ppm: non-negative integer
│       │   ├── distance_scale_km: positive integer
│       │   ├── destination_type_weight_bps: complete type-to-positive-integer map
│       │   ├── same_country_weight_bps: positive integer
│       │   ├── international_weight_bps: positive integer
│       │   ├── relationship_weight_bps: positive integer
│       │   ├── daily_multiplier_min_bps: non-negative integer
│       │   └── daily_multiplier_max_bps: integer >= minimum
│       └── clock_ratios
│           ├── NORMAL: positive integer simulation seconds per real second
│           └── FAST: positive integer simulation seconds per real second
├── deterministic_state                           # authoritative
│   ├── world_seed: non-negative integer
│   ├── streams: dictionary
│   └── id_allocator
│       └── next_by_type: {entity_type: next positive integer}
├── world_state                                   # authoritative
│   ├── player
│   │   ├── player_id: "player"
│   │   ├── ceo_display_name: string
│   │   └── primary_airline_id: airline ID
│   ├── airports: {airport_id: airport}
│   ├── airlines: {airline_id: airline}
│   ├── aircraft: {aircraft_id: aircraft}
│   ├── directional_markets: {market_id: market}
│   ├── connections: {connection_id: connection}
│   ├── schedule_definitions: {schedule_id: schedule}
│   ├── dated_flights: {dated_flight_id: dated_flight}
│   ├── demand_state
│   │   ├── demand_model_revision: positive integer
│   │   ├── universe_date: YYYY-MM-DD
│   │   ├── input_fingerprint: lowercase SHA-256 text
│   │   ├── rounding_policy: "KEYED_SHA256_FRACTION_V1"
│   │   └── processed_cohorts: {"<market_id>@<YYYY-MM-DD>": processed cohort}
│   ├── bookings: {booking_id: booking}
│   ├── itineraries: {itinerary_id: itinerary}
│   ├── active_aircraft_operations: {dated_flight_id: operation}
│   ├── pending_events: {event_id: event}
│   ├── event_history: {event_id: resolved event}
│   ├── financial_accounts: {account_id: account}
│   ├── transactions: {transaction_id: transaction}
│   └── history
│       ├── operations: list
│       ├── financial: list
│       └── world_events: list
└── ui_state                                      # optional saved projection state
    ├── current_focus_airline_id: airline ID or null
    ├── selected_screen: string or null
    └── filters: dictionary
```

## Entity records

```text
airport
  airport_id, reference_code, display_name, iata_code, icao_code, timezone,
  passenger_demand_eligible, population, latitude_microdegrees,
  longitude_microdegrees, country_reference, demand_destination_type,
  active_from_date, active_until_date, demand_input_revision

airline
  airline_id, display_name, base_currency, control_type (PLAYER|AI), owner_type
  (PLAYER|INDEPENDENT|AIRLINE), owner_id, base_airport_ids, hub_airport_ids,
  financial_account_ids

aircraft
  aircraft_id, airline_id, display_registration, model_reference,
  home_airport_id, current_airport_id, status

directional_market
  market_id, origin_airport_id, destination_airport_id

connection
  connection_id, airline_id, market_id, status

schedule_definition
  schedule_id, airline_id, status (DRAFT|ACTIVE|RETIRED), current_revision,
  revisions: {positive decimal revision key: schedule_revision}

schedule_revision
  revision, effective_from_local_date, effective_until_local_date,
  connection_id or null, planned_aircraft_id, origin_airport_id,
  destination_airport_id, service_type (PASSENGER|DEADHEAD), recurrence,
  capacity, fare_offer, passenger_service_classification

recurrence
  frequency (WEEKLY), weekdays (sorted unique integers where Monday is 0),
  departure_local_time, departure_local_fold, arrival_local_time,
  arrival_day_offset, arrival_local_fold

fare_offer
  currency, amount_minor

dated_flight
  dated_flight_id, occurrence_key, schedule_id, schedule_revision, airline_id,
  connection_id or null, planned_aircraft_id, origin_airport_id,
  destination_airport_id, service_type, scheduled_departure_local_date,
  scheduled_off_block_utc, scheduled_in_block_utc, capacity, fare_offer,
  passenger_service_classification, status, published_at_utc,
  superseded_by_schedule_revision or null

itinerary
  itinerary_id, airline_id, dated_flight_ids

booking
  booking_id, airline_id, itinerary_id, passenger_count, booked_at_utc,
  total_fare_minor, currency, status

financial_account
  account_id, airline_id, code, category
  (CASH|ASSET|LIABILITY|REVENUE|EXPENSE), currency, balance_minor

transaction
  transaction_id, airline_id, occurred_at_utc, description, entries
  entry: account_id, amount_minor

pending_event
  event_id, event_type, due_at_utc, owner_type, owner_id,
  operation_revision, order_key [priority, sequence], payload, status PENDING

resolved_event
  all pending-event fields, terminal status
  (COMPLETED|CANCELLED|SUPERSEDED|STALE), resolved_at_utc

processed_demand_cohort
  cohort_key, market_id, cohort_date, demand_model_revision,
  daily_multipliers_bps, composite_multiplier_ppm, actual_daily_bookers,
  rounding_policy, resolution_fingerprint
```

### Milestone 4 world-demand contract

Passenger demand uses the approved Model 3 pipeline. `OriginDailyBookingPool`
is origin population times the configured `daily_booker_rate_ppm`.
`RawPairScore` is destination population pull times distance, destination type,
geography, and neutral relationship weights. `DestinationPairShare` divides
that score by the score total for every eligible destination in the represented
world. `BaseDailyBookers` is the origin pool times that share. These four
quantities are deterministic derived values, not persisted copies.

Population and coefficients enter the formula as integers and score, pool,
normalization, and baseline arithmetic uses a fixed 50-digit Decimal context.
Great-circle distance is derived from integer microdegree coordinates with the
haversine formula and half-even quantized to `0.001` km before Decimal score
arithmetic. Binary floating point is confined to that non-authoritative
trigonometric intermediate; no score, share, baseline, multiplier, or cohort
outcome is stored as binary floating point.

All direct score quotients are calculated before numeric conservation is
applied. The fixed-precision residual goes once to the destination with the
largest raw score, with immutable destination ID breaking an exact tie. Shares
therefore remain non-negative and their stored finite Decimal values sum
mathematically to one exactly (consumers must not re-sum them in a lower
precision context). They do not favor the last iterated destination. No
eligible destination creates no pair and does
not redistribute the unused origin pool. Exactly one eligible destination
intentionally has share one and receives the complete origin pool.

An airport is eligible on the revision-pinned `universe_date` only when
`passenger_demand_eligible` is true, its population is a positive integer, its
microdegree coordinates and stable country reference are valid, its destination
type is supported, `active_from_date` is null or no later than the date, and
`active_until_date` is null or later than the date. The closure date is the
first inactive date. The origin itself is excluded. Unserved, unreachable, and
player-unknown eligible airports remain in the denominator. Stage 1 advances
historical activity only through an explicit revision of the canonical UTC
universe date; local-day historical transitions are deferred.

Reference airport demand inputs are snapshotted into airport authority. Missing
population, coordinates, country, or destination type makes a reference
ineligible by default; an explicitly eligible malformed record is invalid.
Bundled `regional_importance`/`airport_size` data maps to the six canonical
destination types at the construction boundary. Airline, connection, schedule,
dated-flight, fare, capacity, awareness, and UI state are not formula inputs.

`demand.model_version` identifies the formula family.
`demand.configuration_version` identifies the prototype coefficient set.
`demand.revision`, `demand_state.demand_model_revision`, and every changed
airport's `demand_input_revision` make input changes explicit. Configuration or
reference-input changes commit atomically with a one-step revision increment.
`demand_state.universe_date` pins historical airport eligibility for the whole
revision. Crossing an airport opening or closure boundary requires an explicit
revision that advances this date; wall-clock or cohort processing never changes
the normalization universe implicitly. `input_fingerprint` covers the demand
configuration, universe date, and every airport demand input; validation
rejects direct input edits that bypass the revision/construction boundaries.
Runtime demand indexes carry their source fingerprint and revision; a mismatch
causes deterministic rebuild. Existing directional markets remain immutable
identity records when an airport later becomes ineligible, because connections
or history may still reference them. A later explicit reopening revision reuses
those identities; recalculation creates only pairs that never existed.

Daily multipliers use integer basis points. The neutral value is `10000`.
Supported categories are `date_season`, `holiday`, `world`, and `other`; missing
categories are neutral and values must be within the configured inclusive
range. Categories compose by multiplication in that canonical order. All four
integer factors are multiplied exactly before one 50-digit Decimal division by
`10000^4`; there is no category-by-category rounding. The derived composite is
recorded in integer parts per million using half-even rounding.
Negative, floating, boolean, unknown, non-finite, or otherwise malformed values
are rejected before mutation. Airline-side price, reputation, advertising,
frequency, product, and presence are deliberately excluded.

Fractional daily intent uses stateless purpose-keyed stochastic rounding. The
SHA-256 input contains the world seed, immutable market ID, cohort date, model
version, configuration version, canonical multipliers, and the policy name.
The global demand revision is recorded on the cohort but deliberately is not a
draw input: an airport-only or universe revision changes mathematical
thresholds without rerolling the independent sample for every existing pair.
The integer part is
always retained and the fractional part is selected by the keyed threshold.
The 256-bit draw uses rejection sampling before reduction to the exact Decimal
fraction denominator, eliminating modulo/threshold bias; the extraordinarily
rare retry appends a fixed domain separator and an unsigned counter. This
preserves the long-run expectation without processing-order dependence or a
mutable fractional accumulator. The resolved count and marker are persisted
once per market/date. Reprocessing returns the stored outcome and cannot reroll
or double-consume state. No unsuccessful-booker backlog is stored.

Each processed marker carries a `resolution_fingerprint` using
`STAGE1_DEMAND_COHORT_SHA256_JSON_V1`. It covers the world seed and every other
stored cohort field using the same canonical-JSON rules as the input witness.
Validation therefore detects a silently edited outcome, multiplier, identity,
revision, or rounding policy even after later demand revisions make historical
formula reconstruction unavailable. Like the input witness it is an integrity
check, not an authenticity signature.

`processed_cohorts` and the demand/configuration versions are persistent
continuation authority. Airport inputs and directional-market identities are
authoritative reference snapshots. `input_fingerprint` is a persisted,
continuation-critical validation witness: its bytes are reproducible, but the
stored value is authoritative because reload validation uses it to reject
input edits that bypass an explicit revision. Raw scores, origin pools, shares,
baselines, distances, normalization tables, source fingerprints, and indexes
are runtime-derived and must not be serialized under `demand_state`. Rebuild
never creates a cohort, consumes randomness, scans service, or invokes Booking.

The input witness is SHA-256 over UTF-8 canonical JSON identified by
`STAGE1_DEMAND_INPUT_SHA256_JSON_V1`: keys are sorted, separators contain no
whitespace, non-ASCII text is escaped, and non-finite or non-JSON inputs are
rejected. It is an integrity/revision witness, not a security signature;
changing this canonicalization or hash requires save-migration review.

One processed marker is retained for every resolved market/date, including a
zero result. A revision never deletes or rerolls earlier markers; unprocessed
dates use the current revision. Cohort dates may precede or follow
`universe_date`, while eligibility stays pinned to that revision's universe.
Marker growth is therefore directional pairs times processed days. Safe
compaction needs a later approved schema with an equivalent no-reroll proof and
is not part of Milestone 4.

### Milestone 3 schedule-definition contract

One schedule definition identifies one repeating movement plan. Its revision
records are immutable effective-dated plan versions. Revision dictionary keys
are canonical positive decimal strings (`"1"`, `"2"`, ...), equal the nested
`revision` value, and are contiguous through `current_revision`.

Local effective dates and recurrence dates use ISO `YYYY-MM-DD`. Local movement
times use whole-second `HH:MM:SS`. `departure_local_fold` and
`arrival_local_fold` are `0` or `1`. For an ambiguous local time, fold `0`
selects the first occurrence and fold `1` selects the second. An unambiguous
local time requires fold `0`; fold `1` is invalid rather than ignored. A local
time that does not exist under the airport's named IANA time-zone rules is
invalid for both folds and is never shifted. Authoritative expansion loads the
project-pinned first-party `tzdata` release exclusively; a missing package or
zone is a validation failure and never falls back to a host-local time-zone
database. `arrival_day_offset` is the
destination-local arrival-date offset from the origin-local departure date and
may be negative for date-line crossings. The resulting UTC arrival must always
be later than UTC departure.

An active revision applies on and after `effective_from_local_date` and through
its inclusive `effective_until_local_date`, or indefinitely when that field is
null. Adjacent revisions do not overlap or leave an internal gap: revising a
schedule closes the prior revision on the day before the new effective date.
Future dates before the replacement boundary retain the prior revision.

Passenger revisions require an `ACTIVE` airline connection whose directional
market endpoints exactly match `origin_airport_id` and
`destination_airport_id`. They require positive `capacity`, an airline-currency
non-negative integer-minor-unit `fare_offer`, and the Stage 1
`ECONOMY` passenger-service classification. Deadhead revisions are explicit
non-passenger movements: `connection_id` is null, `capacity` and fare are zero,
and classification is `NON_PASSENGER`. A continuity failure never creates a
deadhead implicitly.

### Milestone 3 publication contract

The rolling publication interval is closed at both ends:
`simulation.time_utc <= scheduled_off_block_utc <= target_horizon_utc`. A
command target cannot exceed the configured maximum of simulation time plus
`publication_horizon_days`. Recurrence expansion considers only the bounded
local-date range capable of intersecting that UTC interval and never expands an
indefinite future. Increasing the configured horizon exposes new occurrences.
Reducing it narrows later publication commands but does not delete or supersede
already published authority; only an effective schedule revision or retirement
can supersede unlocked future work.

`occurrence_key` is the canonical string
`<schedule_id>@<scheduled_departure_local_date>`. It is unique across dated
flights and deliberately excludes the revision: an unlocked occurrence revised
for the same schedule and local date keeps its immutable dated-flight ID.
Publication allocates IDs in deterministic `(scheduled_off_block_utc,
schedule_id, local date)` order. Repeated and overlapping publication commands
therefore cannot duplicate an occurrence.

Only `PLANNED` and `SUPERSEDED` dated flights without an active aircraft
operation are revision-mutable. A future
unlocked occurrence that still exists under a replacement revision is updated
in place and retains its dated-flight ID. An unlocked occurrence removed by a
revision becomes `SUPERSEDED`; it may return to `PLANNED` under a later revision
before operational lock. `OPERATIONALLY_LOCKED`, `COMPLETED`, and `CANCELLED`
occurrences are never rewritten by schedule revision. Their copied schedule
revision, planned assignment, endpoints, times, capacity, fare, and service
classification remain historical authority. A locked occurrence also occupies
its occurrence key, preventing stale work from recreating it. Milestone 3 does
not originate operational cancellations; it preserves a `CANCELLED` occurrence
created through an authorized boundary and excludes it from active direct-
service indexes.

Schedule IDs participate in `simulation.operation_revisions`. The value equals
the schedule's `current_revision`. Publication commands may carry expected
schedule revisions; a mismatch is reported as stale and performs no mutation.
Any later scheduled publication event using the generic event kernel is subject
to the same owner-revision invalidation. Milestone 3 performs ordinary
publication synchronously and does not persist routine publication events.

### Milestone 3 aircraft-continuity contract

Publication validates each aircraft's future dated sequence in canonical UTC
order. Assignments may not overlap, must allow at least
`minimum_turnaround_seconds`, and must depart from the prior arrival airport.
The first future assignment must depart from the aircraft's authoritative
`current_airport_id`. Ownership and all entity references must resolve. A
geographic break produces a structured `REPOSITIONING_REQUIRED` conflict; it
does not move the aircraft or create a hidden movement.

The scheduling domain also expands active definitions virtually across the
requested window before commit so conflicts between newly exposed occurrences
are rejected atomically. Draft definitions may remain incomplete plans, but
only active definitions publish.

### Milestone 3 derived indexes

The dated-flight index is runtime-only and rebuildable from
`world_state.dated_flights`. It provides deterministic ordered access by
origin, directional market, airline, planned aircraft, schedule definition, and
occurrence key. Index ordering is `(scheduled_off_block_utc,
dated_flight_id)`. No index is stored in the envelope, and rebuilding indexes
does not publish flights, advance time, invoke demand or booking, start an
aircraft operation, post money, or consume randomness.

`active_aircraft_operations` is keyed by dated-flight ID in Milestone 1 and may
contain the linked `dated_flight_id`, `aircraft_id`, state, revision, and exact
timestamps. Its behavior begins in later milestones.

## ID policy

Allocator namespaces are `airline`, `aircraft`, `airport`, `market`,
`connection`, `schedule`, `dated_flight`, `booking`, `itinerary`, `transaction`,
`event`, and `account`. IDs have a namespace prefix plus a zero-padded monotonic
number, for example `airline-000000000001`. `next_by_type` is authoritative and
must be greater than every issued number in its namespace. Allocation increments
the stored value before returning; IDs are never derived from names,
registrations, or dictionary order and are never recycled inside the lineage.
The version-1 numeric range is `000000000001` through `999999999999`; exhaustion
fails explicitly rather than widening or recycling the namespace.

Every airline has one three-letter uppercase base accounting currency. Its
minimal account foundation contains exactly one each of `cash`,
`aircraft_assets`, `debt`, `unflown_tickets`, `passenger_revenue`, and
`operating_expenses`; all belong to that airline and use its base currency.

## Clock and event contract

- New worlds start at their supplied canonical UTC timestamp in `PAUSED` mode.
- `NORMAL` and `FAST` ratios are exact positive integers. Wall-clock readings,
  sleep calls, render frames, and local time never advance authority.
- `FAST_FORWARD` requires an explicit UTC target at or after current simulation
  time. Reaching, stopping, or blocking fast-forward returns the clock to
  `PAUSED`; loading behavior remains deferred to the exact-save milestone.
- Scheduling assigns `order_key = [priority, event_order_cursor]`, then advances
  the persisted cursor. Sequence values are never reused in the save lineage.
- Queue order is `(due_at_utc, priority, sequence, event_id)`. Dictionary order
  is irrelevant. A heap or other queue index is derived and rebuildable.
- Pending events have `PENDING` status. Resolution moves the immutable event ID
  to `event_history` with one terminal status and `resolved_at_utc`; an event ID
  cannot exist in both collections.
- `operation_revisions` is keyed by immutable owner entity ID. A pending event
  with an older revision is archived as `STALE` without invoking its handler.
- Event payloads are JSON-compatible data only. Handler registrations, Python
  callables, iterators, heap nodes, and other runtime objects are never stored.
- A handler executes against an isolated candidate world. Its event and time
  changes commit only after validation. Failure leaves that event transaction
  unchanged and pending, blocks advancement at the failed event, and is retried
  only by another explicit processing command.
- Handler return value is `None`; the validated candidate is the result. Handler
  context cannot mutate the runtime registry, kernel-owned clock facts, event
  identity/order, or pre-existing pending and terminal event records. It may
  request `PAUSED`; new work is scheduled through the event API.
- Commit detaches the validated candidate again; references retained by a
  handler cannot mutate live authority after the transaction.
- Runtime-only per-command total and generated-event limits prevent unbounded
  same-timestamp self-scheduling. Hitting either leaves the next event pending
  and requires an explicit continuation command; limits are not authoritative
  save data.

## Authoritative, derived, runtime, and compatibility data

- Everything under `world_state`, `simulation`, `deterministic_state`, and the
  version/lineage metadata is authoritative.
- `ui_state` is saved presentation state. It may select an airline but cannot
  change world ownership, simulation scope, or save scope.
- Search indexes, lookup caches, formatted money, local timestamps, screen rows,
  and map positions are derived/runtime-only.
- Dated-flight indexes and publication command results are derived/runtime-only.
  `scheduled_departure_local_date` is retained only as authoritative recurrence
  identity and traceability; other airport-local presentation values are
  derived from the stored UTC instants and named airport time zones.
- World-demand origin pools, raw pair scores, normalized shares, base daily
  bookers, source fingerprints, and pair/origin indexes are derived/runtime-only.
  Persisting them under `demand_state` is a schema error. Processed daily cohort
  outcomes and the input-fingerprint validation witness are authority and are
  not silently repaired.
- `build_legacy_read_projection()` returns a detached compatibility-only copy
  shaped for old readers. Mutating it cannot mutate the authoritative envelope.
- `game/game_state.py`, `game/simulation/daily_tick.py`, route-owned demand, and
  the existing save/load functions remain legacy and non-authoritative. New
  Stage 1 construction never invokes them.

## Entry points

- Construct: `game.world_state.create_new_world(...)`
- Validate without repair: `game.world_state.validate_world(envelope)`
- Allocate an ID: `game.world_state.allocate_id(envelope, entity_type)`
- Build detached legacy view:
  `game.world_state.build_legacy_read_projection(envelope)`
- Create/validate/revise schedule definitions and publish dated occurrences:
  `game.scheduling` non-interactive Milestone 3 API
- Rebuild runtime dated-flight indexes:
  `game.scheduling.rebuild_dated_flight_indexes(envelope)`
- Build/recalculate one origin or the whole world, retrieve a directional
  baseline, compose daily multipliers, resolve one or all daily cohorts, rebuild
  runtime demand indexes, and revise inputs: `game.demand` Milestone 4 API
