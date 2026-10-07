# Quarterly Planning, Weekly Services & Bounded Booking Architecture

**APPROVED DESIGN DIRECTION — NOT YET IMPLEMENTED**  
Approved direction recorded 2026-10-07. Next task: dedicated architecture audit.
This document records the intended gameplay and architecture; it neither performs
that audit nor authorizes implementation. Exact representations remain unresolved.

## Authority and current implemented behavior

This is the focused source for the future direction, not a replacement persistent
state contract. [Stage 1 State Schema](../03%20Technical/Stage%201%20State%20Schema.md)
and its subordinate [template mirror](../../Data/Templates/template_reference.txt)
remain authoritative today: **Schema 7 is unchanged**. Domain specifications
continue to govern current behavior. Historical implementation reports remain
historical; no implementation milestone is completed by this document.

Current documented behavior includes effective-dated weekly schedule revisions,
published dated flights, optional rolling current-week-plus-four-future-weeks
publication, persisted weekly publication events, progressive daily Booking,
a configurable 365-day hard Booking horizon, and validated event-boundary saves.
Current acquisition delivers purchased aircraft immediately at an eligible base/hub.
These are current contracts, not claims that quarterly planning already exists.

Current paid Booking posts ticket cash and an unflown-ticket liability;
fulfilment recognizes passenger revenue and settles operating costs. The gameplay
phrase “revenue when passengers book” means advance cash receipt here, not a
change to current revenue-recognition semantics. See [Economy](Economy%20Simulation.md).
No fuller accounting system is introduced by this direction.

[Stage 3G-A](../03%20Technical/Runtime%20Scalability%20Forensic%20Audit.md)
analyzed runtime scalability. [Stage 3G-B](../03%20Technical/Runtime%20Local%20Certified%20Proofs.md)
localized major proof/event-selection work with substantial measured improvements
and exact behavior preserved. Runtime remains NOT CERTIFIED. Dependency-complete
incremental validation (the contemplated Stage 3G-C) is not complete. Before further
optimization of the existing scheduling/publication architecture, audit this
quarterly/weekly direction to determine retained, simplified and removable
structures, whether/where incremental validation is needed, and safe migration.

## Approved future direction: strategic quarters

Calendar quarters are Q1 January–March, Q2 April–June, Q3 July–September and
Q4 October–December. The quarter is a stable strategic planning and preparation
boundary. During months 1 and 2, strategic changes target the next quarter.
During month 3, that next quarter is already sealed for planning, so new
strategic changes target the quarter after next.

| Change made in | Eligible strategic target |
| --- | --- |
| January / February | Q2 |
| March | Q3 |
| April / May | Q3 |
| June | Q4 |
| July / August | Q4 |
| September | Q1 next year |
| October / November | Q1 next year |
| December | Q2 next year |

Player-facing explanations use planning periods and effective dates, not cache
terminology. A rolling pipeline may conceptually progress from editable/planning
to sealed, prepared/cached, active, then historical. These are conceptual labels,
not final enums or new authoritative fields. Exact boundary/timezone semantics
and rollover mechanics require the audit.

The active strategic operating plan stays stable for its period. Planning affects
an eligible future quarter, avoiding repeated invalidation of strategic state
that cannot legally change now. **Stable strategic plan does not mean frozen
simulation.** Bookings, departures/arrivals, passenger counts, revenue/cost and
actual aircraft state continue evolving. Delays, cancellations, breakdowns,
diversions, emergency maintenance and other legitimate operational consequences
must occur when required, rather than wait for a quarter. Deviations and recovery
representation remain unresolved; strategic exceptions also require audit.

## Approved future direction: weekly plans and service identity

A repeating Monday–Sunday operating pattern is the primary schedule definition
for the applicable quarter, rather than months of separately published records.
For example, Monday 08:00 MNL → DVO and 10:10 DVO → MNL may repeat through the
quarter. Aircraft availability/delivery, airport and route eligibility, range,
turnaround, positioning and other authoritative constraints still apply, including
maintenance/disruption rules when implemented. Permanent full authoritative
records for every future occurrence are not assumed; materialization is an audit
question.

DAB001 illustrates a persistent service identity: April 5, 12 and 19 operations
are dated occurrences of that service, not newly invented service identities.
A Q1 Monday 08:00 plan and Q2 Monday 09:00 plan may retain DAB001. A service may
operate on multiple weekdays/frequencies; one identity is not assumed to mean
exactly one weekly occurrence. Historical results must identify the correct dated
operation and applicable plan/version, and retired identities remain historically
unambiguous. Display flight numbers do not replace immutable internal relationship
IDs. Final storage, versioning and identity allocation/reuse rules await audit.

## Approved future direction: future preparation

Affected future derived state may be incrementally prepared when a future plan
changes. Sealing should let preparation finish against stable strategic inputs.
At rollover the incoming quarter should already be substantially prepared,
avoiding a huge synchronous world rebuild where possible.

“Background preparation” means preparation while the game continues operating;
it does not approve threads or concurrency. Incremental work, bounded work
between runtime updates, maintained indexes, caches or other mechanisms require
audit. Ownership, dependency coverage, invalidation and reconstruction must be
explicit; stale derived state cannot supply authoritative outcomes. Derived
caches do not become authoritative persistent state merely for performance.

## Approved future direction: demand and bounded progressive booking

`base_daily_bookers` remains directional market demand entering the booking
system **each simulation day**, before applicable modifiers. MNL → DVO with
1,000 means approximately 1,000 new potential bookers daily, not 1,000 passengers
for today's departure or independently for every flight. Capacity creates no
additional base demand: the market produces demand, the schedule supplies
services, and Booking distributes demand across eligible future supply. Excess
capacity can dilute load factors; insufficient capacity can constrain/leave
unserved demand. Optimization must preserve this economic foundation.

The future modifier pipeline is base demand → applicable modifiers → effective
daily demand → distribution across eligible future services. Route health,
tourism, seasonality, economy, events, reputation and other approved effects may
have different scopes and may be directional. A conceptual 1,000 baseline with
+15% route health illustrates adjustment, not approved stacking mathematics.
No new modifier, demand value or equation is introduced. Stable inputs and
safe derived values should eventually be maintainable/cacheable.

The intended bookable horizon covers remaining eligible dates in the active
quarter and dates in the immediately following quarter, never beyond it.
Q1 therefore extends through Q2 end; Q2 through Q3 end. At rollover the newly
following quarter opens for booking. Planning eligibility and booking eligibility
are distinct: the sealed next plan can be bookable while new strategic edits
target a later quarter.

Preserve progressive accumulation: flights months ahead can gradually fill as
daily demand enters markets. This is not static quarterly passenger allocation.
Booking inventory, lead-time distributions, exact date boundaries and interaction
with current 365-day configuration/desired-date windows require audit before
changing any current Booking contract.

## Approved future direction: delivery and advance cash

Commercial planning is separate from physical aircraft location. Once an
acquisition/delivery is sufficiently authoritative under game rules, future
planning should be possible before physical arrival. An aircraft acquired in
February for May 10 delivery at MNL may be planned for Q2 operations only after
valid availability at the required location, including preparation/turnaround.
The player need not wait until May 10 to begin planning. Validate projected future
feasibility without weakening range, airport, delivery, positioning or other
constraints. Authoritative delivery guarantees and mid-quarter activation require
audit; delayed delivery is not current immediate-acquisition behavior.

Preserve advance ticket cash receipt unless a later explicit finance design
changes it. Sales increase current available liquidity before operation, allowing
working-capital gameplay while a future transportation obligation remains.
Cash received and service obligation are distinct. Existing liability/recognition
contracts remain intact; no new full deferred-revenue system is specified here.

## Performance intent and future applicability

Runtime cost should primarily follow active operational work, affected markets,
services, aircraft and affected dependency closure, rather than repeated scans of
every aircraft, historical record, distant future occurrence or the whole world.
This is an architectural goal, not measured improvement from this design.
The 50-aircraft Ultra benchmark is a checkpoint, not the final scale target;
future player plus AI fleets may contain hundreds or thousands of aircraft.

Stable strategic periods may enable faster long-range Advance Time later.
Analytical quarter skipping/aggregated simulation is not approved. Any skipping
or aggregation must prove equivalence to authoritative simulation, deterministic
inputs, exact UTC-second/event ordering and correct outcomes; approximation is
not permitted by this direction. No offline progress is authorized.

Future AI network/strategic decisions could use quarterly boundaries, potentially
reducing strategic-AI cost. AI implementation remains deferred. These are generic
core concepts, not Philippines-specific rules. PH 1.0 remains current content
scope; future country policies/data should remain content-driven where possible.
No Southeast Asia content or country expansion is included.

## Open questions requiring the next architecture audit

- Exact authoritative representation of quarter plans and persistent service IDs.
- Service identity relationship to multiple weekly frequencies/days, versions and retirement.
- When dated occurrences materialize and how bounded-horizon Booking inventory works.
- Cache/derived-state domain ownership, dependency closure, invalidation and reconstruction.
- Whether prepared future state is persisted or reconstructed, and horizon persistence needs.
- Quarter sealing/rollover mechanics, date/timezone boundaries and preparation readiness.
- Mid-quarter delivery guarantees, aircraft availability and projected feasibility.
- Strategic schedule exceptions, operational disruptions and recovery.
- Historical compact results, lineage preservation and historical compaction.
- Migration from recurrence/publication structures without silently breaking existing saves.
- Effects on current scheduling GUI, previews, effective-date explanations and commands.
- Deterministic save/load effects: quarter/weekly plans, identity/version history,
  dated operations, booking state, prepared state and cache reconstruction/invalidation.
- Runtime transaction/validation boundaries and interaction with the current event queue.
- Long-range Advance Time equivalence opportunities and eventual AI planning integration.

World-state construction, validation and persistence remain in `game/world_state`;
generic clock/event orchestration in `game/simulation`; domain behavior in its
owning package. Preserve complete event-boundary snapshots, separate validated
load candidates, previous valid files on failure and paused restoration. Existing
processed history and compatibility witnesses cannot be silently rewritten.

## Deferred implementation details and non-goals

No final schema/database representation, lifecycle enum, cache/threading strategy,
rollover algorithm, modifier stacking mathematics or migration is chosen here.
This task does not change Python, tests, JSON/game data, Schema 7, save files,
Booking equations/horizons, demand values, acquisition, finance, runtime or GUI.
It implements neither quarterly planning nor weekly-service persistence, Stage
3G-C, AI or new countries. The next task is the dedicated architecture audit;
implementation needs subsequent bounded approval and contracts.
