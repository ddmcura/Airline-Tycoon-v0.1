# Stage 1 State Schema

## Status and scope

This is the canonical concrete persistent-state schema for Stage 1 Milestones 0
and 1. It supersedes the hybrid `game_state` example in
`Docs/template_reference_with_rules.txt` for new authoritative code. The hybrid
shape remains a compatibility-only legacy structure until later milestones
migrate the CLI and saved games.

Milestone 1 constructs and validates this in-memory, JSON-compatible envelope.
Exact file writing, loading, migrations, event execution, demand generation,
booking, flight publication, aircraft operations, and transaction posting are
not implemented by this schema milestone.

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
│   ├── clock_state: "PAUSED"
│   ├── event_order_cursor: non-negative integer
│   └── configuration
│       └── difficulty: string
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
│   │   ├── market_demand: {market_id: demand facts}
│   │   └── fractional_accumulators: {market_id: value}
│   ├── bookings: {booking_id: booking}
│   ├── itineraries: {itinerary_id: itinerary}
│   ├── active_aircraft_operations: {dated_flight_id: operation}
│   ├── pending_events: {event_id: event}
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
  airport_id, reference_code, display_name, iata_code, icao_code, timezone

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
  schedule_id, airline_id, connection_id, planned_aircraft_id, status,
  recurrence, effective_from_utc, effective_until_utc

dated_flight
  dated_flight_id, schedule_id, airline_id, connection_id,
  planned_aircraft_id, scheduled_off_block_utc, scheduled_in_block_utc, status

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
  operation_revision, order_key, payload
```

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

## Authoritative, derived, runtime, and compatibility data

- Everything under `world_state`, `simulation`, `deterministic_state`, and the
  version/lineage metadata is authoritative.
- `ui_state` is saved presentation state. It may select an airline but cannot
  change world ownership, simulation scope, or save scope.
- Search indexes, lookup caches, formatted money, local timestamps, screen rows,
  and map positions are derived/runtime-only.
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
