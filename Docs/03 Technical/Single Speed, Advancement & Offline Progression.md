# Single Speed, Advancement & Offline Progression — Quarterly Stage 3G-B1

Approved product direction, **2026-10-12**. Documentation only; verified baseline
`34a50915ff21d77c5eeb1d277379c94e8ba4bc35`. AT-058 supersedes AT-041's mandatory
Ultra activation gate and the conflicting future pacing/offline clauses of AT-002,
AT-016, AT-025 and AT-033. It does not change implemented behavior or historical
results. B2, B3 and C require separately authorized implementation tasks.

Authority: [Schema 9](Stage%201%20State%20Schema.md), its subordinate
[template](../../Data/Templates/template_reference.txt),
[runtime specification](Continuous%20Runtime%20Technical%20Specification.md),
[save architecture](Game%20State%20%26%20Save%20Architecture.md),
[save specification](Game%20State%20%26%20Save%20Technical%20Specification.md),
[quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md),
[publication recovery](Quarterly%20Boundary%20Orchestration.md), and
[event safety](Runtime%20Causal%20Generation%20Accounting.md).

## Current implementation and future contract

Current code still offers literal 30/210/900/1800× named speeds, retains pause/resume,
and restores validated saves paused with no offline progression. Close does not
currently persist an offline entitlement. No Python, Kivy, save format, field,
multiplier, event budget or activation changes are made by B1.

The following sections define approved future behavior and a concrete recovery
design to refine before B3. Conceptual metadata responsibilities are not a field
schema. Any future persistent world fields require canonical schema-first approval
and a consistent template before their writers; file-container/provenance changes
also require an explicit save contract and compatibility review.

## Standard continuous pacing

Use one fixed standard ratio: **90 game seconds per real second**. This is exactly
90 game minutes per real minute, 3.75 game days per real hour, and 90 game days per
24 real hours. Thus one real day is approximately one game quarter. Ninety days is
a pacing convention, not a calendar definition: Q1 January–March, Q2 April–June,
Q3 July–September and Q4 October–December retain their actual lengths and leap days.

Retain pause/resume. Future B3 retires Fast, Very Fast and Ultra as supported
continuous gameplay selections; B1 leaves every control and multiplier intact.
Active runtime continues to use exact monotonic uptime and integer fractional
credit. Real-time samples only produce explicit whole-second targets; the engine,
not wall time or rendering, determines authoritative UTC and outcomes. Paused
active-session elapsed time earns no continuous credit. Closed-time eligibility
is a separate bounded provenance decision, not a reinterpretation of live credit.

## Advance Time

Explicit Advance Time is the primary player-controlled acceleration mechanism.
Future interface capabilities include 1, 7, 30 and 90 game days, a selected date,
and a meaningful future event. These options are not implemented or individually
specified by B1. Date interpretation, meaningful-event selection and cancellation
presentation must be defined before those controls are exposed. Existing Next Event
continues to mean exactly one event, including publication with same-UTC Booking
still pending; it must not silently become an arbitrary group of events.

Continuous play, explicit Advance and offline catch-up use the same authoritative
engine and domain handlers. Process required Booking, flight, finance and publication
work in canonical chronology. Preserve deterministic inputs, IDs, pending events,
history, journals and successful-prefix recovery. Stop at mandatory blocking
conditions, failures and safety limits; do not manufacture summarized outcomes.

Keep existing request-wide processed/stale limits and same-UTC causal generation
budgets across yields, cache rebuilds, batch flushes and UI callbacks. B1 neither
raises budgets nor authorizes hidden new requests to evade a blocked limit. A
completed event boundary can still have pending work at the same UTC; a checkpoint
there is not proof that the target timestamp is fully resolved. Explicit correction
or retry retains the existing fresh command boundary and budget semantics.

## Limited offline catch-up

Approve at most **24 real hours per continuous absence**, converted at 90×, hence
at most 90 game days. On successful close, persist a validated complete-boundary
snapshot and an appropriate real-world close reference, then stop executing. There
is no background service, account or server requirement. Reopening validates a
separate candidate first, determines eligible elapsed real time, clamps it, freezes
one target, and processes through the same engine. Present the resulting committed
state paused, including any intervention or incomplete-work diagnostic.

The entitlement is elapsed absence, not CPU time spent catching up. Use exact integer
duration arithmetic and a documented whole-second rounding/residual rule before B3;
do not let frames, processing time or retries extend the frozen target. Loading an
older save without supported offline metadata grants zero unrecorded offline time.
Ordinary manual/autosave/bookmark loads are not automatically new absences.

## Concrete provenance and recovery strategy

Use a local, career-scoped durable receipt journal coordinated with immutable
snapshot identities and an exclusive career lease. This is the intended implementation
design, not an approved Schema 9 layout or a claim that the current SaveStore provides
it. Validate these responsibilities and their storage placement before B3:

1. A successful close records a unique absence generation, exact career/branch and
   snapshot identity/integrity digest, simulation boundary, real UTC reference,
   clock/provenance evidence and eligibility context. Commit an immutable validated
   checkpoint before atomically publishing its receipt reference. A failed close
   cannot publish a new entitlement or destroy the previous valid snapshot.
2. Reopen under an exclusive local career lease. Validate the snapshot and matching
   close receipt. Never derive eligibility solely from a file's modification time
   or the timestamp of whichever older slot was selected. Only the matching durable
   continuation can claim that absence; mismatched provenance cannot earn automatic
   offline credit. Missing/invalid evidence permits ordinary paused recovery, with
   an explanation rather than invented elapsed time.
3. Atomically record the claim before execution: absence identity, source digest,
   sampled reopen reference, capped eligible duration, fixed simulation target and
   recovery status. Repeated loading uses this existing claim; it cannot create a
   second entitlement from the same close reference. A consumed high-water receipt
   is career-level and not rewound by loading an old manual save, autosave or bookmark.
4. At selected completed event boundaries, persist a validated immutable recovery snapshot;
   only then atomically advance the journal's checkpoint pointer and progress status.
   Keep the previous pointer/file valid until replacement succeeds. A crash before
   pointer publication resumes the previous prefix and deterministically re-executes
   only work absent from it. A crash afterward resumes the new prefix. Never combine
   progress from one snapshot with another snapshot's world or remaining duration.
5. On complete target resolution, atomically mark the claim complete against its
   final checkpoint. Reopen/reload restores that checkpoint without applying the
   duration again. On publication failure, safety stop or cancellation, retain the
   fixed claim and successful-prefix checkpoint as incomplete; future recovery must
   use that claim rather than resetting counters or re-earning elapsed time. Required
   explicit retries start only through the existing authorized retry path.
6. Recovery checkpoints are separate from the player's manual save and named
   bookmarks; catch-up cannot silently overwrite them or rotate away its only valid
   recovery prefix. Autosave creation follows a separately reviewed coalescing policy.
   Claim completion and recovery pointers must survive normal autosave rotation.
   Only one session can own a career's mutation/catch-up lease; a second session
   cannot claim or execute the same absence concurrently. Lease acquisition/recovery
   must use OS-backed exclusion, not an unverified stale lock-file timestamp.

An incomplete claim is not a new close generation. Closing/reopening during recovery
does not renew the 24-hour allowance for that same absence. If the player chooses an
older branch, the old claim remains consumed/resumable only on its exact branch;
it must not be transplanted onto the selected snapshot. The player-facing choice
between continuation, branch-only paused play and abandonment needs B3 design.
No branch merge or silent replacement of the selected manual/bookmark is authorized.

Real UTC is an untrusted observation. Clock rollback, noncanonical/missing timestamps,
receipt mismatch or detected clock discontinuity must not yield negative time or
extra entitlement. Preserve the record and offer paused recovery with a diagnostic.
Compare available monotonic/boot evidence where meaningful; it does not span every
reboot. A forward clock change is bounded by the 24-hour cap, not proven truthful.
Without a trusted external clock or tamper-proof storage, a local-only game cannot
prove elapsed time against deliberate clock/save/journal manipulation. Do not claim
anti-cheat guarantees, introduce a server, or hide this limitation.

Determinism means identical validated source, fixed entitlement/target and player
decisions produce identical authoritative outcomes across modes. The wall-clock
observation/provenance decision must be recorded for replay; replay never resamples
the current wall clock. Disk failures preserve prior valid files and active world;
partial candidate restoration is prohibited.

## Publication and intervention

Keep March/June/September/December 1 at 00:00:00Z publication for the incoming
quarter, with the derived publication-before-Booking barrier independent of enqueue
order. The same rules apply during catch-up and large explicit advances. Existing
valid automatic publication and default carry-forward proceed without a new mandatory
confirmation. No unpublished required quarter may be skipped. Failed publication
pauses at its exact fence, retains pending consumers and permits existing certified
correction/fresh retry. Do not silently edit a plan, add positioning or relax literal
execution readiness. Retain all four publication gates and both world copies.

## Derived caching and equivalent batching

Calculate once and reuse only while the inputs remain valid. Candidate caches include
bounded published occurrence indexes, planned departure/arrival lookups, nominal
flight durations, aircraft/route compatibility, published capacity, recurring pattern
structure and stable booking inputs. Domain owners define exact dependency/version
keys, bounded lifetimes, invalidation triggers and independent rebuild comparisons.
Load/rebind discards stale caches; reconstruction cannot allocate authority, consume
randomness, sell seats, post money, publish or advance time. Caches are non-authoritative,
reconstructible, revision-aware and compatible with deterministic replay.

Published capacity is distinct from mutable remaining inventory. Stable booking
inputs do not make passenger allocation immutable: inventory, publication membership,
fare/policy revisions, demand date and retirement must still be current. Planned
times/weekly service identity/aircraft assignment/published occurrence references
remain distinct from actual departures/arrivals, aircraft readiness and dynamic
disruptions. Future airport queues, congestion and downstream delays must work in
every advancement mode; speculative actual outcomes cannot be cached as facts.

B2 may investigate batching only with individually valid chronological transitions,
equivalent strict/reference results, original ordering/fences/budgets and existing
validation/ownership guarantees. No separate simplified offline engine, approximate
finance/demand, skipped events, reduced quarterly gates or copying redesign is
authorized by this direction. Congestion/delay implementation remains deferred.

## Performance and activation acceptance

AT-041's 50-aircraft Ultra 1800×/48-real-seconds-per-day requirement is superseded
as a mandatory activation gate. Preserve its [historical report](Runtime%20Capacity%20Certification.md):
375.151 engine seconds for one day at 50 aircraft and its NOT CERTIFIED result are
unchanged. That legacy workload is not a measurement of the new quarterly 90× path.

Replace that gate with representative standard 90× continuous performance certification,
correct and efficient Advance Time, correct capped offline catch-up, deterministic
equivalence across all paths, save/load/recovery compatibility, and measured fleet
scaling. Report served UTC, retained debt, wall time, memory, callback latency, workload
and hardware separately. Standard runtime must sustain the exact 90× earnings with
bounded recoverable debt; discarded credit or repeated overload is not success.
Use representative 1/10/50-aircraft quarterly careers with real published services,
positive Booking, operations, financial history and publication crossings. Idle fleets
or zero-consumer fixtures cannot establish release capacity.

| Representative 50-aircraft Advance | Aspirational engine objective |
| --- | --- |
| 7 game days | Under 1 second |
| 45 game days | Under 3 seconds |
| 90 game days | Under 5 seconds |

These are optimization objectives pending B2 benchmarking/feasibility, not measured
capabilities or mandatory quantitative release thresholds. Near-instant catch-up
does not permit omitted work. If infeasible, report measured bottlenecks and alternatives
for approval. End-to-end load/provenance/checkpoint/UI time must also be disclosed;
it cannot be concealed behind engine-only timings. B2 must propose practical latency
and Advance/catch-up acceptance bounds for approval before C can claim certification.

## Revised sequence and remaining design work

| Slice | Scope and dependency |
| --- | --- |
| 3G-B1, current | Documentation contract and AT-058 supersession only. No implementation or gameplay activation. |
| 3G-B2, future | Benchmark representative quarterly runtime; identify redundant calculations; implement separately approved measured caches and equivalent advancement optimizations; rebenchmark and verify strict/reference replay. |
| 3G-B3, future | Following B2 evidence and schema/save design review, implement 90× single-speed behavior, capped offline claims/recovery, provenance and exclusive sessions; update Kivy controls. |
| 3G-C, future | Combined functional/normal-speed performance certification, Advance/offline equivalence, save/load compatibility and recovery; activate quarterly gameplay only if every mandatory gate passes. |

Resolve before affected B3 behavior: whether a paused close earns offline entitlement;
how incomplete catch-up cancellation/abandonment and older-branch selection are
presented; crash exits without a successful close receipt; timestamp precision and
residual handling; receipt/checkpoint schema/version and local storage portability;
autosave coalescing and exit-save failure UX; legacy-career rollout/migration scope.
The anti-double-counting and no-retroactive-grant requirements apply regardless of
those choices. None is silently finalized by B1 or authorizes implementation now.

B2 must establish representative workload density, aging, hardware and measurement
protocol, and proposed practical latency/throughput thresholds. Existing Booking
economics, route fees, identity, publication policy, schema structure and safety
budgets remain unchanged. Long-term planning blueprints and congestion remain
deferred. Default quarterly gameplay stays disabled pending B2/B3/C.


## Future verification requirements

B2/B3/C must compare continuous, explicit and fixed-entitlement offline execution
against the same strict chronological reference at matching resolved boundaries,
including exact history, IDs, Booking/inventory, aircraft facts and financial journals.
Exercise fractional 90× credit, calendar/leap-quarter crossings, successful automatic
publication before equal-UTC Booking, failed publication with unchanged pending work,
correction/retry and multiple boundaries. Verify processing limits across yields and
checkpoint recovery, without hidden retries or skipped obligations.

Offline cases include zero/negative/invalid elapsed time, exact and over-24-hour caps,
missing old-save metadata, repeated loading of every slot type, rollback/forward clock
changes, two concurrent sessions, crash before/after claim publication and checkpoint
pointer replacement, completion receipt failure, incomplete catch-up and disk failure.
Require previous-valid-file survival, separate-candidate validation, paused presentation
and replay from the recorded fixed claim. Measure cache cold/warm/load invalidation,
bounded memory and independent reference agreement. These are future acceptance
requirements; B1 runs documentation verification only.

## Exact B1 document scope

- [This contract](Single%20Speed%2C%20Advancement%20%26%20Offline%20Progression.md).
- [Decision Register](Decision%20Register.md).
- [Current Development Status](Current%20Development%20Status.md).
- [Continuous Runtime Technical Specification](Continuous%20Runtime%20Technical%20Specification.md).
- [Production Cooperative Runtime](Production%20Cooperative%20Runtime.md).
- [Runtime Capacity Certification](Runtime%20Capacity%20Certification.md), successor annotation only.
- [Game State & Save Architecture](Game%20State%20%26%20Save%20Architecture.md).
- [Game State & Save Technical Specification](Game%20State%20%26%20Save%20Technical%20Specification.md).
- [Stage 1 Implementation Roadmap](Stage%201%20Implementation%20Roadmap.md).
- [Stage 1 State Schema](Stage%201%20State%20Schema.md), policy annotation only.
- [Quarterly architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md).
- [Paid Bidirectional Route Establishment](Paid%20Bidirectional%20Route%20Establishment.md), activation-blocker successor annotation only.
- [Documentation index](../README.md).
- [template_reference.txt](../../Data/Templates/template_reference.txt), comment annotation only.
