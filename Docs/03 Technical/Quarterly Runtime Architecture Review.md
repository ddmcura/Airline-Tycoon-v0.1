# Quarterly Runtime Architecture Review — Stage 3G-B3C

## Executive summary

**2026-10-13. Architecture proposal only.** Baseline
`8a0a7658c1416fe48c7048ad840935c30f2245fc` matched HEAD, upstream, freshly
fetched origin/master and live remote master, divergence 0/0. Tracked tree/index
were clean; `.venv/`, protected metadata and empty stashes were preserved.
Serena and actual execution, ownership, callbacks and session code were inspected.
No production, test, schema, template, pacing, offline or activation change is made.

Recommend **Option D: hybrid execution**, using independently proved event-local
transactions inside a bounded, exclusively owned working world, with strict
isolation at complex/untrusted boundaries. This combines C's local correctness
proof with B's amortization; it does not make arbitrary mutable handlers trusted.
Retain current strict/shared execution in production and as the migration oracle
until a separately authorized isolated experiment establishes correctness **and
end-to-end benefit**. This recommendation is Proposed, not implementation approval.

The current architecture is a strong reference and compatibility path, but repeated
`events × total retained world` work is an unsuitable default scaling law for
thousands of flights and long-lived histories. Bounded optimization alone is not
evidence of long-term adequacy. Conversely, B3B's complete-snapshot witness costs
more than one full gate and does not establish safe local validation. No alternative
is sufficiently proved for production today. A full rewrite, external history store
or database migration is not justified by the available evidence.

## Authority and evidence boundaries

[AGENTS](../../AGENTS.md), [Schema 9](Stage%201%20State%20Schema.md), its
[template mirror](../../Data/Templates/template_reference.txt), and
[selective folder reference](../../Data/Templates/foldertree.txt) govern.
Relevant evidence and contracts:

- [Quarterly benchmark](Quarterly%20Runtime%20Benchmarking.md) and
  [copy/validation investigation](Quarterly%20Transaction%20Copying%20and%20Validation%20Investigation.md).
- [B3A feasibility](Safe%20Quarterly%20Transaction%20Architecture%20Feasibility.md),
  [B3B certification](Quarterly%20Completion%20Certification%20Feasibility.md), and
  [active/history proposal](Active%20State%20and%20Certified%20History%20Feasibility.md).
- [Ownership](Runtime%20Candidate%20Ownership.md),
  [local proofs](Runtime%20Local%20Certified%20Proofs.md),
  [shared execution](Runtime%20Shared%20Candidate%20Infrastructure.md),
  [causal budgets](Runtime%20Causal%20Generation%20Accounting.md),
  [production runtime](Production%20Cooperative%20Runtime.md), and
  [save specification](Game%20State%20%26%20Save%20Technical%20Specification.md).
- [AT-058 future runtime policy](Single%20Speed%2C%20Advancement%20%26%20Offline%20Progression.md)
  and [Decision Register](Decision%20Register.md). AT-059 remains Proposed.

Existing canonical runtime clauses explicitly require isolated strict candidates,
individual successor validity, complete shared-boundary validation and detached
commit. They also permit precisely certified local proofs for supported built-ins.
They do **not** authorize the proposed quarterly certificates, admitting dispatch
through its current fence, exposing a private candidate across returns, or replacing
whole-world detachment with arbitrary aliasing. Future production work would require
explicit approval and amendments to affected runtime contract clauses before code.
Keeping the Schema 9 wire format does not make a runtime contract change automatic.

## Current bottleneck and scaling

| Evidence scope | Recorded observations | What it establishes |
| --- | --- | --- |
| B2.4/B2.5 Booking-heavy quarterly day, laptop | 13 events: four dispatch, four departure, four completion, one Booking; 27 runtime clones; 15 full gates; eight provider and two reconciliation deepcopies; quiet median 92.251s, peak 1,083.984 MiB | Only 13 events can be costly because the source contains 42,923 Booking/itinerary pairs, 368 dated flights and 75,758,607 JSON file bytes |
| B3B small real Completion | 4,632 keyed records, 1,176 Booking pairs, four selected Bookings; capture 0.206349s, verify 0.054453s, full validation 0.117614s; 4,606,801 snapshot bytes; 7,861,695 additional peak allocation bytes | Whole-source capture plus global checks are not a cheaper local gate; exact bytes alone miss aliases |
| Historical operational airline control, different host/revision, Schema 7 | 50 aircraft, 200 sectors/day, 6,800 dated flights, 7,819 Booking pairs; 401 events/day, quiet 280.155s; 54 gates, 104 kernel copies | Shared legacy flight eligibility already amortizes some work, but large fleet/event/queue work and long main-thread units remain |

The operational evidence is from the
[forensic audit](Runtime%20Scalability%20Forensic%20Audit.md) and
[local-proof investigation](Runtime%20Local%20Certified%20Proofs.md). It is a real
flying airline with natural Booking history, not an idle fleet. It is **not** a
current quarterly control or 90x certification. Hardware, schema, callbacks and
history differ. Do not extrapolate its timings or add B3B seconds to the 92.251s
day. Instrumented inclusive times also cannot be summed with exclusive buckets
or substituted for quiet command latency.

Let W be total authoritative size, E processed events, Q pending events, B retained
Booking/itinerary rows, and K the current event's changed records plus proved read
closure. These are explanatory variables, not a calibrated timing model.

| Growth driver | Current consequence | Important qualification |
| --- | --- | --- |
| Aircraft | More dispatch/departure/completion work, chronology and operational state | Demand does not multiply with flights; one directional market pool remains authoritative |
| Scheduled flights | More sold/imminent rows, queue work, chronology and publication enumeration | Unsold quarterly supply is derived; scheduled descriptors and materialized flights are different counts |
| Active bookings | More manifest association, inventory, financial liability and relationship proof work | Many future commitments are genuinely live even if created long ago |
| Historical bookings | Larger source copies, plain-tree scans and relationship graphs when retained | Age does not prove closed authority; AT-059 storage/partition proposals remain unapproved |
| Processed events | More retained history/results/journals and repeated global checks | Heap selection can be O(log Q); rebuilding/scanning queues and witnesses can still be O(Q) |
| Duration | Appends retained obligations and terminal records, repeating work against a growing W | Under constant arrivals and linear retained growth, repeated global scans can produce cumulative O(T²) work; this is a conditional scaling argument, not a measured curve |

The most consequential factor is **large retained authority multiplied by event
frequency**, followed by repeated provider/preview work and boundary topology.
Aircraft count alone is misleading: one aircraft already carries 42,923 Booking
pairs. Moving only terminal results/history cannot remove those active obligations.
Local selected-ID reads still need a complete association proof; moving a full
Booking scan into a supposedly local lookup merely relocates global cost.

## Safety requirements versus implementation mechanisms

| Requirement that must survive | Current mechanism | Replacement status |
| --- | --- | --- |
| Deterministic UTC/publication/priority/sequence/ID ordering; exact budgets | Canonical queue, kernel lifecycle ownership, request counters | Data structures may change with exact ordering/budget proof; gameplay ordering cannot |
| Valid source and every intermediate successor | Entry/result full gates; selected legacy certificates | A local invariant proof is possible in principle under protected valid inputs; current quarterly gates remain mandatory |
| Atomic event failure and exact successful prefix | Per-event candidates; shared strict replay and disable latch | A sealed staged change set could discard only failed writes; whole-segment rollback alone is incorrect |
| Exactly-once journals, result/Booking lineage, allocator movement | Full successor validation and domain witnesses | Independently derived record equations and complete closure required; balanced totals alone are insufficient |
| No retained reference can mutate committed authority | Isolated source/candidate and detached commit copies | Physical whole-world copy is replaceable in principle by proved ownership/detached outputs, but current whole-world detached commits remain contracted |
| Safe providers and exact diagnostic/exception behaviour | Nested input/before-image copies and output detachment | Replace only through complete callback-specific evidence; B2.6's removed outer pair was necessary |
| Safe save/load, previous file and paused restoration | Full snapshot, detached candidate validation, atomic replacement | Keep comprehensive validation and complete snapshots; runtime certificates do not authorize skipping Load validation |
| Safe observations, commands, yields and rebind | Session serialization, flush/fence/return boundaries | Retain valid committed boundaries; raw session world access prevents assuming exclusive immutability |

Thus valid state, ownership, detachment, determinism and recovery are essential;
deepcopy/codec selection and the physical number of full traversals are mechanisms.
Some mechanisms are also **explicit current contract requirements**. Calling them
replaceable is a proposal for a proven successor, not permission to remove them.
Periodic scans cannot be the sole corruption defence: each admitted mutation must
establish a valid successor before it can influence another event or observer.

## Architecture comparison

### A — retain strict/shared and optimize bounded paths

Safety is strongest today: strict events isolate the whole world; supported legacy
events use existing owned proofs; recovery reselects a strict successful prefix.
Save/load, ordering, Booking and finance have established regression evidence.
Whole-world copies and O(W) gates remain on quarterly dispatch/flight/Booking paths.
Private manifest indexes can amortize selected reads only within proved lifetimes.
Memory includes source, candidates, commits and provider copies; peak factors depend
on allocation lifetimes, not just total copy count.

Complexity and migration risk are lowest, compatibility is established, and A is
the correct current production/reference path. However, shaving codec or scalar
costs does not remove E×W scaling. Existing successful legacy sharing is evidence
for selective ownership, not proof that quarterly inputs can inherit those proofs.

### B — a transactional working world across events

One isolated working world per bounded segment can amortize source copying and
final detachment. It must remain invisible until a valid boundary. Each event
needs staged writes or a valid recovery mechanism: discarding the entire segment
loses previous successful events; retaining partial failed writes corrupts it.
Without independent local successor proof, full validation after every event still
costs O(EW). Whole-world rollback snapshots per event restore the copy problem.

Save, command, cancellation, callback, pause, budget and return boundaries flush
a validated prefix. Ordering remains canonical; each financial/Booking transition
still needs proof. Retained source and private working worlds keep O(W) memory,
plus current delta/proof/index structures. Complexity is medium/high: source
reference lifetimes, failure recovery and session observability are difficult.
Schema 9 serialization can remain unchanged, but raw world APIs and current fence
contracts constrain migration. B alone is insufficient; it requires C or existing
proved transitions rather than merely longer-lived mutable state.

### C — event-local transactions with enforced invariant closure

An event receives read-only selected authority and staged writable rows; new records,
deletions, queue changes and allocators are explicit. Reads bind actual current IDs,
UTC and values. A freshly validated, exclusively held source establishes unchanged
facts; independent local predicates prove all changed relationships. Publication
detaches output rows and cannot leak mutable source/result aliases. This offers
O(K) work per event only if discovering/proving closure is also bounded or safely
amortized. The event's K can be large; Booking and publication need not be cheap.

A failed delta is discarded; prior logical commits survive. Ordering and exactly-once
finance remain explicit equations, not inferred from a change-set label. Save/load
still materializes a complete valid plain Schema 9 envelope and clears runtime
capabilities. Memory can be O(W+K+derived indexes); it is not constant-memory history.
Complexity is high across all domains, with greatest risk in missed indirect
dependencies, typed lineage, source aliases, diagnostic order and chronology.
B3B exposes these gaps and is **not** the required production proof.

### D — hybrid local transactions and strict isolation

Use C only for exact built-ins and explicitly supported inputs; retain the current
strict path for complex or unsupported events and strong isolation for callbacks.
Within a bounded, private working segment, a **separately audited pure built-in**
could execute strictly with its full copies/gate while other events use local
transactions. This preserves successor validity without requiring local proofs for
every domain at once. It must not silently admit a current fence: dispatch remains
a fence today, and changing its placement requires specific lifetime/replay and
observable-boundary evidence plus future contract approval.

Fences/returns retain full validation and detached commit in the proposed first
migration. Unknown handlers, custom providers, arbitrary stop callbacks, Booking,
publication and expiry continue to expose committed prefixes through their strong
boundaries. Local source ownership cannot survive a public yield/rebind. Failed
local admission falls back before effects; divergence recovers through the exact
strict reference and disables the optimization. Replay requires independently
audited absence of deferred/external effects, not a callable name.

Ordering, snapshots, Booking/finance outcomes and legacy routing stay identical.
Memory stays O(W+K+segment indexes), with strict/provider peaks retained at fences.
Complexity is higher than A but bounded by one event family at a time, lower risk
than converting all gameplay to C. It directly uses evidence that exact legacy
ownership works and callback consolidation does not. D is the strongest **design
direction**, not a proved implementation or guaranteed fast path for PH 1.0.

No Option E is recommended. Persistent trees, event-sourced rebuilds or external
history storage would introduce distinct persistence/migration problems without
evidence that bounded D is inadequate. AT-059 does not approve them.

Preserve package ownership: domain calculations stay in Aircraft Operations,
Booking/Demand and Scheduling; World State owns persistent construction, shape/
relationship validation and serialization; Simulation owns clock, generic event
transactions and lifetime orchestration; Stage1Session serializes public commands
and observations. Cross-package use does not relocate domain logic into game/utils.

## Provider and trust analysis

A fresh process-local registry inspection finds ten built-ins: four SHARED metadata
entries (NO_OP, Payment, Departure, Completion), five FENCE entries (Booking, weekly
publication, expiry, quarterly dispatch/publication), and strict market rotation.
Only three have domain local transition proofs; NO_OP has its kernel shortcut.
Flight schemas include 7/8/9, but actual flight support predicates reject the
quarterly operational marker. **Registration/schema support is not input certification.**
No world was constructed or event processed by this inventory.

| Boundary | Actual nested risks | Proposed treatment |
| --- | --- | --- |
| Exact built-in flight/payment handlers | Manifest/checkpoint/lineage, configuration/cost, ledger, queue and read-lookup factories | Admit only audited current call graph and complete local closure; unsupported input remains strict |
| Booking activation providers | Outer Demand provider input/snapshot; inner Shopping adapter input/snapshot; returned iterables and retained references | Preserve all current copies/diagnostics; custom providers never inherit a built-in fast path |
| Direct-service eligibility | Adapter invokes a secondary provider on its own input; Demand pack qualification can invoke another read on the caller | Include all invocations, type/deepcopy/iterator effects and exception timing; this defeated B2.6's shortcut |
| Ordinary eligibility/domain reads | Airport availability, access, connection state, publication membership and actual aircraft position | Selected immutable projections with proven sources; cross-package calls do not create shared utility authority |
| Reconciliation | Backend/publication clone even on no-change; rebuild obligations and schedule missing work | Keep staged atomicity; proving a no-change preflight is a separate optimization, not assumed free |
| Runtime hooks | Registry handlers, support/capture/validate/footprint/read-lookup callables, arbitrary stop callbacks | Identity/version and audited transitive effects; unknown hooks force strict committed boundaries |
| Session/GUI/persistence/extensions | Session.world exposes a mutable root; save/autosave/rebind and future plugins can retain inputs | Audit every alias/observation path; revoke capability before exposure; no trusted status for future extensions |

B2.6's apparently duplicate copies protect different callers. A final world gate
cannot undo a leaked source reference or restore an earlier exception diagnostic.
Changing an arbitrary mutable-input provider into a read-only provider could also
change when/how it fails. No such contract change is approved or proposed as an
automatic migration here. For initial D, retain current provider semantics intact.

## Validation policy proposal

| Boundary | Policy now / proposed first migration | Reason |
| --- | --- | --- |
| Game creation and enrollment | Comprehensive candidate validation | Establish all domain assumptions before local inheritance |
| Save/load | Comprehensive snapshots and detached candidate validation, previous-file safety, paused rebind | No persisted trust; cold external data cannot inherit runtime ownership |
| Explicit player transactions | Current full prepare/apply gates and copies | Mixed domains and stale UI facts; no local command proof is supplied |
| Eligible ordinary events | Currently strict quarterly gates; future local proof only under valid sealed source | Every successor valid immediately; no periodic-scan-only safety policy |
| Unsupported events/providers | Existing strict copies, gates and diagnostics | Unknown mutation closure or effects cannot be speculatively trusted |
| Quarterly publication | Preserve all four command gates, both command world copies, outer ordering/failure boundaries | Broad chronology/identity/carry-forward obligations and same-UTC Booking precedence |
| Segment flush, cooperative return, final clock gap | Keep full boundary validation and detached commit | Do not expose a candidate; changing UTC can change obligations even without handler writes |
| Recovery/divergence | Discard failed local writes; strict canonical recovery, validated prefix, explicit optimizer diagnostic | No invalid intermediate repair or loss of successful work |
| Development/testing | Independent strict/detailed full oracles at each transition plus whole-world/alias mutation checks | Avoid shared unchecked assumptions; timing oracle is separate from candidate production cost |

The local-proof safety argument must establish: valid entry; exclusive source
ownership for its entire lifetime; exact read/write/new/delete closure; immutable
unchanged authority; independent domain equations; complete primitive types and
shape; bounded alias-free detached outputs; exact queue/UTC/allocator progression;
and failure/prefix observational equivalence. B3B supplies partial evidence, not
all these premises. Until they are proved, preserve existing gates.

Advancing `simulation.time_utc` is itself a cross-domain write. Unchanged records
can acquire different validity at the new time: publication obligations, airport
availability, contracts and aircraft chronology must be included where applicable.
Canonical next-event selection alone is not proof of every time-dependent invariant.
A local closure that ignores those reads is incomplete; K is not guaranteed small.

## Long-horizon advancement and responsiveness

90x standard throughput allows **960 real seconds per game day** before overhead;
the 92.251s explicit-day result alone does not certify continuous pacing, source
growth, publication spikes or GUI responsiveness. The future Advance aspirations
are 1/7/30/90 days, distinct from continuous 90x. Date interpretation, cancellation
and meaningful-event semantics remain future design; Next Event stays exactly one.

At 50 aircraft × four sectors/day × 90 days, departure/completion alone require
**36,000 events**; quarterly dispatch and Booking/publication add more. One unchanged
10,000-event request cannot finish that workload. Maintain 100 same-UTC causal
generations and 10,000 processed/stale events across yields, flushes and callbacks.
Reset causal counts only on chronological progress. No hidden new requests may
bypass a blocked budget; current explicit correction/fresh retry is the safe
authorized continuation. A resumable automatic long-Advance coordinator, durable
target/provenance, cancellation and crash policy need separate decisions and
schema-first design if persisted. They are not granted by AT-058's menu aspirations.

Interrupted work restores the last valid complete-event snapshot, paused, with
remaining same-UTC events still pending. Never label that boundary fully resolved
through its UTC. The proposed transaction layer changes no booking horizon,
availability, quarter boundary or flight count and cannot skip events to meet a target.

GUI yield frequency is separate from throughput. Cap eight does not bound a long
Booking/publication/copy/validator unit in seconds. More frequent flushes improve
observation latency but increase global copies/gates. Preserve session serialization,
safe autosave/cancel and credit accounting; no pacing/offline implementation or
unspecified multithreading is authorized. Report unit p95/max and lag as well as
engine day time in any future experiment.

## Quantitative performance potential

These are **structural estimates**, not measured speedups. Let n be ordinary
mutating events in a measured segment set, k successfully proved local events,
g owned segments actually needed, p preview copies, and a additional comprehensive
source gates required when exclusive validity cannot be inherited at reacquisition.
Exclude nested domain/
provider/reconciliation work unless explicitly counted. Normal strict cost is
approximately 2n+p whole-world runtime copies and n+entry/gap full gates.

| Option | Whole-world copies | Comprehensive gates | History dependence / memory / failure |
| --- | --- | --- | --- |
| A | 2/event for ordinary strict mutation; roughly 2/group for existing eligible sharing | 1/result for strict; full entry/gap/flush retained | O(EW), plus manifests/providers; multiple O(W) allocations; strict recovery cost |
| B without C | About 2g+p if rollback is staged; otherwise per-event rollback copies reappear | n+entry/flush/gap, potentially more than A | Still O(EW) validation; O(W+delta); full replay from valid prefix on failed speculation |
| C with physical per-event world commits retained | Up to 2/event despite O(K) proof | Local checks plus currently mandatory full commits | Copy bottleneck remains; record-detached commit would require a further contract/lifetime proof |
| D, conditional first migration | 2(n-k)+2g+p, plus unchanged nested copies | (n-k)+g+entry/gap+a, plus local proofs | Global work O((n-k+g+a)W), plus per-segment Book index scans and O(sum K); O(W+K+indexes), provider peaks retained; conservative replay can duplicate work |

For the Booking-heavy 13-event vector, **Completion-only k=4, p=1** yields
**19+2g runtime copies and 11+g+a full gates**, versus 27/15. Illustrations with
the **unproved optimistic assumption a=0**:
g=1 → 21/12; g=2 → 23/13; g=4 → 27/15. Add unchanged eight provider and two
reconciliation deepcopies to each copy total. At g=4 no count saving remains;
local proof/index costs can make it worse. If each public return requires a fresh
source gate, a can be at least g-1; g=2 would then require 14 gates, g=4 at least 18.
Extra ownership bootstrap/alias scans must also be counted. Raw session references
prevent simply assuming a=0. These arithmetic results were checked
by the lightweight inventory, not by executing the candidate architecture.

Current dispatch fences and unsupported quarterly flight inputs prevent assuming
g=1 or g=2. A segment containing twelve ordinary events cannot fit an eight-event
cap; actual event trace, fences, pause/yield points and admission determine g.
Admitting audited strict built-ins inside private segments could improve g, but
requires its own ownership/replay proof and contract approval. No timing trace in
the retained counts proves that admission is valid or that ideal groups exist.

Extending local proofs to both flight phases would increase k, but is not part of
the proposed first experiment. Booking preview/replay, provider isolation, dispatch,
reconciliation and quarterly publication may still dominate. Their measured
inclusive profile totals do not yield an additive quiet-time saving estimate.
B3B's 0.206+0.054 versus 0.118 seconds is only a small-fixture comparison and cannot
price removed gates on the 42,923-row world. A realistic quantitative percentage
or 50-aircraft/90-day guarantee is **not available**.

## Proposed single bounded proof-of-concept

Propose a **test-only owned-segment quarterly Completion experiment**, not another
whole-world snapshot certificate and not production integration. Central hypothesis:
exclusive detached source lifetime plus complete local Completion closure reduces
repeated global work over a real event stream without changing observable prefixes.

1. Capture a fresh valid detached source inside a private test owner, expose only
   protected selected read projections and staged delta outputs, and expire all
   capabilities at flush. Derive manifest quantities/lineage and finance/result
   equations independently of handler constructors. Prove unchanged authority by
   inaccessible mutation paths, not object identity/revisions or a per-event full
   typed scan. Audit all raw source, alias, callback and session-like observation paths.
2. Permit local transactions only for real quarterly Completion. All other events
   retain their full strict execution. To test segment amortization, separately
   audit whether exact built-in dispatch/departure can execute strictly **inside**
   the private segment without external observations/effects. Do not silently bypass
   the current dispatch fence. If that cannot be proved in the isolated harness,
   keep its fence and accept the negative performance result. Booking/publication,
   arbitrary hooks and returns remain strong fences. Cap segments at eight events.
3. Compare against independent unmodified strict execution and detailed full
   validation after every intermediate event, flush, failure and saved prefix.
   Compare complete worlds, queues, manifest lineage, journals, diagnostics, IDs,
   failure results and retry outcomes, not only hashes. Legacy controls retain their
   original authority. Reference scans run outside timed candidate samples; separately
   report shadow/oracle overhead rather than presenting it as optimized engine cost.
4. Reuse the retained Booking-heavy source/13-event target where accessible; do not
   prune its 42,923 obligations. Add one operational quarterly workload through
   public scenario/acquisition/route/planning/Booking paths, with several actual
   aircraft and enough naturally consecutive Completions to exercise multiple
   valid intermediate states. Report fixture setup separately. A small operational
   fixture does not certify 50 aircraft. Use actual chronology, not fabricated
   terminal results or artificially reordered events.
5. Test each write/alias fault, source mutation, wrong dependency/event/UTC, bool/float
   lineage, omitted Booking, extra/deleted/reordered queue work, missing/duplicate
   finance/results, retained projections, outside-footprint mutation and foreign/
   expired ownership. Inject faults before and after allocator, journal, account,
   aircraft, result and event lifecycle work. Test failure after successful local
   and strict prefixes, strict replay divergence, same-UTC budget accounting,
   publication fences, explicit retry, cancellation/yield and paused save/load.
6. Alternate at least three fresh-process quiet strict/candidate pairs serially,
   identical source/target/budgets, on each workload. Time the **whole advancement
   command**, including entry/flush, strict fallback, indexes and nested provider/
   reconciliation costs. Separately count copies, full gates, globally visited rows,
   changed/read records, segment sizes/fences, rebuilds/retries, peak RSS and retained
   memory. Count closure discovery and ownership initialization; do not hide them
   outside candidate timing. Verify complete results after timing and measure
   callback/step p95/max where sample size supports it.

Correctness acceptance is zero outcome/diagnostic/prefix mismatch and rejection of
all adversarial violations without source/committed alias leaks. Performance
acceptance requires a reproducible end-to-end reduction beyond paired noise on
both workloads, fewer dominant global copies/scans, no unexplained memory or safe-unit
latency regression, and no weaker fences/budgets. If singleton/fence topology yields
no benefit on the Booking-heavy stream, classify it as inadequate for that bottleneck
even if consecutive Completions improve. No percentage threshold is invented before
the protocol's control variability is established.

Stop the prototype for incomplete invariant closure, a required per-event global
source/protected scan, unsafe raw exposure, different provider diagnostics, lost
prefix, double finance, any reference disagreement or equivalent/worse whole-command
cost. Preserve negative evidence; no automatic second optimization, production
integration or active/history redesign follows. This proposed experiment itself
requires separate authorization. No POC code or workload is constructed in B3C.

## Decision gate and migration risks

1. **Retain strict/shared long-term?** Retain its strict oracle/fallback and established
   compatible paths, but do not accept blanket quarterly E×W processing as the
   long-term scaling design without evidence. Current production stays unchanged.
2. **Essential versus replaceable?** Essential: successor validity, alias-safe authority,
   exact chronology/budgets, financial/Booking lineage, prefix recovery and safe saves.
   Physical per-event world copying/global checking can be replaced only by proven
   ownership/local invariants; current contracted boundaries cannot simply disappear.
3. **Strongest alternative?** D: narrowly admitted C transactions with B amortization
   and strict callback/complex fences. Existing legacy ownership supports the idea;
   B2.6 and B3B establish limits rather than production readiness.
4. **Smallest disproof?** The Completion-only owned-segment experiment above. One
   alias/closure/prefix mismatch, or no whole-command benefit after real fences and
   lookup costs, can reject the central hypothesis without rewriting other domains.
5. **Realistic improvement?** Removing repeated O(W) work from selected events is
   structurally plausible; isolated count estimates above bound the opportunity.
   Singleton-heavy traces or Booking/provider dominance may erase it. No defensible
   percentage, large-fleet throughput or 90-day target certification exists.
6. **Principal risks?** Missed live dependencies, mutable session/source escape,
   proof/model sharing, stale indexes, event/allocator history, exact diagnostic
   order, failure-prefix recovery, custom callbacks and cross-quarter chronology.
   Preserve legacy mode selection and saved record meaning; identical Schema 9
   JSON alone does not prove runtime compatibility. Candidate indexes are runtime-only,
   revoked at rebind; new persisted coordinator/cache/history fields would need
   separate schema-first approval.
7. **Begin implementation?** No production implementation. Seek separate authorization
   only for the bounded test-only experiment after its closure/admission protocol is
   reviewable. AT-059 remains Proposed. Longer-request automatic continuation and
   raw-world API/lifetime changes remain explicit unresolved design decisions.

Future congestion/delays fit explicit event-local resource/schedule deltas better
than unrestricted world mutation, but can greatly expand closure across aircraft,
airport resources, bookings and next-leg events. Large/unsupported operations should
remain strict until their contracts exist. No runway queue, delay economics or
published-schedule mutation behaviour is invented or approved by this preference.

## Review verification

Only this report, Current Development Status, Decision Register and documentation
index change. Fresh process-local inventory confirms ten current handler contracts
without constructing a world, scheduling events or altering files. Its first scratch
invocation needed the repository root on sys.path; the corrected read-only invocation
passes, exit 0. The arithmetic is hypothetical, not a new benchmark. No expensive
benchmark, gameplay test suite, production prototype or schema change is run.
Documentation checks pass **362 local links / 77 heading targets**, zero errors.
Production/test/schema/template diffs against baseline are empty; whitespace check
passes. No application compilation is needed for the documentation-only retained
scope. Exact four-file scope and actual evidence are recorded in
[Current Development Status](Current%20Development%20Status.md).

Four lightweight diagnostic scripts/logs are preserved with SHA-verified copies in
local temporary archive `airline-tycoon-b3c-8a0a765-5067fb2449db4b3b8ae5776de6e67c6a`.
The verified task scratch directory was removed; no generated evidence is staged.
