# Quarterly Planning, Weekly Services & Bounded Booking Architecture

**APPROVED DESIGN — STAGE 1 FOUNDATION IMPLEMENTED; QUARTER WORKFLOWS NOT YET IMPLEMENTED**
Approved direction recorded 2026-10-07; publication and lifecycle product
clarifications approved after the migration audit on 2026-10-07. This remains
the canonical future-design description, not implementation permission. The
[audit](../03%20Technical/Quarterly%20Weekly%20Architecture%20Migration%20Audit.md)
preserves its original analysis with explicitly superseded assumptions.
The [Stage 1 implementation record](../03%20Technical/Quarterly%20Authority%20and%20Identity%20Foundation.md)
and canonical schema now define the dormant identity foundation. Remaining workflows
and later representation decisions are not implemented.

## Authority and current implemented behavior

This is the focused source for the future direction, not a replacement persistent
state contract. [Stage 1 State Schema](../03%20Technical/Stage%201%20State%20Schema.md)
and its subordinate [template mirror](../../Data/Templates/template_reference.txt)
define current authority: **Schema 8 adds the dormant Stage 1 foundation**; existing
operational domain semantics remain. Schema 7 is historical development authority. Domain specifications
continue to govern current behavior. Historical implementation reports remain
historical; only the bounded authority/identity Stage 1 is implemented.

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
incremental validation (the contemplated Stage 3G-C) is not complete. The completed
migration audit recommends its concept as part of transition to the new authority
model, in a reduced/different form, rather than broad optimization of outgoing
publication machinery. This recommendation does not authorize implementation.

## Approved future direction: strategic quarters

Calendar quarters are Q1 January–March, Q2 April–June, Q3 July–September and
Q4 October–December. Quarter boundaries use the global simulation calendar / UTC;
flight departure/arrival planning retains appropriate airport-local time rules.
The quarter is a stable strategic planning and preparation boundary. During
months 1 and 2, the next quarter is normally editable and unpublished. At the
start of month 3 it automatically publishes and locks for ordinary strategic
editing; new planning targets the quarter after next.

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

Player-facing explanations use planning periods, publication and effective dates,
not cache terminology. Conceptual lifecycle states are **planning/unpublished →
published/committed → active → historical**; no persisted enum names are approved.
Derived preparation is separate from commercial commitment. **Unpublished flights
cannot receive bookings.** Publication bridges strategic planning and sale.

| Active quarter | Months 1–2 | Automatic publication at 00:00 UTC | Month 3 |
| --- | --- | --- | --- |
| Q1 | Q2 planning/unpublished | March 1: Q2 publishes | Q2 committed/bookable; Q3 planning |
| Q2 | Q3 planning/unpublished | June 1: Q3 publishes | Q3 committed/bookable; Q4 planning |
| Q3 | Q4 planning/unpublished | September 1: Q4 publishes | Q4 committed/bookable; next-year Q1 planning |
| Q4 | Next-year Q1 planning/unpublished | December 1: next-year Q1 publishes | Next-year Q1 committed/bookable; next-year Q2 planning |

At quarter rollover the published incoming plan becomes active. Ordinary PH 1.0
strategic edits cannot alter published plans, whether future or active; after
publication they target the next eligible unpublished quarter. This includes an
early manual commitment: its published quarter is no longer a free editing target.

### Carry-forward and first operating quarter

The current published weekly schedule is the baseline for the next planning quarter.
The player edits that future version optionally. With no strategic changes, the
weekly schedule carries forward unchanged and publishes on the normal automatic
date. No player action does not mean no future schedule. Copy-on-write or another
storage mechanism is not chosen here; operational feasibility constraints still apply.

A new airline follows the same future-quarter targets in the table above: January/
February → Q2, March → Q3, and so on. There is **no partial-current-quarter Initial
Operating Plan**. Its first weekly plan is built for the eligible future quarter;
there is no existing service to carry forward before such a plan exists.

Early **Manual Publish** is supported for the initial/new-airline situation. The
player may explicitly commit the eligible future-quarter plan before its normal
automatic publication date, making its eligible future occurrences bookable without
moving their operating dates into the current quarter. This also applies when the
normal initial target is the quarter after next under the month-3 rule.
Before confirmation, the eventual GUI must explain that publication opens passenger
bookings, commits the schedule and closes ordinary free strategic editing, or the
player may keep planning and await automatic publication. Final wording/UI is deferred.
This does not approve unrestricted manual publication of arbitrary future periods.

### Published amendments versus operational outcomes

PH 1.0 supports free edits of unpublished planning versions. Published plans are
locked against ordinary strategic edits. They are not architecturally impossible
to amend forever: future post-publication amendments may involve rebooking, refunds,
compensation, operational cost, reputation or other consequences. Those mechanics
are deferred, outside the current implementation target.

Published strategy and actual outcomes are distinct. A published DAB01 planned for
08:00 may later have a CANCELLED result with reason aircraft unavailable; the result
does not rewrite the planned flight as though it never existed. Delays, diversions,
maintenance and other legitimate operational exceptions remain possible when their
systems exist. No new disruption mechanics are implemented or approved here.

The active strategic operating plan stays stable for its period. Planning affects
an eligible future quarter, avoiding repeated invalidation of strategic state
that cannot legally change now. **Stable strategic plan does not mean frozen
simulation.** Bookings, departures/arrivals, passenger counts, revenue/cost and
actual aircraft state continue evolving. Delays, cancellations, breakdowns,
diversions, emergency maintenance and other legitimate operational consequences
must occur when required, rather than wait for a quarter. Deviations and recovery
representation remain unresolved; post-publication amendments remain deferred.

## Approved future direction: weekly plans and service identity

A repeating Monday–Sunday operating pattern is the primary schedule definition
for the applicable quarter, rather than months of separately published records.
For example, Monday 08:00 MNL → DVO and 10:10 DVO → MNL may repeat through the
quarter. Aircraft availability/delivery, airport and route eligibility, range,
turnaround, positioning and other authoritative constraints still apply, including
maintenance/disruption rules when implemented. Permanent full authoritative
records for every future occurrence are not assumed; materialization remains an
implementation-planning question.

The weekly plan is the repeating unit. If it contains DAB01 through DAB25,
the following week repeats those same numbers; it does not start at DAB26 merely
because a week elapsed. DAB01 / 2028-04-03, DAB01 / 2028-04-10 and DAB01 /
2028-04-17 are distinct dated occurrences of a recurring weekly flight number.
Player-facing numbers alone cannot be database/history primary identities.

A continuing service normally keeps its number across quarterly versions: DAB01
MNL → DVO at 08:00 in Q1 may remain DAB01 at 08:30 in Q2. A new quarter does not
renumber continuing services. A genuinely new unrelated service receives a new
number; removing a service retires/reserves its number rather than automatically
assigning it to the next unrelated new service.

Conceptually distinguish active/continuing numbers, retired/reserved numbers and
potential future reusable numbers. A later approved reuse/cooldown policy may make
retired display numbers reusable, but history must remain unambiguous through stable
internal identity and dated/version attribution. No cooldown, encoding or storage
representation is chosen here.

A service may operate on multiple weekdays/frequencies; one identity is not assumed
to mean exactly one weekly occurrence. Correct dated occurrence and applicable
plan/version must remain attributable even after retirement or eventual number reuse.
Immutable internal IDs own relationships; flight numbers remain display values.

## Approved future direction: future preparation

Affected future derived state may be incrementally prepared when a future plan
changes. Sealing should let preparation finish against stable strategic inputs.
At rollover the incoming quarter should already be substantially prepared,
avoiding a huge synchronous world rebuild where possible.

“Background preparation” means preparation while the game continues operating;
it does not approve threads or concurrency. Incremental work, bounded work
between runtime updates, maintained indexes, caches or other mechanisms need
concrete implementation contracts. Ownership, dependency coverage, invalidation and reconstruction must be
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

**Bookings may only use commercially published supply.** Active-plus-next-quarter
supply is not continuously bookable. Normally January–February sell eligible Q1
occurrences only: Q2 remains unpublished. On March 1 Q2 publishes, so eligible Q1
and Q2 dates become sellable. April–May sell eligible Q2 only; Q3 opens June 1.
July–August sell Q3 only, with Q4 opening September 1. October–November sell Q4
only, with next-year Q1 opening December 1. Published state and exact occurrence
eligibility determine sales; unpublished planning projections are never offers.

The sellable horizon expands at publication, rather than automatically opening a
new following quarter at rollover. An initial early Manual Publish similarly opens
only that eligible committed future plan, including the month-3 initial target;
it does not make other unpublished quarters bookable.

Preserve progressive daily accumulation. Published flights months ahead gradually
fill as daily directional demand arrives; no static quarterly passenger allocation.
Capacity does not create base demand. Booking inventory and lead-time distribution
within the publication-dependent horizon still need implementation contracts before
changing the current 365-day Booking configuration/equations.

## Approved future direction: delivery and advance cash

Commercial planning is separate from physical aircraft location. Once an
acquisition has an authoritative future availability/delivery timestamp and
location, future planning should be possible before physical arrival. An aircraft acquired in
February for May 10 delivery at MNL may be planned for Q2 operations only after
valid availability at the required location, including preparation/turnaround.
The player need not wait until May 10 to begin planning. Validate projected future
feasibility without weakening range, airport, delivery, positioning or other
constraints. No additional philosophical delivery-guarantee system is requested
for PH 1.0. No occurrence may operate before authoritative availability. If current
acquisition lacks the necessary time/location contract, later implementation may
introduce only the minimum required authority. Delayed delivery is not current
immediate-acquisition behavior; no acquisition change occurs in this task.

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

## Implementation details still unresolved

- Later plan workflow/consumer integration; minimum quarter/service identity is defined by Schema 8.
- Service identity relationship to multiple weekly frequencies/days, versions and retirement.
- When dated occurrences materialize and how bounded-horizon Booking inventory works.
- Cache/derived-state domain ownership, dependency closure, invalidation and reconstruction.
- Whether prepared future state is persisted or reconstructed, and horizon persistence needs.
- Exact publication/rollover mechanics, same-time event ordering and preparation readiness; quarter calendar is UTC.
- Minimum future availability contract and projected feasibility, including mid-quarter delivery.
- Operational exception representation and recovery; costly post-publication amendments remain deferred.
- Historical compact results, lineage preservation and historical compaction.
- Replacement of recurrence/publication authority for new saves; no development-save conversion requirement.
- Effects on current scheduling GUI, previews, effective-date explanations and commands.
- Deterministic save/load effects: quarter/weekly plans, identity/version history,
  dated operations, booking state, prepared state and cache reconstruction/invalidation.
- Runtime transaction/validation boundaries and interaction with the current event queue.
- Long-range Advance Time equivalence opportunities and eventual AI planning integration.

World-state construction, validation and persistence remain in `game/world_state`;
generic clock/event orchestration in `game/simulation`; domain behavior in its
owning package. Preserve complete event-boundary snapshots, separate validated
load candidates, previous valid files on failure and paused restoration. These
safety requirements remain; they do not require conversion of old development saves.

## Historical records and development saves

Retain finalized flights/results and accounting facts for finished-flight inspection,
finance reporting, route/service/airline statistics, historical analysis and future
replay/analytics where supported. Retained completed flights should not participate
in booking eligibility, future aircraft availability, current schedule conflict checks
or active event discovery merely because their history remains stored. Separate cold
history from hot work safely; no destructive compaction losing required player-visible
facts is approved.

Existing development Schema 7 saves do **not** need compatibility with the new
quarterly architecture; new saves after transition are acceptable. Do not add
conversion/run-off/compatibility layers solely to migrate those development files.
Schema 8 is current for new careers; older development saves are rejected cleanly.
Further schema changes must
be explicit, documented, validated and internally coherent; incompatible old saves
must not be silently misinterpreted. No files are deleted or migrated here. Required
history/accounting within new careers and safe save/load still apply.

## Deferred implementation details and non-goals

Schema 8 now defines minimum service/quarter-plan/slot identities and commitment
facts. Calendar helpers, validation and deterministic persistence are implemented.
This does not activate quarterly planning/publication/Booking workflows, carry-forward,
future delivery, occurrence thinning, reduced 3G-C, AI or new countries. Cache/thread
strategy, rollover/event generation, modifier/lead-time mechanics, number reuse and
history representation remain later decisions. Existing Booking economics/horizon,
operational recurrence, acquisition, finance and GUI remain unchanged. Subsequent
implementation requires bounded approval and concrete contracts.
