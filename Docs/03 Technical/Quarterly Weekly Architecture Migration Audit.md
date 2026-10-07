# Quarterly / Weekly Architecture Migration Audit

**AUDIT / RECOMMENDATION — NOT IMPLEMENTED**

Audited 2026-10-07 at **c0a4191a615132615df699d49722d66a150d222f**.
Local HEAD and live origin/master matched. Only pre-existing untracked `.venv/`
was present. This is targeted source/dependency tracing and review of recorded
measurements, not new performance testing. No production, tests, schema, templates,
data, migration, optimization or Stage 3G-C implementation changed.

## Authority, method and conclusion

The [approved target](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md)
is future direction; [Schema 7](Stage%201%20State%20Schema.md) and its subordinate
[template](../../Data/Templates/template_reference.txt) remain current authority.
[AGENTS.md](../../AGENTS.md), folder reference, documentation indexes, status,
roadmap, decisions, updated domain contracts and 3G-A/B evidence were reviewed.
The current application path was traced; legacy menu stubs are not production
acquisition/scheduling authority. No diagnostic execution was needed.

**Recommended engine:** one persistent service with quarter-applicable weekly plan
versions; one dated identity shared by sales, execution and history; daily progressive
Booking over active-plus-next-quarter supply; maintained reconstructible indexes;
nearby operational records and exact events. Do not wrap a second recurrence model
around the old publisher or add independent booking-inventory authority.

**First coherent bridge:** reuse full dated rows within the bookable horizon because
current Booking/fulfilment/GUI/save joins require them. Then evidence-gate thinning
reconstructible plan facts and nearby departure queuing. This bridge is not a second
permanent timetable. Pure lazy operations without dated sales identity cannot preserve
current obligations. Broad horizon expansion must follow local-validation/index work,
because it can increase live state over today's five-week publication.

**3G-C recommendation: B + D — as part of quarterly migration, in a reduced/different
form.** Prove target dependency-local mutable boundaries before expanding supply;
do not first implement a comprehensive incremental validator for the outgoing
publication graph. Keep complete foreign-input/Save/Load gates and independent
strict recovery. Quarter stability does not make evolving Booking/history cheap.

All recommendations and stages require subsequent bounded approval. Audit completion
is not approval of schema fields, migration policy, lead-time mathematics or disruptions.

## Current path and authoritative boundaries

Source links and function names identify evidence at the audited baseline.

| Path | Actual flow and state |
| --- | --- |
| [Workspace](../../app/gui/weekly_workspace.py), [Builder](../../app/gui/schedule_builder.py) | `start_schedule`, Add/edit/drag/copy and review create transient intents. `_queue_schedule_publication` pauses and defers one atomic command to paint feedback, not engine preparation. |
| [Session](../../app/session.py) | `begin_scheduling` creates `WeeklyDraft`; `save_scheduling` calls `save_current`, marks management change and invalidates owned reads. UI selection does not own simulation. |
| [WeeklyDraft](../../game/scheduling/weekly.py) | Full validated snapshot/fingerprint, transient legs/undo/replacement IDs. `validate_current` replays intents against current world. `_candidate` stages canonical definitions/revisions, publishes live bounded window, then publishes a discarded configured-horizon preview. `save` commits only complete validated candidate. |
| [Feasibility](../../game/scheduling/planning_feasibility.py), [activation](../../game/scheduling/activation.py), [timing](../../game/scheduling/timing.py), [references](../../game/world_state/planning_reference.py) | Retained V1/V2 range, timing and reservation/location proof. Reachable draft gaps do not physically position aircraft; publication still requires explicit movement. |
| [Recurrence](../../game/scheduling/recurrence.py) | `rolling_horizon` current week + four future weeks; `ensure_publication_event` one priority-0 airline base-local Monday event; `pattern_edit_date` first safe unmaterialized home-local week, not quarter target. |
| [Publication](../../game/scheduling/publication.py) | `_stage_schedule_definition`/revision, `_expand_schedule`, `_publish_candidate`: local effective revisions become copied dated rows; key reconciliation is idempotent. Confirmed bookings and locked/completed work protect identity/history. `_continuity_conflicts` scans future flights grouped across all aircraft. |
| [Dated indexes](../../game/scheduling/indexes.py) | `rebuild_dated_flight_indexes` sorts all dated records, including history, into origin/market/airline/aircraft/schedule/key lookups; disposable, not persisted. |
| [Checkpoint](../../game/booking/checkpoint.py) | Preparation/process run daily demand → shopping → allocation → revision rechecks → persisted batches/itineraries, cash/liability journals, market/date outcomes and next UTC midnight event. Strict runtime fence. |
| [Shopping](../../game/booking/shopping.py), [allocation](../../game/booking/allocation.py), [Booking indexes](../../game/booking/indexes.py) | Rebuild authoritative supply; desired-date allocation and ±3 UTC-date search; deterministic fare/date/duration/outside choice and proportional capacity contention. Capacity consumption derives from confirmed Booking/itinerary authority; inventory revisions protect commit. |
| [Model 4](../../game/demand/model4.py), [activation](../../game/demand/activation.py) | Full-universe directional normalization, future-service and pack/availability gates, daily multiplier/rounding and persisted cohort witnesses. Supply does not renormalize base demand. |
| [Fulfilment](../../game/aircraft_operations/fulfilment.py) | Departure requires exact next event, manifest and actual parked aircraft at origin; freezes operation/configuration and queues Completion. Completion settles liability/revenue/cost once, parks aircraft, updates lifecycle and writes immutable result. |
| [Kernel](../../game/simulation/kernel.py), [shared resolver](../../game/simulation/shared_candidate.py) | Canonical due/priority/sequence/ID order, detached candidate and commit, local certified Payment/Departure/Completion proofs, full batch validation, strict fences and successful-prefix recovery. |
| [Pacing](../../game/simulation/pacing.py), [resolver](../../game/simulation/resolver.py) | Single owner, bounded safe steps, exact retained credit, suspension exclusion, pause/catch-up and overload drain; explicit Advance uses same resolver. |
| [Validation](../../game/world_state/validation.py), [planning](../../game/world_state/planning_validation.py), [recurrence](../../game/world_state/recurrence_validation.py) | Full JSON/ID/reference/domain graph; all schedule versions/flights and reservation adjacency, weekly-event completeness, Booking/finance/result lineage. Index hints do not waive authority checks. |
| [Persistence](../../game/world_state/persistence.py) | Deep-copied complete validated snapshot/integrity and atomic previous-file recovery; adjacent migration on a separate validated load candidate, restored paused. No pacing debt or disposable indexes saved. |

### Identity and weekly representation

No `flight_number`, `flight_code` or `flight_no` generator was found in traced
`game`/`app` Python paths. DAB001 is an architectural intention, not implemented
public-number authority. Schedule IDs are immutable and retained across revisions;
`_occurrence_record` uses `<schedule ID>@<origin-local date>`, then publication
allocates a globally unique dated-flight ID. A definition supports multiple weekdays
at one local departure time; multiple same-day frequencies require separate definitions.

Bookings reference itineraries containing dated-flight IDs and schedule/revision/key
lineage plus copied fare/time terms. Operations/results, manifests, journals, events
and operation revisions depend on dated identity. Service and occurrence are already
separate concepts, but service ownership is implicit. `WeeklyDraft._candidate` maps
`_replacement_ids[index]` to sorted new legs: reorder/insert/delete can associate an
old schedule ID with a different movement. That cannot implement lifetime DAB001.

Reuse local weekly day/time, route, assignment, fare/capacity and timing concepts;
adapt effective applicability to quarter versions. Introduce explicit stable internal
service relationship/display identity and stable slot discriminator where several
frequencies occur on one date. Service-plus-date alone is insufficient. Do not use
mutable departure time, list ordinal, airport code or registration as foreign keys.
Retired identity must remain unambiguous. Final storage/number allocation is unresolved.

### Horizon premise correction: three different windows

[Schema constants](../../game/world_state/schema.py) set
`DEFAULT_PUBLICATION_HORIZON_DAYS = 90`; [construction](../../game/world_state/construction.py)
uses it. Generic publication accepts a positive configurable limit and explicit
extension, and only materializes through caller target. Normal recurrence publishes
roughly 28–35 days (current week through fifth Sunday). **365 is Booking**, with
inclusive offsets 0..365, a 90..365 bucket, and ±3-day tolerance: potentially 366 UTC
dates. There is no mandated 365-day scheduling/publication default in production.
The audit prompt's premise differs from code; the approved target correctly calls
365 the Booking horizon and does not need silent amendment.

The scheduling limit bounds expansion, draft accepted dates, Earliest search and
virtual movement/continuity validation. `_base_movements` expands all active schedules
to that limit before filtering selected aircraft; `_candidate` full-publishes a
second discarded preview for recurrence/revision continuity. Arbitrary-future work
exists even at default 90, but not necessarily as live 365-day state.

Immediate deletion breaks construction/validation/saves, draft Add/Earliest/repeat,
rolling guard, manual/rotation/publication APIs and tests. Independently deleting
Booking 365 breaks configuration fingerprints, complete lead buckets, date allocation,
shopping/activation and historical witnesses. Replace responsibilities with period
applicability/proof and bounded sales availability first; never delete a sold future
operation just because its date exceeds the new horizon.

## Recorded performance and remaining global work

[3G-A](Runtime%20Scalability%20Forensic%20Audit.md) quiet days for 1/10/25/50 aircraft:
1.142/17.992/78.870/280.155s. Its 50 fixture had 6,800 dated rows, 7,819 Bookings and
itineraries each, 6,580 pending events, 482 history rows, 200 definitions and 401 due
events/day. These coupled fixtures are not independent complexity fits.

[3G-B](Runtime%20Local%20Certified%20Proofs.md) recorded 1.083/13.256/47.189/138.925s,
with exact full-world hashes/event vectors. At 50, proof 111.096→12.826s, validation
78.402s; 54 full gates and 104 outer copies remained. Witness pending/history visits
2,862,629→400. Native median callback 5.528→2.899s; Booking 13.895s/heartbeat 13.975s
remained poor. 621.9x remains below Ultra 1800x. These are earlier host measurements,
not new audit tests or predictions of target performance.

Source confirms `_shared_batch` entry clone, `_validate_batch` full gate and
`_replace_envelope` second clone. Booking/publication/expiry stay strict. Validator
walks include retained ID/JSON/reference/history; planning visits all revisions/flights
and sorts reservations; recurrence completeness calls rolling discovery by airline.
Candidate manifest lookup still builds/verifies relations from retained confirmed
sales per candidate. Calendar bounds alone cannot make retained history cheap.

## Occurrence materialization: dependencies and recommendation

A dated sales identity and inventory concurrency boundary are required before sale;
full copied operational object/event for every possible date is not intrinsically
required. Current APIs nevertheless require full dated rows.

| Alternative | Dependencies / determinism | Assessment |
| --- | --- | --- |
| A: all active + next quarter full rows | Reuses Booking, manifests, fulfilment, GUI and save joins; stable expansion order | Simplest first coherent bridge; up to 184 dates can increase live rows/events over five weeks. Local boundary/preparation gates first. |
| B: only booking horizon | Future passenger set equals A under target rule; retain airborne/history and non-passenger obligations | Not a distinct reduction unless A includes elapsed history. No deletion of committed or cross-quarter arrivals. |
| C: separate inventory from operational rows | All dated-ID witnesses/validators need migration and reconciliation | Reject two independent authorities. One compact occurrence commitment usable by both is acceptable. |
| D: lazy nearby operation | Requires persistent dated sales lineage, future sequence proof and deterministic frontier | Useful later reduction; generate unbooked/deadhead work too. Completion is already lazy. |
| E: query-derived occurrences | Good for uncommitted dates/previews; cannot invent history or sold terms | Avoid repeated expansion via maintained indexes; saves static copies but increases resolver responsibility. |
| F: hybrid, one identity | Immutable plan supplies facts; commitment stores obligations/exceptions; near operation locks actuals | Recommended end direction; thin existing occurrence role instead of adding parallel recurrence/inventory. |

Booking needs dated fare/capacity/lineage now. Departure needs actual position/state,
current manifest and exact due event; Completion starts only after Departure.
Future location/availability/turnaround/conflicts can use derived plan sequences;
actual state cannot. Finance requires sale and carriage lineage, not every empty future
row. GUI future queries may project dates with clear provenance; historical views
require retained results. Saves/replay preserve sold/locked/completed identity,
exceptions, deterministic IDs/order and any required execution frontier.

Recommend full rows only within target sales horizon as the first bridge, no distant
editable-quarter materialization. Later thin reconstructible facts and shorten
Departure queuing if measured benefit justifies risk. Do not discard zero-booking
flights: they still cost money and move aircraft. No static quarterly passenger fill.

## Booking flow, growth and horizon policy

Daily checkpoint resolves today's active directional cohorts, builds direct supply,
allocates desired dates, scores offers, contends for capacity, and commits batches/
itineraries/inventory revisions/cash and liability with checkpoint conservation.
`_model4_record` multiplies `base_daily_bookers` by existing approved daily modifiers
and deterministically rounds with seed/date/market witnesses; cohorts are processed
once daily/reused, not rerolled. Full valid destination universe includes unserved
markets. Capacity is excluded from structural activation. Added flights distribute
one daily pool, never manufacture per-flight demand.

`rebuild_direct_flight_shopping_indexes` rebuilds dated indexes even if caller hints
exist; it filters structure/horizon/actual airport dates. `rebuild_booking_indexes`
scans all Bookings/itineraries/checkpoints; Completion does not remove CONFIRMED sales.
Processed cohorts, checkpoint desired-date summaries, itinerary terms, sale references,
frozen manifest and result witnesses overlap but prove conservation/provenance.
They are not cosmetic duplicates safe to erase.

The proposed bound reduces fully populated 365-offset supply/date work, not lifetime
Booking/history growth. Current rolling publication is shorter already, and ordinarily
offers no flights months ahead from that pattern. Target must expose quarter dates
early enough for daily progressive sales. Modifiers remain Demand-owned, may be
directional/scoped, and preserve baseline → modifiers → effective demand → distribution;
no new modifier or stacking mathematics is recommended.

Illustrative 2027, UTC-date quarters and inclusive eligible departures; time-of-day
removes elapsed departures. UTC is recommended to align existing cohorts/shopping,
but timezone choice requires human approval; patterns remain airport-local/pinned tzdata.

| Current date | Horizon end | Maximum lead offset | Inclusive dates |
| --- | --- | ---: | ---: |
| January 1 | June 30 | 180 | 181 |
| February 15 | June 30 | 135 | 136 |
| March 1 | June 30 | 121 | 122 |
| March 31 | June 30 | 91 | 92 |
| April 1 | September 30 | 182 | 183 |

Across years/positions roughly 91–184 dates; leap years matter. Endpoint jumps one
quarter at rollover. Clip ±3-date search and exact current timestamp; a qualifying
departure may legitimately arrive after horizon/quarter end.

**Open economic decision:** current 15% spread over lead 90..365 cannot simply fit a
shorter date array: buckets must cover configured horizon and sum to one. Renormalize
permitted dates, retain excluded intent as unserved, or approve a new variable-horizon
policy? Each changes residual ranks, cash/load and months-ahead access. Version rules,
preserve prior cohorts, and test progressive accumulation/conservation/capacity dilution.
No mathematics chosen here.

**Open product tension:** next quarter is bookable but editable in months 1–2.
Current `_booked_change_conflict` rejects protected fact/lineage changes with
`BOOKED_FLIGHT_CHANGE_REQUIRES_DISRUPTION_WORKFLOW`. Limit edits/retain sold terms,
or approve change/refund/reaccommodation? Sealing in month 3 does not answer earlier
sales. Also approve initial-career bootstrap, no-change carry-forward, retirement and
strategic exceptions; an active-quarter edit ban changes today's immediate Add/stop.
No approved intent is silently changed.

Affected evidence/tests: [shopping](../../tests/test_stage1_booking_shopping.py)
final inclusive horizon/±3 and desired-date allocation;
[foundation](../../tests/test_stage1_booking_foundation.py) default 365/fingerprint;
[allocation](../../tests/test_stage1_booking_allocation.py) ranks/overflow/capacity;
[checkpoint](../../tests/test_stage1_booking_checkpoint.py) idempotence/finance;
[publication](../../tests/test_stage1_flight_publication.py) bounded expansion/DST/
revision protection. GUI recurrence descriptions, save witnesses, activation and event
safety also migrate. These files were inspected, not modified or executed.

## Quarter sealing, rollover and preparation

Minimum authority: service identity, accepted weekly movements/version/applicability,
assignment/fare/capacity/timing references, delivery commitments and sold/operational
exceptions. Active quarter/eligible edit target derive from simulation date: plus one
quarter in months 1–2, plus two in month 3, with year carry. October/November→Q1 next
year; December→Q2 next year. Separate mutable copies of every lifecycle label are
unnecessary. Calendar-derived closure can prohibit edits without a persisted enum,
but accepted frozen plan content/version and non-derived default selection must
survive load. Readiness is derived, not authority.

| Case | Required target behavior |
| --- | --- |
| Load in month 3 | Derive target from saved time; retain same frozen next-quarter version/sales; rebuild indexes, no offline outcomes. |
| No changes / player inactivity | Approve carry-forward/empty/retirement rule; persist selected accepted content if not purely derivable. Do not silently design a network. |
| One/multiple quarter Advance | Process every required seal/activation/sales opening before affected daily Booking/Departure; stable order, not final-quarter-only activation. |
| Partial preparation | Restart/reconstruct disposable work; verify readiness/version before activation. Catch up under bounded visible runtime policy, never stale or incomplete supply/frame-dependent fallback. |
| Rollover paused | Paused clock cannot cross itself. Explicit Advance can; UI paint is not transition authority. Load at exact boundary respects committed prefix. |
| Overload recovery | Quarter work remains owed chronological work; no bypass/drain-credit loss/early activation. |
| Weekly/quarter edges | Last old movement→first new, overnight arrivals, weekly wrap, availability/preparation, DST/fold/gap and airport active dates all require proof. |

Sealing cannot validate only one prototype week: airport-local offsets/DST/delivery/
closures vary across dates. Preparation should be deterministic resumable derived
work on the existing single owner, with version checks. No thread is required by
this evidence. Current runtime forbids a mutable private candidate across returns;
use detached derived scratch or explicitly approve a changed transaction contract.
Boundary clock/event orchestration stays `game/simulation`; plan behavior Scheduling;
commercial indexes Booking; persistent construction/validation/save `game/world_state`.
Package-local operations do not become `game/utils` merely because multiple callers
need them.

### Maintained indexes: explicit correctness contracts

All recommended indexes reconstruct after load by default. Persist only under a
later measured benefit and exact version-integrity contract; none replaces authority.

| Derived value / owner | Source of truth | Invalidation | Rebuild | Persist? | Benefit / risk |
| --- | --- | --- | --- | --- | --- |
| Market/date eligible supply / Booking | Service versions, commitments, route/airport/pack policy, exceptions, simulation window | Plan/route/airport/pack/status/horizon transition; inventory separate | Stable bounded expansion with authoritative eligibility and independent reconstruction oracle | Reconstruct | Avoid all-flight/history discovery; omissions/resurrected cancellations change demand/choice. |
| Aircraft ordered reservations / Scheduling | Weekly slots/timing, quarter edges, actual operation, delivery/contract | Assignment/plan/configuration/timing/availability/expiry/deviation | Per-aircraft sequence including wrap, boundaries and date-specific cases | Reconstruct | Follow affected aircraft; stale predecessor teleports or overlaps. |
| Occurrence Booking IDs/counts / Booking | Confirmed Booking/itinerary and approved adjustment facts | Atomic sale/refund/status/itinerary change | Full lineage oracle at trust entry, then committed deltas | Reconstruct | Local manifests, no lifetime scan per batch; missing inverse relation causes oversell/wrong settlement. Count not second reservation authority. |
| Service/plan dependency map / Scheduling | Immutable IDs, versions, route/aircraft/airport/references | Relevant version/exception; inverse remove/add together | Verified forward+inverse graph on load | Reconstruct | C closure checks; leaving old reverse edges is unsafe. |
| Route timing / Scheduling | Retained timing/performance witnesses and aircraft config | Model/config/endpoint/reference policy version | Existing snapshot/predicate | Reconstruct; witness persists | Reuse stable inputs; never reinterpret history using today's catalog/taxi data. |
| Demand baseline/normalization / Demand | Model/config/revision contexts, universe and country/airport/pack inputs | Relevant demand/universe/availability/reference change; modifier scope separate | Existing `rebuild_model4_indexes` full-universe semantics | Reconstruct | Avoid repeated stable derivation; wrong key rerolls cohorts or normalizes only served markets. |
| Historical service/date/airline reads / domain projections | Immutable results/sale journals/events/plan versions | Append/partition binding | Build verified date/service index, detached projections | Reconstruct | Requested pages rather than H scans; projections cannot invent actual history. |

`_OwnedReadViews` caches eight detached pages within a source epoch and invalidates
on progress; `CandidateManifestLookup` is protected candidate-local, not a cross-commit
simulation index. Reusing either across commits without new ownership/invalidation
is unsafe. Stable plan indexes may outlive routine operations only when exceptions
and all inverse/time-sensitive dependencies are maintained separately.

## Future aircraft planning and finance

[Purchase](../../game/aircraft_market/acquisition.py) validates fresh preview,
[fleet entry](../../game/fleet_management/acquisition.py) creates aircraft and
registration, purchase posts cash/asset journal, then validates/commits. Ownership,
home/configuration and current delivery location exist together at commit, immediately
PARKED. The temporary registration string `PENDING` is not an undelivered lifecycle.
[Marketplace](../../game/aircraft_market/step5.py) `accept_lease`/used purchase also
enter immediately; lease remains lessor-owned under contract. `confirmed_contract_horizon`
follows approved successors, with expiry protections. Manufacturer order menu stubs
are not authoritative future delivery.

`WeeklyDraft` accepts PARKED/IN_FLIGHT and projects a single active arrival; publication
starts continuity at current/projected location. Departure requires actual parked
origin. No future delivery not-before UTC exists. Adding an undelivered aircraft to
parked fleet would teleport it.

Recommend accepted acquisition/availability facts: stable aircraft relationship,
exact available UTC and delivery location, model/configuration and ownership/contract
provenance. Registration allocation timing is secondary; it never owns joins. Project
future planning from that anchor, with preparation after valid availability, range/
airport/positioning/turnaround and contract end respected. Only delivery transition
changes physical state/location; Departure rechecks reality. Guaranteed versus
estimated time, delays/obligations, payment start/cancellation and ownership before
arrival require approval. Test May 10 mid-quarter availability, equal-time preparation,
wrong location, delay and lease expiry; no fields added now.

Booking [checkpoint](../../game/booking/checkpoint.py) posts cash and category-normal
unflown liability, balanced signed journal, paid sale references; zero fare reserves
capacity without journal. [Completion](../../game/aircraft_operations/fulfilment.py)
reduces liability, recognizes carried passenger fare and pays costs once. Bounded
sales change cash opportunities/timing, not accounting policy. Preserve all previously
sold out-of-horizon obligations; no retroactive refund/revenue recognition. Cancellation/
refund system is not yet implemented and is relevant to editable sold plans. No new
full accounting/deferred-revenue redesign recommended.

## History, queue, validation and transactions

Completed dated flights, CONFIRMED sale batches/itineraries, checkpoints/desired-date
outcomes, processed cohorts, transactions, results and resolved events remain.
No quarter-plan collection exists. Completion deletes active operation only; kernel
moves resolved event to history. Dated/Booking index rebuilds, candidate manifest
lookup, full validation/copy, recent Finance sorting and operational projections
still touch historical authority. One aged aircraft can be expensive.

Recommend immutable historical partition/index first, not deletion or lossy passenger
totals. Later compaction must preserve GUI/finance/replay/statistics/service lifetime
lineage and exact witnesses. A partition still deep-copied every batch is not cold.
Physical sharing requires immutable ownership and full snapshot inclusion. Do not
delete sale/cohort provenance needed for idempotence/conservation.

Publication queues Departure priority 100 for all eligible materialized occurrences;
revision advances owner revision leaving prior events stale. Departure creates
Completion; there is no distant arrival queue to remove. Booking keeps one next
priority 0 midnight event, recurrence one next weekly publication per airline.
Marketplace payments/expiry include legitimate future contractual events independent
of quarters and must remain.

Near-operation departure queuing could shrink pending from sales O to a short window
plus boundary/contracts. Needs deterministic frontier/successor and ordering proof:
later allocation changes event IDs/sequences and same-time publication-versus-Booking
order. Never let Booking/Advance pass ungenerated due operations. Preserve exact UTC,
priority/sequence, stale handling, retry/strict successful prefix, rollback, cap 8,
generation 100, processed 10000, overload/drains. Full byte equality remains oracle
for unchanged stages; approved representation changes require versioned semantic
sales/results/aircraft/event-order comparisons, not exclusions hiding causal differences.

| Validation point | Target proof |
| --- | --- |
| Edit | Ownership/IDs, slot uniqueness, route/airport/range/timing, delivery/expiry, selected aircraft chronology/quarter edges and sold obligations; dependency closure. |
| Seal | Accepted version frozen; complete period/date-specific legality and adjacent-period continuity, supply completeness. |
| Runtime | Exact selected event, actual state/location, inventory/manifest/finance lineage, exception dependencies and local outputs/aliases/inverse refs. |
| Rollover | Accepted version/window, readiness version and last-to-first obligations, deterministic boundary order, no history rewrite. |
| External input/command, Load, Save | Complete schema/JSON/reference graph and exact snapshot; independent index reconstruction. |

Incremental validation remains necessary for mutable Booking/operations/finance/event
closure. A Completion changes aircraft, flight/result, accounts/journal, IDs/revisions
and event history; sales change cohorts/checkpoint, batches/itineraries, inventory,
cash/liability and successor. Stable plan legality is reusable only until relevant
version/exception changes. Diversion/substitution/delivery delay/airport changes
invalidate affected operational proofs. Changed-row-only validation misses inverse
and clock-sensitive edges. Keep 3G-B certified local witnesses/selection, but they
are not a complete incremental validator today.

Two outer world copies enforce no leaks, detached atomic commit and rollback.
Future owned deltas can share truly immutable sealed plans/history under read
capabilities, validate complete closure, then atomically publish. A “sealed” mutable
dict is insufficient. Kernel/application/domain transaction conventions must migrate
together. No partial sale/departure/settlement/rollover is visible. Save includes all
immutable shares; strict recovery remains independent. Bounded Booking preparation
may retain detached derived scratch with source recheck, never partial visible sales
or outcomes decided by frame time.

## Simplification table

REMOVE/REPLACE are eventual recommendations, not immediate safe deletion.

| Mechanism | Current purpose | Target / classification | Reason | Migration risk |
| --- | --- | --- | --- | --- |
| Builder draft | World snapshot, legs/undo/current-week intents | ADAPT quarter/service edit draft | Retain understandable weekly tooling, remove world-sized coupling | HIGH stale saves/positional reassignment |
| Recurrence definitions | Weekly effective revisions | ADAPT weekly slots/quarter versions | Reuse local timing/assignment/fare, no second recurrence layer | MEDIUM identity/applicability |
| Recurrence expansion | Arbitrary configured-date loops/reconciliation | REPLACE bounded period projection/commitments | No endless parallel publisher | HIGH DST/sales/duplicates |
| 365-day publication horizon | Not current mandate; scheduling 90/Booking 365 | REMOVE arbitrary publication limit after replacement | Period policy owns range | HIGH saves/APIs/tests |
| Dated future flights | Copied supply/inventory token/event owner | ADAPT bounded bridge then compact unified commitments | Dated sale identity needed, distant full operation not | HIGH foreign keys |
| Flight-number generation | No canonical public generator found | REPLACE absence with service numbering contract | DAB001 not dated ID | MEDIUM reuse/allocation |
| Occurrence IDs | Globally unique joins, schedule@date | KEEP ID; ADAPT slot discriminator | Multi-frequency uniqueness/history | HIGH collisions/remap |
| Pending departures | All published supply queued | ADAPT near operational window later | Booking window need not equal queue | HIGH ordering/retry |
| Pending arrivals | Created at Departure | KEEP | Already actual-airborne bounded | LOW if unchanged |
| Daily checkpoint | Demand/choice/sales/cash recurrence | KEEP; ADAPT window/index/preparation | Progressive economics | HIGH rounding/atomicity |
| Eligibility discovery | All dated supply rebuilt | REPLACE maintained trusted relations | Avoid history/global scan | HIGH invalidation |
| Booking/itineraries | Aggregate sale/provenance | KEEP obligations; ADAPT lineage/partition | Not static quarterly allocation | HIGH finance/replay |
| Full validation | Trust entry and repeated final gates | KEEP external/save/load; REPLACE routine only after proof | Quarter stability not sufficient | HIGH inverse/time edges |
| Dependency-local proofs | Certified Payment/flight exactness | KEEP / ADAPT footprint | Measured benefit, reusable induction | MEDIUM new contracts |
| Sealed selection 3G-B | Handler/candidate canonical heap proof | KEEP | Still needed after quarters | MEDIUM allocation policy |
| Whole-world copies | Detached rollback/commit | REPLACE later owned deltas/immutable shares | Stable/history facts need no writable clone | HIGH aliases/recovery |
| Availability projection | Current/airborne + planned chronology | ADAPT future anchor/quarter edges | Future planning not present-location-only | HIGH teleportation |
| Acquisition/delivery | Immediate fleet entry | ADAPT under explicit availability contract | Missing not-before time | HIGH ownership/finance |
| Save/load | Exact world/adjacent migrations | KEEP safety; ADAPT representation | No silently broken saves | HIGH obligations |
| Historical flight storage | Full dated + result witnesses | ADAPT partition/index; UNCERTAIN compaction | Preserve exact history, remove hot scans | HIGH replay/report joins |
| GUI schedules | Local week, recurrence/publish modes | ADAPT active versus planning views | Explicit effective/sealed quarter | MEDIUM provenance |

## Complexity We Can Potentially Delete

1. `recurrence.py` rolling-four-weeks conveyor and `recurrence_validation.py`
   Monday completeness exist to maintain publication. Quarter sales-window opening/
   materialization frontier replaces responsibility. Migrate Booking availability,
   event registry/save contracts and boundary tests first; old policy writers/events
   retire only after converted saves no longer depend on them.
2. `WeeklyDraft._base_movements` globally expands active definitions before aircraft
   filtering; `_candidate` full-publishes discarded preview. Per-aircraft period and
   adjacent-quarter/date exception proof replaces it. Migrate Add/Earliest/save/wrap/
   DST/positioning first; removing preview without proof is unsafe.
3. `_publish_candidate` arbitrary unlocked future rewrite/supersession/stale-event
   reconciliation. Frozen accepted strategic versions and stable commitments reduce
   active rewrites. Migrate editable sold-plan policy/operational exceptions first;
   future editable versions and cancellation witnesses still need explicit semantics.
4. `_occurrence_record` copies static endpoints/aircraft/timing/fare/capacity facts.
   Accepted immutable plan resolver supplies uncommitted facts; sold terms/actual
   exceptions remain authority. Migrate shopping/validators/manifests/GUI/save to one
   resolver before thinning. Historical copied terms cannot be reinterpreted.
5. `_reconcile_schema4_departure_events` distant queue entries and global reconciliation.
   Near operational frontier replaces them after order/IDs/retry/save proofs. Completion
   generation is already lazy; do not rewrite it for symmetry.
6. Index builders/Finance/operational reads repeatedly rediscover historical inverse
   relations. Maintained verified indexes and immutable partitions replace scans, not
   history. Mutation ownership/load rebuild/inverse closure come first.
7. Draft `_bytes` full-world fingerprint, `_base` world copy and positional replacement.
   Explicit service/quarter/dependency versions replace them only after an authoritative
   target edit boundary exists. Preserve current-world stale revalidation and rejection.

None is safe to delete now. Compatibility should be one-way conversion/run-off with
an explicit sunset, not permanent old/new timetable writers.

## Recommended target state and persistence

| Class | Minimum role / assessment |
| --- | --- |
| AUTHORITATIVE | MUST PERSIST stable service/display identity, accepted weekly slots/plan applicability/version, aircraft/fare/capacity/timing meaning; sale/itinerary obligations and journals, exceptions, actual aircraft/operations/results, deterministic IDs/event authority. |
| FUTURE AVAILABILITY | MUST PERSIST once introduced: accepted aircraft/contract relation, exact not-before time/location, model/configuration and ownership provenance. No fictitious current physical position. |
| PERIOD CONTROL | DERIVED active quarter/edit target/calendar closure/bookable endpoint from simulation time and policy. LIKELY PERSIST accepted frozen/default-selected version when not purely derived. UNCERTAIN explicit seal/activation witness and near-event frontier until order/retry specified. |
| DERIVED / CACHED | RECONSTRUCT supply/reservation/inverse dependency/count/demand/GUI indexes and preparation readiness. Not a replacement sale authority. |
| RUNTIME-MATERIALIZED | Full bridge dated rows then compact commitment/near operation. MUST PERSIST sold identity/revisions, exceptions, manifest lock, active operation and due order/frontier wherever not reproducible. Unsold unexecuted projections reconstruct. |
| HISTORICAL | MUST PERSIST exact service/quarter/version attribution, dated actual results, paid/zero-fare lineage, checkpoints/cohorts, journals/events. Compaction format UNCERTAIN; no loss authorized. |

```text
accepted acquisition availability + route/airport/model authority
                           ↓
stable service → quarter weekly plan/version → deterministic dated projection
                           ↓                         ↓
                 aircraft reservations       eligible market/date supply
                                                     ↓
base daily demand → approved modifiers → daily choice / capacity allocation
                                                     ↓
                                 one dated commitment + Booking + sale journal
                                                     ↓
                         nearby Departure → locked operation → Completion
                                                     ↓
                         immutable result / recognized revenue / history
```

The smallest authoritative future plan is identity, weekly slot intent, period/version
and domain references, not a list of all far-future events. One accepted plan owns
strategy; one dated commitment owns commercial exceptions; operation/result owns
actuals. No final schema fields/enums/storage chosen. Changing persistent authority
later requires canonical schema first, then template and explicit migration/tests.

## GUI and Advance dependencies

[Workspace](../../app/gui/weekly_workspace.py) selects current/home-local week,
one-off/until/continuous recurrence, first editable week after published reservations,
and four-week bookability descriptions. Target needs active quarter visible/read-only,
eligible future quarter editable, effective date/month 3/sealed status explicit,
stable service selection and valid future-aircraft choice. Replace arbitrary
repeat-until strategy with quarter applicability; legitimate operational exception
commands cannot be an active-plan-edit bypass.

[Management projection](../../game/aircraft_operations/management_projection.py)
and [owned reads](../../app/owned_reads.py) feed Flights/Bookings from committed dated
rows; date/week queries still loop whole airline dated history. Matrix differentiates
equal-time occurrences by immutable IDs; preserve separate capacity when service
has multiple slots. Show service/version/projection provenance, never manufacture
historical flights. Fleet actual position/utilization must distinguish undelivered
planning from physical aircraft. Finance preserves cash versus recognized revenue.
Dashboard period context derives from clock; cannot become authority. Existing finite
table/lifecycle safeguards remain useful. No GUI redesign/mockup implemented.

Continuous runtime stays primary, open-app only, no offline progress, paused load and
hard management/save pause. `begin_advance_to` hard-pauses/drains and starts cooperative
shared resolution; `advance_tick` commits safe prefixes, with whole-request limits.
`_complete_target` validates final gap. Neither path skips daily Booking/operations.

SAFE SIMPLIFICATIONS FOR LATER IMPLEMENTATION: bounded supply, per-aircraft plan proof,
maintained indexes, immutable accepted-plan proof reuse. FUTURE AGGREGATION REQUIRING
PROOF: batching/skipping weeks/quarters. Sales/inventory/actual aircraft/finance/market
events interact; prove equivalent daily residual ties, order/IDs and exceptions before
any analytical shortcut. Long Advance must process every meaningful calendar/cohort
boundary and honor retry limits; no cap increases or approximation implied here.

## Scalability model

A aircraft; S weekly services/slots; M active markets; O materialized occurrences;
B active inventory/sale batches; H historical state; E due events; C affected closure.
Approximate source-tracing costs, not independent formal bounds or speed predictions;
sorts, reference fanout and multi-round choice add factors.

| Operation | Current scaling | Intended target |
| --- | --- | --- |
| Draft/save | Global S×configured days + O/H enumeration, discarded expansion, full gate/copies | Selected aircraft slots and C/date/quarter edges; complete period acceptance/seal proof |
| Service discovery | Sorted O + historical dated rows then M filtering | Maintained market/date relation; C for window/exception updates, relevant offers visited |
| Daily allocation | M×lead-day/offer work, B+H index rebuild, contention rounds | M×bounded dates/offers + affected B; exact daily choice remains |
| Flight batch | E local proofs plus repeated O(A+S+O+B+H) gates/copies | E×C mutable validation/deltas and local indexed manifest; full trust gates separately |
| Queue | Heap over published O + obligations, rebuilt at entry | Near operation/boundary/contracts; logarithmic selection in pending size |
| Rollover | Absent | Prepare new bounded supply/closure, validated activation; not claimed constant cost |
| History read | O(H+O) scan/sort at fresh epoch | Indexed requested rows; rebuild/save still total-state work |
| Save/load | Full clone/validate/JSON/migration | Still exact total persisted state; fewer static future copies possible, no H-free save claim |

Illustrative four sectors/day/aircraft gives ~8A due flight events/day. Fully
materialized 91–184-date quarter horizon is ~364–736 rows/aircraft versus up to 140
for five weeks or 1,464 for inclusive offsets 0..365. Approximate arithmetic only;
elapsed history/exception/frequency differences excluded. Daily Booking can create
many batches per occurrence.

| A | Due flight events/day | Quarter-window full rows |
| ---: | ---: | ---: |
| 1 | 8 | 364–736 |
| 10 | 80 | 3,640–7,360 |
| 25 | 200 | 9,100–18,400 |
| 50 | 400 | 18, 200–36,800 |
| 100 | 800 | 36,400–73,600 |
| 250 | 2,000 | 91,000–184,000 |
| 500 | 4,000 | 182,000–368,000 |
| 1000 | 8,000 | 364,000–736,000 |

At 1000, daily events plus contracts approach existing 10,000 whole-request Advance
limit; longer jumps exceed it. Preserve explicit retry/limit semantics, no uninterrupted
jump promise. AI adds markets/strategic changes; quarter strategic AI may help later,
not implemented here. Bounding a fully populated 365-day future roughly halves supply,
but can multiply current five-week live supply. Local mutable boundaries and hot/cold
separation are necessary beyond 50. No measured improvement from this design claimed.
Core planning/demand/time remain country-generic; PH 1.0 stays content scope, no new
countries/AI or airport-code branches.

## Risk register

| Risk | Rank | Mitigation / later verification |
| --- | --- | --- |
| Booking determinism / lead reweighting | HIGH | Approved versioned policy; unchanged-stage hash oracle, new calendar/residual/conservation witnesses; cross-speed/Advance/reload. |
| Lost sold future bookings | HIGH | Retain every obligation/value, legacy run-off ledger; months-ahead fill and out-of-horizon commitments. |
| Service ambiguity / duplicate occurrences | HIGH | Stable service/slot/version keys and retirement; same-day frequencies, reorder/delete and idempotent materialization tests. |
| Premature aircraft / schedule discontinuity | HIGH | Exact availability/preparation/location/expiry/wrap proof; Departure physical check; equal-time/wrong-origin/delay tests. |
| Rollover gaps / stale indexes | HIGH | Deterministic priorities/readiness version; inverse reconstruction oracle; interrupted load/preparation, no-change/leap/DST/multi-quarter tests. |
| Save corruption / history replay loss | HIGH | Separate load candidate/previous-file recovery; paid/zero-fare/locked/retired exact lineage; unsupported conversion fails closed. |
| Operational exception conflict | HIGH | Explicit authority, no active strategic rewrite; disruption/recovery scope approved before tests/implementation. |
| Finance timing / partial sale | HIGH | Cash/liability/recognition once; zero fare, negative cash and failures; no visible partial checkpoint. |
| Ordering/aliases/rollback | HIGH | Same-time sequence, stale/generated limits, strict prefix recovery, forced mid-transaction failure/protected mutation tests. |
| Long Advance differs | HIGH | Semantic compare at each calendar/cohort/flight boundary; no aggregation assumption. |
| Quarter expansion worsens callbacks | HIGH | Local/delta/index foundation first, count/memory/checkpoint worst-callback gates; full-row bridge rollback. |
| GUI shows projection as actual | MEDIUM | Explicit active/planning/sealed/actual provenance, separate occurrence capacity/history tests. |
| Calendar/country explanation | MEDIUM | Approve UTC/local semantics; non-PH zones, year carry and pack gates. |
| Duplicate derived lifecycle enums | LOW | Derive target/quarter/readiness from time/versions; do not duplicate authority. |

## Proposed migration stages and rollback

Proposals only; each needs bounded approval. Compatibility is one-way conversion/
run-off with a sunset, never permanent dual scheduling writers.

| Stage | Goal / systems / prerequisite | Behavior / schema-save impact | Tests / benchmark | Rollback / removable machinery |
| --- | --- | --- | --- | --- |
| 0: product contracts | Calendar/bootstrap/carry-forward, sold-edit policy, identity grouping and horizon mathematics; domain specs | Docs only; approve minimum authority before schema/template | Review exact date/old-obligation examples; no benchmark | Audited baseline; nothing removed |
| 1: target authority/compatibility boundary | Service-slot/quarter version/obligation lineage; world_state + Scheduling; stage 0 | Explicit new versioned state and adjacent save conversion later; retain old sold/locked/history meaning; approve legacy run-off or fail-closed conversion | ID/reorder/frequency/DST/old-save round trips and ledger compare; 1/10 size/load probes | Original Schema 7/previous valid files; no dual writers; obsolete arbitrary writes restricted only under approved policy |
| 2: local foundation | Trusted indexes, inverse closure, period proof, owned mutable boundary/immutable shares; runtime/world_state/domains; stage 1 | Exact supported behavior, complete external/save/load gates; no broad supply expansion | Strict closure/alias/failure/recovery/event safety; aged 1 and 10/25 short probes, copies/gates/history touches | Strict fallback and pre-stage saves; remove target-plan repeated proof/global rediscovery only after exact proof; reduced 3G-C |
| 3: quarter strategy/activation | Target/seal/defaults/aircraft edges/GUI context; stages 0–2 | Approved strategic timing change; persist accepted versions/witness if needed; preserve sold terms | Months 1/2/3/year/leap/DST/bootstrap/no changes/paused/overload/multi-quarter tests; bounded rollover probes | Converted snapshots; remove positional replacement/arbitrary effective-week target/full preview for target plans |
| 4: bounded progressive sales | New date policy/supply/preparation; Scheduling/Booking/Demand/Finance/GUI; stage 3 plus sold-edit/lead approval | Active+next sales and daily cash unchanged; full dated-row bridge with IDs; old commitments run off | Months-ahead accumulation, endpoint/±3/conservation/dilution/capacity/finance/reload; 1/10/25 checkpoint then 50 practical probes | Versioned prior window/policy; retire rolling-four-week writer/events and arbitrary extension after consumers/saves migrate |
| 5: future aircraft | Committed availability/delivery and projections; delivery policy + target plans | Actual delayed delivery gameplay; explicit persistent contract amendment | Order→plan→delivery→Departure, expiry/payment start/not-before/location/delay/load; small probes | Pre-delivery-stage saves; remove present-location-only planning gate, never Departure physical check |
| 6: thin occurrences/queue | Compact unified commitment, projected unsold supply, nearby departures; stable target sales plus measured cost | Representation/event allocation change; explicit frontier/save proof | IDs/same-time/retry/load/unbooked/deadhead, cross-speed/Advance semantic oracle; pending/O/B/memory/callback, 50/100 short probes | Full bounded bridge until proven; remove distant departures/static unsold copies/reconciliation, not sale identity |
| 7: history/certification | Immutable cold graph/index, evidence-gated compaction; all history consumers migrated | Exact approved save/history contract, no result loss | Old/retired/paid/zero-fare/finance/GUI/replay; aged probes/save-load; final 50 Ultra/native gate, cautious 100/250+ | Pre-compaction saves; remove hot historical scans/copies only after every reader/validator migrates |

Stage 2 deliberately precedes two-quarter growth; it is not instruction to start old
3G-C. Stages can split for review, not combine into an untestable rewrite. Stage 6 and
compaction are optional if measured benefit does not justify risk. No AI/country/
analytical skipping implementation stage. Later substantive source work follows
AGENTS.md focused/full-suite requirements; this audit runs no gameplay suite.

## 3G-C conclusion and implementation measurements

Choose **B (part of migration) + D (reduced/different form)**. Evidence: repeated
full validation 78.402s remains largest measured category in the 50-aircraft one-day profile after 3G-B; two outer
copies and strict Booking fences remain. Enlarging live future rows first risks worse
stalls. But incrementalizing all old recurrence/publication rules before replacing
them invests in disappearing dependencies. Specify target mutable closure/immutable
plan proof, then prove on converted representative inputs before horizon expansion.
No approval to implement 3G-C follows from this conclusion; full trust-entry/save/load
validation, strict recovery and causal invariants remain.

Reuse [forensic tooling](../../tests/profile_runtime_forensics.py),
[capacity tooling](../../tests/certify_runtime_capacity.py) and 3G-A/B native phase-filtered
heartbeat/OS methodology during later implementation. Separate exclusive/inclusive
categories; no production instrumentation or measurement run in this audit.

- Throughput/day, safe-step/worst callback, p50/p95/sample count, heartbeat starvation,
  active OS response, exact credit/backlog/drain/overload/recovery; ratios/cap visible.
- Pending events by type, materialized/projected/sold/locked dates, active inventory
  and retained batches/cohorts/results/history; hot historical touches and C/fanout.
- Complete/local validation counts, copy counts/bytes if measurable, GC/peak memory;
  edit/seal/preparation/rollover, Booking checkpoint/manifest/settlement costs.
- Save bytes and validation/encoding/write, load/migration/reconstruction time,
  paused exact reload and previous valid file protection.
- Unchanged-stage complete hashes/event vectors; approved representation/gameplay
  stages use versioned semantic cash/liability/sales/results/actual-aircraft/order
  witnesses without convenient exclusions concealing divergence.

Use 1/10 fresh+aged bounded probes per stage, 25/50 for affected paths once safe.
Include one calendar rollover and months-ahead progressive Booking, not just flight
batches. 100 short headroom after 50 improves; 250/500/1000 begin with construction/count/
memory and short prefixes rather than multi-hour days. Vary H/M/S independently of A.
Reserve sustained 50 Ultra/native certification for coherent milestones, not every
small step. Higher fleets are future scale targets, not forecasts from arithmetic.

## Human decisions and gameplay invariants

Approval still needed: calendar timezone/boundary priority; new-career bootstrap/
no-change carry-forward; editable sold next-quarter terms/refund rights; multi-frequency
service grouping/number reuse; variable horizon lead-time policy; guaranteed/estimated
delivery/ownership/payment start/delay semantics; disruption/recovery scope; legacy
far-future and irregular schedules conversion/run-off; seal/frontier persistence;
compact history/replay contract. No final fields/enums/thread strategy or future
modifier stacking chosen.

Preserve continuous runtime only while open; hard management/save pause and paused
load; no offline progress; understandable weekly plans; daily directional demand;
months-ahead progressive fill; booking cash under existing liability/recognition;
capacity-not-demand; planning future aircraft once availability is authoritative;
no physical use before valid availability/location; immediate legitimate operational
effects; no active strategic quarter rewrite and late planning targeting later quarter;
determinism. Sold-plan and bootstrap tensions require policy, not silent design changes.

## Audit validation and delivery scope

Only this audit and concise status/roadmap/index links change. Approved target,
historical 3G reports, schema/template, production/tests/data remain unchanged.
AT-045 remains Approved future direction; these recommendations are not promoted
to Approved implementation decisions. No gameplay/performance execution or compilation.
Validation PASS on 2026-10-07: inline Python local-link/heading/casing checker
checked 157 local links and 4 heading targets across 6 changed Markdown files.
Complete audit/diff, authority/contradiction/scope review and `git diff --check` PASS.
No dedicated tracked documentation validator was found; no repository test/tool files
were created. `.venv/` remains untouched.
