# Safe Quarterly Transaction Architecture Feasibility

## Executive summary

Stage **3G-B3A**, design and isolated proofs only, **2026-10-13**. Approved baseline
`3df1eb125a934673378474c00fd760786b0e98eb` matched HEAD, upstream, freshly fetched
origin/master and live remote master; divergence 0/0, tracked tree/index clean,
only `.venv/` untracked, stashes empty. No production engine, Schema 9, template,
save format, history storage, pacing, offline or activation change is made.

There is a technically credible **conditional** route to reducing whole-world work:
**C, transaction-local certification under enforced ownership**, followed only if
proved by **A, bounded eligible event grouping**. Certification can address complete
graph scans; grouping can amortize candidate/commit copies. Neither is a ready-made
quarterly optimization. Existing legacy certificates expressly exclude quarterly
careers, and B2.6 disproved provider-identity-only isolation consolidation.

**B, copy-on-write**, needs substantially broader mutation and publication design.
Shallow copying is unsafe. Reusing the existing read/write capsules inside an
already detached candidate is more credible than sharing mutable committed worlds.
That does not eliminate the two outer whole-world copies by itself.

Eleven isolated proofs use real quarterly state, existing ownership primitives and
independent strict/full-world references. They establish a concrete blocker:
strict quarterly Completion succeeds, but the same handler on the current protected
read/write capsule fails manifest lineage checks. B2.3 requires exact plain dict
lineage; read-only views are not dicts. Detached selected read projections preserve
types and isolation. A lexical test-only read-projection bridge then executes actual
Completion with an exact strict/full-world successor and safe retained projections.
That observation is **not a transition certificate** and does not remove any gate.

Recommend one separately authorized **test-only Completion certification shadow
experiment**, replacing the lexical bridge with explicit selected-ID-bound reads
and proving the full dependency closure against strict execution. Retain every
production gate/copy and all callbacks'
isolation. Do not introduce a production certificate/dispatcher API or enable batching.
This is enough justification for a bounded proof experiment, **not production gate
removal or migration**. AT-059 remains Proposed. Defer performance certification of
the 90-day aspiration until representative fleet/history/budget measurements exist.

## Authority and reviewed evidence

[AGENTS.md](../../AGENTS.md) governs scope and verification. Persistent authority is
[Schema 9](Stage%201%20State%20Schema.md), then
[template_reference.txt](../../Data/Templates/template_reference.txt).
[foldertree.txt](../../Data/Templates/foldertree.txt) is selective placement guidance.
Current code and [status](Current%20Development%20Status.md) supersede older Serena
memory checkpoints; Serena was activated and targeted symbols inspected.

Relevant behavior and evidence:

- [B2.5 investigation and B2.6 follow-up](Quarterly%20Transaction%20Copying%20and%20Validation%20Investigation.md),
  [runtime benchmarks](Quarterly%20Runtime%20Benchmarking.md),
  [active/history feasibility](Active%20State%20and%20Certified%20History%20Feasibility.md).
- [Quarterly backend contract](Quarterly%20Backend%20Consumer%20Cutover.md),
  [shared publication](Quarterly%20Shared%20Publication.md),
  [boundary recovery](Quarterly%20Boundary%20Orchestration.md).
- [Shared candidate infrastructure](Runtime%20Shared%20Candidate%20Infrastructure.md),
  [ownership](Runtime%20Candidate%20Ownership.md),
  [local proofs](Runtime%20Local%20Certified%20Proofs.md),
  [causal accounting](Runtime%20Causal%20Generation%20Accounting.md).
- [Save architecture](Game%20State%20%26%20Save%20Architecture.md),
  [save specification](Game%20State%20%26%20Save%20Technical%20Specification.md),
  [Decision Register](Decision%20Register.md), especially AT-058/059/060/062.

The user-named B3A transaction design stage does not implement the separately
planned AT-058 pacing/offline work. Roadmap names do not confer that scope.

## Current architecture and measurement baseline

### Measured facts

| Observation | Value | Evidence category |
| --- | --- | --- |
| One-day actual Advance | 13 events: four dispatch, four departure, four completion, one Booking | Retained complete production-session result |
| Runtime clones | 27: 13 event candidates + 13 detached commits + Booking preview | Instrumented count reconciled with source |
| Full validations | 15: request entry + 13 event results + final clock gap | Instrumented count reconciled with source |
| Additional world deepcopies | Eight provider isolation + two reconciliation | Source/caller accounting; B2.6 confirms four provider copies per pass |
| Quiet one-day baseline | Median 92.251s, range 89.620–93.369s | Three retained fresh-process quiet controls; not a B3A benchmark |
| Quiet maximum peak working set | 1,083.984 MiB | Lifetime process high-water mark, not live allocation size |
| Full validation | 115.501s inclusive; root residual 13.377s exclusive | Instrumented, includes child checks |
| Plain authority / Booking graph | 57.163s / 23.455s exclusive | Instrumented child categories |
| Hooked deepcopy / runtime clone | 95.860s / 29.557s exclusive | Instrumented disjoint categories, sum 125.417s |
| Baseline provider-only pass | Four world copies, 7.918470s copy / 8.179789s total, 552.750 MiB peak | One B2.6 instrumented component, zero events; not quiet Advance |

The full instrumented command took 263.729s, versus the quiet controls near 92s.
Do not subtract instrumented seconds from quiet latency or sum nested inclusive
validation/shopping/allocation rows. The late-import publication reconciliation
deepcopy is absent from hooked copy totals; cProfile records 9.328s cumulative.
Complete source/result hashes and environment are in the benchmark report.
No new expensive fixture construction or advancement benchmark is performed here.

### Lifecycle and ownership map

| Phase | Implemented boundary and safety purpose | Consolidation constraint |
| --- | --- | --- |
| Public request | [Session](../../app/session.py) freezes target and exclusive owner; [resolver](../../game/simulation/resolver.py) selects shared facade | Shared facade does not grant quarterly certificates |
| Entry / reconciliation | Full source gate, backend and outstanding publication reconstruction, derived heap | Both reconcilers currently stage whole worlds even when unchanged; changing them is outside this design experiment |
| Selection | [Kernel](../../game/simulation/kernel.py) orders UTC, mandatory publication barrier, priority/sequence/ID | Must reselect after generated children; precomputed event lists are not authority |
| Event candidate | Whole detached runtime clone; copied selected event and private token | Separates original committed source from handler mutation/failure |
| Domain execution | Dispatch materialization; manifest/departure; completion/settlement; Booking checkpoint | Every intermediate completed event must be valid, not merely the batch end |
| Provider / eligibility | Booking preview and replay each use inner input/before-image, outer input/before-image; direct-service and pack eligibility may call provider again | B2.6 shows outer and inner scopes differ. Keep all eight provider copies and result/error checks |
| Generated events | Allocate deterministic IDs/order; archive parent; insert children into canonical heap | Charge actual committed same-UTC generation and processed/stale history, not speculative work |
| Validation / commit | Full successor validation; second whole-world clone then no-yield root replacement | Result validity and reference detachment are distinct responsibilities |
| Failure / retry | Keep successful prefix and failed pending event. Publication commits only a separate validated pause/diagnostic fence. Explicit retry observes fresh facts | Whole-request rollback and automatic retry change behavior |
| Final gap | Change target UTC, full validate, restore last committed UTC on failure | Event completion and fully resolved target are different |
| Save / Load | Full completed-boundary snapshot; atomic file replacement; separate validated paused load world, previous valid file recovery | No candidate, capability or cached proof is save authority |

Current quarterly dispatch/publication are fences; Booking is strict. In
[flight transition validation](../../game/world_state/flight_transition_validation.py)
both support predicates explicitly reject quarterly mode. All 13 benchmark events
therefore remain strict through the shared facade. Publication-containing days also
include four nested command gates and two command copies, plus outer event work;
they are absent from this day's 27/15, not removable by extrapolation.

## Candidate A — bounded event batching

**Conditional feasibility; unsafe for arbitrary adjacent events.** Start from a
fully validated source and detached working world. Select only identity-certified,
supported pure transitions, prove each event successor, insert children and stop
at cap, fence, unsupported/stale input, pause, target or requested boundary.
Full final validation and detached commit remain. No uncommitted candidate crosses
a cooperative return, presentation read, management command or save.

Three distinct checkpoint models must not be conflated:

1. **Commit only batch end.** A later failure discards speculation, then strictly
   reselects/replays the successful prefix. This matches existing recovery only
   for certified deterministic handlers without external/deferred effects.
   Whole-batch rollback without replay loses observable progress.
2. **Commit an intermediate detached snapshot and continue without yielding.**
   In principle retain one working world and detach each committed successor:
   roughly k+1 whole copies for k events, instead of 2k. Genuine per-event
   predecessor evidence, local proof expiry and candidate/source relationship must
   be rebuilt. This is a transaction-organization change, not the existing shared
   algorithm; no arbitrary handler may retain a reference into reused working state.
3. **Yield/save/allow commands after every intermediate commit.** Drop working
   candidate/proofs before each return. Under current contracts, the next step
   starts from a new isolated candidate; restoring per-event visibility removes
   much of the proposed sharing. Retaining a candidate across the return violates
   the existing lifetime contract. An undo log or immutable root/checkpoint store
   would be a separate major design, not free rollback.

Batching can change externally visible progress granularity, callback/cancellation
latency, saved prefix choice and event-requested pause behavior even if final worlds
match. Arbitrary stop callbacks stay strict. A publication failure must leave its
strict prefix, original obligation and dependent consumers intact; it cannot roll
back earlier events or defer its fence to an unrelated batch end. Booking, dispatch,
publication and expiry remain strict/fences in any first experiment.

Both limits remain request-wide across batch flushes/yields. Default same-time
causal ceiling **100** and the existing explicit Advance **10,000** exception are
preserved; processed/stale ceiling **10,000** is unchanged. Later-UTC children do
not consume the parent's causal count. The generating event stays committed at a
budget stop. Recovery discards speculative counters and reconstructs committed
progress; it cannot secretly renew a budget. Explicit new retry remains separate.

## Candidate B — copy-on-write transaction state

**Major redesign for cross-world sharing; bounded ownership reuse is credible
inside an already detached world.** Shallow root/table copies share nested mutable
lineage, lists and journal/manifest records. A failure cannot roll back those writes.
The isolated shallow-copy proof changes the original itinerary and fails independent
Schema 9 validation.

A safe design needs recursively protected reads, explicit writable row/key footprints,
path copying of every modified ancestor, new/deleted key checks, output alias checks,
and publication that never shares mutable objects with old worlds or retained callbacks.
Wide itinerary/Booking tables still require expensive table copies unless a persistent
map/overlay is introduced. Overlay/proxy nodes, memo tables, lookup indirection,
fragmentation and materialization can shift cost and increase peak memory.

Existing [capsules](../../game/simulation/candidate_ownership.py) copy simulation,
allocator and approved records while exposing protected rows through guarded views.
They still begin within a complete detached candidate and finish with full validation
and detached publication. They do not implement copy-on-write committed worlds.
Readonly roots must not be trusted merely because their identity is unchanged:
their backing graph must be genuinely validated and inaccessible to ordinary writes.

Provider input, direct-service checks, lazy iteration/output validation, retained
references and exception paths all belong to the mutation footprint. B2.6 is a
counterexample to covering only the primary callback. Keep provider isolation;
do not send raw shared authority to custom providers. A guarded view may also change
exact type behavior, as the quarterly Completion probe demonstrates.

Serialization must still produce the complete canonical plain Schema 9 world with
exact ints/strings, no caches/proxies/certificates. Load fully validates a separate
candidate; failure preserves active world and valid files. Logical unchanged JSON
does not prove heap isolation or permit mutable sharing across snapshots. No new
save field/version or immutable-history store is assumed or approved here.

## Candidate C — transaction-local certification

**Strongest conditional safety argument; quarterly domain proof still missing.**
Use actual complete source validation, enforced protected ownership, genuine typed
before-event facts, explicit affected dependency closure, and an exact local transition
proof. The induction is: valid predecessor + unchanged protected dependencies +
correct typed affected successor implies valid intermediate world. Final full-world
validation and independent strict/shadow selection remain safety/reference boundaries.

Validity is not a revision number, object identity, cached boolean or digest.
Identity binds a genuine capability to its source; it does not establish correctness.
Certification expires after the synchronous transition, failure, commit, boundary
return, management change, fence, Save/Load or rebind. Protected validity can be
inherited within a live bounded candidate only while write isolation and all permitted
transitions maintain it. No trusted certificate is stored in the career.

Corruption before entry is caught by complete validation. During owned execution,
unapproved protected writes are denied; writable outputs require exact shapes/types,
alias checks and all indirect invariants. Corruption introduced across a cooperative
return requires fresh source proof or an explicitly approved enforceable committed
ownership boundary. A caller-supplied refresh/revision claim is insufficient. If
that boundary is not proved, include another complete source gate in the cost model.
Final global validation detects residual corruption but cannot excuse a bad
intermediate state later repaired by another event.

For quarterly Completion, required closure includes published plan/revision/slot and
service/date identity; flight and frozen operation; actual aircraft readiness/counters;
manifest Booking/itinerary/checkpoint/sale witnesses; carried passengers and finance
source IDs; exact settlement journal/account/airline changes; event history/pending
removal; UTC/revision/cursor/allocator invariants. Bookings/itineraries remain protected
live obligations. An immutable sale is not permission to archive unflown liability.

The same handler/domain constructors must produce outcomes. The independent oracle
is strict kernel execution plus full-world validation and exact complete-world
comparison, including money, events, witnesses, history and types. Local proof code
must not compare a candidate to itself or silently repair a read projection.

## Isolated feasibility proofs

[Eleven test-only proofs](../../tests/test_quarterly_transaction_feasibility.py) are
invoked only by explicit unittest execution. Normal app/game modules do not import
this module. Synthetic event handlers use a **local** registry, never production
registration/certification. State construction uses temporary scenario files and
fresh in-memory worlds, never player Saves.

Actual quarterly source: valid published services, **1,176 Booking/itinerary pairs**,
one active flight after processing through `2027-01-02T01:00:00Z`, next real Completion
at `2027-01-02T02:40:00Z`. Strict execution succeeds and independently validates.
The existing generic completion footprint is used solely as an isolation probe;
it does not override the quarterly support exclusion or mint a flight certificate.

| Proof | Result and scope |
| --- | --- |
| A: discard batch after second synthetic event fails | Loses first completed event versus strict reference; whole rollback unsafe |
| A: discard speculation and strictly reselect pure synthetic prefix | Exact processing result, diagnostic, IDs and complete world match strict control; algorithmic proof only, not custom-handler eligibility |
| A: replay uncertified external effect | Effect occurs twice; local registration remains non-shareable. Final world equality cannot certify replay purity |
| B: shallow world copy, nested lineage mutation | Original changes; independent full validator rejects boolean revision |
| B/C: guarded nested reads | Booking lineage, published slot list and finance writes reject; detached working world remains identical |
| C: selected plain read projection | Deepcopy of guarded lineage is detached exact dict; valid integer types preserved. True/False, float/string/null, negative/zero revision reject; source remains identical |
| C: JSON/alias checks alone | Ownership construction accepts JSON-compatible bool lineage, but independent domain validation rejects; ownership is not domain certification |
| C: actual Completion through current capsule | Fails `HANDLER_FAILED` / `Booking ... does not match exact flight lineage`; private source unchanged. Strict succeeds. Exact dict predicate rejects protected itinerary lineage views |
| C: foreign/expired predecessor | Equal-value foreign world and closed capability reject; identity/lifetime bind access, not correctness |
| C: lexical plain-read bridge with actual Completion | Test-only guarded getter mock returns detached plain lineage projections. Actual handler completes; full validator and complete world match independent strict execution. Mutation of retained projections after closure does not change source/result/manifest/journal |
| C: malformed source projection | Source bool revision is rejected by full validator; deepcopy preserves bool and the lineage predicate rejects it, without repair |

Standalone bridge-inclusive proof run: **11 PASS / 7.785s**. Earlier nine-proof
run: **9 PASS / 7.115s**. An initial module import exposed
the imported backend TestCase to unittest discovery, producing 50 extra backend
regression passes and one proof-call error (missing explicit `shadow=False`). The
fixture import now uses its module alias, and the private contract call is corrected.
The initial 59-test run is not reported as a passing proof suite. Focused combined
verification is recorded in Current Development Status.

The bridge is a lexical `unittest.mock.patch` of the guarded read getter only for
`quarterly_lineage` values already represented by the genuine protected view.
The original getter is asserted restored. One diagnostic invocation creates **198**
fresh projections; this is a count for that actual handler/source, not retained
authority or a new cache. The test mutates retained projections after owner closure
and independently validates the unchanged exact strict successor. The mock is not
a proposed global production getter rule: a real proof requires selected-ID/source/
lifetime binding and an audited dependency closure.

These proofs establish ownership/failure counterexamples and an actual read-bridge
success under the full oracle. They do **not** establish a new quarterly transition
certificate, production COW, batching
performance, publication-crossing safety or bounded GUI latency. No production gate
is removed and no new production API is added.

## Safety contract comparison

| Invariant | A: bounded eligible grouping | B: COW | C: local certification |
| --- | --- | --- | --- |
| Complete authority / intermediate validity | Individually valid events plus full detached flush | Enforce recursive ownership and complete materialization; shallow copy fails | Prove affected closure against valid source and immutable protected dependencies |
| Booking / itinerary | Booking remains strict fence; no preview/replay reuse | Protect both sides, inventory and lazy callback references | Exact B2.3 lineage types/relations; typed projections must not weaken canonical validators |
| Finance | Replay cannot duplicate ticket/settlement effects | Row/key isolation must preserve account/journal links | Balanced journals, source IDs, liabilities, revenue/costs and exact account deltas |
| Aircraft / schedules / manifests | Same actual handler and chronological selection | Guard nested operation/manifest/slot rows | Actual position/readiness, counters, locked carriage, current publication membership |
| Quarterly publication | Strict four-gate/two-copy command and separate failure fence | No shared mutable revision or obligation | No certificate crosses publication; fresh full proof after it |
| Event order / children | Dynamic heap insertion after each successor; no static vector | Protect selected row/queue topology | Sealed canonical selection and exact allocator/cursor/history deltas |
| Same-time / processed budgets | Request-wide counters survive all flushes; strict prefix at stop | No hidden continuation through new overlay roots | Count committed transitions, not discarded speculation; 100/default and 10,000 limits unchanged |
| Failure / retry | Strict successful-prefix recovery, optimizer divergence disables optimization | Discard unpublished delta; earlier committed prefix survives | Expire proof; fresh exact witnesses, strict retry and diagnostics |
| Save / interruption | No candidate across return; safe prefix may have equal-UTC pending work | Complete plain snapshot and detached paused candidate Load | No serialized certificates; full Save/Load trust-boundary checks |
| Legacy compatibility | Unsupported/custom/stale/fence paths strict | No silent conversion of legacy state or writers | Separate explicit quarterly support/version; existing legacy certificates unchanged |

Ownership/type/cursor/selected transition properties are locally testable. Whole
dependency completeness, cross-quarter chronology, publication/Booking barriers,
finance/carriage integration, strict-prefix recovery, interruptions/management,
budgets and Save/Load/rebind need end-to-end adversarial differential tests. Neither
local row equality nor final hash alone proves all intermediate/failure behavior.

### Contracts needing explicit approval before production changes

- Quarterly Schema 9 currently mandates strict flight validation and excludes
  legacy certificate inheritance. New quarterly certification needs separately
  approved supported inputs/proof/version and a precise behavioral contract update.
  No such amendment or persisted field is made here.
- Reusing candidate/proof across commit/return, sharing mutable committed roots,
  changing observable partial progress or removing final full checks needs explicit
  lifetime/publication/recovery approval. The present design does not grant it.
- Booking/publication/provider boundaries, four publication gates/two copies,
  legacy writers, save rejection policy and budgets are retained. Offline provenance
  and longer-request continuation remain AT-058 work, not an automatic consequence.

## Performance potential and limitations

All avoidance estimates below are theoretical. Let k be certified events in one
eligible group, and g the number of groups; strict fences are outside those groups.

| Candidate | Potential avoidance | Mandatory/additional work and worst failure |
| --- | --- | --- |
| A, end-only detached group | 2k → 2 outer copies; k result scans → one final full scan **only after** complete local certification | Entry/final/gap/load; local proof per event; strict fences/provider copies. Failure may perform k speculative transitions plus up to k strict replay transitions; shadow adds a full strict reference world and per-prefix gates |
| A, intermediate commits without returns | 2k → approximately k+1 copies if independent local predecessor capture replaces staging copies | k detached commits remain; validity and alias proof per event; callback/return forces discard/restart. New organization and retained-reference audit required |
| B | Potentially copy changed records/ancestor paths instead of full staging world | Full publication/materialization may still copy all data; overlays, wide tables, view memo and rollback metadata may cost more than saved copies. Failed deltas discarded, no escaped aliases |
| C | Replace selected full scans with typed local closure proofs within owned lifetime | Fresh complete entry, final/gap and Save/Load remain. Read projection, manifest/index checks and proof/capability work add cost; missing closure invalidates approach. Failure falls back to strict reference |

For the benchmark's eight departure/completion events, an **optimistic illustration**
with four eligible two-event groups would change runtime copies **27 → 19** and
full gates **15 → 11**, keeping five strict dispatch/Booking events, preview and
all ten additional provider/reconciliation copies. This assumes both quarterly flight
transitions are genuinely certified, existing entry validity can safely be inherited,
and no extra source gates are needed. It is not a measured grouping or a B3A result.
Four dispatch fences prevent claiming a single eight-flight group. Singleton groups
offer no copy/full-scan saving; Booking, pause, stale work or additional fences can
reduce the opportunity. Source inspection confirms the first retained pending head
is dispatch at `2026-10-02T03:10:00Z`, followed by equal-UTC departure, with zero active
operations; no advancement was run to fabricate a new complete grouping trace.

If fresh full source validation is required at each of those four groups, gates
become **15**, not 11. More singleton groups plus extra entry checks can exceed
current validation work. Certification without grouping may replace domain scans,
but mandatory final validation of a singleton group still traverses the world.
Certification and batching are therefore complementary, not independent promised gains.

Measured runtime-codec copy exclusive cost is 29.557s of the 263.729s instrumented
run. Avoiding some of it cannot remove the 95.860s hooked deepcopy category or the
115.501s inclusive validation category. Even broad flight certification leaves the
provider-heavy daily Booking fence, reconciliation and final trust-boundary work.
Do not convert diagnostic fractions into predicted quiet seconds or a speedup ratio.
The tiny projection proof does not benchmark a complete manifest or certificate.

Copy reduction may lower transient trees/GC, but C adds witnesses/views/projections,
A shadow holds an independent whole reference and B adds overlay/path metadata.
Lifetime peak is not retained memory. Failure/replay is the worst-case latency path;
count-bounded work alone does not establish responsive callbacks on an aged world.
Use representative 1/10/50-aircraft, aged-booking, publication-crossing and interrupted
scenarios before certifying capacity. No 50-aircraft or 90-day result is claimed.

## Recommended bounded next experiment

**C: one test-only quarterly Completion shadow proof**, before any production
optimization. Boundary: one selected actual Completion at the canonical head,
with a fully validated genuine predecessor, detached private working candidate,
protected unchanged state and independent strict full-world successor. No grouping,
production contract registration, new dispatcher API or actual gate/copy removal.

Likely ownership: World State defines quarter-specific typed transition witnesses
and validation; Aircraft Operations owns manifest/settlement constructors; Simulation
owns generic capability lifetime/selection. Test-only harness code initially stays
in tests. A later production proposal must keep these package boundaries; cross-package
use does not make a domain helper `game/utils` code.

Exact experiment obligations:

1. Derive the actual completion read/write footprint and indirect invariant closure
   from Schema 9 and all domain predicates. Audit every callback and helper read,
   including manifests/checkpoints/publication and finance; do not copy a legacy
   version label or disable the quarterly support exclusion.
2. Replace the lexical mock with **selected detached plain projections**
   bound to the genuine validated source and actual selected IDs. Preserve original
   ints/strings, shapes and diagnostics. No bool/float coercion, arbitrary Mapping
   admission or global validator relaxation. Projection mutation/retention cannot
   change working or committed world, and malformed source rejects before projection.
3. Execute the unchanged actual Completion against the isolated capability; prove
   exact typed outputs, unchanged protected state, selected event lifecycle, manifest/
   finance equations and output aliases. Close all capabilities on every exit.
4. Compare strict and shadow complete worlds/results after this single event, plus
   independent full validation. Mutation cases include both itinerary/flight sides,
   extra/missing fields, True/False/float/string/null, unrelated account/config/history
   corruption, protected writes, footprint overflow, selected-row replacement,
   late dependency change, forged/stale capability, exception and retained-reference
   mutation. Verify failure preserves exact source and diagnostic, and retry equals
   fresh control. Include paused Save/Load/rebind and legacy exclusion controls.
5. Reuse the retained Booking-heavy fixture and identify a genuine upcoming Completion
   through ordinary strict processing only as needed; record setup separately.
   Alternate fresh-process quiet strict and shadow samples serially, identical UTC,
   budgets/source hashes, no concurrent tests. Separately time full validation,
   projection/witness/proof/alias work and allocations. Capture peak and retained
   memory and all complete hashes. Shadow necessarily retains the full oracle;
   its command time is overhead evidence, not an optimized speedup benchmark.

Acceptance: actual Completion succeeds under protected ownership and matches the
independent strict/full-world reference for every supported case; adversarial input,
source corruption and retained references are rejected safely; no production/schema
change is present; local proof/projection cost is reproducibly smaller than the
repeated global work it would replace without material memory growth. State exactly
which global checks remain. This is a **feasibility acceptance**, not authority to
remove gates. The subsequent production experiment would need its own contract
approval and paired end-to-end improvement/rollback gate.

Stop/revert test-only prototype if selected reads require unsafe raw source exposure,
type weakening, provider isolation removal, persisted trust, broad history migration,
or incomplete dependency closure; if reference outcomes/diagnostics differ; or if
complete proof is as expensive as the full scans it would replace. Retain honest
negative evidence. No automatic second experiment or full migration follows.

## Decision gate answers

1. **Credible route to substantially less whole-world work?** Yes, conditionally:
   enforced local certification plus eligible bounded groups can amortize scans and
   copies. Neither the magnitude nor large-fleet throughput is demonstrated. Current
   singleton/fence-heavy topology and provider costs materially constrain benefit.
2. **Strongest safety argument?** C, using real full source proof, sealed ownership,
   typed closure and independent strict/full-world oracle. A depends on that proof;
   B requires a broader physical-state redesign.
3. **Hardest contract?** Preserve the exact strict successful chronological prefix,
   including publication failure fences, budgets and observable save/return boundaries,
   while proving every intermediate state. Failure-after-success is not whole-request
   atomic rollback. Protected validity across ownership/lifetime changes is closely related.
4. **Missing evidence?** A working quarter-specific Completion read/proof bridge,
   complete invariant closure, callback/retention audit, safe entry-proof reuse,
   actual eligible-group trace, repeated quiet proof/command costs and representative
   history/fleet/failure/publication/Save-Load scenarios.
5. **Bounded implementation experiment justified?** Yes for the test-only shadow
   experiment above; **no** for production gate/copy removal yet. This report proposes
   scope and does not authorize that future experiment or change existing support.
6. **90-day target?** Keep it as an aspiration, **defer certification and any numerical
   revision pending representative measurements**. At 50 aircraft × four sectors/day,
   departure/completion alone imply at least 36,000 events over 90 days, beyond a
   single 10,000-event request. Faster copying does not approve hidden continuation
   or offline entitlement. AT-058 policy and its outstanding provenance work remain.

## Open risks and assumptions

- Capsules are an ordinary audited Python ownership mechanism, not a hostile-code
  sandbox against private-token reflection or monkeypatching. Exact helper/callback
  call graphs are part of the trusted boundary and must be audited, not assumed pure.
- The successful small read projection proves type preservation/isolation only;
  it does not prove manifest/finance or all cross-quarter chronology closure.
- Private candidate lifetime and source-proof reuse across cooperative boundaries
  may erase theoretical savings. Include conservative extra gates until proved.
- The source head observation is not a generated-event replay or group histogram.
  Current counts/quiet times are retained evidence, not freshly measured candidates.
- B2.6 provider isolation remains intact. AT-059 history classes, immutable live
  obligations and cold-load certification are not solved by any of these candidates.
- The pre-existing cold `game.utils.quarters` import issue remains separate; proof
  modules initialize World State first and do not claim to repair cold import order.
- AT-058 offline claims, durable provenance, longer-request recovery and pacing
  need separate design/approval. Current code and all protected files remain intact.

Verification, compilation, local links/heading checks, exact diff scope and final
Git outcomes are recorded in [Current Development Status](Current%20Development%20Status.md).

Seven raw proof/test/source-check logs are preserved, with SHA-verified copies, in
the local temporary evidence archive
`airline-tycoon-b3a-3df1eb1-86153dde0f4e46069516837f8ad15fc3`.
The verified task-only scratch directory was removed; no generated evidence or
player save is staged. The retained benchmark source hash was rechecked as
`ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0`.
