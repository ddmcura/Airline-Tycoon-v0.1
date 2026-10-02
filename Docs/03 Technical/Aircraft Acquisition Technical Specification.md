# PH 1.0 Basic New-Aircraft Acquisition

## Step 5 compatibility and future manufacturer financing

Schema-6 leasing and used-aircraft behavior is specified separately in the
[Aircraft Marketplace Technical Specification](Aircraft%20Marketplace%20Technical%20Specification.md).
It reuses this specification's immediate eligible-base/hub delivery, immutable
catalog references, maximum-Economy configuration contract, deterministic
registration allocation, atomic candidate commit and stale-preview boundary.
Manufacturer outright purchase behavior is otherwise unchanged.

Manufacturer installments remain future scope. The intended product requires a
down payment, finances the remaining purchase price with interest, and gives the
player ownership and configuration rights from delivery. It may offer greater
availability and flexibility, potentially at a higher monthly cost than a
comparable lease-to-own offer. Exact rates, terms, lender mechanics and
refinancing are unresolved and are not schema-6 behavior.

Status: Approved for implementation on 2026-09-16, PH release step 3.
Persistent vocabulary follows the [schema-5 contract](Stage%201%20State%20Schema.md#approved-ph-acquisition-increment-schema-5)
and [template mirror](../../Data/Templates/template_reference.txt).

## Behavior and ownership

Purchase New Aircraft browses the immutable 20-model catalog, selects one model
and an existing player base/hub for delivery, then previews maximum Economy
seats, price and remaining USD cash. Confirmation creates one parked aircraft
immediately without advancing time. Cancel, EOF and interrupted forms do not
commit. Exact cash balance is valid; insufficient funds reject. Historical
production years do not gate availability.

Aircraft Market owns offer/preview and atomic orchestration. Fleet Management
owns entry and registration; Economy owns affordability and the balanced journal.
World State owns construction, validation and migration. Scheduling owns model
eligibility and timing. No legacy acquisition or name-keyed fleet path is called.

Existing required `home_airport_id` remains independent: new aircraft use the
airline's first operating base in immutable-ID order. Delivery sets only initial
`current_airport_id`. Choices are existing `base_airport_ids`/`hub_airport_ids`;
creating bases/hubs is outside scope. A new game currently has one such choice.

The journal debits `aircraft_assets` and credits `cash` at the pinned catalog USD
price. No revenue or operating expense is created. The journal owns acquisition
provenance, command identity and request fingerprint; there is no duplicate
acquisition collection or aircraft copy of price/model physics.

Preview hashes cover the authoritative envelope, excluding UI. Confirmation
revalidates all inputs and freshness, constructs and validates a detached
candidate, then replaces authority. Exact committed-preview replay returns the
original aircraft; conflicting command reuse rejects. Failure preserves all
state, ID cursors, RNG and time.

Base/hub delivery eligibility is a purchase-time command rule. The acquisition
journal retains the immutable delivery airport as history; a later base or hub
change does not invalidate that completed purchase. The referenced airport must
still exist, and new previews continue to reject locations outside the airline's
current base/hub set.

## Identity, configuration and presentation

Aircraft IDs own relationships. PH registrations use a seed-keyed hash of
aircraft ID and home country to select a 12-digit RP-C suffix, followed by
deterministic linear collision probing against existing world registrations.
This expanded game convention is not a real-world legal format assertion.
Unknown country conventions reject; no uncontrolled RNG, 9,999-number pool or
new persisted RNG cursor is used. Future re-registration preserves aircraft IDs.

Purchased aircraft bind an exact catalog version and maximum-Economy installed
configuration; existing `model_reference` holds the catalog model ID. Scheduling,
Booking and fulfilment consume installed capacity. Fresh PH careers now grant a
configured catalog `airbus-a320neo` under the schema-7 `STARTER_GRANT` contract.
Saved unconfigured A320-200 aircraft remain separate compatibility aircraft
without inferred acquisition/configuration facts.

Fleet display/selection extend the existing detached projection with pages of
20, showing registration, model, physical location and operational state. Lists,
counts and affordability are derived. Finance shows aircraft assets and recent
purchase journals separately from flight contribution.

## Versioned PH performance

`PH_SCALAR_RANGE_V1` uses the approved scalar reference maximum range. Distance
rounds upward to metres; equality with the ceiling is allowed. The eligibility
boundary permits future airport compatibility and versioned configuration/payload
performance without rewriting history. No payload curves, cargo or runway inputs
are fabricated. Future cargo should use integer mass (preferably kilograms) with
tonne display conversion; no unused authoritative fields are added now.

`PH_SCHEDULING_TIMING_V2` reserves total stand turnaround once before off-block:
30 minutes for turboprops/regional jets/narrowbodies; 45 for widebodies. Taxi-out
and taxi-in remain separate in block time. No post-arrival handling or
taxi-to-stand is added. The first departure reserves the same preparation time.
Existing minimum turnaround remains a lower bound (30 minutes in PH). Cruise
flight time retains upward five-minute rounding. Retained snapshots do not reload
current taxi references. Saved A320-200 V1 critical-path timing remains unchanged; fresh configured
A320neo starters use V2.

Quick Rotation remains an unconfigured A320-200 compatibility command; fresh
A320neo starters and purchased aircraft use Weekly Scheduler.
Deadheads retain zero passenger capacity/revenue and the existing fixed cost.
Fulfilment cost revision 1 is unchanged; model operating-cost balancing is deferred.

## Compatibility, limitations and non-goals

Explicit 4-to-5 migration changes only schema version in a validated candidate.
Existing aircraft, bookings, schedules, processed demand, event history, money
and witnesses are preserved. Required unknown catalog/model/performance bindings
fail explicitly. No historical purchases or configuration provenance are inferred.

Acquisition did not change scenario capital. Fresh careers now receive the
catalog-backed A320neo starter as a non-cash opening grant. The
later approved PH 1.0 Normal starting-capital correction supplies USD 300 million
to new careers; existing careers retain saved cash. This is not final economy or
difficulty balancing. Acquisition tests independently supply valid ample cash.

Runway support remains unvalidated: widebodies can be planned at PH airports
without physical runway checks. Scalar range is temporary gameplay calibration,
not a full-load dispatch guarantee. Compact records and the large registration
namespace avoid an artificial small fleet cap. World copying, hashing,
validation, registration scans and sorted fleet IDs still scale with world size;
this milestone does not claim tested interactive performance at tens of thousands
of aircraft. Realistic profiling remains runtime-milestone work.

This acquisition increment did not add leasing, used sales, financing, delayed
delivery, queues, maintenance, depreciation, cabin editing, payload-range, AI,
disk saves, graphics or existing-plan editing. Continuous runtime was implemented
by the later PH step 4 increment and does not alter this acquisition contract.

## Verification

[Acquisition tests](../../tests/test_stage1_aircraft_acquisition.py) cover all
20 models, balanced journals, affordability, separate delivery/home, command
freshness/replay, rollback, deterministic registration/collisions beyond legacy
ID limits, all timing categories, capacity/range boundaries, mixed-model booked
operations/deadheads, JSON/stepping equivalence, migration, terminal cancellation
and confirmation, and paged selection. Existing catalog/planner/Booking/fulfilment
tests remain regression coverage. Executed results are recorded in
[Current Development Status](Current%20Development%20Status.md).
