# Quarterly Backend Consumer Cutover — Stage 3E

Stage 3F successor: [isolated quarterly GUI](Quarterly%20Planning%20GUI.md) exposes
the existing new-career capability only through an explicit development entry,
certified planning/publication controls and detached session reads. Ordinary New
Game and legacy Load still do not enroll or migrate. General activation remains
Stage 3G; earlier statements about missing GUI describe this Stage 3E checkpoint.

## Approved PH 1.0 booking policy

User approval dated 2026-10-11 resolves the Stage 3E economics gate. This
contract supplements the [quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md)
and [passenger demand specification](../01%20Core%20Simulation/Passenger%20Demand%20Technical%20Specification.md).
Implementation certification and revision evidence are recorded in development status.

Preserve the absolute calendar lead profile: day 0 has 5%, days 1–6 have 15%,
days 7–29 have 35%, days 30–89 have 30%, and days 90–365 have 15%. Existing
deterministic allocation within inclusive buckets and integer residual rules
remain unchanged. Publication changes available supply, not these probabilities.
No passenger booking intent targets a departure more than 365 days ahead.
Earlier publication may establish commitments beyond that preference horizon.

Preserve shopping flexibility of ±3 UTC calendar days across publication
boundaries. Each selected offer must be valid, published and within the approved
booking horizon. Keep the passenger's original desired date. Unavailable intent
is terminal unsuccessful demand: no redistribution or renormalization of missing
probability mass, no backlog and no later recovery.

Preserve one directional market demand pool. Additional flights do not multiply
that pool. Existing fare sensitivity, outside option, deterministic capacity
contention and progressive daily accumulation remain authoritative. Quarterly
careers must use quarterly booking and operations exclusively; Booking365 must
not be an additional operational writer. Legacy careers retain their authority.
Retirement excludes new sales while retaining existing committed obligations;
there is no silent cancellation or passenger reassignment.

## Deferred long-term scheduling blueprints

The requested ability to manually save scheduling drafts beyond the quarterly
planning window is deferred. These are non-authoritative planning blueprints,
not published commitments. They cannot create bookings, operational flights or
aircraft obligations, or bypass quarterly publication. Exact editing and
application behavior requires future design. Stage 3E does not implement them.

## Isolated consumer authority and ownership

Stage 3E is implemented and certified as an isolated backend. Final certification
and revision evidence belong in [Current Development Status](Current%20Development%20Status.md).
Ordinary New Game and existing saves retain legacy operational authority. Only
`enable_quarterly_backend_for_testing` enrolls an untouched new-career candidate:
valid paused Schema 9, creation UTC unchanged, no legacy schedules/flights, sales,
operations, results or processed demand. Its initial empty bootstrap checkpoint
and successor remain intact. Load never invokes enrollment or converts a career.

[Canonical schema](Stage%201%20State%20Schema.md#quarterly-stage-3e-isolated-operational-authority)
defines `simulation.operational_authority = QUARTERLY_BACKEND_V1` and exact stored
publication references. The mode applies to the whole career, independently of
UI focus. Scheduling owns published supply and dispatch; Booking owns daily
shopping/allocation/reservations; Aircraft Operations owns actual fulfilment;
World State owns construction, validation and persistence; Simulation owns event
ordering and complete transaction publication. Existing Session serialization
remains the application boundary. No GUI mode selector or second state owner exists.

Quarterly Booking uses the existing directional Model 4 pool, absolute desired-date
allocator, Balanced fare/date/duration scores, outside option and deterministic
capacity contention. Its sole supply provider reads published quarterly slots.
Legacy dated-flight discovery and rolling publication are excluded in this mode;
legacy scheduling/publication writers reject it. The shared Booking engine is one
writer selected by the explicit mode, not an additional Booking365 sales pipeline.
Legacy careers preserve their previous provider, events, equations and saved rows.

## Derived supply, inventory and fixed sale lineage

Supply reuses Stage 3B's `QuarterlyOccurrenceReference` and pure dated interval
projection. The public 3B query retains its source gates and freshness checks.
Call-local indexes select published frequencies by immutable market/aircraft/service
IDs and explicit UTC date; pinned origin timezones/folds determine local dated keys.
Queries convert candidate local dates only for that day and selected published
period. Drafts, retired services, unusable connections/airports, invalid dates and
offers outside day 365 cannot become sales. Actual positioning is checked separately.

Runtime quarterly offers and inventory observations use the canonical
`service_id@origin-local-date#slot_number` key with frozen explicit publication
lineage; their legacy schedule lineage is null. Upon sale, one standard allocated
dated-flight ID becomes its proven bijective alias. Itineraries and lifecycle events
reference that allocated ID and the same published plan/revision/service/slot/date/
timestamp. No legacy schedule record is fabricated and no independent identity is
introduced. Commercial and timing facts trace exactly to that commitment.

Only selected sold occurrences and immediate operational work allocate dated rows.
Publication alone allocates none. A quarter may legitimately become fully sold and
therefore fully represented after real daily demand; this is not eager publication
materialization. Per-command alias/index reconstruction avoids scanning the complete
dated table for every selected offer. Remaining capacity comes from installed
published capacity minus confirmed Booking quantities. Inventory revisions persist;
remaining/booked capacity, unsold descriptors, caches and preparations do not.

The sale transaction retains fresh configuration, demand, inventory, finance and
event-cursor checks, plus exact quarterly dependency observations before and after
staging. Selected alias creation and its departure events are part of the same
isolated candidate; late source changes or failure discard all reservations,
finance, rows, events and allocations. Retry uses the unchanged deterministic inputs.
Paid fares debit cash/credit unflown liability; zero fares reserve seats without
ticket-sale journals. Accepted original desired dates never change.

## Execution, publication, recovery and persistence

An aircraft-owned strict `QUARTERLY_DISPATCH` selects its next published occurrence,
with at most eight local-date probes per frequency. Priority 90 materializes that
imminent row and its existing priority-100 departure event, then schedules the next
dispatch. Missing or stale future dispatch work is reconstructed from commitments;
duplicates consume normal lifecycle work without allocating a second occurrence.
Publication's existing equal-UTC barrier precedes all consumers, including older
priority-0 Booking events. New plan ownership enrolls the existing Stage 3D mandatory
publication frontier before processing; manual commitment is observed on reconciliation.

Flight execution delegates to the existing strict departure/completion pipeline.
The published aircraft assignment is required; actual origin, availability, installed
configuration, active arrival and complete neighboring-quarter chronology remain
checked. Existing commitments can already be inside their preparation block:
readiness uses actual completed/active work and creation UTC, not a fresh planning
edit at the current clock. Sparse sold rows do not replace complete published-chain
validation. Past mandatory occurrences stream from publication authority and must
already be executing/completed; deleting work and moving the clock cannot erase them.

Retirement blocks new sales and carry-forward while preserving committed execution,
sold reservations, flight numbers and history. Explicit published DEADHEAD movements
execute with no passengers/revenue; hypothetical positioning never becomes movement.
No automatic substitution, positioning, airport queue or disruption policy is added.
Unavailable execution blocks at the existing strict boundary, preserving its work.

Operations, manifest Booking witnesses, event payloads and finalized results retain
the exact quarterly lineage. Manifest fingerprints include it. Existing cash,
unflown liability, revenue, operating cost, maintenance and lifetime utilization
equations remain intact and settle once. Repeated completed fulfilment or restored
Booking checkpoints reuse history without new financial effects.

Quarterly flight inputs explicitly reject legacy shared certificates. Dispatcher
and publication are strict causal fences; strict/shared resolver requests use the
same strict quarterly flight work. Kernel handlers cannot alter career authority.
All four Stage 2 command gates, both world copies, indexes, chronology and final
freshness remain. Full validation and detached publication are not reduced.

Schema remains 9, with explicit optional versioned mode and conditional lineage;
absence preserves the legacy contract. Existing complete JSON snapshots include all
sold, operational and historical facts. Save preserves the previous valid file on
failure; Load validates a separate candidate, restores paused and rebuilds transient
indexes/handlers/work. No legacy save migration, historical replay or hidden session
authority is introduced.

## Certification and remaining limits

Measured on the frozen working tree, one aircraft/two daily frequencies, three
fresh-candidate samples per path, concurrently with full regression discovery.
Candidate setup/cloning is excluded; transaction-internal gates/copies are included.
Lookup and inventory rows are inner derived operations, not complete validated
consumer throughput. Save/load includes temporary filesystem setup and cleanup.
World bytes below are compact sorted JSON with default ASCII escaping, excluding
the save wrapper. Times are diagnostic observations, not pacing or gameplay inputs.

| Measured path | Median seconds | Min–max seconds | Resulting dated rows / Bookings / completed flights | World bytes |
| --- | ---: | --- | --- | ---: |
| Published UTC-day lookup, including call-local index | 0.000665 | 0.000618–0.000739 | 0 / 0 / 0 | 322015 |
| Public Stage 3B occurrence query, including source gates | 0.100147 | 0.096234–0.112395 | 0 / 0 / 0 | 322015 |
| Inventory index reconstruction and one access | 0.003045 | 0.002967–0.006146 | 180 / 1176 / 2 | 2426533 |
| Daily Booking event, including preparation/apply gates | 1.174940 | 1.138402–1.191650 | 180 / 1176 / 2 | 2426533 |
| Two dispatch/departure/completion movements | 0.453636 | 0.449402–0.454389 | 2 / 0 / 2 | 333635 |
| Publication boundary plus same-UTC Booking | 1.563442 | 1.510477–1.738625 | 172 / 837 / 0 | 1948954 |
| Save and separate paused Load | 0.874433 | 0.872747–0.881356 | 180 / 1176 / 2 | 2426533 |
| Two-day strict advancement | 4.130801 | 4.111673–4.338637 | 180 / 2341 / 4 | 4213639 |

The positive-demand fixture can sell every Q1 occurrence; those 180 rows are
supported by genuine reservations or completed work. Publication-only probes
retain zero dated rows. Neither these samples nor the zero-demand quarter traversal
certify large-fleet capacity, memory bounds across long histories or improvement
against a matched legacy benchmark. No runtime-capacity certification is claimed.

Focused cases cover published-only supply, demand conservation, unavailable mass,
capacity, fares/zero fares, retirement, fixed identity, deadheads/positioning,
departure/completion, exactly-once finance, early/manual/automatic publication,
committed skip, correction fences, year rollover, real operating-quarter continuity,
stale/missing events, save/load/rebind, deterministic retry, source mutation,
alias rejection, writer isolation and strict/shared equality. The public 3B resolver
and literal identity/interval expectations cross-check supply; shared timing/economic
formulas are reused rather than claimed as independent reimplementations.

Final verification: **50 focused cases PASS in 153.436s**, frozen complete discovery
**1,526 PASS in 2,013.471s** (prior 1,476 plus 50). All 317 source/test SHA-256
witnesses match before and after full discovery. Scoped compilation, documentation
links/headings, whitespace and self-review pass. Detailed commands, intermediate
regression scopes and actual revision evidence are recorded in development status.

The operating-quarter continuity fixture versions demand to zero to isolate real
aircraft movement/history over 91 days. Separate positive-demand and zero-fare cases
certify sales and settlement. Final full regression evidence is recorded in status
after verification. World/history gates and copies, complete
chronology, Booking validation and retained journals remain significant costs.
Small fixtures cannot certify fleet scalability or the parked 3G-C capacity milestone.

Stage 3F still needs mode-aware GUI/session integration and ownership-safe controls.
Stage 3G still needs explicit coherent activation and end-to-end release certification.
Ordinary quarterly gameplay remains dormant. Long-term blueprints, automatic
positioning, runway queues, new economics and unrelated marketplace bootstrap
issues are excluded. No new product-policy decision was required beyond AT-053.

## Exact Stage 3E working-tree file scope

36 files. Temporary test/probe artifacts and `.venv/` are excluded.

- [Data/Templates/template_reference.txt](../../Data/Templates/template_reference.txt)
- [Docs/01 Core Simulation/Passenger Demand Technical Specification.md](../../Docs/01%20Core%20Simulation/Passenger%20Demand%20Technical%20Specification.md)
- [Docs/01 Core Simulation/Quarterly Planning, Weekly Services & Bounded Booking Architecture.md](../../Docs/01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md)
- [Docs/03 Technical/Current Development Status.md](../../Docs/03%20Technical/Current%20Development%20Status.md)
- [Docs/03 Technical/Decision Register.md](../../Docs/03%20Technical/Decision%20Register.md)
- [Docs/03 Technical/Game State & Save Technical Specification.md](../../Docs/03%20Technical/Game%20State%20%26%20Save%20Technical%20Specification.md)
- [Docs/03 Technical/Quarterly Backend Consumer Cutover.md](../../Docs/03%20Technical/Quarterly%20Backend%20Consumer%20Cutover.md)
- [Docs/03 Technical/Quarterly Dependency Ownership and Command Contracts.md](../../Docs/03%20Technical/Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md)
- [Docs/03 Technical/Quarterly Operational Lineage.md](../../Docs/03%20Technical/Quarterly%20Operational%20Lineage.md)
- [Docs/03 Technical/Stage 1 State Schema.md](../../Docs/03%20Technical/Stage%201%20State%20Schema.md)
- [Docs/README.md](../../Docs/README.md)
- [game/aircraft_operations/fulfilment.py](../../game/aircraft_operations/fulfilment.py)
- [game/booking/allocation.py](../../game/booking/allocation.py)
- [game/booking/checkpoint.py](../../game/booking/checkpoint.py)
- [game/booking/shopping.py](../../game/booking/shopping.py)
- [game/demand/activation.py](../../game/demand/activation.py)
- [game/maintenance/routine.py](../../game/maintenance/routine.py)
- [game/scheduling/publication.py](../../game/scheduling/publication.py)
- [game/scheduling/quarterly_backend.py](../../game/scheduling/quarterly_backend.py)
- [game/scheduling/quarterly_commands.py](../../game/scheduling/quarterly_commands.py)
- [game/scheduling/quarterly_feasibility.py](../../game/scheduling/quarterly_feasibility.py)
- [game/scheduling/quarterly_occurrences.py](../../game/scheduling/quarterly_occurrences.py)
- [game/scheduling/quarterly_readiness.py](../../game/scheduling/quarterly_readiness.py)
- [game/scheduling/quarterly_supply.py](../../game/scheduling/quarterly_supply.py)
- [game/scheduling/timing.py](../../game/scheduling/timing.py)
- [game/simulation/kernel.py](../../game/simulation/kernel.py)
- [game/simulation/resolver.py](../../game/simulation/resolver.py)
- [game/world_state/booking_lineage_validation.py](../../game/world_state/booking_lineage_validation.py)
- [game/world_state/booking_validation.py](../../game/world_state/booking_validation.py)
- [game/world_state/flight_transition_validation.py](../../game/world_state/flight_transition_validation.py)
- [game/world_state/fulfilment_validation.py](../../game/world_state/fulfilment_validation.py)
- [game/world_state/planning_validation.py](../../game/world_state/planning_validation.py)
- [game/world_state/quarterly_consumers.py](../../game/world_state/quarterly_consumers.py)
- [game/world_state/validation.py](../../game/world_state/validation.py)
- [tests/test_quarterly_backend.py](../../tests/test_quarterly_backend.py)
- [tests/test_simulation_resolver.py](../../tests/test_simulation_resolver.py)
