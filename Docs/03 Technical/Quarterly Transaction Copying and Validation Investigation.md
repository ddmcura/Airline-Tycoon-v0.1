# Quarterly Transaction Copying and Validation Investigation

## Executive summary

Stage **3G-B2.5**, investigation only, **2026-10-13**. Verified baseline:
`bcaf3efe55289f658e1e272c8341ad0e46c3f48f`. HEAD, upstream, freshly fetched
origin/master and live remote master matched; divergence 0/0, tracked tree/index
clean, only protected `.venv/` untracked, stashes empty. No production, diagnostic,
test, Schema 9 or template change is made in this stage.

The benchmark's **27 runtime clones = 13 isolated event candidates + 13 detached
commits + 1 Booking preparation preview**. Its **15 full validations = 1 request
entry + 13 event results + 1 final clock-gap gate**. These counts are completely
reconciled with the implemented call graph and the retained profile. They are not
27 copies of just active state, nor 15 checks of an unchanged world.

Additional whole-world copying matters: two Booking discovery passes each apply
four provider-isolation deepcopies; backend and publication reconciliation each
copy an already reconciled world once. Thus the traced successful fixture path
has **37 whole-envelope copy operations**, of which only 27 use the runtime codec.
This is a source-path accounting supported by retained call counts, not a new
per-allocation memory trace. The 66,057 instrumented imported deepcopy calls also
include small records and partial structures; they are not 66,057 world clones.

The safest next experiment is **one provider-isolation boundary for the exact
built-in quarterly activation adapter**. Preserve its detached input, mutation
before-image, detached typed output and independent reference; investigate avoiding
the outer duplicate isolation, not the 27 runtime clones or 15 full gates. This
has a materially larger measured cost surface than B2.4's rejected itinerary
micro-optimization and a smaller proof obligation than quarterly flight certification.
It is a proposal for separately authorized **B2.6**, not implementation permission.

Longer term, bounded quarterly flight certification offers a plausible route to
fewer event copies/gates, but existing certificates explicitly reject quarterly
mode. Reusing them by removing that exclusion is unsafe. Arbitrary batching,
mutable structural sharing and validate-only-at-end are unsafe under current
contracts. AT-059 remains **Proposed**; no history redesign is approved.

## Authority and inspected scope

Authority remains [Schema 9](Stage%201%20State%20Schema.md), subordinate
[template reference](../../Data/Templates/template_reference.txt) and
[repository instructions](../../AGENTS.md). The selective
[folder tree](../../Data/Templates/foldertree.txt) does not supersede current ownership.
Serena manual, repository activation, `core` and `scheduling/stage2_context`
memories were read. Those memories describe older checkpoints; current code and
contracts prevail. Relevant references:

- [Quarterly backend](Quarterly%20Backend%20Consumer%20Cutover.md),
  [shared publication](Quarterly%20Shared%20Publication.md),
  [publication recovery](Quarterly%20Boundary%20Orchestration.md).
- [Shared infrastructure](Runtime%20Shared%20Candidate%20Infrastructure.md),
  [mutation ownership](Runtime%20Candidate%20Ownership.md),
  [local proofs](Runtime%20Local%20Certified%20Proofs.md),
  [causal accounting](Runtime%20Causal%20Generation%20Accounting.md).
- [Atomic boundary optimization](Atomic%20Boundary%20Cost%20Optimization.md),
  [retained Booking validation](Retained%20Booking%20Validation%20Optimization.md).
- [Save architecture](Game%20State%20%26%20Save%20Architecture.md),
  [save specification](Game%20State%20%26%20Save%20Technical%20Specification.md),
  [benchmark evidence](Quarterly%20Runtime%20Benchmarking.md),
  [active/history feasibility](Active%20State%20and%20Certified%20History%20Feasibility.md),
  [decisions](Decision%20Register.md), especially AT-058/059/060.

## Actual transaction lifecycle

### Request and selection

[Stage1Session](../../app/session.py) `advance_to` drains `begin_advance_to` /
`advance_tick`. It establishes manual ownership and a fixed FAST_FORWARD target,
then calls [resolver](../../game/simulation/resolver.py) `begin_resolution` with
`shared=True`. This selects `SharedResolutionRequest`, not blanket shared execution.
Its first [step](../../game/simulation/shared_candidate.py) calls the kernel's
`_valid_world_failure`, reconciles quarterly work and builds the derived heap.
Validated management changes require refresh and a new entry gate.

`_can_share` binds actual callable, certificate identity, supported input/schema
and execution-state eligibility. [Flight proofs](../../game/world_state/flight_transition_validation.py)
`supports_departure` / `supports_completion` explicitly return false when
`simulation.operational_authority` is present. Dispatch and publication are fences;
daily Booking is strict. Consequently all 13 fixture events follow `_strict_one`.
The existing cap eight does not group these quarterly events.

[Kernel](../../game/simulation/kernel.py) event keys retain UTC/priority/sequence/ID
with the mandatory publication-before-consumer barrier. Generated children enter
the heap after the committed transition, before next selection; no static future
event vector is authoritative. Four dispatches materialize actual published
occurrences and generate departure/next dispatch work. Four departures freeze
actual manifests/aircraft witnesses and generate completion. Four completions
post settlement/results/counters. One daily Booking advances its checkpoint,
cohorts, inventory, ticket journals and successor. No publication occurs during
this particular October 2–3 measured day.

### Single strict event

`_execute_event(live, event_id)` creates a whole detached candidate with
`_clone_runtime_world(live)`. `_apply_handler_candidate` sets candidate UTC, passes
a copied event plus private transaction token to the same domain handler, checks
kernel-owned changes, determines generated IDs and resolves the selected event
into history. The domain mutates only this candidate. A failure discards it.

`validate_world(candidate)` independently checks the current complete graph and
domain relationships. On success `_replace_envelope` creates a second detached
whole world, then clears/updates the live root without yielding. Staging provides
rollback isolation; detachment prevents handler-retained candidate references from
mutating published authority. Close temporal proximity does not duplicate purpose.
The request records committed IDs/counters and yields only a completed boundary.
No candidate is retained between steps or exposed to reads, GUI or Save.

The codec in [serialization](../../game/world_state/serialization.py) uses internally
produced protocol-5 bytes and a globals-rejecting primitive reader. Plain mutable
containers remain mutable after cloning; cloning preserves internal relationships,
not immutable-history certification. Nonplain compatibility inputs fall back to
deepcopy. It is neither a save decoder nor a schema migration.

At target, `_complete_target` changes UTC and performs another full validation.
Failure restores the last committed time; previously successful events remain.
NO_OP and STALE have distinct lifecycle-only paths, not this fixture's two-copy
event path. Arbitrary stop callbacks receive detached state and force strict
request semantics. These distinctions prohibit universalizing the 27/15 formula.

### Booking nesting and isolation

[Checkpoint](../../game/booking/checkpoint.py) preparation creates one additional
runtime clone for the real allocation probe. It returns exact detached witnesses;
the preview candidate is discarded. Processing reruns allocation from the current
event candidate with a PENDING checkpoint, then checks demand/configuration,
inventory, Booking revision and quarterly dependency freshness before committing
Booking/itinerary pairs, balanced ticket journals and successor together.

The private event token means preparation/process do not repeat their public-command
source/final full gates or outer commits: the kernel owns those gates/copies here.
Public standalone commands retain their own validation/isolation. Preview and
replay each build Booking indexes once from different observations; their result
is not interchangeable without a new freshness/transaction proof.

[Shopping](../../game/booking/shopping.py) passes an exact built-in quarterly provider
inside `_IsolatedActivationProvider`. [Demand discovery](../../game/demand/activation.py)
sees that wrapper as a custom provider, copies the whole envelope and its before-image,
then invokes the wrapper. The wrapper again copies the whole envelope and a before-image,
checks input immutability and detaches/type-checks output. Demand also checks its own
before-image and validates market/pack eligibility. Each layer currently protects
its own boundary; deleting either wholesale is not justified by the count alone.

### Publication, failures and recovery

[Backend reconciliation](../../game/scheduling/quarterly_backend.py) clones before
trying to reconstruct missing dispatch; [publication reconciliation](../../game/scheduling/quarterly_boundary.py)
clones before reconstructing outstanding obligations. Both discard these copies
without validation/commit when no work changes. This fixture has no reconstructed
work, so neither adds a full gate/runtime commit clone to 27/15.

Actual publication invokes fresh [quarterly command](../../game/scheduling/quarterly_commands.py)
prepare/apply inside the outer strict event. All four command gates and both
command copies remain, in addition to outer event isolation/validation/detachment.
They are absent from this day's count, not eliminated. Publication must finish
before equal-UTC Booking even when enqueue sequence would otherwise disagree.

Ordinary handler/contract/result failure preserves the live pre-event state and
pending failed event, with the successful prefix retained. Publication alone can
commit a separate validated detached failure fence: exact boundary UTC, PAUSED,
no target and durable diagnostic, without committing the failed publication or
dependent consumers. Its extra clones/gates are failure-path costs outside 27/15.
Retry is explicit and reobserves current facts. Shared failure discards speculation,
reselects and strictly replays the successful prefix; optimizer divergence disables
optimization and reports a diagnostic. It must never roll back already observable
successful strict events or silently charge speculative budgets.

### Persistence and interrupted requests

[SaveStore](../../game/world_state/persistence.py) copies/validates a completed-event
snapshot, writes and rereads a temporary complete file, validates recovery data
and atomically replaces the selected file. Load parses a separate candidate,
fully validates Schema 9, restores PAUSED/no target, validates again and rebuilds
queue ordering before session exposure. Integrity digests do not certify domain
correctness. B2.3 exact lineage types and clear malformed-world rejection remain;
valid previous-file recovery is explicit, otherwise active state/files survive failure.

These copies/gates are outside advancement timing. Cancellation/close between
steps preserves the completed prefix, including unresolved equal-UTC work; a
complete event boundary is not necessarily a fully resolved timestamp or target.
No candidate/proof/cache can survive Load, rebind or resume as trusted authority.

## Clone and validation accounting

The retained profile reports four events of each flight phase and one Booking:
`4 dispatch + 4 departure + 4 completion + 1 Booking = 13`.

| Caller → callee / phase | Count | Scope and safety role | Approximate instrumented cost |
| --- | ---: | --- | --- |
| `_execute_event` → `_clone_runtime_world`, dispatch | 4 | Complete source; isolate materialization/events from live authority | Part of staging group below |
| Same, departure | 4 | Complete source; isolate manifest, aircraft, operation and child event | Part of staging group |
| Same, completion | 4 | Complete source; isolate result, journal, aircraft and account updates | Part of staging group |
| Same, daily Booking | 1 | Complete source; isolate demand/inventory/allocators/finance | Part of staging group |
| `_replace_envelope` → `_clone_runtime_world`, each successful event | 13 | Complete validated successor; detach retained candidate aliases before publication | 14.706s inclusive commit region |
| `prepare_daily_booking_checkpoint` → `_clone_runtime_world` | 1 | Complete event candidate at preparation; discard allocation preview after witness extraction | Shares remaining clone duration with staging |
| **Runtime codec total** | **27** | **13 + 13 + 1** | **29.557s exclusive / 31.708s inclusive** |
| `_valid_world_failure` → `validate_world`, request entry | 1 | Complete current source, before reconciliation/selection | 8.233s inclusive caller interval |
| `_execute_event` → `validate_world`, dispatch / departure / completion / Booking | **4 / 4 / 4 / 1** | Complete distinct successor after lifecycle resolution; reject independently invalid state | Approximately 99.534s inclusive in aggregate, by subtraction |
| `_complete_target` → `validate_world`, final gap | 1 | Complete world at target UTC, rollback time on invalid successor | 7.734s inclusive caller interval |
| **Full gate total** | **15** | **1 + 13 + 1** | **115.501s inclusive; root residual 13.377s exclusive** |

Runtime staging plus preview together account for about **17.002s inclusive**
after subtracting the detached-commit region from all runtime-clone regions.
Amortized clone exclusive cost is 1.095s; gate inclusive cost 7.700s. These averages
are scale descriptions, not measured per-event latency. Existing instrumentation
does not retain individual event/clone samples or separate preview from staging
exclusive time. No precise per-event exclusive duration is claimed; aggregate
exclusive categories and inclusive call-site intervals must not be mixed/summed.

Every source/result/clock gate can independently reject. Entry proves source only;
dispatch, departure, completion and Booking successors differ in events, witnesses,
finance or inventory. The final gap has different UTC-dependent applicability.
Large unchanged tables are rescanned, but complete predicate results are not reused
across these mutations. Current plain-tree and Booking graph proofs are call-local.
Removing a result gate admits corrupt successors; removing entry permits corrupt
unchanged dependencies; removing final gap can admit invalid target-time obligations.
Combining them requires complete dependency/isolation proof, not a matching final hash.

### Other copies and derived work

| Call path | Whole-world copies on fixture | Purpose / result reuse / failure |
| --- | ---: | --- |
| Demand discovery → deepcopy input + snapshot | 4 over two discovery passes | Protect caller and detect provider mutation; discard after each pass; provider can fail independently |
| Isolated provider → deepcopy input + before-image | 4 over two passes | Protect adapter caller, reject input mutation; detach outputs; discard after return |
| Backend reconcile → deepcopy | 1 | Stage potential missing dispatch atomically; discarded unchanged here |
| Publication reconcile → deepcopy | 1 | Stage potential missing obligation atomically; discarded unchanged here |
| **Additional whole-envelope deepcopies** | **10** | Separate from the **27** runtime-codec copies |

Outer Demand copy-wrapper caller intervals total about **42.116s**; inner adapter
copy-wrapper intervals about **44.523s**, including tiny copied window/output work.
These are disjoint call-site intervals of wrapped copy calls, including their GC,
not isolated exclusive whole-world allocation measurements. Backend's copy-wrapper
caller is **9.614s**; publication's unwrapped deepcopy cumulative is **9.328s**.

Important attribution limitation: alias hooks patch modules already imported when
installed. Publication reconciliation is imported later and its deepcopy is absent
from the 66,057 hooked copy regions. cProfile nevertheless records it. Recorded
exclusive categories total **253.168s** against **263.729s** command time, leaving
**10.561s** residual; the late-import copy is a major identified contributor, not
an exact exclusive residual decomposition. Do not claim every low-level copy/GC
allocation has a complete exclusive attribution. Count reconciliation of 27/15
is complete; low-level timing attribution is not.

Other copies are partial: event payloads, simulation/obligation contract witnesses,
quarterly services/plans/connections/aircraft freshness snapshots, fare/lineage,
returned checkpoint results and manifest witnesses. Derived `_ScalarRows`, heap,
Booking indexes, supply lookup and manifest lookup are temporary structures, not
new saved state. Exact enumeration of all 66,057 small calls is not required to
explain the whole-world counts and has not been measured separately here.

## Measured cost breakdown

All following runtime timings are retained **B2.4 baseline** evidence, reexamined
in B2.5 using JSON and cProfile caller records; no new advancement benchmark is run.

| Region | Calls | Exclusive seconds | Inclusive seconds |
| --- | ---: | ---: | ---: |
| Imported deepcopy regions | 66,057 | 95.860 | 99.046 |
| Runtime clones | 27 | 29.557 | 31.708 |
| Plain authority traversal | 15 | 57.163 | 57.163 |
| Booking relationship graph | 15 | 23.455 | 23.456 |
| Booking prefix validation | 15 | 14.373 | 37.829 |
| Full validation residual | 15 | 13.377 | 115.501 |
| Quarterly consumer validation | 15 | 5.624 | 5.635 |
| Fulfilment validation | 15 | 0.633 | 0.636 |
| GC observations | 4,641 | 6.082 | — |
| Manifests | 8 | 1.935 | 2.024 |
| Booking indexes | 2 | 1.632 | 1.637 |

The hooked copy categories sum to **125.417s exclusive**, without the late-import
publication copy. Full validation's 115.501s includes child predicates and must
not be added to those child rows. Allocation/shopping inclusive **93.585 / 90.414s**
largely contain provider isolation, not demand arithmetic alone. Dispatch handler
body and flight settlement are small relative to outer safety work.

Quiet fresh-process baseline pairs measure **89.620 / 92.251 / 93.369s**, median
**92.251s**; maximum peak working set **1,083.984 MiB**. The instrumented run takes
**263.729s** (cProfile region 264.188s, 410,320,376 calls). The instrumented phase
percentages are diagnostic and cannot predict quiet speedups by subtraction.
B2.4's typed-fact trial improved one builder ~15% but failed whole-command acceptance;
it was reverted. No performance improvement is claimed for this investigation.

## Architectural alternatives

| Approach | Classification | Copies/gates potentially avoided; mandatory work | Complexity, memory and principal risk |
| --- | --- | --- | --- |
| A. Current event architecture, bounded inner optimizations | **Feasible with bounded changes** | Provider consolidation could avoid four outer whole-world deepcopies across two passes; keep 27 runtime clones/15 gates and fresh preview/replay. A separately scoped no-op reconciliation probe might avoid two staging deepcopies, but is not B2.6 scope. | Smallest safety surface; fewer temporary trees may lower allocation churn, peak benefit unmeasured. Must preserve real isolation and freshness rather than declare a provider trusted by name. Remaining complete-world work limits potential. |
| B. Shared candidate for certified quarterly flight transitions | **Feasible but requires a major redesign of quarterly certification** | For an eligible run of k events, two outer copies and final full gate could replace 2k copies/k result gates only after individually valid local transitions are proved; entry/gap/Booking/publication fences remain. No numeric savings are established for the actual vector. | Existing machinery reusable, but new quarterly before/after proofs, read/write capsules, lineage, dispatch dependencies and manifest ownership required. Candidate/read capabilities add Python objects/memo cost; lower allocation count need not lower peak. |
| C. Arbitrary chronological transaction batching | **Unsafe under current contracts** | Adjacency alone removes no approved gate/copy. Only explicitly certified bounded B is eligible. | Whole-request rollback loses the successful observable prefix; end-only validation can hide invalid intermediates. Retry, failure fences, child events, saves and budget semantics change. Major contract revision would be required. |
| D. Copy-on-write / structural sharing | **Feasible but requires a major redesign**; raw mutable sharing **unsafe** | Could reduce complete staging traversal for immutable protected structures; final canonical detached publication/full checks still required absent a new authority contract. | Plain dict/list references can mutate old live worlds or other candidates; Python proxy/version/path-copy metadata and wide Booking tables may offset savings. Need enforceable mutation ownership, alias proof and lifetime closure. Existing one-event capsules within an already detached candidate are not cross-commit immutable sharing. |
| E. Certified substructures / transaction-local proofs | **Feasible with bounded changes inside one validation call**; cross-event replacement requires **major certification work** | Existing plain-tree/ScalarRows proofs already consolidate current-call scans. Cross-event subproofs could avoid selected result scans only with complete write/dependency coverage and unchanged-state proof; retain independent reference, full entry/final/load. | Raw revision/hash/boolean cannot certify unchanged tables. External corruption before entry must be caught; corruption during execution must be prevented or independently detected. An undetected write to unrelated finance/config/history invalidates the proof. Broad validator rewrite has no bounded authorization. |
| F. Active/history separation (AT-059) | **Feasible but requires a major redesign**; benefit justification **insufficient evidence** | Immutable closed classes could reduce copying, not remove live Booking/itinerary relationship checks. Mandatory cold Load/full trust-boundary proof remains. | 42,785/42,923 Booking pairs are unflown in the feasibility source. Immutable sale facts still own active obligations; age/status is not closure. Storage/certification/export generations and save recovery require class-specific design. No new evidence approves external stores or history compaction. |

B and E are related but distinct: B changes candidate lifetime/commit organization;
E proves intermediate validity without another global scan. B with all per-event
full gates might reduce copying but retain most validation cost. E without enforced
ownership cannot safely rely on prior proof. Neither alone confers quarterly support.

## Safety comparison

The promising bounded A experiment is assessed separately from larger B/D/E/F.
All requirements below are acceptance obligations, not claims of implemented safety.

| Invariant | Bounded provider isolation (A / proposed B2.6) | Quarterly certification (B/E) and structural/history designs (D/F) |
| --- | --- | --- |
| Atomicity / visibility | Keep strict event candidate, final gate and detached commit; provider exposes only detached IDs | Prove each intermediate transition; no candidate crosses a step return; D/F need atomic generation publication |
| Deterministic ordering | Provider only returns canonical market IDs; preserve queue untouched | Reselect actual heap head after each child; preserve UTC/priority/sequence/ID and publication barrier |
| Financial consistency | Compare exact checkpoint/journal/accounts; no new writer | Include ticket liabilities, settlement sources and protected unrelated accounts; immutable sale is not settled liability |
| Booking / itinerary | Preserve demand pool, horizon/flexibility, inventory witnesses and B2.3 exact types | Prove both sides, orphan/ownership/coverage equations and capacity dependencies; reject bool/int equality |
| Flight / aircraft | No provider writes; full kernel result gate checks actual projection | New quarterly operations/manifest/publication lineage proofs; aircraft readiness and actual location cannot be inferred |
| Publication | Provider reads only genuine published supply; no cached publication trust | Publication remains strict four-gate/two-copy command inside strict fence; failed obligation precedes consumers |
| Generated events | Adapter cannot allocate; normal Booking/dispatch children unchanged | Insert after transition, account only committed generation, retain pending children at stop |
| Failure rollback | Input mutation/exception rejects inside event candidate; live pre-event preserved | Discard speculation and strictly recover exact successful prefix; publication diagnostic is a separate transition |
| Strict / shared equivalence | Same provider results and complete world as old strict path; shared facade still executes quarterly strict | Independent strict selection and full-world oracle for each prefix, not just final hash |
| Save / Load | No new format/proof; detached paused Load/full checks remain | Runtime certificates expire on commit/Load/rebind; D/F must materialize complete logical snapshot and cold validate |
| Schema 9 / legacy | No fields/normalization; custom and legacy provider paths retain old isolation | Exact supported-mode boundaries; legacy certificates not silently repurposed; no save migration |
| Same-time generation budget | Default **100**, existing explicit Advance **10,000** exception untouched | Counters survive flush/yield/recovery at same UTC; future children not counted as causal work |
| Processed-event budget | **10,000**, including stale lifecycle, unchanged | No hidden reset inside batches or automatic retry; speculative work not charged as committed work |
| Interrupted advancement | Each returned boundary remains complete; cancel/save preserve prefix | Strict successful-prefix recovery and unresolved-target reporting; no persisted uncommitted candidate |

At 50 aircraft with four sectors/day, departure+completion alone exceed 10,000
events over 30 days. Copy/validation optimization does not authorize renewing
that request budget. AT-058 offline claims/checkpoints/pacing and B3 remain separate.
Neither 50-aircraft throughput nor the 90-day target is certified by this one-aircraft
investigation.

## Recommended approach and proposed B2.6 experiment

Choose **A: consolidate nested isolation inside one Booking activation transaction**.
Target only `prepare_daily_booking_shopping` → Demand discovery → the exact
`_IsolatedActivationProvider(QuarterlyActivationProvider())` path. Retain one whole
detached provider input and a genuine before-image, detached typed output, both
layers' eligibility checks and current mutation diagnostic. Avoiding the outer two
world copies per pass is a hypothesis: **four additional deepcopies per measured
day**, not four of the 27 runtime clones. Do not also optimize reconciliation.

Ownership must be explicit: Booking owns shopping, Demand owns provider discovery
and its isolation protocol, Scheduling owns the quarterly provider and published
supply. An opaque runtime capability must be minted/validated by the isolation
owner, bound to the actual exact adapter/callable/input and consumed synchronously.
Caller-set flags, subclass recognition, names or a mutable `is_safe` marker cannot
bypass isolation. If this cannot be accomplished with a small domain-local contract,
stop and recommend targeted diagnostics instead. It is not a generic `game/utils`
function or a new persisted certificate.

Required experiment sequence, only after separate implementation authorization:

1. Establish untouched controls with both provider layers. Trace exact world-copy
   call sites and exclusive/GC durations including late imports; measure one
   discovery pass separately before repeating whole-day runs.
2. Implement only the narrowly supported path; unknown/custom/legacy/replaced
   adapters retain the original isolation. Keep direct plain-data output checks,
   package ownership and independent original two-layer reference callable.
3. Compare exact market IDs, order/duplicates/eligibility/errors and unchanged
   source on the same frozen source, then compare preparation witnesses, allocations,
   checkpoint results and complete authoritative world at every event boundary.
4. Adversarial tests: provider input/nested mutation, alias-returned mutable output,
   retained input used after return, generator exceptions/late mutation, malformed
   IDs/duplicates, forged/stale capability, subclass and callable replacement,
   invalid window and unpublished supply. Mutation or exception must preserve
   original diagnostics, live world, allocator/event cursors and valid save files.
5. Test preview versus fresh replay with late inventory/configuration/publication
   changes; do not cache results across them. Verify deterministic retries, bool/
   float/string/null lineage rejection, reference versus optimized validation,
   strict versus shared facade, publication crossing/failure and paused Save/Load.
6. Focused provider/Booking/quarterly regressions first; full suite and scoped
   compile for retained production changes. No real Saves. Measure serialized
   fresh-process alternating whole-day pairs on the retained fixture, same target,
   budgets and hardware, with no concurrent test/profile work. Separate quiet and
   instrumented times. Compare source/result SHA and all authoritative rows.

Acceptance: retain only if the four expected outer copies disappear on the supported
path, all mutation/alias/error checks still hold, **27 runtime clones / 15 gates**
remain, exact deterministic worlds/diagnostics agree, and repeated quiet advancement
shows meaningful reproducible benefit beyond observed run variation without material
memory growth. There is no invented percentage threshold or extrapolated target claim.
Measure current peak and retained memory, not lifetime peak alone.

Rollback: revert the production trial if benefit is negligible/inconclusive, memory
regresses, any predicate/gate/alias boundary is weakened, legacy fallback changes,
or scope needs cross-event trust/history changes. Retain useful diagnostic evidence
and regressions only. Stop after this one experiment; no second optimization,
quarterly event certification, batching or gameplay activation by default.

Expected benefit is hypothetical: outer provider copy intervals occupy ~42.116s
of the instrumented run, but quiet savings cannot be inferred from that number.
Two retained inner copies plus fresh preview/replay, all full scans, outer runtime
copies and persistence remain. This cannot establish practical large-fleet/90-day
latency. If successful, separately investigate quarterly Departure/Completion
certification using existing infrastructure; keep Booking/dispatch/publication strict
until their own proofs are approved.

## Open questions and risks

- Exact per-event exclusive copy/validation times are not retained; timings above
  explicitly separate measured aggregates from amortized estimates. A new opt-in
  trace must cover late-import aliases before claiming complete allocation attribution.
- Publication-crossing days add nested four-gate command work and failure fences;
  the 13-event day cannot certify their performance or safety under future changes.
- A capability for single provider isolation needs genuine write prevention or
  retained mutation comparison, safe output detachment and unforgeable supported
  identity within the existing Python ownership model. This is not a security sandbox.
- B2.4 records a pre-existing cold import cycle for `import game.utils.quarters`;
  cold `import app.session` succeeds. Utility-first import safety needs separately
  scoped correctness work, not an architectural performance fix in this stage.
- Closed-history dependency closure and multi-file recovery remain unresolved AT-059
  design questions. B2.5 adds no evidence that most retained Bookings can be archived.
- AT-058 entitlement/provenance and request continuation decisions remain outstanding;
  no sleeping, offline progress, pacing change or budget increase is recommended here.

## Evidence and reproducibility notes

Retained fixture `fleet-1.json`: **75,758,607 file bytes**, source at
`2026-10-02T03:00:00Z`, one aircraft, 10 connections, four services, one plan,
42,923 Bookings/itineraries, 368 dated flights, five results, 42 journals,
50 history and 367 pending rows. Complete source SHA:
`ddddfcba13fa020a69a857b21ca07f637ae9a3dc268164a9567c61768589efe0`.
Target `2026-10-03T03:00:00Z`; 13 committed events, 43,467 Booking pairs,
nine results, 47 journals, 63 history, 363 pending. Complete result SHA:
`f2639799ac18443c62a85dcab3e613e12adbb5627df2051b19a4367df66091a2`.
File bytes are encoding size, not heap size or exact bytes copied per operation.

Evidence is the B2.4 archive identified in the completed investigation session:
`airline-tycoon-b24-f93e1990941540068d2871c973e53798` under the local temporary
evidence directory. Inputs used here are `postb23-profile.json`,
`postb23-profile-0.prof` and `paired-baseline-{0,1,2}.json`, plus the retained
fixture/audit. No machine-specific path is embedded in application or diagnostic
source. These local raw files are not a portable tracked fixture; source/target
hashes and [benchmark reproduction tooling](../../tests/profile_quarterly_advancement.py)
define the control. Evidence remains outside player Saves and Git.

B2.4 read/parse/current validation **0.038 / 0.928 / 2.955s** and historical
construction/warmup **595.657 / 586.522s** are outside Advance. SaveStore component
save/load **10.466 / 8.285s** are separate single samples, not engine improvements.
Hardware: Windows 11 build 26200, Python 3.12.10, i5-1035G1, eight logical CPUs,
8,361,132,032 bytes RAM. Quiet pair peaks are lifetime working-set observations.

B2.5 reads `pstats.Stats(...).stats` caller records through
`.venv/Scripts/python.exe -B -`; it performs no monkeypatching, fixture construction,
Advance, save writing or engine invocation. The examination confirms clone/validation
counts, entry/gap caller intervals, nested provider-copy callers and the unhooked
publication deepcopy. Documentation scope/link/heading/whitespace and final Git
verification are recorded in [Current Development Status](Current%20Development%20Status.md).
No gameplay suite or compilation is needed for these documentation-only changes.
