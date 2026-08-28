# Stage 1 State Schema

## Status and scope

This is the canonical concrete persistent-state schema for Stage 1 Milestones 0
through 5A. It supersedes the hybrid `game_state` example in
`Docs/template_reference_with_rules.txt` for new authoritative code. The hybrid
shape remains a compatibility-only legacy structure until later milestones
migrate the CLI and saved games.

Milestone 1 constructs and validates this in-memory, JSON-compatible envelope.
Milestone 2 adds authoritative clock advancement and generic event execution.
Milestone 3 adds repeating schedule definitions and bounded publication of
dated flights. Milestone 4 adds world-owned directional passenger demand and
idempotent daily intent resolution. Milestone 4.5A compacts only rebuildable
demand derivation and adds runtime active-market discovery; it adds no
persistent fields. Milestone 4.5B-1 adds the explicit in-memory schema-1-to-2
migration foundation and Model 4 authority shapes while deliberately retaining
Model 3 calculation. Milestones 4.5B-2 and 4.5B-3 activate Model 4 and add the
country market-pack lifecycle. Milestone 5A adds schema-3 Booking configuration,
identity, revision, compatibility, and optimistic-concurrency authority without
executing Booking. Exact file writing/loading and general save-pipeline
migrations, Booking processing, aircraft operations, and transaction posting
are not implemented.

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

## Envelope version 2 — Milestone 4.5B-1 foundation

Schema 2 is reached only through the explicit `migrate_schema_1_to_2`
boundary with a separately supplied, approved country-reference snapshot.
The schema-1 constructor remains available during this staged increment; it
does not invent region or country authority. Migration first validates the
complete schema-1 source, including every V1 cohort witness, operates on a
detached candidate, validates the complete schema-2 candidate, and replaces
the caller's envelope only after success. A failure leaves the source
byte-equivalent. Missing or conflicting airport-country mappings are
structured failures and are never inferred from display names.
The snapshot also supplies one explicit boolean allocation-membership value per
airport; migration never derives future Model 4 membership from Model 3
eligibility.

Schema 2 adds `region` and `country` immutable-ID allocator namespaces and the
following persistent authority:

```text
world_state
├── regions: {region_id: region}
├── countries: {country_id: country}
├── airports
│   └── <airport_id>
│       ├── country_id: immutable country ID
│       └── demand_allocation_member: boolean
└── demand_state
    ├── processed_cohort_schema_version: 2
    ├── model3_terminal_demand_revision: null
    ├── model4_revision_contexts: {}
    └── processed_cohorts
        └── "<market_id>@<YYYY-MM-DD>"
            ├── contract: MODEL3_PROCESSED_COHORT_V1
            └── payload: exact historical Model 3 V1 cohort

simulation.configuration.demand
├── market_pack_configuration
│   ├── contract: MARKET_PACK_CONFIGURATION_V1
│   ├── configuration_version: non-empty version
│   ├── revision: positive integer
│   ├── market_pack_ids: sorted unique pack IDs
│   ├── market_packs: {market_pack_id: country pack lifecycle record}
│   └── configuration_fingerprint: lowercase SHA-256 witness
└── travel_scope_configuration
    ├── policy: ORIGIN_COUNTRY_TRAVEL_SCOPE_ENVELOPE_V1
    ├── configuration_version: non-empty version
    ├── revision: positive integer
    ├── reference_snapshot_version: non-empty version
    ├── default_profile
    │   ├── domestic_weight_bps: 6500
    │   ├── home_region_international_weight_bps: 2500
    │   └── rest_of_world_international_weight_bps: 1000
    └── country_overrides: {country_id: complete three-field profile}
```

A region contains only `region_id`, `external_reference_code`, and
`display_name`. It is a pure aggregate and owns no demand coefficient or
formula. A country contains `country_id`, `region_id`, unique
`external_reference_code`, `display_name`, nullable canonical
`effective_from_date`/`effective_until_date`,
`demand_attractiveness_bps`, and `relationship_weight_bps`. During 4.5B-1 both
country demand values must remain the neutral integer value `10000`. Every scope profile contains
exactly the three canonical non-negative integer fields and sums to `10000`.
Country overrides use immutable country IDs, never names or external codes.

`country_reference` remains in a migrated airport only as Model 3 V1
compatibility input. `country_id` is the new authoritative foreign key.
Migration requires them to identify the same supplied snapshot country and
does not rewrite the compatibility value. `demand_allocation_member` is
authoritative membership for the later country-local allocator; it does not
change Model 3 eligibility or calculations in 4.5B-1.
Every airport added through a schema-2 public boundary must explicitly supply
both an existing `country_id` and a boolean `demand_allocation_member`; the
latter is never inferred from Model 3 eligibility.

The one `processed_cohorts` keyspace continues to use
`<market_id>@<YYYY-MM-DD>`. Schema 2 supports exactly the wrapper contracts
`MODEL3_PROCESSED_COHORT_V1` and `MODEL4_TRAVEL_SCOPE_COHORT_V1`. The Model 3
wrapper payload is preserved field-for-field and its
`STAGE1_DEMAND_COHORT_SHA256_JSON_V1` input excludes the wrapper. Historical
configuration or universe metadata is never fabricated. Model 4 contexts have
version and revision references, a pinned universe date, an input fingerprint,
and `STAGE1_DEMAND_REVISION_CONTEXT_SHA256_JSON_V1` witness. The Model 4 cohort
contract uses `STAGE1_DEMAND_COHORT_SHA256_JSON_V2`, but no Model 4 context or
cohort may exist while Model 3 is active.

During 4.5B-1, schema 2 must retain `demand.model_version == 3`, the existing
Model 3 input-fingerprint material, formulas, deterministic draw inputs, and
outcomes. `model3_terminal_demand_revision` remains null and
`model4_revision_contexts` remains empty. No production command can activate
Model 4. The first context and terminal Model 3 revision are committed only in
the later atomic 4.5B-2 activation.

## Envelope version 3 — Milestone 5A Booking foundation

Schema 3 is reached only through the explicit detached
`migrate_schema_2_to_3` boundary. The migration validates the complete schema-2
source, constructs and validates a detached candidate, and returns that
candidate without mutating or retaining caller-owned authority. Validation,
projection, demand processing, scheduling, and unrelated commands never invoke
this migration implicitly. Repeated migration and future-version sources are
structured rejections.

Schema 3 preserves all schema-2 demand, market-pack, scheduling, finance,
identity, cohort, event, history, allocator, and UI authority except for these
approved additions:

```text
metadata
└── save_schema_version: 3

simulation.configuration.booking
├── contract: STAGE1_BOOKING_CONFIGURATION_V1
├── configuration_version: non-empty version string
├── revision: positive integer                         # initially 1
├── booking_horizon_days: integer 0..365               # approved default 365
├── desired_date_policy: STAGE1_DESIRED_DATE_POLICY_V1
├── lead_time_buckets: ordered list
│   └── bucket
│       ├── minimum_lead_days: non-negative integer
│       ├── maximum_lead_days: integer >= minimum
│       └── weight_bps: non-negative integer
├── desired_date_tolerance_days: integer 0..horizon    # approved default 3
├── choice_policy
│   ├── contract: STAGE1_BOOKING_CHOICE_POLICY_V1
│   ├── production_input_families: [FARE, SCHEDULE]
│   ├── schedule_inputs: [DATE_DEVIATION, DEPARTURE_TIMING, DURATION]
│   ├── absent_airline_quality_signals: NEUTRAL
│   ├── deterministic_rank_usage: INTEGER_RESIDUALS_AND_EXACT_TIES_ONLY
│   └── currency_policy: SINGLE_CURRENCY_ONLY
└── configuration_fingerprint: lowercase SHA-256 witness

world_state.booking_state
├── booking_revision: non-negative integer             # initially 0
└── booking_checkpoints: {booking_checkpoint_id: checkpoint}

world_state.airlines.<airline_id>
└── finance_revision: non-negative integer              # initially 0

world_state.dated_flights.<dated_flight_id>
└── inventory_revision: non-negative integer            # initially 0

deterministic_state.id_allocator.next_by_type
└── booking_checkpoint: next positive integer
```

The approved lead-time buckets are the ordered, inclusive ranges `0..0` at
`500` basis points, `1..6` at `1500`, `7..29` at `3500`, `30..89` at `3000`,
and `90..365` at `1500`. A configuration's buckets must cover every day from
zero through its configured horizon exactly once, without gaps, overlaps, or
out-of-order ranges, and their weights must total exactly `10000`. The default
horizon is 365 UTC dates and the desired-date search tolerance is ±3 UTC dates.
Booleans are never accepted as integers.

The Booking configuration fingerprint is the canonical SHA-256 witness over
the complete Booking-owned configuration except the fingerprint field itself.
It excludes demand inputs and cohorts, pack state, airports and markets, fares,
schedules and dated flights, capacity consumption, airlines, financial state,
and UI/current-focus state. No Booking result is added to a demand,
derived-source, revision-context, or market-pack fingerprint.

The V1 choice-policy contract reserves only fare and schedule as production
input families. Schedule may later use date deviation, departure timing, and
duration. Reliability, reputation, perks, presence, awareness, and loyalty are
neutral while absent and must not be invented. Keyed deterministic ranks may
resolve integer residuals and exact ties only; uncontrolled passenger-level
randomness is prohibited. `SINGLE_CURRENCY_ONLY` makes mixed-currency
competition an unsupported boundary that later processing rejects as
`UNSUPPORTED_FARE_CURRENCY`; schema 3 adds no foreign-exchange authority. Score
transforms, weights, allocation, and execution remain Milestone 5C work.

A Booking checkpoint contains exactly:

```text
booking_checkpoint
  booking_checkpoint_id, checkpoint_date, due_at_utc,
  status (PENDING|COMPLETED), processed_at_utc,
  booking_revision, booking_configuration_revision,
  booking_configuration_fingerprint, demand_model_revision,
  market_pack_revision, market_results, financial_transaction_ids
```

Checkpoint IDs are immutable and allocated from the new `booking_checkpoint`
namespace. `checkpoint_date` is a canonical UTC date and `due_at_utc` is its
canonical midnight. A pending checkpoint has null `processed_at_utc`, pins the
current revisions and Booking fingerprint, has the current Booking revision,
and contains empty `market_results` and `financial_transaction_ids`.
Completed checkpoints require canonical processing time and strict result and
transaction-reference topology. Milestone 5A creates neither a bootstrap nor a
historical checkpoint: the existing event kernel has no Booking event ownership
requirement, and recurrence belongs to 5D. Therefore migration leaves
`booking_checkpoints` empty and does not consume any allocator.

Schema 3 reserves these strict future production contracts but creates no
records under either contract during migration:

```text
itinerary (STAGE1_DIRECT_ECONOMY_ITINERARY_V1)
  itinerary_id, contract, market_id, airline_id, origin_airport_id,
  destination_airport_id, dated_flight_ids, scheduled_departure_utc,
  scheduled_arrival_utc, cabin, fare_offer_snapshot, schedule_lineage, status

fare_offer_snapshot
  currency, amount_minor

schedule_lineage
  schedule_id, schedule_revision

booking (STAGE1_AGGREGATE_BOOKING_V1)
  booking_id, contract, booking_checkpoint_id, cohort_key,
  desired_travel_date, airline_id, itinerary_id, passenger_count,
  booked_at_utc, total_fare_minor, currency,
  inventory_revision_at_commit, finance_transaction_id,
  booking_revision, status
```

The direct V1 itinerary has exactly one dated-flight ID, cabin `ECONOMY`, and
status `CONFIRMED`; its endpoints, market, airline, times, fare snapshot, and
schedule lineage must match that flight and its retained schedule revision.
The aggregate V1 Booking has a positive passenger count, status `CONFIRMED`, no
individual passenger IDs, a one-to-one Booking-to-itinerary relationship, and
total fare equal to passenger count times the itinerary snapshot amount. Its
currency must match the snapshot. Revision and finance references are strict.

Because schema 2 accepted nonempty minimal Booking and itinerary placeholder
records, migration preserves each payload byte-for-byte inside the explicit
`SCHEMA2_BOOKING_COMPATIBILITY_V1` or
`SCHEMA2_ITINERARY_COMPATIBILITY_V1` wrapper. Compatibility wrappers do not
invent checkpoint, fare-snapshot, finance, or revision lineage. Schema 2
required only non-empty Booking status text and defined no canonical status
vocabulary, so compatibility payloads do not establish confirmed capacity
commitments even when their text happens to equal `CONFIRMED`. Runtime
capacity derivation counts only strict production V1 authority; compatibility
topology remains traceable without inventing reservation semantics.

`inventory_revision` and `finance_revision` are optimistic-concurrency tokens
only. Migration initializes each to zero and Milestone 5A performs no inventory
mutation, capacity commitment, financial posting, or transaction creation.
Booked and remaining capacity are derived at runtime from confirmed production
V1 Booking and itinerary authority; `remaining_capacity`, `booked_capacity`,
and rebuildable Booking indexes are forbidden persistent fields.

### Milestone 4.5B-2 Model 4 travel-scope contract

Schema-2 countries may omit `population`, `centroid_latitude_microdegrees`, and
`centroid_longitude_microdegrees` while Model 3 remains active. Migration never
infers them from airport records. Atomic Model 4 activation requires every
country to supply a positive integer population and valid integer microdegree
centroid coordinates; the values then become continuation-critical demand
authority covered by the Model 4 input and revision-context witnesses.

Activation operates on a detached candidate, requires the current demand
revision, sets `model3_terminal_demand_revision` to that revision, advances the
demand revision once, changes the active model to 4, and creates exactly one
context for the new revision. The context pins model/configuration,
travel-scope, universe date, market-pack, multiplier-bound, and complete demand
input witnesses. Loading, validation, migration, and Model 3 processing never
activate Model 4 implicitly.

For each allocation-member origin, `OriginDailyBookingPool` remains origin
population multiplied by `daily_booker_rate_ppm / 1000000`. The exact pool is
split by the configured `DOMESTIC`, `HOME_REGION_INTERNATIONAL`, and
`REST_OF_WORLD_INTERNATIONAL` basis-point profile. The residual scope is the
greatest-weight scope, with canonical scope code breaking ties. An empty
international scope remains latent.

The domestic country receives its whole scope. Within either international
scope, effective countries are normalized by
`sqrt(country population / 1000000) * (1 / (1 + centroid distance km /
distance_scale_km)) * attractiveness / 10000 * relationship / 10000`.
Haversine distance alone uses binary float and is half-even quantized to
`0.001` km before fixed 50-digit Decimal arithmetic. The residual country is
the greatest raw score, with the greatest immutable country ID breaking exact
ties. Region values are exact sums of country values and have no independent
weight or residual rule.

Each detailed country amount is normalized only over that country's
allocation-member airports other than the origin using the committed airport
population, distance, and destination-type factors. No country or geography
factor is repeated. The residual airport is the greatest raw score, with the
greatest immutable airport ID breaking exact ties. Closed, unavailable, or
pack-disabled members retain their leaf as latent; values are not redistributed.
The materialized directional-pair baseline is its destination airport leaf.
Available and unavailable materialized leaves, latent detailed-country leaves,
latent unmaterialized countries, and empty-scope amounts conserve the complete
origin pool exactly.

Model 4 runtime indexes and hierarchical projections are derived, detached,
and excluded from persistence. New Model 4 processed cohorts use
`MODEL4_TRAVEL_SCOPE_COHORT_V1` and
`STAGE1_DEMAND_COHORT_SHA256_JSON_V2`, reference the matching revision context,
and coexist with byte-preserved Model 3 wrappers in the one market/date
keyspace. Existing valid wrappers are always reused according to their own
contract. The unrestricted whole-world compatibility cohort command is not
supported while Model 4 is active; only prospective active-market processing
may create new Model 4 markers.

### Milestone 4.5B-3 country market-pack lifecycle

`market_pack_configuration` now persists a sorted `market_pack_ids` list, a
matching `market_packs` mapping, and a
`STAGE1_MARKET_PACK_CONFIGURATION_SHA256_JSON_V1` witness. Each pack owns its
immutable country, canonical reference and version, `LATENT|ENABLED|DISABLED` status,
nullable canonical status date, sorted catalog IDs, and the complete stable
catalog-ID-to-world-airport-ID mapping. External catalog and pack identifiers
are never foreign keys outside this mapping.

Materialization catalog records are exact dictionaries containing catalog ID,
reference code, display name, timezone, positive population, integer
microdegree coordinates, and destination type. They may additionally assert
the matching country identity and canonical opening/closing dates; aliases and
unknown fields are rejected rather than normalized into authority.
Once Model 4 is active, the country-pack materialization command is the only
airport-addition boundary; the legacy single-airport construction API rejects
instead of bypassing pack mappings and revision ownership.
Committed schema-2 worlds with the versioned empty `stage1-empty-v1` pack
record remain valid compatibility authority. Their first materialization
atomically installs the canonical pack shape and country allocation revisions;
new worlds never emit the legacy shape.

Each country owns a positive `airport_allocation_revision`. First
materialization sorts catalog records before allocating monotonic world airport
IDs, then creates missing directional markets in endpoint world-ID order. It
advances pack, demand, and target-country allocation revisions once and creates
the matching Model 4 context. Enable and disable preserve all IDs and
historical authority and advance only the pack revision.

Pack status and airport opening/closure are prospective activation inputs, not
allocation inputs, and are excluded from the Model 4 demand-input witness.
The canonical status-effective date is inclusive; a future disable leaves the
currently enabled pack active until that UTC date rather than applying early.
Closed and disabled members retain latent leaves without redistribution. Both
endpoint packs must be enabled and both airports available on the current
simulation UTC date before valid direct published passenger service can create
a cohort. Historical V1/V2 markers remain reusable and no transition backfills
prior dates.

## Entity records

```text
airport
  airport_id, reference_code, display_name, iata_code, icao_code, timezone,
  passenger_demand_eligible, population, latitude_microdegrees,
  longitude_microdegrees, country_reference, demand_destination_type,
  active_from_date, active_until_date, demand_input_revision,
  country_id (schema 2), demand_allocation_member (schema 2)

region (schema 2)
  region_id, external_reference_code, display_name

country (schema 2)
  country_id, region_id, external_reference_code, display_name,
  effective_from_date, effective_until_date, demand_attractiveness_bps,
  relationship_weight_bps, population, centroid_latitude_microdegrees,
  centroid_longitude_microdegrees, airport_allocation_revision

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

### Milestone 4.5A compact derivation and activation contract

Milestone 4.5A changes runtime derivation only. For each eligible origin, the
runtime demand index retains its exact `OriginDailyBookingPool`, full-universe
normalization denominator, committed residual destination, and exact residual
share. Distance, `RawPairScore`, non-residual share, and `BaseDailyBookers` for
one directional market are recalculated on demand with the same 50-digit
Decimal contexts, distance quantization, residual rule, and immutable-ID tie
break as Milestone 4. A mapping-compatible runtime projection preserves the
existing pair lookup API without retaining one rich object per directional
pair. These summaries, projections, source fingerprints, and lookup indexes are
rebuildable runtime state and remain excluded from persistence.

The denominator still includes every revision-eligible represented destination
other than the origin, including unserved destinations. Direct-service
activation is a separate runtime selection step and is never a formula input.
The default activation provider reads published dated flights inside an
explicit inclusive UTC window. A market activates only when at least one
structurally usable `PASSENGER`/`ECONOMY` occurrence is `PLANNED` or
`OPERATIONALLY_LOCKED` and retains valid schedule, aircraft, airline,
connection, market, time, fare, and positive published-capacity traceability.
Both endpoints must also remain eligible in the revision-pinned demand
universe.
Deadhead, cancelled, completed, superseded, malformed, out-of-window, or
otherwise unusable occurrences do not activate demand processing. Remaining
sellable capacity is deliberately not an activation input: a published full
service still makes the market relevant to Booking's later capacity and
outside-option decision. Results are deduplicated and returned in immutable
market-ID order.

`DemandActivationProvider` is a runtime-only boundary. Milestone 5 may combine
the direct provider with permitted connecting-pattern providers and its own
booking-horizon policy. Milestone 4.5A implements neither connecting discovery
nor itinerary validation. Its transitional active daily command resolves only
the current simulation date, so publishing service never backfills historical
days. Removing the last usable occurrence removes only future active work and
does not delete an existing marker.

`processed_cohorts` remains Demand-owned persistent continuation authority for
Milestone 4.5A. The approved later design is an atomic Demand-to-Booking daily
transaction in which Booking owns the checkpoint and sparse booking outcome
metrics. Defining those fields, migrating existing markers, proving equivalent
no-reroll continuation, and then removing `processed_cohorts` are explicitly
deferred to Milestone 5. No Booking checkpoint, Booking outcome, Booking metric,
capacity reservation, history-compaction, or connecting-itinerary field is
added by Milestone 4.5A.

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
  bookers, compact per-origin normalization summaries, source fingerprints,
  active-market provider results, and pair/origin indexes are
  derived/runtime-only.
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
  runtime demand indexes, revise inputs, discover active markets, and resolve
  the current active daily set: `game.demand` Milestone 4/4.5A API
