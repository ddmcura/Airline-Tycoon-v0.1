# Quarterly Authority and Identity Foundation — Implementation Stage 1

Implemented scope: dormant Schema 8 authority/identity foundation, 2026-10-07.
Baseline **c6fab14e6ed63161cf50882cef867fc81645b226**. This is not full quarterly
planning, publication, Booking migration, future delivery or reduced 3G-C.
The [canonical future design](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md)
still governs later behavior; the [schema](Stage%201%20State%20Schema.md#quarterly-migration-stage-1-authority-foundation-schema-8)
owns exact persistent names, followed by the template mirror. Schema/template were
edited before production. The migration audit remains historical and unchanged.

## Design reported before production changes

Current authority was schedule definitions/effective-dated revisions, allocated dated
flights, occurrence keys, inventory/operation revisions and Booking/event/result links.
No canonical public flight-number generator existed. Minimal new authority is three
empty New Game tables: services, airline number cursors and quarter weekly plans.
They are dormant, not a second operational scheduling writer or a converted legacy
schedule. Later stages must select one authority and retire the outgoing writer.

Schema 8 deliberately versions the new persistent roots and ID namespaces. Disk saves
must be schema 8; old development files fail with UNSUPPORTED_SCHEMA and are never
reinterpreted or converted. Earlier domain migration functions remain historical
bootstrap/fixture code; fresh New Game constructs its existing domains then initializes
the private foundation once, only on an unoperated bootstrap. Save/load still validates
separate candidates, retains previous valid files, restores paused and applies no
offline progress. No data files or historical results are rewritten.

## Implemented APIs and ownership

- [UTC quarter utility](../../game/utils/quarters.py): immutable `Quarter(year, number)`,
  canonical `quarter_id`, `start_utc`, exclusive next-quarter end, `shift` (negative
  for previous), `parse_quarter_id`, `quarter_containing` and `normal_target_quarter`.
  Whole-second aware timestamps normalize to UTC; dates mean UTC calendar dates.
  Month arithmetic lives here, not in airport-local scheduling. Out-of-range years
  and shifts fail explicitly; no offline/runtime/calendar events are added.
- [World-state constructors](../../game/world_state/quarterly_construction.py):
  `create_service`, `allocate_service_slot`, `retire_service`, `create_weekly_plan`,
  `append_weekly_plan_revision`. Like existing construction primitives, callers must
  own an isolated candidate and complete their validated transaction before exposure.
  These are not player editing/carry-forward/publish actions. Rejected ordinary inputs
  leave records and cursors unchanged; slot facts are deep-copied to prevent aliases.
- [Domain identity/lifecycle reads](../../game/scheduling/service_identity.py):
  `flight_number`, `occurrence_identity`, `plan_occurrence_identity`, `plan_lifecycle`.
  No ID/flight/event allocation during occurrence queries, and no publication command.
- [Validation](../../game/world_state/quarterly_validation.py) is integrated into
  complete `validate_world`; no full-world safety gate is weakened or optimized.

Service IDs use standard persisted monotonic `service-NNNNNNNNNNNN` allocation.
Plan IDs similarly use `weekly_plan-NNNNNNNNNNNN`, one per airline/quarter. Explicit
service IDs, never row positions or world fingerprints, carry identity into another
quarter. Plan revisions contain only weekly slot facts/references and immutable prior
versions, not world snapshots. Append requires expected revision and rejects published
plans or new inclusion of a retired service. No automatic semantic matching.

Airline prefix is explicit (2..8 uppercase ASCII letters), fixed once initialized.
A number is monotonic per airline; display is prefix plus at least two digits, growing
naturally beyond 99. Retired services keep their records/numbers; cursor never rewinds.
No cooldown/reuse/renumbering implementation. Prefix and number are authority; rendered
flight-number text is derived. Identical display strings in different airlines are
not foreign keys. Continuing services keep identity/number over weeks/quarter versions.

Stable slot numbers are allocated within service, supporting several same-day
frequencies or a shared slot on several weekdays. The future occurrence key is
`service_id@origin-local-operating-date#slot_number`, excluding mutable time/aircraft/
fare/plan revision. Correct plan/revision remains separate facts lineage. Quarter-aware
queries use pinned local departure conversion and check actual departure within UTC
quarter; this protects local/UTC edge cases. There is no separate commercial identity,
no saved occurrence table, and no remapping of current dated-flight IDs.

Only a nullable publication commitment timestamp is persisted per revision. Validation
allows at most one committed revision, which must be current, not in the future or
later than quarter start. Lifecycle derives PLANNING before commitment, PUBLISHED
before the operating quarter, ACTIVE during it and HISTORICAL afterward. No saved
lifecycle/target/readiness cache. There is deliberately no API setting the commitment:
automatic/manual publication belongs to Stage 3.

Slots validate exact fields, allocated IDs/slot cursors, ownership/connection market
endpoints, integer fare/capacity, sorted weekdays/time/fold, retained timing/model/
distance/configuration and unique ordering. Full feasibility, weekly wrap/conflict
proof and projected delivery are not implemented; these are dormant planning facts,
not executable supply. Retained versions remain attributable after retirement.

## Transitional operational compatibility

Existing schema guards now accept additive schema 8 for the same existing paths:
recurrence/publication, Booking365, demand, acquisition, maintenance, fulfilment,
projections and existing shared NO_OP / certified Payment/Departure/Completion. No new handler certification,
proof algorithm, event type, supply discovery, time rules or equations. Existing
local proof protection also covers the dormant tables; full final gates remain.

Current GUI drafts and dated-flight publication do not write/read new plan authority.
Current Bookings do not shop unpublished foundation slots or treat their timestamps
as new commercial supply. Current flights/events/history keep original identities.
This explicit transitional separation prevents accidental duplicate authority while
later consumers have not migrated. It must not become a permanent second scheduler.
The player-facing quarter locks/new-airline targeting are future workflow behavior,
not activated by foundation constructors.

Identity/slot/flight-number allocation uses direct cursors and collection-key collision
checks, without aircraft/history scans or world fingerprints. Plan creation checks
uniqueness in the small plan collection; complete validation intentionally visits all
foundation authority alongside the existing graph. No quarter occurrences, threads,
broad caches or transaction optimization introduced. No throughput improvement claimed.

## Verification scope

Focused new regressions: [test_quarterly_foundation](../../tests/test_quarterly_foundation.py).
Coverage includes all monthly targets/year/leap/UTC edges and invalid calendar inputs;
weekly reuse and distinct dates/slots; continuing identity and retained quarter/revision
facts; retirement/reservation; numbering past99; atomic rejection; publication-derived
lifecycle/invalid commitments; malformed authority/duplicates; exact serialized save/
load detachment and equivalent actions. A complete operational comparison against
schema 7 removes only the three intentional roots/two cursors/schema tag, then proves
same scheduling, daily Booking, departures/completions, finance and event history.

Default host Python lacked pinned tzdata. Tests use the pre-existing `.venv/Scripts/python.exe`
with `-B`; no environment packages installed or files changed. All filesystem tests
use TEMP. Relevant historical schema5/6 fixtures explicitly omit the additive empty
foundation; no production converter was added. Save tests now assert old-version
rejection instead of conversion; historical migration domain tests remain.

Commands/results are recorded in Current Development Status after final verification.
The first full discovery ran 1155 cases: 1152 passed; two fixed schema-7 hash fixtures
needed the explicit empty-foundation projection, and the existing NO_OP contract's
schema guard needed 8. All 49 advancement/shared cases then passed in 47.298s.
Historical hash values remain intact; full schema-8 clone/runtime/reload checks remain.
Final `.venv/Scripts/python.exe -B -m unittest discover -s tests -q`: **1155 passed
in 1151.585s** after that guard/test correction, with source/tests frozen. Scoped
compilation PASS; 365 documentation links / 63 heading targets and casing PASS;
complete diff/authority/scope review and `git diff --check` PASS. No later-stage
implementation or performance certification included.
Full suite, scoped compilation, link/heading/casing and diff review are required here;
no giant performance certification. Allocation sanity constructs 101 services without
slot validation/occurrence materialization; this is structural regression evidence,
not a large-fleet timing benchmark.

## Remaining work and Stage 2 prerequisites

Stage 2 needs target dependency/validation/ownership contracts before broad publication
or Booking migration: protected dormant authority, inverse relations, plan-local
feasibility, deterministic atomic edits and legacy-writer retirement boundary. Schema 8
must remain coherent with every existing domain/certificate. Stages3+ implement carry-
forward, targeting GUI/locks, publication, published-only sales, lead-time mechanics,
delivery and operational history/occurrence changes under separate bounded approval.

Unresolved product/implementation decisions: lead-time policy within published supply,
exact event ordering at publication/rollover, service-frequency UX, future availability
contract, possible number reuse/cooldown, amendments/disruption scope and history
representation. No further human approval was needed for this bounded foundation.

## Exact changed production and test scope

Production (31; four new foundation modules, existing persistence/bootstrap/schema/
validation and otherwise additive acceptance guards):

- [game/aircraft_market/acquisition.py](../../game/aircraft_market/acquisition.py)
- [game/aircraft_market/step5.py](../../game/aircraft_market/step5.py)
- [game/aircraft_operations/fulfilment.py](../../game/aircraft_operations/fulfilment.py)
- [game/aircraft_operations/manifest_lookup.py](../../game/aircraft_operations/manifest_lookup.py)
- [game/aircraft_operations/projections.py](../../game/aircraft_operations/projections.py)
- [game/booking/checkpoint.py](../../game/booking/checkpoint.py)
- [game/booking/indexes.py](../../game/booking/indexes.py)
- [game/booking/shopping.py](../../game/booking/shopping.py)
- [game/demand/model.py](../../game/demand/model.py)
- [game/demand/model4.py](../../game/demand/model4.py)
- [game/fleet_management/acquisition.py](../../game/fleet_management/acquisition.py)
- [game/scheduling/publication.py](../../game/scheduling/publication.py)
- [game/scheduling/service_identity.py](../../game/scheduling/service_identity.py)
- [game/scheduling/weekly.py](../../game/scheduling/weekly.py)
- [game/simulation/kernel.py](../../game/simulation/kernel.py)
- [game/utils/quarters.py](../../game/utils/quarters.py)
- [game/world_state/acquisition_validation.py](../../game/world_state/acquisition_validation.py)
- [game/world_state/booking_fingerprint.py](../../game/world_state/booking_fingerprint.py)
- [game/world_state/construction.py](../../game/world_state/construction.py)
- [game/world_state/demand_fingerprint.py](../../game/world_state/demand_fingerprint.py)
- [game/world_state/flight_transition_validation.py](../../game/world_state/flight_transition_validation.py)
- [game/world_state/fulfilment_validation.py](../../game/world_state/fulfilment_validation.py)
- [game/world_state/ids.py](../../game/world_state/ids.py)
- [game/world_state/payment_validation.py](../../game/world_state/payment_validation.py)
- [game/world_state/persistence.py](../../game/world_state/persistence.py)
- [game/world_state/planning_validation.py](../../game/world_state/planning_validation.py)
- [game/world_state/quarterly_construction.py](../../game/world_state/quarterly_construction.py)
- [game/world_state/quarterly_validation.py](../../game/world_state/quarterly_validation.py)
- [game/world_state/schema.py](../../game/world_state/schema.py)
- [game/world_state/stage1_scenario.py](../../game/world_state/stage1_scenario.py)
- [game/world_state/validation.py](../../game/world_state/validation.py)

Tests (12; new foundation cases and explicit latest/historical fixture boundaries):

- [tests/legacy_starter_fixture.py](../../tests/legacy_starter_fixture.py)
- [tests/test_advancement_performance.py](../../tests/test_advancement_performance.py)
- [tests/test_candidate_manifest_lookup.py](../../tests/test_candidate_manifest_lookup.py)
- [tests/test_flight_certification.py](../../tests/test_flight_certification.py)
- [tests/test_local_runtime_proofs.py](../../tests/test_local_runtime_proofs.py)
- [tests/test_operations_gui.py](../../tests/test_operations_gui.py)
- [tests/test_payment_certification.py](../../tests/test_payment_certification.py)
- [tests/test_quarterly_foundation.py](../../tests/test_quarterly_foundation.py)
- [tests/test_stage1_aircraft_acquisition.py](../../tests/test_stage1_aircraft_acquisition.py)
- [tests/test_stage1_terminal_harness.py](../../tests/test_stage1_terminal_harness.py)
- [tests/test_step6_maintenance.py](../../tests/test_step6_maintenance.py)
- [tests/test_step7_save_load.py](../../tests/test_step7_save_load.py)
