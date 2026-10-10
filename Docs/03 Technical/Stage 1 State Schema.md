# Stage 1 State Schema

## Quarterly Stage 3D dormant boundary authority

Schema 9 optionally stores `simulation.quarterly_publication`, an airline-ID map
to exactly `{next_quarter_id, failure}`. Absence preserves ordinary PH gameplay.
Only the explicitly isolated test activation path creates entries. The next quarter
is the outstanding mandatory publication obligation; its due time is derived from
the UTC month-three calendar. It advances by one quarter only in the same complete
event transaction as successful Stage 3C publication or a validated committed skip.
`failure` is null or exactly `{code, message, details}`, with details a JSON list of
structured diagnostics. A failure requires simulation UTC to equal that obligation's
boundary. No runtime preparation, index, iterator, pacing credit or readiness is saved.

`QUARTERLY_PUBLICATION` is an airline-owned strict event, priority 0, current owner
operation revision, payload exactly `{contract: QUARTERLY_BOUNDARY_V1, quarter_id}`.
The derived queue has an explicit publication barrier at equal UTC: these events
precede all other events; unrelated events retain priority/sequence/ID order. This
is an ordering amendment, not negative priority or enqueue-order dependence.

The versioned recovery rule reconstructs only each enrolled owner's outstanding
event from the persisted obligation. Duplicate or obsolete publication events resolve
as budgeted lifecycle-only work without changing unrelated events. Stale resolution cannot discharge
an obligation. No arbitrary historical event replay is authorized. A frontier before
saved UTC is invalid, rather than silently repaired. Saves preserve failures and
obligations; Load stays paused and processing reconciles before selecting work.
Retained quarterly publication history also requires that owner's enrollment entry;
omitting continuation authority is invalid, not a dormant-world conversion.

Failure commits only the boundary clock/pause and deterministic diagnostic while
the failed event and dependent work stay pending. A certified command may correct
only that genuinely fenced unpublished quarter, including initialization from its
existing published baseline; published revisions remain immutable. Retry uses fresh
Stage 3C preparation, all four full gates and both world copies. Existing Schema 9
saves omit this optional field and require no migration. No ordinary activation,
quarterly operational supply, Booking migration or GUI integration is introduced.

## Schema 9 — reusable flight-number authority

Schema 9 supersedes Schema 8's permanent airline/number uniqueness, retaining
exactly the same record fields and allocator namespaces. New Game constructs
Schema 9; disk Load accepts only Schema 9, with no development-save conversion.
Earlier versions remain validatable as historical fixtures under their own rules.
Quarterly workflows remain dormant; legacy scheduling, Booking365 and runtime
remain the operational consumers.

Service IDs and slot identities are never reused. Retained services may share
an airline's player-facing numeric suffix across distinct lifetimes. A service
protects its suffix if `retired_at_utc` is null (including exclusive draft
reservation), or if it is referenced by the current published revision of a
plan whose UTC quarter has not ended. This covers active and future committed
use even after retirement. Unpublished retained versions and historical published
quarters alone do not protect a retired service's number. Removing plan membership
does not release a non-retired service's reservation. Two distinct protected
services for the same airline/suffix are invalid; historical holders alone are
not collisions. Retirement does not erase any retained reference or obligation.

New service allocation chooses the lowest eligible retired numeric suffix,
deduplicated across historical holders, only when no protected holder remains.
Otherwise it uses `service_numbering.next_number`. Reuse never advances or
decreases that cursor; fresh allocation advances it by one. The cursor remains
strictly greater than every retained suffix. Continuing services keep their
numbers; surviving services are never renumbered to fill gaps. Prefix/format
rules below remain unchanged. Eligibility/holder lookups are derived from
services, current published plan references and simulation UTC; no pool or
holder index is persisted. Cold Load validates/reconstructs without allocating.

All retained slots referencing one service must have identical directional
origin/destination IDs, across frequencies, revisions and quarters. Changing
either endpoint requires a new service ID, regardless of number reuse.
Canonical dated occurrence identity remains service/date/slot, never display
number. Complete trust-boundary validation retains all existing checks and
adds protected-holder exclusivity and the retained endpoint invariant.
Low-level constructors remain caller-owned candidate primitives, not Stage 2B
commands. Allocation rejects malformed relevant authority before consuming IDs
or cursors. Reconstructive lookups are temporary; maintained indexes remain 2D.

Stage 3B [lineage contract](Quarterly%20Operational%20Lineage.md) resolves bounded
explicit dated references from existing retained authority. Descriptors and their
plan/revision/service/slot/date references are derived runtime-only query values,
not new saved fields or operational supply. Commitment remains the exact selected
revision's publication timestamp; no schema/version or serialization change.

Stage 3C [shared publication](Quarterly%20Shared%20Publication.md) may set that
existing timestamp through the validated dormant transaction. Missing targets with
a published baseline create one normal full-slot revision; existing explicit
revisions (including removals/empty plans) prevail, and retired services are not
inherited. No extra persisted fields, version, supply table or operational consumer.
The first create/continue edit of a missing eligible future plan seeds that same
published baseline before its explicit change; all later revisions are complete
snapshots. This prevents omission during first-edit initialization from masquerading
as explicit removal. Source freshness and complete candidate validation are retained.

## Quarterly migration Stage 1 authority foundation (schema 8)

The following records the original Stage 1 contract. Schema 9 above supersedes
its lifetime-number reservation and current disk-version statements, and adds
the retained endpoint invariant without adding fields.

Schema 8 adds dormant identity/plan authority; current schedule definitions, dated
flights, Booking365, recurrence, events, finance and GUI still operate unchanged.
No quarter publication/carry-forward/Booking integration is implemented in Stage 1.
New Game alone initializes empty foundation tables after constructing fresh legacy
domain state. Disk Load accepts schema 8 only; older development saves are rejected
with UNSUPPORTED_SCHEMA. No 7-to-8 migration is provided. Earlier schemas remain
validatable as historical fixtures, not playable new-schema saves.

Authoritative new world roots:

- `services`: map of standard `service-NNNNNNNNNNNN` IDs to exactly
  `service_id`, `airline_id`, `flight_number_number` (positive integer),
  `next_slot_number` (positive integer, initially 1), `retired_at_utc` (null or
  exact UTC timestamp at/before current simulation time). IDs/numbers never reused.
- `service_numbering`: airline-ID map to exactly `flight_number_prefix` (2..8
  uppercase ASCII letters) and `next_number` (positive integer, initially 1).
  Prefix fixed once initialized. Number allocation is monotonic per airline;
  display is prefix + number padded to at least two digits, no two-digit limit.
  Display text is derived, not a foreign key. Retired services retain their number;
  no cooldown/reuse policy. `next_number` exceeds every retained airline number.
- `weekly_plans`: standard `weekly_plan-NNNNNNNNNNNN` ID map to exactly
  `weekly_plan_id`, `airline_id`, `quarter_id` (canonical `YYYY-Q1`..`YYYY-Q4`),
  `current_revision` and `revisions`. One plan per airline/quarter. Revision map
  keys are contiguous canonical integer strings 1..current_revision. Each value
  has exactly `revision`, `published_at_utc` (null until committed), and `slots`.
  Slots are a list of records each with exactly `service_id`, `slot_number`,
  `weekdays` (sorted unique integers 0..6), `departure_local_time` (HH:MM:SS),
  `departure_local_fold` (0/1), `origin_airport_id`, `destination_airport_id`,
  `planned_aircraft_id`, `connection_id`, `service_type`, `capacity`, `fare_offer`,
  `planning_timing`. These use the existing passenger/deadhead, integer-minor fare,
  connection ownership/endpoints, installed capacity and retained timing contracts.
  A slot number is stable within its service and less than its `next_slot_number`.
  Distinct frequencies use distinct slot numbers; multiple weekdays may share one.
  Service IDs own continuity across quarter plans; no positional semantic matching.
  Slot rows are ordered by `(service_id, slot_number)` and unique within a revision.

Whole-world construction/serialization/validation remain world_state-owned. New
entity namespaces `service` and `weekly_plan` extend the persisted standard allocator.
Local slot/flight-number cursors avoid global scans during allocation. Low-level
constructors mutate caller-owned detached candidates, like existing construction
primitives; they do not constitute GUI/strategic editing workflows. Revision append
preserves prior facts, requires expected revision, and rejects committed plans or
new inclusion of retired services. Existing retained versions remain valid on retirement.

Publication authority is only `published_at_utc`: at most one published revision,
which must be current; timestamp cannot exceed simulation time or quarter start.
Stage 1 supplies no command/event that sets it. Pure lifecycle derives PLANNING
when null; otherwise PUBLISHED before quarter start, ACTIVE within quarter,
HISTORICAL after quarter end. No lifecycle/target/cache labels are saved.
Quarter boundaries use UTC, `[start, next_start)`; shared utility handles year carry
and normal target months1–2 +1 quarter, month3 +2. Airport-local time is unchanged.

Future dated commitment identity is the pure key
`<service_id>@<canonical origin-local operating date>#<slot_number>` (unpadded
positive slot number). It excludes mutable number/time/aircraft/version and is stable
across plan revisions; applicable plan/revision facts remain separate lineage.
This is one shared future commercial/operational identity contract, not another
saved occurrence table. No occurrences are materialized and no legacy dated IDs
are remapped in Stage 1. Quarter/slot-aware identity query checks membership,
weekday and UTC-quarter applicability using pinned airport timezone conversion.

Full validation checks exact shapes, IDs/allocator cursors, ownership/foreign keys,
number/plan/slot uniqueness, timing/capacity/route facts and commitment timestamps.
Future execution feasibility, cyclic conflict validation, automatic publication,
manual publication, carry-forward, Bookings and operational exceptions remain later.


## Approved airport-local recurring weekly planner (2026-10-03)

Schema 7 accepts two optional `schedule_revision.recurrence` fields:

- `publication_policy`: when present, exactly `ROLLING_FOUR_WEEKS_V1`.
  Scheduling maintains the current airline-base-local Monday–Sunday week plus
  four future calendar weeks through the existing bounded publisher. Finite
  recurrence retains `until_local_date`; its absence means continuous recurrence.
  Absence of this policy preserves manual publication of older schedules.
- `enabled`: optional boolean, default true. A false effective-dated revision
  stops future expansion of that movement, retaining earlier revisions and all
  already-published obligations. It creates no cancellation or refund.

The generic persisted event `STAGE1_WEEKLY_PUBLICATION` is airline-owned, uses
the airline's current operation revision, priority 0, and payload exactly
`{"contract": "ROLLING_FOUR_WEEKS_V1"}`. Its next due time is the following
Monday 00:00 in the airline's first authoritative base airport timezone,
converted to canonical UTC with pinned tzdata. One pending event per participating
airline extends publication atomically and schedules the next week; no UI timer
or offline progression participates. No new world collection or schema version
is required. Existing saves without the optional policy gain no new events.

Weekly drafts may contain elapsed slots in the current airport-local week as
pattern intent only. The publisher excludes elapsed departures/preparation:
these slots never create dated flights, bookings, operations, history, journals,
or utilization. Schedule definitions can retain their local pattern start date.
Default pattern replacement starts on the first base-local Monday after all
published aircraft reservations, and never earlier than the next week. Since
revisions cover whole origin-local dates, a western-origin Sunday already
published on that boundary defers replacement to the next safe home-local week. Existing
published/booked flight records remain byte-for-byte unchanged. Replacement uses
atomic effective-dated revisions; removed movements receive `enabled: false`.
The aircraft's rolling definitions together form its editable weekly pattern;
pattern identity requires no duplicate persistent state.

Scheduling inputs use origin-airport-local time; arrivals use destination-local
time. Policy-managed occurrences derive UTC arrival from their retained
`planning_timing` maximum block duration and UTC departure; the revision local
arrival fields describe the prototype rather than freezing a destination clock
across DST changes. Older manual revisions retain exact local-arrival intent. The pinned IANA timezone/fold/gap rules below apply. Weekly row dates and
coordinates use the aircraft's authoritative home-airport timezone, explicitly
labeled when it differs from the flight endpoint zones. Planning may use an
airborne aircraft's authoritative active operation to project its arrival
location, reservation and turnaround; current PARKED status is not a prerequisite.

## PH 1.0 Step 7 durable save boundary (schema 7 unchanged)

Disk persistence captures the complete validated schema-7 envelope at a completed
transaction boundary. File-level career IDs, slot kinds, bookmark names, save
serials, real-time timestamps, integrity digests and recovery copies are outside
the authoritative world. The player airline's `display_name` labels its career,
but is not a filesystem key or foreign key. Loading a detached candidate sets
`simulation.clock_state` to `PAUSED` and clears any fast-forward target at the
saved exact UTC second. No offline time is applied. `ui_state` remains optional
presentation state, never the scope of the saved world. Pacing credit, active
timers, and autosave cadence are runtime-only and are not persisted as world
authority. Schema-1 migration requires the matching approved foundation snapshot;
schemas 2–7 use explicit adjacent migrations. No new authoritative field or
schema version is introduced by Step 7.

## Approved PH 1.0 Step 6 routine maintenance increment (schema 7)
Schema 7 adds a direct cash routine-maintenance component at successful flight
completion. Detached 6-to-7 migration adds only the maintenance configuration;
it preserves historical results, journals, aircraft, events and allocators.
Flights already locked at migration retain V1 settlement. No historical cost
or aircraft lifecycle fact is backfilled.

`simulation.configuration.maintenance` has exactly `contract:
PH_ROUTINE_MAINTENANCE_CONFIGURATION_V1`, `configuration_version:
ph-routine-maintenance-v1`, `classification_version:
ph-aircraft-aerodrome-class-v1`, `factor_minor_per_km_by_class`, and
`configuration_fingerprint`. The integer USD minor-unit factors per kilometre
for A through G are 15, 35, 80, 130, 200, 300 and 450. The fingerprint is
SHA-256 of sorted-key canonical JSON excluding the fingerprint itself.
`maintenance_expense_minor = ceil(distance_m * factor_minor_per_km / 1000)`.
Hours, cycles, age and condition are not formula inputs.

`Data/Stage1/aircraft_aerodrome_class_v1.json` is immutable external
reference authority. Its exact fields are `contract:
PH_AIRCRAFT_AERODROME_CLASS_V1`, `classification_version`,
`band_basis: ICAO_WINGSPAN_WITH_PROJECT_G_EXTENSION`, and `models`. The model map covers
the 20 catalog IDs and legacy starter `A320-200`. Each entry records
`wingspan_mm`, `aerodrome_class` (A..G), and `source_url`. A..F use the
ICAO wingspan bands [0,15000), [15000,24000), [24000,36000),
[36000,52000), [52000,65000), [65000,80000) mm. G is the project
extension at 80000 mm or more. Airport `max_aircraft_class` is never used
to classify an aircraft. Legacy `A320` model references resolve to the
starter entry solely for pre-PH world compatibility.

New departures add to the active operation: `maintenance_distance_m`,
`maintenance_distance_source`, `maintenance_classification_version`,
`maintenance_class`, `maintenance_factor_minor_per_km`, and
`maintenance_configuration_fingerprint`. Distance source is one of
`PLANNING_TIMING_V1`, `PLANNING_TIMING_V2`, or
`AIRPORT_COORDINATE_FALLBACK_V1`. The schedule revision's immutable
`planning_timing.distance_m` wins where present, preserving V1 truncation
and V2 ceiling. Otherwise the existing shared geographic distance from
authoritative airport coordinates is converted to integer metres and frozen
at departure. The actual aircraft supplies the model class. Older locked
operations have none of these fields and remain V1.

New completed results retain `STAGE1_FLIGHT_RESULT_V1` with
`result_version: 2` and add exactly `base_operating_cost_minor`,
`maintenance_expense_minor`, and the six maintenance departure witnesses.
`operating_cost_minor = base_operating_cost_minor + maintenance_expense_minor`.
The base uses the unchanged flight-fulfilment revision-1 formula. Historical
V1 results and their exact journals keep their original fields and meaning.
One `FLIGHT_FULFILMENT` journal debits `operating_expenses` and credits
`cash` by the total, with existing revenue entries unchanged. Completion
increments finance revision once. Deadheads pay; uncompleted flights do not.
Negative cash is permitted. Replay is idempotent. Existing lifetime seconds
and cycles continue independently. No maintenance account, payable, reserve,
second journal or calendar event is introduced.

## Approved PH 1.0 Step 5 aircraft-market increment (schema 6)

Schema 6 adds deterministic aircraft leasing, lease-to-own contracts and a
persistent used-aircraft market without rewriting schema-5 history. Migration
creates market authority and schedules its first monthly rotation; it does not
invent lifecycle facts for legacy aircraft. All money remains integer USD minor
units and all timestamps remain exact whole-second UTC.

`simulation.configuration.aircraft_market` is the immutable
`PH_AIRCRAFT_MARKET_CONFIGURATION_V1` tuning contract. It records the operating
lease and lease-to-own financing basis-point tables for terms one through five,
the annual depreciation rate, residual-value floor, condition-value floor,
maximum restoration share, offer counts and formula version. The initial term
tables are operating `{1:175, 2:160, 3:145, 4:135, 5:125}` and lease-to-own
financing `{1:100, 2:85, 3:70, 4:60, 5:50}` basis points per month. Lease-to-own
financing is therefore always below comparable operating rent. Depreciation is
400 basis points per completed year with a 2000-basis-point residual floor;
condition multiplies value from a 5000-basis-point floor at zero condition to
full value at 10000 condition. Restoration is at most 2000 basis points of new
value, linearly proportional to missing condition.

`world_state.aircraft_market_state` has exact fields `aircraft_market_id`,
`contract: PH_AIRCRAFT_MARKET_STATE_V1`, `current_month`,
`rotation_revision`, `next_rotation_at_utc`, and `active_lease_offer_ids`.
The new keyed collections are `aircraft_market_counterparties`,
`aircraft_lease_offers`, `used_aircraft_listings`, and `aircraft_contracts`.
New allocator namespaces are `aircraft_market`, `market_counterparty`,
`lease_offer`, `used_listing`, `airframe`, and `aircraft_contract`.

Counterparties have an immutable ID, `counterparty_type` (`LESSOR` or
`BACKGROUND_AIRLINE`), display name, active flag and a model-specialization
list. Background airlines are marketplace identities only. Lease offers record
their lessor, generation month, expiry, exact catalog/model/value/configuration,
available quantity and `ACTIVE`, `EXHAUSTED`, or `EXPIRED` status. Every monthly
rotation expires still-active lease offers and deterministically creates new
limited offers. Existing signed contracts never depend on current offer or
lessor visibility.

Used listings record `used_listing_id`, immutable `airframe_id`, seller,
generation month, exact catalog/model/configuration, manufactured date,
lifetime flight seconds, lifetime cycles,
service-condition basis points, asking price and `ACTIVE` or `SOLD` status. Age
is derived from manufactured date and the requested simulation timestamp; it is
not duplicated as mutable authority.
Monthly rotation adds coherent deterministic background listings; unsold
listings persist. Purchase changes the one listing to `SOLD`, links its acquired
aircraft ID, and preserves all airframe facts.

Schema-6 market aircraft require `lifecycle`, containing exactly `airframe_id`,
`acquisition_type` (`NEW_PURCHASE`, `USED_PURCHASE`, `OPERATING_LEASE`,
`LEASE_TO_OWN`, or `STARTER_GRANT`), `ownership_status` (`OWNED`,
`LESSOR_OWNED`, or `RETURNED`), nullable `aircraft_contract_id` and `source_listing_id`, `fixed_configuration`,
`manufactured_date`, `lifetime_flight_seconds`, `lifetime_cycles`, and
`service_condition_bps`. Completed flights add their gate-to-gate duration and
one cycle. Step 5 does not deteriorate condition. Returned aircraft records and
history remain authoritative but are excluded from usable-fleet projections.

`STARTER_GRANT` is the canonical provenance for one configured, catalog-backed
player aircraft supplied only during fresh scenario construction. It uses the
existing lifecycle fields and immutable airframe ID; no new aircraft field or
purchased-model specification copy is added. The grant is `OWNED`, has null
contract and listing links, an unlocked configuration, and no purchase, used or
lease transaction or obligation. Its initial manufacture date is the scenario
start date, condition is 10000 basis points, and lifetime hours/cycles are zero;
subsequent operations update those lifetime values normally. Validation permits
at most one grant, owned by the primary player airline, with the catalog-backed
configuration and no purchase journal. The player market has no grant command.
The grant is an opening scenario fact: it does not debit cash or create a
transaction or aircraft-asset ledger entry. The catalog reference price remains
a detached reference, not an opening balance. Existing unconfigured A320-200
aircraft and their V1 timing/history retain their saved compatibility meaning.
Fresh PH careers select catalog model `airbus-a320neo` for this grant and use
normal configured-aircraft V2 timing and maintenance. No saved career is
converted by validation or migration.

Aircraft contracts record immutable parties, aircraft, accepted offer (nullable
only for an operating renewal), predecessor/successor links, selected delivery
airport, start/expiry, term, exact pricing witness, installment progress,
next-payment timestamp, command/fingerprint witnesses and status. Contract type
is `OPERATING_LEASE` or `LEASE_TO_OWN`; status is `FUTURE`, `ACTIVE`,
`COMPLETED`, `RETURNED`, or `CANCELLED`. Monthly payments are in arrears at each
monthly anniversary, including expiry. Payment events precede flight events;
expiry/transfer/return follows all payments and flight completion at the same
second. A leased flight must complete at or before the continuous confirmed
contract horizon. Aircraft are never removed midflight.

The exact common contract fields are `aircraft_contract_id`, `contract_type`,
`status`, `airline_id`, `aircraft_id`, `lessor_id`, nullable `offer_id`, nullable
`predecessor_contract_id`, nullable `successor_contract_id`,
`delivery_airport_id`, `started_at_utc`, `expires_at_utc`, `term_years`,
`total_installments`, `paid_installments`, `aircraft_value_minor`,
`monthly_rent_minor`, `monthly_financing_minor`, `principal_base_minor`,
`principal_remainder_installments`, `principal_paid_minor`,
`financing_paid_minor`, nullable `next_payment_at_utc`, `command_id`, and
`request_fingerprint`. A cancelled lease-to-own contract additionally records
`cancellation_depreciated_value_minor`, `cancellation_equity_minor`, and
`cancellation_restoration_minor`; no other contract gains those fields.

Operating monthly rent is `ceil(new_value * term_rate_bps / 10000)`. Early
termination charges every unpaid rent installment immediately and no other
penalty. Renewal creates a priced successor operating contract beginning at
current expiry, preserving airframe, aircraft, registration, configuration and
history.

Lease-to-own principal is the original aircraft value divided across all term
months, with one minor unit added to the earliest remainder installments. Its
monthly financing component is
`ceil(original_value * term_financing_bps / 10000)`; only principal builds the
aircraft asset and equity. Final payment transfers ownership and configuration
rights. Early cancellation first computes age-depreciated value without a
condition multiplier, then computes `equity_after_depreciation =
max(0, depreciated_value - remaining_principal)`. The single net cash
settlement is `equity_after_depreciation - all_unpaid_financing_components -
restoration_cost`. Remaining principal is extinguished. This formulation applies
depreciation once through depreciated value, applies condition once through the
separate restoration charge, and never refunds more equity than paid principal.
Positive settlement credits cash; negative settlement debits cash. The journal
removes accumulated aircraft assets and posts the residual to operating expense.

Market commands use the schema-5 isolated-candidate, whole-world freshness and
idempotent command pattern. Journals use source types
`AIRCRAFT_LEASE_PAYMENT`, `AIRCRAFT_LEASE_TERMINATION`,
`AIRCRAFT_LTO_PAYMENT`, `AIRCRAFT_LTO_CANCELLATION`, and
`USED_AIRCRAFT_PURCHASE`. Automatic payments and settlements may make cash
negative. No delinquency, grace, default, repossession, loan, banking or
bankruptcy threshold is represented. A future bankruptcy duration would count
consecutive time below zero and reset on positive cash; its threshold is unresolved.

The valuation/condition contract is deliberately minimal. Future maintenance
may deteriorate condition using hours and cycles (short-haul flying accumulating
more cycles per hour), add age-sensitive A/B/C/D-style checks, component
overhauls, cost and downtime, and restore relevant condition without ever
resetting age or lifetime history. Manufacturer installments, physical delivery
and return, active AI fleet listings, AI distress/bankruptcy sales, banking,
consecutive-negative-cash bankruptcy rules, and lease-to-own refinancing remain
future behavior and are not schema-6 authority.

## Approved PH acquisition increment (schema 5)

Schema 5 extends schema 4 without rewriting existing aircraft, schedules,
bookings, journals, demand or event history. Explicit 4-to-5 migration changes
only the schema version. Older aircraft retain their compatibility behavior;
no acquisition or configuration provenance is inferred for them.

Purchased aircraft retain the existing fields. `model_reference` is the exact
catalog model ID. They additionally require `configuration`, exactly:
`contract: PH_MAX_ECONOMY_V1`, `catalog_version`, `economy_capacity`, and
`performance_contract: PH_SCALAR_RANGE_V1`. Capacity is a positive integer equal
to that version's maximum Economy layout. Reference binding resolves explicitly;
unknown or changed published content rejects. No physical model data is copied
into each aircraft. Configuration editing is not supported.

Acquisition provenance is an existing `transactions` journal with `source_type:
AIRCRAFT_PURCHASE`, `source_id` equal to the immutable aircraft ID, and exactly
the standard transaction fields plus `command_id`, `request_fingerprint`, and
`delivery_airport_id`. Command IDs are nonempty canonical strings, unique across
purchase journals; request fingerprints are lowercase SHA-256 hex. Each purchased
aircraft has exactly one purchase journal. Its two ordered entries debit
`aircraft_assets` and credit `cash` for the bound catalog USD price. Currency is
USD; timestamp is the command's exact simulation UTC second. No expense/revenue,
delivery event or elapsed time is created. Finance revision advances once.

Delivery selection is from the owning airline's base/hub airport IDs and sets
initial `current_airport_id` only. The independently required `home_airport_id`
uses the airline's first base in immutable-ID order; delivery does not reassign
it. Purchase-time commands enforce current base/hub eligibility. The retained
journal continues to reference the immutable airport after a later base/hub
change; validation must not reinterpret that historical choice against only the
airline's current memberships. New aircraft enter `PARKED`. No new base/hub
relationship is introduced.
Registration is a display value, globally unique at allocation. PH registration
uses RP-C plus a seeded SHA-256-derived 12-digit suffix (deterministic collision
probing); this game namespace is not a real registration-format assertion.
The seed, immutable aircraft ID and home country define the starting draw;
linear collision probing avoids consuming
another subsystem's RNG stream. No registration cursor or summary is persisted.

Schema-5 acquired-aircraft planning requires `PH_SCHEDULING_TIMING_V2` snapshots
with exactly `contract`, `profile_version: ph-acquisition-timing-v1`,
`model_reference`, `catalog_version`, `performance_contract: PH_SCALAR_RANGE_V1`,
`distance_m`, `cruise_speed_kph`, `turnaround_seconds`, `taxi_out_seconds`, and
`taxi_in_seconds`. Taxi fields retain integer min/max pairs; distance is an
integer rounded upward to metres for range eligibility. Cruise and scalar range
resolve from the immutable model; range is tested through the feasibility
boundary. Flight time retains upward five-minute rounding. Turnaround is 1800
seconds for turboprops/regional jets/narrowbodies and 2700 for widebodies. Reserve
it once before off-block; no additional post-arrival handling or taxi-to-stand
is added. Taxi-out/in remain in gate-to-gate time. First departure reserves the
same preparation allowance. Existing V1 snapshots and saved A320-200
starter behavior remain unchanged; a fresh configured A320neo grant uses V2.

Preview/confirmation data and whole-world freshness fingerprints are runtime
values. A successful journal retains the request fingerprint for idempotent
replay; mismatched reuse rejects. Commit uses a validated isolated candidate,
so failures preserve money, aircraft, IDs, events, RNG and time. Fleet lists,
pagination, counts and affordability are derived. Whole-world validation/copying
remains a scale limitation; there is no fixed fleet or registration pool limit.

Scalar performance and timing contracts are temporary PH 1.0 boundaries. Future
versioned configuration/payload-range and airport compatibility can replace the
eligibility provider without rewriting history. Payload, cargo weight, runway
requirements, maintenance, depreciation, leases and disk saving are not added.

## Approved aircraft catalog reference contract

The PH 1.0 catalog is versioned external reference authority, not a new world
collection. It does not change save schema 4, `metadata.reference_data_version`,
existing `aircraft.model_reference`, or any schedule/Booking/finance state.
Its bounded behavior is defined in the [catalog specification](Aircraft%20Catalog%20Technical%20Specification.md).

`Data/Stage1/aircraft_catalog_v1.json` contains exactly:

- `contract`: `AIRCRAFT_CATALOG_V1`;
- `catalog_version`: immutable content identifier `ph-aircraft-catalog-v1`;
- `manufacturers`: dictionaries keyed by stable IDs; each record contains
  `manufacturer_id`, `display_name`, and `notes`;
- `models`: dictionaries keyed by stable IDs; each record contains `model_id`,
  `manufacturer_id`, `display_name`, `family`, `aircraft_category`,
  `max_economy_seats`, `reference_range_km`, `cruise_speed_kph`,
  `production_start_year`, `production_end_year`, `source_ids`, and `notes`;
- `reference_prices`: dictionaries keyed by model ID; each record contains
  `model_id`, `currency` (`USD`), `amount_minor`, and `basis`
  (`GAME_NEW_EQUIVALENT_V1`);
- `sources`: dictionaries keyed by stable IDs; each record contains `source_id`,
  `title`, and an HTTPS `url`.

IDs match `[a-z][a-z0-9]*(?:-[a-z0-9]+)*` and record IDs equal their keys.
Foreign keys resolve inside the pack. Prices cover exactly the model IDs.
Names, family labels and manufacturer notes never own relationships.
Categories are `NARROWBODY`, `WIDEBODY`, `REGIONAL_JET`, or `TURBOPROP`.
Seat counts (1..1000), ranges (1..30000 km), cruise speeds (1..2000 km/h), and
prices (1..1000000000000 minor units) are integers, never booleans or floats.
Production years are null or integers in 1900..9999; known end >= known start.
Null means unestablished, including an unestablished end; it does not assert
current production. Years describe production, not certification or first service.
Each model has a nonempty, duplicate-free list of source IDs and nonempty notes
stating calibration assumptions and any production-date uncertainty.
All text is nonempty, stripped, and free of control characters. Collections
are nonempty exact dictionaries. Unknown fields and duplicate JSON keys reject.

Catalog versions are selected explicitly and loaded into an immutable runtime
value; lookups and sorted projections are detached. No implicit latest-version
fallback, alias matching, live network fetch, or missing-model substitution exists.
Production dates do not filter v1.0 availability. Reference ranges are illustrative,
not full-load dispatch guarantees; prices are game calibration, not transactions.
Individual-aircraft configuration/version binding was outside the catalog
milestone; schema 5 defines it in the acquisition increment above.
Published reference versions must not be edited in place; content changes require
a new version. The shipped version has a checked semantic content digest.

## Approved weekly planner increment (2026-09-07)

Schema 4 accepts two optional additions to schedule revisions. Absence preserves
existing scheduling, publication, serialization and historical contracts; no
implicit migration or retrospective timing calculation occurs.

- `recurrence.until_local_date`: inclusive canonical origin-local date, not
  earlier than `effective_from_local_date`. Absence means open recurrence. This
  bounds a one-date movement or an explicitly repeated weekly plan independently
  of the revision's effective window and the rolling publication horizon.
- `planning_timing`: immutable input snapshot with exactly `contract`
  (`PH_SCHEDULING_TIMING_V1`), `profile_version`, `model_reference`, `distance_m`,
  `cruise_speed_kph`, `max_speed_kph`, `activities`, `taxi_to_stand_seconds`,
  `taxi_out_seconds`, and `taxi_in_seconds`. Distance is a non-negative integer;
  speeds are positive integers and maximum speed is at least cruise speed.
  Taxi values are two-element integer lists `[minimum, maximum]` in seconds,
  with `0 <= minimum <= maximum <= 86400`. Activities contain exactly
  `baggage_loading`, `catering`, `refueling`, `cleaning`, `boarding`,
  `disembarking`, `baggage_unloading`, each with the same range representation.
  Version and model are nonempty strings. The model matches the planned aircraft.

Scheduling reserves maxima. Pre-departure seconds equal taxi-to-stand maximum
plus max(baggage loading, catering, refueling, cleaning + boarding). Post-arrival
seconds equal max(disembarking, baggage unloading). The minimum projection uses
the same dependency graph with minima. Flight seconds are distance/cruise speed,
rounded upward to five minutes (minimum five minutes), preserving the legacy
planning rounding. Off-block is departure from the stand; in-block is off-block
plus taxi-out maximum, airborne seconds and taxi-in maximum. Both timestamps
remain existing authoritative dated-flight fields. Reserved intervals are
derived from those fields and the retained revision snapshot, never persisted.
Every new timed leg reserves pre-departure work even if already parked at a gate.
Consecutive reservations must not overlap; the existing turnaround minimum also
applies. Validation checks snapshot shape, calculated duration and reservation
overlap, including prior completed and currently locked work. Old revisions are
never enriched from current reference data.

Drafts, Monday-week views, suggested slots, copied blocks and command selections
are runtime-only. Save validates a detached complete candidate and publishes
through an explicit bounded UTC horizon; it is not disk saving. One-way is the
default, return is an explicit reverse leg at the earliest feasible departure.
Positioning requires explicit confirmation. Timed schema-4 DEADHEAD movements
use the existing departure/completion lifecycle with zero capacity, no Booking,
zero revenue and the existing revision-1 fixed flight cost (seat costs are zero).
For these explicit positioning operations/results only, existing `market_id` is
null, because a deadhead has no commercial connection or passenger market claim.
Legacy untimed deadhead behavior is unchanged. Detailed handling execution,
random actual taxi/handling, disruptions, catalog/acquisition, and graphics remain
deferred. Maximum-speed recovery is not used for planned duration.

Input calibration is `Data/Stage1/scheduling_v1.json`: curated A320-200 speed
values copied from manufacturer data and explicit PH airport taxi ranges.
Handling values and taxi ranges are versioned gameplay calibration, not claims
of real measured airport performance. Unsupported models/airports reject rather
than silently receiving performance defaults. Published snapshots survive later
reference changes without re-reading that file.

## Status and scope

This is the canonical concrete persistent-state schema for Stage 1 Milestones 0
through 7. It supersedes the hybrid `game_state` example in
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
identity, revision, compatibility, and optimistic-concurrency authority.
Milestones 5B–5D implement Booking preparation and checkpoint persistence,
Milestone 6 adds schema-4 minimal flight fulfilment and settlement, and
Milestone 7 exposes that authority through a deterministic in-memory terminal
harness without changing this persistent schema. Exact file writing/loading and
general save-pipeline orchestration remain deferred.

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
├── revision: positive integer                         # legacy 5A 1; production 5C 2+
├── booking_horizon_days: integer 0..365               # approved default 365
├── desired_date_policy: STAGE1_DESIRED_DATE_POLICY_V1
├── lead_time_buckets: ordered list
│   └── bucket
│       ├── minimum_lead_days: non-negative integer
│       ├── maximum_lead_days: integer >= minimum
│       └── weight_bps: non-negative integer
├── desired_date_tolerance_days: integer 0..horizon    # approved default 3
├── choice_policy                                      # exact identity depends on revision
│   ├── revision 1 legacy contract: STAGE1_BOOKING_CHOICE_POLICY_V1
│   │   └── schedule_inputs: [DATE_DEVIATION, DEPARTURE_TIMING, DURATION]
│   └── revision 2+ production contract: STAGE1_BALANCED_FARE_SCHEDULE_CHOICE_V1
│       ├── production_input_families: [FARE, SCHEDULE]
│       ├── schedule_inputs: [DATE_DEVIATION, DURATION]
│       ├── component_weights_bps
│       │   ├── fare: 5000
│       │   ├── desired_date_deviation: 3000
│       │   └── journey_duration: 2000
│       ├── outside_option_weight_score_units: 2500
│       ├── absent_airline_quality_signals: NEUTRAL
│       ├── deterministic_rank_usage: INTEGER_RESIDUALS_AND_EXACT_TIES_ONLY
│       └── currency_policy: SINGLE_CURRENCY_ONLY
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

Schema-3 worlds produced by the committed 5A/5B implementation retain the
exact revision-1 legacy policy and its original fingerprint as valid authority.
They are not silently reinterpreted or rewritten. Fresh schema-2-to-3
migrations materialize revision 2 and the production policy. The explicit
detached `transition_booking_configuration_to_production_choice(...)` boundary
accepts only the exact revision-1 legacy policy plus the caller's matching old
revision/fingerprint, replaces only the choice policy, advances the Booking
configuration revision to 2, recomputes its Booking-only fingerprint, validates
the complete candidate, and commits atomically. Repeating it with current
revision-2 witnesses is an idempotent no-op. Allocation itself requires the
production policy and never performs this transition implicitly.

Both supported choice-policy identities reserve only fare and schedule as
production input families. Revision 1 reserved departure timing without
assigning production scoring semantics; revision 2 removes that unused input
and fixes fare, date-deviation, and duration scoring exactly. Reliability,
reputation, perks, presence, awareness, and loyalty are neutral while absent
and must not be invented. Keyed deterministic ranks may resolve integer
residuals and exact ties only; uncontrolled passenger-level randomness is
prohibited. `SINGLE_CURRENCY_ONLY` makes mixed-currency competition an
unsupported boundary that later processing rejects as
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
transaction-reference topology. Each market result owns requested, booked,
outside-option, insufficient-capacity, no-eligible-service, and no-departure
counts plus exact desired-date subresults and sorted Booking IDs. Every level
conserves requested passengers. Migration creates neither a bootstrap nor a
historical checkpoint and consumes no allocator; the first direct 5D command
processes only `simulation.time_utc[:10]`, then schedules the following UTC
midnight.

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
  schedule_id, schedule_revision, occurrence_key

booking (STAGE1_AGGREGATE_BOOKING_V1)
  booking_id, contract, booking_checkpoint_id, cohort_key,
  desired_travel_date, airline_id, itinerary_id, passenger_count,
  booked_at_utc, total_fare_minor, currency,
  inventory_revision_at_commit, finance_transaction_id,
  booking_revision, status
```

The direct V1 itinerary has exactly one dated-flight ID, cabin `ECONOMY`, and
status `CONFIRMED`; its endpoints, market, airline, times, fare currency, and
schedule lineage must match that flight and its retained schedule revision.
The fare amount is the immutable offer actually accepted by that Booking, not
a foreign key to a later/current display offer; this permits paid and zero-fare
batches to coexist while preserving exact sale lineage.
The aggregate V1 Booking has a positive passenger count, status `CONFIRMED`, no
individual passenger IDs, a one-to-one Booking-to-itinerary relationship, and
total fare equal to passenger count times the itinerary snapshot amount. Its
currency must match the snapshot. Revision and finance references are strict.
`finance_transaction_id` is null exactly for a zero-fare Booking; such a
Booking still commits capacity but changes no account or finance revision.
Paid Bookings reference the checkpoint's one aggregated transaction for their
airline.

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

`inventory_revision` and `finance_revision` are optimistic-concurrency tokens.
Migration initializes each to zero. A completed 5D checkpoint increments each
affected flight inventory revision once, each paid airline finance revision
once, and the global Booking revision once. Multiple Booking batches on one
flight store the same resulting inventory revision. Ticket-sale journals debit
cash and credit the unflown-ticket liability under the debit-positive journal
convention; category-normal display balances for both accounts increase, while
passenger revenue remains unchanged.
Booked and remaining capacity are derived at runtime from confirmed production
V1 Booking and itinerary authority; `remaining_capacity`, `booked_capacity`,
and rebuildable Booking indexes are forbidden persistent fields.

The event type `DAILY_BOOKING_CHECKPOINT` is owned by the completed checkpoint
that scheduled it. Its payload is exactly the following checkpoint date. One
pending next-day event exists after success; event dispatch calls the same
atomic command, and the kernel resolves the firing event only after the whole
candidate validates. Completed-checkpoint reuse allocates nothing and leaves
serialized authority byte-identical.

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
  airport_id, catalog_airport_id, reference_code, display_name, city,
  iata_code, icao_code, timezone,
  passenger_demand_eligible, population, latitude_microdegrees,
  longitude_microdegrees, country_reference, demand_destination_type,
  ground_network_id, tourism_pull_ppm,
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

Stage 3E (2026-10-04) activates the existing exact three certificates in production
session pacing and explicit Advance. One bounded shared resolver step per frontend
callback retains full final validation, detached commit, strict/fence/custom fallback
and successful-prefix recovery. Pacing debt, selected speed, catch-up/error states
and cooperative request metadata remain runtime-only. Pause drains earned finite
time; confirmed overload freezes accrual, drains and remains paused until explicit
Resume. Hard pause preserves complete committed boundaries. No schema fields,
version, gameplay, offline progression or additional certification change. See
[Production Cooperative Runtime](Production%20Cooperative%20Runtime.md) for the
current policy; following dated stage descriptions retain their historical scope.


PH continuous runtime uses these existing fields without changing their shape.
Normal Speed means 30 game days per real day. Named player speeds Normal Speed,
Fast, Very Fast and Ultra have relative multipliers 1, 7, 30 and 60 and literal
ratios 30, 210, 900 and 1800. Explicit Resume/speed selection writes the chosen
literal ratio to `simulation.configuration.clock_ratios.NORMAL` and uses
`clock_state = NORMAL`. Generic kernel `FAST` is not the player label Fast.
New and loaded sessions remain paused. Each controller initially selects Normal
Speed without rewriting loaded ratios; explicit Resume replaces the old literal
ratio rather than multiplying it. Player selection is runtime-only and resets on
load; current and legacy snapshots keep their saved literal configuration.
The pacing controller submits explicit whole-second kernel targets. Active-uptime samples, fractional credit, input
queues, suspended iterators and overload diagnostics are runtime-only and must
not be serialized. See the [runtime contract](Continuous%20Runtime%20Technical%20Specification.md).

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
  The isolated quarterly Stage 3D foundation adds the explicit equal-UTC publication
  barrier described above; all unrelated events retain this relative order. See
  [Quarterly Boundary Orchestration](Quarterly%20Boundary%20Orchestration.md).
- Pending events have `PENDING` status. Resolution moves the immutable event ID
  to `event_history` with one terminal status and `resolved_at_utc`; an event ID
  cannot exist in both collections.
- `operation_revisions` is keyed by immutable owner entity ID. A pending event
  with an older revision is archived as `STALE` without invoking its handler.
- Event payloads are JSON-compatible data only. Handler registrations, Python
  callables, iterators, heap nodes, and other runtime objects are never stored.
- Ordinary and unapproved handlers execute against isolated, fully validated
  single-event candidates. Explicitly certified deterministic built-ins may share
  a bounded private detached candidate while preserving canonical event order.
  Every transition must remain individually valid; final batch validation cannot
  excuse invalid intermediate state, even when later work would repair it.
- Shared work becomes authoritative only after complete world validation and a
  detached commit. No uncommitted candidate survives a cooperative return or
  reaches presentation, session-owned indexes, saves, or player commands.
  Certified handlers retain no candidate references and perform no deferred or
  external side effects. Handler identity, supported input, versioned proof and
  deterministic replay eligibility are runtime contracts, never save authority.
- DAILY_BOOKING_CHECKPOINT, STAGE1_WEEKLY_PUBLICATION and
  AIRCRAFT_CONTRACT_EXPIRY flush preceding shared work and execute strictly.
  Unknown, custom and uncertified handlers also retain strict boundaries.
- Failure preserves the strict successful chronological prefix. Discard failed
  speculative work and reselect events canonically through the strict executor;
  the first strict failure remains unchanged and pending. If strict replay
  succeeds where shared execution fails or differs, retain the valid strict
  result, disable the optimization and stop with an explicit optimizer diagnostic.
  Retry requires another explicit processing command; no automatic continuation.
- Saves and commands observe only validated complete-event boundaries. A boundary
  may retain pending events at the same UTC and must not be described as fully
  resolved through that timestamp. Batch size and cooperative timing cannot alter
  authoritative outcomes, IDs, ordering, revisions, journals or witnesses.
- Stage 3A (2026-10-04) provides opt-in infrastructure and shadow verification,
  with complete validation after EVERY candidate event and at final commit.
  Only the exact kernel NO_OP is shared-classified; Payment, Departure and
  Completion remain strict. Production session/pacing/Kivy stay strict. Future
  reduced validation requires precise write-footprint/dependency proofs and
  intermediate equivalence; final-world equality alone is insufficient.
  See [Runtime Shared Candidate Infrastructure](Runtime%20Shared%20Candidate%20Infrastructure.md).
- Stage 3B (2026-10-04) certifies only the exact built-in
  AIRCRAFT_CONTRACT_PAYMENT under `ph-aircraft-contract-payment-shared-v1`.
  Supported schema-6/7 active USD anniversary inputs use genuine before-event
  witnesses and exact domain transition proof instead of per-payment full-world
  validation. Protected dependencies remain unchanged and final full validation/
  detached commit remain mandatory. Unsupported/custom payment inputs stay strict;
  expiry stays a fence. Session/Kivy pacing remains strict. No persistent field,
  formula, flight certification or Stage 3C–3F behavior changes.
  See [Contract Payment Shared Certification](Contract%20Payment%20Shared%20Certification.md).
- Stage 3C (2026-10-04) separately certifies the exact built-in
  STAGE1_FLIGHT_DEPARTURE (`ph-flight-departure-shared-v1`) and
  STAGE1_FLIGHT_COMPLETION (`ph-flight-completion-shared-v1`) for supported
  schema-7 inputs. Genuine before-event witnesses, existing domain constructors/
  predicates, exact changed records, protected unchanged structures and canonical
  JSON compatibility and mutable-container alias checks prove each intermediate
  successor. Departure
  freezes the existing manifest/maintenance witnesses and generates one exact
  completion; Completion preserves existing result/settlement/counter behavior.
  Unsupported/custom/stale inputs remain strict, including older schemas. Migrated
  V1 in-flight operations in schema 7 retain V1 result behavior. Final full
  validation/detached commit, strict recovery, causal fences, event ordering and
  save authority remain unchanged. Payment keeps its Stage 3B certificate; Rotation
  stays strict. Session/Kivy/Advance pacing stays strict; Stage 3D–3F are not
  implemented. Schema remains 7 and no persistent fields or formulas change.
  See [Flight Shared Certification](Flight%20Shared%20Certification.md).
- Revised Stage 3D (2026-10-04) optimizes the existing flight proof only.
  Exact typed predecessor/successor protected bytes retain all unchanged-value
  guarantees. Per-event canonical JSON checks cover all changed/excluded records;
  protected compatibility is inherited only after exact equality. An equivalent
  full-candidate mutable-alias predicate remains mandatory. Final full validation,
  detached commit, recovery, fences, handler identity and saved Schema 7 are
  unchanged. No request-level witness reuse or private index is introduced.
  Session/Kivy/Advance pacing remains strict; no additional handlers or Stage 3E/3F.
  See [Flight Proof Cost Optimization](Flight%20Proof%20Cost%20Optimization.md).
- Stage 3D.2 (2026-10-04) preserves the same exact three certificates with
  an enforced private mutation boundary. Certified handlers receive writable
  copies only for approved records, simulation and allocator; other authority
  is recursively read-only. Genuine predecessor witnesses and exact changed/new
  output proofs remain per event. JSON/alias validity inherits from validated
  detached entry plus local output checks and detached publication. Full protected
  and alias oracles remain in shadow mode. Final full validation, detached commit,
  strict successful-prefix recovery and fence/strict boundaries remain unchanged.
  Capability memos expire before flush/recovery and never enter saves or Stage 2.
  No persistent field or schema version changes. Normal session/Kivy/Advance
  pacing stays strict; no additional handlers, Stage 3E or Stage 3F are implemented.
  See [Runtime Candidate Ownership](Runtime%20Candidate%20Ownership.md).
- Stage 3D.3 (2026-10-04) adds only a private candidate-local Booking-ID
  lookup for the existing certified flight handlers. Verified sorted IDs derive
  from Booking-to-itinerary-to-flight authority and remain reusable only while
  the enforced write footprints protect those source collections. Current-record
  manifest/lineage checks and exact predecessor/output proofs remain mandatory.
  Lazy construction and independent complete-coverage checks occur once per
  candidate; lookup state is discarded before every commit/return/fence/recovery.
  It is separate from Stage 2 reads and never saved. Schema stays 7; normal
  session/Kivy/Advance remains strict, with no added certification or Stage 3E/3F.
  See [Candidate Manifest Lookup](Candidate%20Manifest%20Lookup.md).
- Handler return value is `None`; the validated candidate is the result. Handler
  context cannot mutate the runtime registry, kernel-owned clock facts, event
  identity/order, or pre-existing pending and terminal event records. It may
  request `PAUSED`; new work is scheduled through the event API.
- Commit detaches the validated candidate again; references retained by a
  handler cannot mutate live authority after the transaction.
- Runtime-only processed-event limits accumulate across the entire request.
  Generated-event limits instead count children due at the generating event's
  exact UTC, accumulating across yields/flushes at that causal timestamp and
  resetting only when processing advances to another UTC. Later pending children
  do not consume that budget, even when inside the requested target. The generated
  limit stops only while more work remains at the exhausted timestamp. Hitting
  either limit retains complete-event commits and leaves the next event pending
  for explicit continuation; counters are not authoritative save data. See
  [Causal Generation Accounting](Runtime%20Causal%20Generation%20Accounting.md).

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
- Milestone 5B desired-date allocations, market plans, pre-choice dispositions,
  direct-shopping offer snapshots, and market/date/flight shopping indexes are
  detached runtime command results. They are not itinerary, Booking, checkpoint,
  cache, or save authority. The only permitted 5B persistent change is a valid
  current-day V1/V2 demand marker produced through the existing prospective
  active-market boundary.
- Milestone 5C score evidence, outside/capacity dispositions, observed
  inventory-revision snapshots, selected-offer counts, market results, and the
  `STAGE1_DAILY_BOOKING_ALLOCATION_PLAN_V1` result are detached runtime-only
  data. `selected_passengers` describes proposed capacity assignment, never a
  Booking or reservation. No allocation plan, score, remaining-capacity value,
  or contention cache is save authority. The command may persist only the same
  current-day cohort marker as 5B.
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
- Allocate aggregate desired dates, rebuild direct-shopping indexes, and
  atomically prepare the current-day pre-choice plan:
  `game.booking` Milestone 5B API
- Score aggregate choices, observe authoritative capacity/revisions, and build
  a detached contention-safe allocation plan:
  `game.booking.prepare_daily_booking_allocation(...)` (Milestone 5C)
- Prepare exact detached Booking checkpoint witnesses without mutating
  authority: `game.booking.prepare_daily_booking_checkpoint(...)`.
- Construct the curated temporary Stage 1 scenario:
  `game.world_state.create_stage1_new_game(...)`.
- Atomically create the fixed weekly outbound-and-return workflow and publish
  its first pair: `game.scheduling.create_weekly_round_trip_rotation(...)`.
- Project bounded enriched flights, fleet, airline finances, and the next
  pending event through the production projection packages.

## Envelope version 4 — Milestone 6 Minimal Flight Fulfilment

Schema 4 is reached only through detached `migrate_schema_3_to_4`. It preserves
schema-3 authority, adds `simulation.configuration.flight_fulfilment`, an
initially empty `world_state.flight_results`, each dated flight's
`operation_revision`, and canonically ordered departure events for eligible
future active direct-Economy flights. Past-due nonterminal flights and airline
currencies without an explicit profile reject atomically. Migration performs
no catch-up, carriage, settlement, or completion. An exact valid pre-existing
pending departure event is reused without allocator movement; conflicting
dated-flight event authority rejects the detached migration candidate.

The immutable revision-1 contract is
`STAGE1_FLIGHT_FULFILMENT_CONFIGURATION_V1`; its formula identity is
`FIXED_CAPACITY_SEAT_BLOCK_MINUTE_V1`. Block minutes and variable cost use
ceiling integer arithmetic. The USD profile is 75,000 fixed minor units, 300
minor units per published seat, and the Balanced `25/100` stored rate (25 minor
units per seat-block-minute under revision 1's hundredth-minor calibration),
giving 669,000 minor units for 180 seats and 120 minutes. PHP uses immutable
58/1 calibration (4,350,000 fixed; 17,400 per seat; `29/2` stored rate). EUR
uses immutable 86/100 calibration (64,500 fixed; 258 per seat; `43/200` stored
rate). These are explicit profiles, never runtime FX.

`PLANNED -> OPERATIONALLY_LOCKED -> COMPLETED` is driven by one departure and
one completion event at scheduled off-block and in-block UTC. The active
operation freezes sorted paid and zero-fare Booking IDs, ticket-sale IDs,
Booking/inventory witnesses, actual aircraft, and configuration witnesses.
Completion removes it and writes one `STAGE1_FLIGHT_RESULT_V1` keyed by flight.
Load factor and operating profit remain derived. Whole-world validation
recomputes the configured operating cost, requires exact terminal departure and
completion event history, and binds the latest aircraft state to the completed
destination (or to one later active operation).

Departure advances dated-flight operation revision and the event ID/order
cursors for its completion event. Completion advances dated-flight operation
revision, owning-airline finance revision, and the transaction allocator.
Booking and inventory revisions do not change. Booking checkpoints retain
priority 0; both flight events use priority 100.

## Milestone 7 in-memory terminal boundary

Milestone 7 adds no authoritative field and does not increment schema version
4. `Stage1Session`, menu navigation, loss-warning state, and display-currency
preference are runtime-only application data. Remaining capacity, booked and
carried load factors, operating contribution, formatted money, stable numbered
choices, and display conversions are detached derived presentation data.

`stage1-philippines-v1` constructs a private candidate from an immutable curated
reference pack, advances it through the approved schema/configuration
transitions, and establishes the first production Booking checkpoint and
recurrence. The original terminal milestone installed one free `A320-200`
before the later market schemas.
The current fresh-career path completes migration to schema 7, then installs
one configured catalog `airbus-a320neo` with `STARTER_GRANT` lifecycle and
validates the complete candidate. The grant posts no acquisition transaction.
Saved unconfigured `A320-200` aircraft retain their existing meaning.

USD is the only authoritative scenario currency. PHP and EUR display values use
scenario-defined integer ratios with round-to-nearest, ties-to-even minor-unit
rounding. They are never inputs to Demand, Booking, scheduling, fulfilment,
finance, fingerprints, revisions, events, validation, or serialization. The
terminal always retains a visible USD amount alongside any conversion.

Milestone 7 does not read or write saves. Exiting discards the in-memory world.
Authoritative file save/load, slots, autosave, backups, recovery, and persistence
migration orchestration remain Milestone 8. AI airlines and broader integrated
workflows remain Milestone 9.

## Philippines v1 recovery airport authority

Recovery Batch 1 retains save schema 4 while completing the previously
unreleased Stage 1 reference authority. Airport records may now carry nullable
`catalog_airport_id` and `city` fields; Philippines v1 requires both. Catalog
IDs are immutable external identities and must be unique. Non-null IATA and
ICAO codes are independently unique. Display names, cities, and codes remain
labels and never act as foreign keys.

`PHILIPPINES_COMMERCIAL_AIRPORT_PACK_V1`, version
`ph-commercial-airports-v1-2026-09-01`, is pinned to 2026-09-01. It contains 43
active scheduled-commercial allocation members and one inactive historical
reference record, LGP/RPBL. Only the 43 active records enter authoritative
World State; every ordered pair of distinct active members is materialized,
producing exactly 1,806 directional markets. DRP/RPLK has its own catalog and
world identity and is never an alias or rewrite of LGP.

The scenario records the enabled Philippine pack and its complete sorted
catalog-to-world mapping in `market_pack_configuration`. This freezes domestic
allocation membership for the version. A same-country materialization attempt
rejects after bootstrap. A later membership correction requires a new pack and
demand-calibration revision. Foreign pack materialization may advance the
global Demand revision but cannot change established Philippine domestic pair
baselines; processed cohort wrappers remain immutable and reusable.

Population is a versioned airport-catchment calibration input, not an assertion
that every record represents a municipal census boundary. Coordinates are
integer microdegrees and every active member uses `Asia/Manila`, an explicit
destination type, and true service/allocation/eligibility membership in the
source pack. The source pack also carries status flags for non-materialized
reference records. Runway data is not authoritative eligibility input in this
batch and aircraft compatibility is not inferred from it.

`game.demand.project_market_opportunities(...)` is a runtime-only bounded
projection. It exposes Model 4 revision witnesses, exact Decimal base daily
directional bookers, diagnostic share, authoritative-coordinate distance,
availability, endpoint display data, and current qualifying player
service/capacity/fare/confirmed-booking observations. The projection validates
once, reuses Model 4 pair authority, stays canonically ordered and detached,
and creates no cohort, connection, schedule, flight, Booking, event, random
input, revision, or persistent record.


## Philippines Demand Recovery Batch 2: optional Model 4 suitability

Model version remains 4 and save schema remains 4. Optional authoritative
`simulation.configuration.demand.air_suitability_configuration` contains exactly
`contract` = `MODEL4_AIR_SUITABILITY_V1`, a non-empty canonical
`configuration_version`, `interpolation_policy` = `PIECEWISE_LINEAR_RATIONAL_V1`,
`right_boundary_policy` = `HOLD_LAST`, `same_ground_network_points`, and
`separated_ground_network_points`. Each curve has at least two exact objects
containing `distance_m` (non-negative integer) and `suitability_bps` (0..10000
integer); distances strictly increase from zero. Boolean integers are invalid.

Airport authority may carry `ground_network_id` (stable non-empty canonical
string) and `tourism_pull_ppm` (integer 0..5000000, excluding booleans).
Both are required for every allocation member when the policy is present.
`population` remains the authoritative effective resident catchment.
Equal network IDs select the same-network curve; unequal IDs select the
separated-network curve. No code-specific demand branches are permitted.

The new score is `(sqrt(population / 1000000) * destination_type_weight_bps /
10000 + tourism_pull_ppm / 1000000) * suitability_bps / 10000`.
Suitability uses piecewise linear interpolation with the existing deterministic
50-digit Decimal arithmetic, without rounding to whole basis points, on the
existing distance converted to metres. Beyond the final point, hold its value.
The new curve replaces legacy airport distance attenuation. Apply the score
before country-local normalization, exactly once. Zero leaves have exact zero
baseline and contribute nothing to the denominator; positive leaves conserve
the existing country envelope. An all-zero nonempty destination allocation is
an invariant error, not a new latent category. Tourism never enters origin pools.

The tagged policy selects `STAGE1_MODEL4_DEMAND_INPUT_SHA256_JSON_V2`, covering
policy contracts and every point, network IDs, population, tourism, existing
mathematical configuration, country/scope inputs, revisions, lineage, and
immutable market identities. Service, fares, temporary availability, UI and
display currency are excluded. All legacy V1 branches and witnesses remain
unchanged when the policy is absent. Revision transactions append a new context
and affect only unprocessed cohorts; processed wrappers, counts, Bookings,
reservations, finance and checkpoint witnesses remain unchanged.

The scenario root may supply this optional configuration; active airport-pack
records then require both new airport inputs. `ph-air-suitability-v1` and
`ph-effective-catchments-v2` identify gameplay calibration, not census or
passenger-throughput claims. USD minor units remain financial authority;
PHP/EUR conversion is display-only.

PH 1.0 defers landmass registries, surface-access and catchment-overlap classes,
ferry factors, access zones, geography exceptions, business and regional/VFR
factors, tourism-origin/return balancing, long-haul decline, all-zero latent
categories, integer great-circle replacement and graphical curve editors.
This batch adds no save/load, AI, aircraft marketplace/manufacturers, leasing,
lease-to-own, used aircraft, maintenance, continuous runtime or broader scheduling.
