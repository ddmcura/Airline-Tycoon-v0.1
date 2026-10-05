# Current Development Status

Last updated: **2026-10-05**. Current snapshot, not operational authorization.

## Scheduling Patch 1 - initial partial-week activation and hang (2026-10-05)

Baseline **3b524084cc0ea24e69a9505a1ac31e4a5fd5126a** matched local HEAD,
upstream and live origin/master. [Full reproduction and implementation evidence](Scheduling%20Initial%20Activation%20Fix.md).

- Fixed an infinite recurrence loop: skipping elapsed preparation no longer skips
  advancing the date cursor. The baseline repeated one occurrence indefinitely;
  timing arithmetic was not the root cost.
- Draft and publisher distinguish inert intent from real aircraft position and
  reservations. A new policy-managed initial partial week can omit an infeasible
  unpublished prefix until first feasible activation; post-activation continuity,
  turnaround and conflicts remain strict. The next week keeps the full pattern.
  Existing published/booked obligations and established revisions remain protected.
- Fresh five-leg pattern now adds in **.417 s**, publishes in **.133 s** (three-run
  medians); baseline rejected its second leg. Preparation-boundary Add previously
  hung, now **.081 s**. No finite baseline completion/speedup is claimed.
- Thirteen new regressions; focused scheduling/publication/performance/GUI suites
  **109 passed in 72.869 s**. Full `python -B -m unittest discover -s tests`:
  **1037 passed in 1003.867 s**, production source frozen throughout the run.
  Scoped compilation, **31 affected local documentation links**, diff whitespace
  and complete self-review pass; no unresolved in-scope finding.
- Actual Windows Kivy builder smoke PASS: five Add actions **.158-.227 s** each,
  publication **.151 s**, two initial-week and five next-week occurrences,
  real flight completion and exact manual save/paused reload. Programmatic smoke
  does not prove human smoothness. All fixture/save/profile output is TEMP.
- No schema/template/persistent-field/save, economy, demand, runtime architecture,
  speed or unrelated GUI changes. No deadhead or retroactive operational effects.
  Stage 3F capacity failure remains; no Stage 3G begins. `.venv/` untouched.

## Stage 3F - final runtime capacity certification (2026-10-05)

Baseline **ebdfc1239cb88f2ccd12a481033f1ba236588b04** matched local HEAD,
upstream and live origin/master before measurement. Evidence covers this
working-tree certification scope; [methodology, complete measurements and limits](Runtime%20Capacity%20Certification.md).

- **PH 1.0 RUNTIME NOT CERTIFIED. Stage 3 scalability project NOT COMPLETE.**
  The approved 50-aircraft literal Ultra 1800x requirement fails on the documented
  i5-10400 Windows host. A real 200-sector/day airline with 7819 Bookings and
  6800 rolling dated flights takes **375.151 engine seconds/game day** through
  existing explicit Advance: **230.307x** unpaced, only **12.795%** of requirement.
  Ultra permits 48 seconds/day; processing is **7.816x** that budget.
- Actual session/controller/resolver, cap eight, strict/fences, credit ledger,
  committed UTC, overload, Stage 2 invalidation and autosave remain active.
  1/10/25/50 aircraft x all four speeds are measured separately from setup and
  later commanded drain; short drained windows are not labeled sustained passes.
- Longer 50 Ultra: running backlog slope **+1672.89 game seconds/input second**,
  max debt **278521.0206 s**, one overload entry; **zero observed recoveries**
  before the 220-second engine budget. Earnings freeze, exact target/credit stay
  retained. Stop is a validated committed prefix, not a completed recovery.
- Complete validation, detached copies and per-event kernel event/history
  witness/comparison dominate. The 84-event prefix spends **31.2%** in kernel
  event/history witness phases; complete-day validation is **103.161 s**.
  The one daily Booking fence is **16.362 s**; most deficit is outside it.
- Ordinary preloaded large requests also expose the unchanged cumulative
  **100 generated-event** safety stop. Explicit Advance's existing allowance
  completes the day. No silent retry, limit change or performance fix is made.
  50 Day3/Day7, long explicit advances and conditional 100-aircraft stress are
  not escalated after conclusive Day1 failure.
- One-aircraft seven-day production-pump control passes seven Booking fences,
  one real weekly publication and natural autosave (**14.627 s**). History grows;
  Booking fence .834 ->1.518 s. 50 Normal live pause/drain/save/exact paused
  reload/zero debt/resume/continuation/autosave checks pass outside service timing.
- Four-speed 50-aircraft equal-time Departure/Completion prefix matches the
  independent strict oracle across all authoritative fields. Quiet/profiled
  entire-day hashes and all 401 event vectors match. Profiling identity/ledger/
  routing guards prevent benchmark-only shortcuts; runtime exactness is retained.
- Final fresh Windows Kivy direct-Load smokes pass: starter through Booking,
  50 through flights/all speeds/15-second Ultra observation/pause/drain/save/
  reload/resume/view navigation. Median/max: starter **.118/.280 s**, 50
  **6.640/8.498 s**. Tick refresh <=**.065 s**. 50 responsiveness is **POOR**;
  programmatic correctness does not prove human smoothness or capacity.
- Focused `tests.test_runtime_capacity`, Booking-lineage, atomic-boundary and
  production session/GUI runtime suite: **86 passed in 165.431 s**, including
  **15 new harness accounting/routing/equivalence/persistence guards**.
  Full `python -B -m unittest discover -s tests`: **1024 passed in 1056.680 s**
  (baseline 1009). Final test-only unpaced metric labels/guard assertions were
  subsequently checked with **15 passed in 14.394 s**; production source stayed
  unchanged throughout. Scoped compilation, **228 local documentation links**,
  new capacity anchor, diff whitespace and complete self-review pass.
- **No production source changed.** Schema **7**, ratios **30/210/900/1800**, cap
  **8**, exact proofs/UTC/credit, three existing certificates, gameplay and save
  semantics remain. No offline progression, additional handlers, worker or next
  runtime optimization stage. Pre-existing untracked `.venv/` remains untouched.

Certification measurements, verification and report are complete. The failed
capacity gate does not authorize another implementation milestone. Commit/push
outcomes are reported separately after delivery; no pending hash is invented.

## Stage 3E.2 - retained Booking/itinerary validation (2026-10-04)

Baseline **b9e8cde819deec22fcdd0bb4d8eb92fbcc643d1c** matched local HEAD,
upstream and live origin/master before edits. Evidence covers this working-tree
implementation; [complete technical audit, measurements and proof](Retained%20Booking%20Validation%20Optimization.md).

- Original direct ID lookup is already linear, not Booking x itinerary. Call-local
  exact source scalar tables remove repeated retained record reads and repeated
  flight/date facts. All records/relationships are proved; anomalies use the
  unchanged ordered diagnostic suffix and frozen differential oracle.
- Every complete-world gate, E.1 alias/JSON/money/UTC proof, domain predicate,
  detached copy, strict/fence transaction and persistence validation remains.
  Tables end at validation return; no saved/session/Stage 2 trust or reuse.
- Final quiet controls: Divine Booking **.5391 -> .3190 s** (~41% lower), full
  validation **1.2894 -> .9912 s**. Divine next **5.363 -> 4.689 s**, short
  **5.587 -> 4.938 s**, clock-only **2.653 -> 2.150 s**, dense25/100 events
  **7.465 -> 7.064 s**. All complete hashes and callback event/commit vectors match.
- Production-source focused suite: **79 passed in 39.854 s**, including **23 new**
  differential/corruption/read-only/coverage/timestamp/scaling tests. Full suite
  `python -B -m unittest discover -s tests`: **1009 passed in 1288.163 s**.
  Production/functional source stayed unchanged during the run; later profiler-only
  attribution changes passed diagnostic fixture runs. Scoped compile, local links,
  diff whitespace and complete self-review pass; no unresolved in-scope finding.
- Fresh-process Windows Kivy direct-Load smokes all PASS: starter through Booking
  fence, comparable Divine departure and Divine through Booking fence. All four
  speeds, pause/drain, exact paused save/reload and no offline progress verified.
  Comparable Divine: 14 callbacks, median **2.119 s**, p95 **3.699 s**, maximum
  **3.934 s**, GUI refresh **.00247 s**, versus E.1 median2.780/max5.397.
  Longer strict Booking-fence run: 16 callbacks, max **6.839 s**. Programmatic
  smoke does not prove human smoothness or sustained speed/backlog capacity.
- Divine tables own ~**5.61 MiB**; isolated validation allocation peak ~**8.32 MiB**.
  Storage is O(B+I), call-local and released, never accumulated across callbacks.
- **READY FOR STAGE 3F**, under the approved formal-test readiness standard:
  targeted ordinary retained-lineage stalls are substantially reduced; no new
  concrete blocker makes formal 50-aircraft testing meaningless. Remaining full
  traversal/copy/checkpoint costs are disclosed. This is not 50-aircraft Ultra
  certification. Stage 3F remains unimplemented; no automatic E.3 begins.
- Schema **7**, cap **8**, one safe unit/callback, ratios **30/210/900/1800**, exact
  credit/drains/recovery/save semantics remain. No gameplay, RNG, new handlers,
  offline progression or worker changes. Pre-existing `.venv/` remains untouched.

## Stage 3E.1 — atomic boundary cost optimization (2026-10-04)

Baseline **be4fdd356563e7370ffef7e16aee23a4193d9f32** matched local HEAD,
upstream and live origin/master before edits. Evidence covers this working-tree
scope. [Full audit, controls, correctness arguments and limits](Atomic%20Boundary%20Cost%20Optimization.md).

- Consolidated exact JSON/alias/forbidden-field-money-UTC graph predicates into
  one call-local traversal. Diagnostic fallback retains original errors/paths;
  every domain/reference/equation check and complete-world gate remains.
  Constant common flags and parallel stacks reduce temporary allocation/GC work.
- No world/session validation trust flag, new index, ownership transfer or copy
  removal. Existing private manifest lookup, strict recovery, shadow/oracle,
  committed Stage 2 epochs and persistence safeguards remain unchanged.
- Final alternating finite controls (two samples): Divine-next **8.621 → 5.177 s**,
  max callback **6.315 → 3.945 s**; dense25/100 events **9.216 → 7.527 s**;
  Divine clock-only **4.696 → 2.518 s**. Complete hashes/commit vectors match.
  Fresh original controls and host variation are separately reported.
- Focused certification/runtime/ownership/owned-read/world suite: **282 passed in
  658.522 s**. Final new/affected Advance suite: **29 passed in 53.558 s**.
  `python -B -m unittest discover -s tests`: **986 passed in 1291.308 s**,
  versus baseline 970. Production/functional regression source stayed unchanged
  during the full run; subsequent profiler-only timing assertions: **2 passed in
  .045 s**. Final scoped compilation, **55 local links**, diff whitespace and
  complete self-review passed. No unresolved in-scope finding.
- Final native Windows Kivy direct-Load smoke: both PASS, New Game forbidden,
  actual flight/fence processing, all four speeds, drain, exact save/reload,
  paused zero-credit restore and no offline advance. Starter 20 callbacks,
  median **.139 s**, p95 **.304 s**, max **.312 s**. Divine 14 callbacks,
  median **2.780 s**, p95 **4.707 s**, max **5.397 s**; max engine **5.290 s**,
  graphical refresh **.0074 s**. Programmatic smoke does not prove human smoothness.
- **ONE MORE SPECIFIC BLOCKER BEFORE STAGE 3F:** retained Booking/itinerary
  validation still makes ordinary one-aircraft clock-only callbacks multi-second.
  Proposed next bounded scope is exact retained-lineage predicate/lookup work,
  separately approved before implementation. No automatic E.2 or Stage 3F begins.
- Schema **7**, cap **8**, one safe step/tick, ratios **30/210/900/1800**, exact
  pacing credit, drains/recovery and save semantics remain unchanged. No new
  handlers, gameplay, offline progression or worker thread. `.venv/` untouched.

## Stage 3E — production cooperative shared runtime (2026-10-04)

Baseline **94c53db7b86b04eea117ad696819909cf2515534** matched local HEAD,
upstream and live origin/master before edits. Evidence covers this working-tree
implementation. [Complete production policy, measurements and limitations](Production%20Cooperative%20Runtime.md).

- Normal session/Kivy pacing and explicit Advance now opt into the existing exact
  shared resolver, one safe step per callback, cap **eight** certified events.
  Payment/Departure/Completion remain the same identity-bound certificates;
  Booking/publication/expiry remain fences, rotation/custom/unsupported remain
  strict. Candidates/lookups close before callbacks return; no worker threads.
- Literal ratios **30/210/900/1800** are unchanged. Integer earned credit and
  finite request limits survive cooperative returns. Player Pause freezes accrual
  and drains owed work. Existing normalized **120-second backlog /30-second grace**
  confirms overload; catch-up freezes earnings, drains exactly and stays paused
  until explicit Resume. Hard pause closes requests at committed boundaries.
- Save/bookmark and GUI return/exit use a drain barrier then existing storage and
  Save/discard/cancel choices. Deferred actions are runtime-owner-bound/revoked on
  replacement/error. Autosave still snapshots only committed authority at existing
  thresholds. Load is exact/paused with zero pacing debt and no offline progress.
- Deterministic failure stays paused without retry storms. Optimizer divergence
  keeps the strict recovered prefix and disables sharing until controller replacement;
  explicit Resume can continue strictly. Stage 2 invalidates once per committed unit;
  GUI views retain throttled refresh. Clock display never substitutes earned target.
- Finite frozen dense-25/100-event controls: strict **54.92 s**, shared cap eight
  **10.63 s**; cap64 **4.91 s** but longer atomic callbacks (**2.65 vs1.04 s**).
  Final controller repeat **9.192 s**, 13 commits/14 callbacks; all
  strict/shared/budget complete-world hashes match. Isolated routes remain near
  parity; no speculative lookahead routing is added.
- All **20** production speed probes validate. Starter/ten/aged-ten show bounded
  short tails; dense25 Very Fast ends with a larger unfinished target. Divine Air
  still stalls **6–7 seconds**, including costly clock-only work. These are short
  probes, not sustained speed acceptance or proof of human GUI smoothness.
- Schema remains **7**. No gameplay, new certification, saved runtime fields,
  offline progression, Stage 3F or additional GUI/gameplay work. Pre-existing
  untracked `.venv/` is untouched.
- Recommendation: **NOT READY FOR STAGE 3F** responsiveness/capacity acceptance.
  Profile remaining whole-world/clock-only validation and commit costs in a
  separately approved task before claiming responsive 50-aircraft Ultra.

### Verification

- Final new regressions: `python -B -m unittest tests.test_cooperative_runtime
  tests.test_gui_cooperative_runtime -q`: **32 passed in 129.299 s**.
- Broader focused runtime/resolver/shared/GUI/advancement suite: **114 passed in
  250.199 s**; final new suite also covers subsequent scoped status/action guards.
- `python -B -m tests.smoke_cooperative_runtime`: **PASS**, fresh native Windows
  Load Game with New Game forbidden, all four speeds, pause/drain/save/exact reload,
  controlled overload catch-up and paused recovery. **65 callbacks**, median
  **.194 s**, p95 **.225 s**, maximum **1.064 s**; final exact paused saved UTC
  `2026-09-07T02:36:00Z`. Programmatic interaction between units only.
- `python -B -m unittest discover -s tests`: **970 passed in 1435.903 s**,
  versus predecessor 938. Includes complete Stage 1 exact-world oracle, Stage 2
  ownership/invalidation, prior Stage 3 certification/recovery, Booking/manifest,
  finance/journal, aircraft/maintenance, kernel/runtime/Advance, GUI and persistence.
- `python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`:
  passed on final source. Production and regression-test source stayed unchanged during the full run;
  diagnostic benchmark guards were separately changed and verified afterwards.
- Scoped Markdown local links and `git diff --check`: passed. Complete diff reviewed
  for debt/targets, safe boundaries, strict/fences, failure/replay, UI/deferred actions,
  Stage 2 visibility, persistence/Schema 7 and Stage 3F scope protection.

## Stage 3D.3 — candidate-local Booking/manifest lookup (2026-10-04)

Baseline **a58fdd021ac904aea161a1d7e6bb023dbb6b61de** matched local HEAD,
upstream and live origin/master before edits. Evidence covers this working-tree
implementation. [Complete access/proof/lifetime/performance audit](Candidate%20Manifest%20Lookup.md).

- Certified flight capture/handlers use lazy immutable Booking IDs grouped by
  authoritative itinerary flight relationship. Construction independently checks
  complete coverage, association and exact sorted order; current manifest lineage,
  capacity, revisions, checkpoint/sale and frozen completion checks remain.
- Source Bookings/itineraries stay protected by the actual certified mutation
  footprints. Generic capsules expose only a source-bound read callable. Lookup
  state closes before commit/return/fence/discard/recovery; strict replay and full
  shadow scan/oracle remain. No whole-manifest cache or persistent authority index.
- Stage 2 committed reads stay separate. Schema remains **7**, saves are unchanged,
  no handlers are additionally certified, and normal session/Kivy/Advance pacing
  stays strict. No Stage 3E/3F, overload, speed, gameplay, validation/clone/history
  redesign or unrelated GUI changes. Pre-existing untracked `.venv/` is untouched.
- Same eleven frozen fixtures retain exact complete-world hashes and shared commit
  vectors. Fresh three-sample medians: dense-25 / 100 events **7.931 → 4.688 s**;
  manifest **3.998 → 1.331 s**, actual manifest Booking visits **355,200 → 7,104**.
  Two candidate builds each make one build and one independent coverage pass.
- Dense max shared step **4.997 → 2.730 s**. Divine-next **10.913 → 9.929 s**;
  Divine-short **12.569 → 10.154 s**. Largest post step **7.470 s**; these are still
  synchronous stalls. Full validation (~8.1 s) and cloning (~1.4 s) dominate Divine.
- Controlled fixed 14-ID manifest at 896/1,616/4,453 Bookings: canonical lookup
  **16.4/23.5/53.3 ms**, indexed **3.3/2.6/3.4 ms**. Candidate lookup structural
  size ~18 KiB dense /225 KiB Divine; construction temporary memory remains O(B).
  Isolated peaks dense **81.19 → 82.45 MiB**, Divine **374.37 → 372.94 MiB**.
- Exploratory 50 aircraft /200 events: **12.471 s**, max step **4.048 s**, one shared
  sample only. This is not formal 50-aircraft Ultra/Stage 3F certification.
- All six Payment fixtures match strict authority. Alternating isolated medians
  overlap/are near parity; strict for exactly one eligible transition is a reasonable
  future integration policy, not implemented or proven universally fastest here.
- **A — proceed to a separately approved bounded Stage 3E integration** is the
  recommendation. Remaining history/full-validation/clone costs remain visible;
  this is not sustainable Ultra or human GUI responsiveness acceptance.

### Verification

- `python -B -m unittest tests.test_candidate_manifest_lookup
  tests.test_candidate_ownership tests.test_flight_proof_optimization
  tests.test_flight_certification tests.test_payment_certification
  tests.test_shared_candidate -q`: **183 passed in 641.146 s**, including 26 new
  lookup/order/corruption/lifetime/recovery/serialization/metadata regressions.
- `python -B -m tests.profile_contract_payment --case all --mode both --repeats 1`:
  all six strict/shared complete-world hashes match, after final certificate review.
- `python -B -m unittest discover -s tests`: **938 passed in 1557.209 s**,
  versus predecessor 912. Includes complete Stage 1 oracle, Stage 2 ownership/
  invalidation, Stage 3A–D infrastructure/certification/recovery, Booking/manifest,
  finance/journal, aircraft/maintenance, kernel/runtime/Advance, GUI and persistence.
- `python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`:
  passed on final source. No source changes followed the full run.
- `python -B -m tests.smoke_runtime_startup`: **PASS**, native Windows Python
  3.12.10 / Kivy 2.3.1 / SDL2 / OpenGL, fresh process direct Load Game without
  New Game, two completed Booking checkpoints /14 Bookings, exact paused
  save/reload at `2026-09-02T00:00:30Z`; window 2560 ×1377. Ordinary strict
  production startup is verified; human shared-path responsiveness is not claimed.
- Final self-review covers the complete diff, exact source/order/coverage,
  immutable IDs/current resolution, protected mutation union, expiry/recovery,
  aliases/JSON, Payment metadata identity, weak callback lifetime, Stage 2 and
  persistence separation. Documentation links and `git diff --check` pass.
  Commit/push outcomes are reported after the actual Git operations.

The dated Stage 3D.2 evidence below records the predecessor implementation; its
"another proof-cost pass first" recommendation is superseded by Stage 3D.3 above.

## Stage 3D.2 — shared-candidate mutation ownership (2026-10-04)

Baseline **1bf99b647163ee0834908ec8820a6abd4339ba56** matched local HEAD,
upstream and live origin/master before edits. Current evidence covers this
working-tree implementation. [Detailed ownership/proof/profile audit](Runtime%20Candidate%20Ownership.md).

- Only exact certified Payment/Departure/Completion receive per-event write
  capsules. Protected authority is recursively read-only; genuine predecessor
  and selected successor proofs remain. Local canonical JSON/alias checks and
  detached publication preserve entry guarantees. No identity/revision shortcut
  substitutes for value or alias proof. Full shadow protected/alias oracles remain.
- The candidate-local read-capability memo uses strong source references, ends
  before flush/recovery and never enters saves, session projections or Stage 2.
  No Booking/manifest/history index was added. Final full validation, detached
  commit, strict successful-prefix recovery, mixed events and causal fences remain.
- Schema remains **7**. No formulas, gameplay, RNG, scheduling, save migration,
  additional handler certification, normal Kivy/session/Advance shared activation,
  pacing credit/speed or overload recovery changes. Stages 3E/3F remain unimplemented.
  Pre-existing untracked `.venv/` remains untouched.

### Measurements and limits

Same eleven frozen Stage 3C worlds/targets; all original/strict/owned world hashes
and event commit vectors match. Three-sample shared medians, independent exclusive
profiles and isolated memory runs are recorded in the audit.

- Dense-25 / 100 events: fresh shared **15.873 → 7.869 s**; historical Stage 3D
  optimized shared was 12.283 s. Capture/transition proof **11.787 → 1.261 s**;
  additional capsule construction/publication/close costs are explicitly included
  in a separate approximately 1.75 s diagnostic-adjusted combined profile.
- Protected encoding **6.383 → 0 s** / 886,445,732 bytes → 0; alias proof
  **4.226 → 0.127 s**, now small complete output packs, not the growing world.
  Final validators still traverse the whole world. Dense max step **4.698 s**.
- Divine-next shared **11.199 → 12.072 s**; Divine-short **12.846 → 13.053 s**.
  The isolated regression is not solved; the largest final shared step is
  **10.834 s**. No human GUI responsiveness or 50-aircraft acceptance claim.
- Guarded manifest reads now dominate dense-25 (**4.134 s**), retaining
  O(events × Bookings) scans. Full validation/copying dominate the large save;
  kernel pending/history witnesses and topology seals still grow with history.
- Isolated process peak: dense-25 **75.93 → 79.76 MiB**; Divine-next
  **373.83 → 373.99 MiB**. Private memo structural estimates are 6.24/30.49 MiB
  respectively, cleared before commit/recovery. They are not total heap/RSS.
- All six Payment performance fixtures match strict; dense-64 Payment shared is
  1.176 s versus 6.138 s strict (one sample/path). Shadow remains deliberately costly.

### Verification

- Final focused command: `python -B -m unittest tests.test_candidate_ownership
  tests.test_flight_proof_optimization tests.test_flight_certification
  tests.test_payment_certification tests.test_shared_candidate -q`:
  **157 tests passed in 627.348 s**. New ownership module adds 31 regressions.
- `python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`:
  passed. `git diff --check`: passed. All **200** scoped local documentation links exist.
- `python -B -m tests.smoke_runtime_startup`: native Windows Kivy 2.3.1 / SDL2 /
  OpenGL fresh process, direct Load Game without New Game, two completed Booking
  checkpoints / 14 Bookings, exact paused save/reload: **PASS**. Strict production
  path only; this does not test shared multi-event GUI pacing or human responsiveness.
- Full `python -B -m unittest discover -s tests`: **912 tests passed in
  1397.137 s** (881 baseline + 31 new). This includes all Stage 1/2/3A–D,
  booking, finance/journal, aircraft/maintenance, kernel/runtime, GUI and persistence
  coverage. Final review then added read-view attribute-deletion rejection;
  its affected ownership/proof tests are rerun separately below. No certified
  handler deletes attributes; valid engine paths/benchmark results are unchanged.
- After that final review fix: `python -B -m unittest tests.test_candidate_ownership
  tests.test_flight_proof_optimization -q`: **50 tests passed in 33.018 s**.
  Final scoped compilation, 200 local documentation links and `git diff --check`
  pass. Complete diff self-review is clean within approved Stage 3D.2 scope.

**Next gate: ANOTHER ENGINE OPTIMIZATION before Stage 3E.** Separately scope
cheaper guarded manifest/read access and validation/copy/event-history scaling.
Multi-second steps remain unsuitable for normal cooperative pacing. No follow-up
implementation is authorized by status; stop after Stage 3D.2. Prior dated notes
below retain their historical scope and measurements.

## Revised Stage 3D — flight proof-cost optimization (2026-10-04 implementation)

Baseline **c3d47de83b9c1d7cce1c1d82fbb48697757da21d** matched local HEAD,
upstream and live origin/master before edits. This approved slice replaces
additional-handler certification as Stage 3D's purpose.
[Detailed exclusive profile, protected/type/alias audit, proof and measurements](Flight%20Proof%20Cost%20Optimization.md).

- Flight certification replaces sorted JSON/SHA protected fingerprints with exact
  typed runtime bytes. Genuine before-event equality still protects **all**
  unchanged authority; identity/revisions are not substituted for mutation proof.
- Canonical JSON compatibility runs on every changed/excluded record, whole
  simulation and allocator. Protected compatibility inherits only after exact
  typed equality. Plain root/table guards prevent shallow-view type erasure.
  An equivalent **whole-candidate** alias predicate remains, without allocating
  unused primitive paths. No invalid event can wait for a later repair.
- No request witness reuse, candidate index, Stage 2 cache sharing, schema field,
  save migration, gameplay/formula/RNG/timing change or new handler certification.
  Payment code/proof is unchanged. Rotation remains strict; Booking, weekly
  publication and expiry remain fences. Strict replay, shadow, final full-world
  validation and detached commits remain unchanged.
- Schema remains **7**. Normal session/Kivy/Advance pacing is unchanged and strict.
  No Stage 3E, Stage 3F, overload recovery or production batching activation.
  Pre-existing untracked `.venv/` remains untouched.

### Results and current limits

Same eleven frozen Stage 3C inputs, targets and complete-world hashes, three
latency samples per flight path. Tooling uses direct non-retaining wrappers and
exclusive timings; old nested/mock post-change measurements were discarded.
Host timing varies; no portable performance threshold or human responsiveness
claim is made. Full comparison tables and call/byte/scaling counts are in the audit.

- Dense 25 / 100 events: fresh shared **24.694 → 12.283 s**, recorded 3C 30.662 s.
  Fresh capture + proof **22.900 → 9.860 s**; recorded 3C 27.072 s.
- Dense-25 max shared step **7.070 s**, versus recorded 3C 19.798 s.
  Largest final step across all fixtures **9.018 s** (Divine-short).
- Divine-next: shared **10.228 → 9.689 s**, still above fresh strict 8.576 s.
  Divine-short **14.012 → 11.484 s**. Isolated regression is not eliminated.
- Validation/clone/commit vectors are unchanged: dense-25 retains four full gates,
  four world clones and 64/36-event commits. All 11 exact worlds match strict.
  All six original Payment profiling fixtures also match strict (one sample/path).
- Fresh dense-25 process peak **76.09 → 78.97 MiB**. Witness buffers are O(world
  size), live for one transition only; no accumulation/index cache enters saves.
- Remaining global encoding/alias and growing event/Booking/history scans remain
  O(events × retained authority), with unchanged final-gate cost. No formal or
  exploratory 50-aircraft certification is claimed.

### Verification (actual implementation working-tree scope)

- `.venv/Scripts/python.exe -B -m unittest tests.test_flight_proof_optimization
  tests.test_flight_certification tests.test_payment_certification
  tests.test_shared_candidate`: **126 PASS, 487.609 s**.
- `.venv/Scripts/python.exe -B -m unittest discover -s tests`:
  **881 PASS, 1327.709 s** (862 baseline + 19 new regressions).
  Includes Stage 1 complete-world/oracle, Stage 2 ownership/invalidation,
  Booking/manifest, finance/journal, aircraft/maintenance, kernel, persistence,
  runtime/Advance, frontend and all Stage 3A–3C gates. No expected gameplay
  witness/result was changed.
- `.venv/Scripts/python.exe -B -m tests.smoke_runtime_startup`: **PASS** on native
  Windows/Kivy 2.3.1 SDL2/GLEW, fresh process → Load directly → Resume/Advance →
  two Booking checkpoints / 14 bookings → exact paused save/reload. Window
  2560×1377. This exercises unchanged strict production pacing, not shared GUI
  activation or human-level responsiveness.
- `.venv/Scripts/python.exe -m compileall -q app game tests main.py
  make_snapshot.py settings.py test.py`: **PASS**. Protected/runtime directories
  excluded. Direct documentation links and `git diff --check`: **PASS**.
- Full diff self-review covers genuine predecessor/type/alias guarantees,
  intermediate failure/replay, fences, no speculative Stage 2 reads, no saved
  witness/index, package ownership, unchanged schema/gameplay/production pacing
  and Stage 3E/3F exclusion. Only intended implementation/tests/tooling/docs.

Recommend another separately bounded proof-cost/ownership investigation before
Stage 3E production activation: multi-second steps and isolated-event overhead
remain. **Stop after Revised Stage 3D.** Prior dated evidence below describes the
implemented earlier scopes; it is superseded by this current runtime snapshot.

## Flight lifecycle certification — Stage 3C (2026-10-04 working tree)

Baseline **3f6f6ab76194b36825d3850651b6f96d1fd7267e** matched local/upstream/live
origin/master before edits. Only this separately approved Stage 3C is implemented.
[Separate footprints, dependency maps and proof](Flight%20Shared%20Certification.md).

- Exact built-in Departure and Completion independently bind schema-7 input
  predicates, genuine before-event capture and exact transition validators under
  `ph-flight-departure-shared-v1` / `ph-flight-completion-shared-v1`. Custom/stale/
  unsupported inputs remain strict. Older schemas remain strict; migrated V1
  operations in schema 7 still produce V1 results without maintenance backfill.
- Pure existing operation/cost/journal/result construction stays localized in
  aircraft_operations; world-state proofs reuse it without changing formulas.
  All flight/aircraft/manifest/result/account/journal/revision/event/allocator
  changes are exact. Unchanged authority is fingerprinted; canonical JSON
  compatibility and mutable alias validation run at EVERY flight transition,
  before another event executes.
- Final full validation and detached commit remain mandatory. Mixed shared batches
  follow canonical event order, immediately enqueue generated completions, and
  use unchanged strict successful-prefix recovery/divergence handling. Booking,
  weekly publication and expiry stay fences; Rotation stays strict; Payment remains
  certified. No private candidate reaches Stage 2 views or persistence.
- Schema remains **7**, with no new persistent fields, booking index, cache,
  historical reinterpretation or gameplay/formula/RNG/scheduling change. Production
  session, Kivy, explicit Advance, pacing and overload behavior remain strict and
  unchanged. Stage 3D–3F are NOT implemented. Pre-existing `.venv/` remains untouched.

### Flight measurements

Original-source BEFORE: Stage 3B baseline, first eight fixtures measured before
flight certification; dense-25/Divine fixtures measured against a read-only TEMP
archive of that same baseline with tooling copied into it. AFTER strict controls
use the unchanged strict path; final shared samples include canonical JSON and
alias checks. An initial cold shared-only profiler run lacked explicit registry
initialization for its first case; discarded and remeasured that case after fixing
startup. The tool now asserts timed/instrumented commit boundaries agree.

Python 3.12.10/Windows desktop, three latency samples per path, medians below.
Workstation was not CPU-isolated; other verification ran concurrently, so compare
strict controls and structural counts rather than treating timings as a formal
speed certification. Setup/input copying/output hashing are excluded; counters
and nested timers run separately. Same persisted input fixtures and complete-world
hashes are used throughout, batch cap 64, no normal-runtime activation.

| Fixture | Events | Before strict s | After strict control s | Final shared s | Full gates before → shared | World clones before → shared | Events/commit shared | Max shared step s |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |
| one-departure | 1 | 0.330521 | 0.414115 | 0.518057 | 3 → 3 | 2 → 2 | 1 | 0.427281 |
| one-completion | 1 | 0.349669 | 0.398141 | 0.542275 | 3 → 3 | 2 → 2 | 1 | 0.422155 |
| round-trip | 4 | 0.781458 | 0.825645 | 0.796733 | 6 → 3 | 8 → 2 | 4 | 0.775766 |
| dense-departure | 10 | 2.466152 | 2.965744 | 2.284076 | 12 → 3 | 20 → 2 | 10 | 2.188171 |
| dense-completion | 10 | 2.580800 | 3.124040 | 2.344798 | 12 → 3 | 20 → 2 | 10 | 2.219581 |
| mixed-ten | 40 | 9.577224 | 11.878121 | 7.763072 | 42 → 3 | 80 → 2 | 40 | 7.778779 |
| representative-ten | 81 | 29.551979 | 39.215595 | 24.447573 | 83 → 5 | 162 → 6 | 40/1/40 | 12.790564 |
| aged-ten | 40 | 11.040979 | 15.130512 | 8.645272 | 42 → 3 | 80 → 2 | 40 | 8.798113 |
| dense-25 | 100 | 47.202209 | 61.212800 | 30.661683 | 102 → 4 | 200 → 4 | 64/36 | 19.797565 |
| divine-next-departure | 1 | 9.045439 | 11.302757 | 12.566691 | 3 → 3 | 2 → 2 | 1 | 9.698388 |
| divine-short | 3 | 17.137414 | 19.756459 | 16.910362 | 5 → 3 | 6 → 2 | 3 | 14.098230 |

Three shared full gates are request entry, flush and final clock gap. Two clones
are private candidate and detached commit, not small before-event witnesses. The
two-day ten-aircraft workload contains one strict Booking fence (40/1/40 commits);
dense-25 uses 64/36 commits. Aged-ten adds 1,000 genuinely resolved NO_OP records.
Divine Air is a read-only detached schema-7 fixture at 2026-09-12T12:20:00Z with
one aircraft and 21,901 Booking rows; short target is four hours after next departure.
Production Saves were not modified.

| Fixture | Capture s | Validation s | Protected serialization s | JSON s | Alias s | Manifest s | Cost + records s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| one-departure | 0.022229 | 0.061488 | 0.043203 | 0.017535 | 0.021059 | 0.001257 | 0.000000 |
| one-completion | 0.032351 | 0.072967 | 0.057255 | 0.018496 | 0.024963 | 0.001575 | 0.000545 |
| round-trip | 0.093942 | 0.274888 | 0.185113 | 0.078112 | 0.093950 | 0.005667 | 0.000789 |
| dense-departure | 0.478257 | 1.115888 | 0.755659 | 0.342924 | 0.383117 | 0.120219 | 0.000000 |
| dense-completion | 0.456914 | 1.104926 | 0.786533 | 0.342526 | 0.354468 | 0.066445 | 0.008939 |
| mixed-ten | 1.876093 | 4.845697 | 3.334697 | 1.458831 | 1.623376 | 0.290014 | 0.022498 |
| representative-ten | 5.606922 | 14.355765 | 10.099238 | 4.335878 | 4.811186 | 0.883039 | 0.044877 |
| aged-ten | 1.908589 | 5.030544 | 3.399827 | 1.613002 | 1.657281 | 0.276568 | 0.018954 |
| dense-25 | 7.574336 | 19.497465 | 13.708251 | 5.935706 | 6.546654 | 1.107496 | 0.048383 |
| divine-next-departure | 0.559192 | 1.400822 | 1.009732 | 0.405121 | 0.506275 | 0.074641 | 0.000000 |
| divine-short | 1.668031 | 4.807162 | 3.084928 | 1.227269 | 2.036520 | 0.220626 | 0.000769 |

Capture/validation include nested serialization/manifest/JSON/alias/helper time;
columns must NOT be summed. Cost+records includes handler AND proof calls, not an
isolated finance-only timer. Manifest calls double (e.g. 40 → 80 in mixed-ten); no
second Booking index was introduced. Kernel before-event pending/history witnesses
cost .549165 s in aged-ten versus .044853 s in mixed-ten; Completion input checks
also scan prior aircraft results. These scans still grow with retained history.

| Fixture | Complete authoritative SHA-256 (before = after strict = final shared) |
| --- | --- |
| one-departure | `5e42898747dea9a5c07d2e34270224dadc854d9579ba8b0bf36b308988364c87` |
| one-completion | `b2346d27f4cb0c75b68c544fe9e553de140e747f32b9ac3abb4ea80640a1d1b8` |
| round-trip | `a74008b1f14e316f320c269a8d0303518780b527c988c4e5fccc56aa657c8a49` |
| dense-departure | `eda36ae619c8f7b004f6cf4ed788da7c4bb560be60000dc2d37a56d04dfcc233` |
| dense-completion | `0b0717295a901727e6c2020f88e1626de4d0a025e9acbb5656bb90258d5f03c1` |
| mixed-ten | `393ddb47218f2427162c0b1a464f463ed75f744c22451823093de5f979d2f726` |
| representative-ten | `8eb47f6302cf6bb497c54372e3d504598481693eb5aabd5e70bb4f2687912c43` |
| aged-ten | `9fa843144124d850242b4b58306fe61623ef2666eeb654893531500169a9cded` |
| dense-25 | `81b58ab5340fb59790468e855031e1752d79909a35ce8bb3edd648b9fd23de0c` |
| divine-next-departure | `85aff62c20cf92053921eef2e940228e845f2eaa6631d36a4259e5c2073f5d51` |
| divine-short | `c9578420b04edb4b63e98274eb92d26fd53e1899905ec4a9e0896b1e0ad0da37` |

Dense throughput improves; isolated events have no clone/full-gate reduction and
pay extra proof costs. The 10-aircraft two-day case is 29.55 → 24.45 s; the controlled
25-aircraft case is 47.20 → 30.66 s. Shared steps reach 12.79 and 19.80 s respectively.
Divine next departure regresses 9.05 → 12.57 s; short advancement is 17.14 → 16.91 s.
These results do not prove Normal/Ultra/500-aircraft GUI responsiveness or Stage 3F
acceptance. Full-world gates, serialization, JSON/alias walks and Booking/history
scans remain dominant. Stage 3D needs separately approved scope; Stage 3E must retain
a separate production correctness, bounded-latency and runtime performance gate.

### Memory findings

Fresh-process dense-25 controls, one latency sample per process, identical input and
output hash: original strict source measured **89,305,088 bytes (85.17 MiB)** before
instrumentation; final shared measured **79,921,152 bytes (76.22 MiB)**. These are
process-lifetime high-water marks including imports/setup, not per-event allocations
or a steady-state memory guarantee. The extra one-sample latency observations
(58.41 / 28.70 s) are not substituted for the three-sample timing table.

Mock-instrumented peaks were **1,160,318,976 / 121,266,176 bytes**. Mock call histories
retain arguments, including distinct strict candidates, so those larger values
cannot establish production memory savings. The profiler records the pre-mock
`latency_lifetime_peak_bytes` separately from its post-instrumentation high-water
mark. To compare cases without contamination from earlier instrumentation, run each
case/mode in a fresh process. Full combined-process peaks are not working memory.

### Flight verification

- Independent Departure proof + original fulfilment gate: 25 PASS, 16.414 s,
  before enabling Departure; subsequent Departure shared gate: 12 PASS, 34.530 s.
- Independent Completion proof + fulfilment + maintenance gate: 35 PASS, 58.691 s,
  before enabling Completion. Development flight/Stage 3A gate: 60 PASS, 93.980 s.
- Final JSON/alias/type-proof gate: `python -B -m unittest
  tests.test_flight_certification.DepartureProofTests
  tests.test_flight_certification.CompletionProofTests -q` — 13 PASS, 21.003 s.
- Final affected gate: `python -B -m unittest
  tests.test_flight_certification.DepartureProofTests
  tests.test_flight_certification.DepartureSharedTests
  tests.test_flight_certification.CompletionProofTests
  tests.test_flight_certification.CompletionSharedTests tests.test_shared_candidate
  tests.test_payment_certification tests.test_stage1_flight_fulfilment
  tests.test_step6_maintenance -q` — **124 PASS, 389.223 s**; all 36 Stage 3A and
  28 Stage 3B regressions passed.
- `python -B -m unittest tests.test_flight_certification.FlightFenceTests -v` —
  **2 PASS, 127.158 s**. Both seeds preserve real matured history; weekly/Booking
  fences, saved prefixes and Payment/Departure/Expiry/Completion ordering match.
  Early fixture errors retained schema-7 recurrence fields in a schema-6 world
  and published after the pre-flight reservation began; fixtures corrected using
  valid older options and earlier publication, without changing gameplay rules.
- Full repository suite: `python -B -m unittest discover -s tests -q` —
  **862 PASS, 1,367.288 s**, baseline 819 + **43 new Stage 3C tests**. Verified
  final production source and all tests before the stronger month-boundary fixture
  below; no production source changes followed this run.
- Post-review month-boundary gate: `python -B -m unittest
  tests.test_flight_certification.FlightFenceTests.test_real_final_payments_departure_expiry_and_completion_exact_order
  -q` — **1 PASS, 81.779 s**. The stronger existing fixture retains actual strict
  Rotation and Booking inside the compared request before the shared Payment/
  Departure prefix, expiry fences and Completion, including saved continuation.
  Only this test fixture and documentation changed after the full run.
- Native fresh-process `python -B -m tests.smoke_runtime_startup` — PASS: direct
  Load Game, Resume/Advance, two completed Booking checkpoints, 14 Booking rows,
  no advancement error, exact paused save/reload; SDL2/GLEW/Intel UHD Graphics 630,
  window 2560×1377. No New Game/screen navigation in the child. This strict GUI
  smoke does not prove shared multi-event production responsiveness.
- Scoped `python -m compileall -q app game tests main.py make_snapshot.py settings.py
  test.py` — PASS after review. 184 documentation paths/anchors — PASS;
  `git diff --check` — PASS. Final diff/source review found no unresolved issue.
  No later stage or production pacing change is included.

Benchmark commands: `python -B -m tests.profile_flight_certification --fixtures
<TEMP fixtures> --mode both --observed-fixture <detached TEMP envelope> --repeats 3`
for controls; `--mode shared` after final JSON proof checks; corrected first case
uses `--case one-departure --mode both`. Fresh-process memory controls use
`--case dense-25 --mode strict/shared --repeats 1`.

## Contract Payment certification — Stage 3B (2026-10-04 working tree)

Baseline `f44b2790bf02bec2d5ddd4c2bd674ffc902c6b07` matched live origin/master.
Only the exact built-in Payment is certified for supported active schema-6/7 USD
anniversary inputs, under `ph-aircraft-contract-payment-shared-v1`. See the
[write footprint, validator dependency map and proof](Contract%20Payment%20Shared%20Certification.md).

- Pure existing installment arithmetic stays in aircraft_market; exact posting
  normalization/construction stays in economy. The world-state transition proof
  checks genuine before/after records, exact cash/assets/expense/principal/financing,
  journal lineage, finance revision, all allocator cursors, kernel lifecycle and
  successor topology. Protected fingerprints include untouched records/history.
- Every payment proves intermediate validity; final full validation/detached commit
  remains. Custom/replacement/unsupported inputs retain strict execution. Strict
  replay preserves the successful prefix or visibly disables on optimizer divergence.
- Expiry, Booking and weekly publication stay fences. Departure/Completion/Rotation
  stay strict. Session/Kivy/Advance remain strict; no multi-event pumping, overload
  recovery, formula/RNG/flight/schedule change or Stage 3C–3F work.
- Stage 2 reads never see candidate finance; detached commit invalidates the old
  epoch. Save/load remains paused and exact, schema remains **7**, no proof metadata
  or candidate state is persisted. Existing .venv remains untouched.

### Payment measurements

Before: original Stage 3A strict source, before payment refactoring/certification.
After: identical in-memory fixtures, final proof source; strict control included
for host variation. Python 3.12.10/Windows, three latency samples per path, batch
cap 64. Setup, real-event maturation, cloning and output hashing are excluded from
latency; operation counts/timers use separate instrumented runs. All five hashes
match the original baseline exactly. Sequential-eight uses eight contracts with
successive one-second anniversaries; dense-64 uses equal-time payments. Aged-eight
adds 1,000 resolved NO_OP history records, not fabricated journals/flights.

| Fixture | Before strict seconds | After strict control | After certified shared | Full validations before → shared | World clones before → shared | Commits before → shared |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| One payment | .110350 | .100590 | .107457 | 3 → 3 | 2 → 2 | 1 → 1 |
| Sequential eight | .444271 | .407174 | .197038 | 10 → 3 | 16 → 2 | 8 → 1 |
| Dense 64 | 4.480499 | 4.382520 | 1.250030 | 66 → 3 | 128 → 2 | 64 → 1 |
| Two final payments + expiry fences | .688422 | .620431 | .557959 | 6 → 5 | 8 → 6 | 4 → 3 |
| Aged eight | .810209 | .725704 | .422988 | 10 → 3 | 16 → 2 | 8 → 1 |

The three shared-only full gates are request entry, candidate flush and final clock
gap. Clone counts include detached commits, not small witnesses. Shared payment
batch sizes here are 1/8/64/2/8; each expiry still executes its own strict transaction.
One payment has no structural gain and adds proof overhead versus the after strict
control. Dense payments improve; this does NOT solve flight/normal runtime speed.

| Shared fixture | Capture seconds | Transition proof seconds | Full market-validator seconds (before → shared) | Complete world SHA-256 |
| --- | ---: | ---: | ---: | --- |
| One | .004046 | .004850 | .001236 → .000862 | `6fb6110daa0d024ea81eeaa52d68412369febc37d26b005459ea58aa2797c1af` |
| Sequential eight | .035940 | .038508 | .006860 → .001394 | `c66a567a6a73168a3ff26c0dfb87a9aedfe96633f034d75b7a7cca1f9ddfcbeb` |
| Dense 64 | .439217 | .483599 | .184010 → .007795 | `654f00ac0d985026d14fd4ecef1d065afbd283dcd5ae0adce14379d4599c6584` |
| Final/expiry | .018170 | .020007 | .006967 → .006658 | `82dddb0771b43ba1c7d300b4723ed518dec8c5d2978abe54baf8ca32259331d2` |
| Aged eight | .069187 | .072177 | .004958 → .001435 | `9b11ade3af6157dd83ce6e9f469b2acbd8d842a362fca6e99524c61fc1ad047d` |

Proof capture/validation account for significant measured work. Protected-state
serialization and transaction chronology scans grow with history; kernel witnesses
also copy/scan pending/history. Market-validator timing includes journal/contract
checks, not finance-only isolation. No speculative cache or history optimization.

Additional same-contract three-anniversary control (measured after extraction,
using the retained strict reference): strict **10.265891 s**, shared **10.619857 s**;
68 full validations/132 clones/66 commits on BOTH paths, three payments among 66
real events over two more months. Proof capture .013676 s, proof validation .014566 s;
market validation .026571 → .024038 s. Exact matching full-world hash:
`612b76349fdd0d73b503f8ba041e7a6eed1ffd197765eddfaa0db4fadf4276f5`.
Intervening strict Booking/rotation fences prevent those distant installments from
sharing one candidate. This mixed runtime control shows no batching benefit; it is
not an original-source BEFORE measurement and is not a runtime speedup claim.

### Verification

Verified 2026-10-04 using existing `.venv/Scripts/python.exe`, Python 3.12.10:

- Initial proof + marketplace gate: `python -B -m unittest
  tests.test_payment_certification tests.test_stage1_aircraft_marketplace -q` —
  14 PASS, 36.064 s, before enabling the payment certificate.
- Development payment/Stage 3A gate: `python -B -m unittest
  tests.test_payment_certification tests.test_shared_candidate -q` — 59 PASS,
  175.962 s. Early fixture errors used nonexistent session setters/methods; fixed
  to the actual read-only airline property and `finances()` API.
- Affected gate: `python -B -m unittest tests.test_payment_certification
  tests.test_shared_candidate tests.test_simulation_resolver tests.test_owned_reads
  tests.test_stage1_aircraft_marketplace tests.test_stage1_aircraft_acquisition
  tests.test_stage1_event_kernel tests.test_step7_save_load tests.test_stage1_runtime
  tests.test_advancement_performance tests.test_runtime_startup
  tests.test_player_speeds -q` — **242 PASS**, **593.383 s**. All 36 Stage 3A,
  23 Stage 1 resolver/oracle and 19 Stage 2 ownership tests passed; 26 payment tests
  at that gate. Final additions/changes are covered by the next three-test gate.
- Final review regressions: `python -B -m unittest
  tests.test_payment_certification.PaymentSharedTests.test_first_invalid_transition_cannot_wait_for_a_later_repair
  tests.test_payment_certification.PaymentBoundaryTests.test_near_time_partitions_and_saved_payment_prefix_exact_oracle
  tests.test_payment_certification.PaymentProofTests.test_approved_financing_cent_remainder_witnesses
  -q` — **3 PASS**, **23.600 s**. Current Stage 3B total: **28 new tests**.
- Full repository suite: `python -B -m unittest discover -s tests -q` —
  **819 PASS**, **1,026.613 s**, no failures; baseline 791 + 28 new Stage 3B tests.
  Verified final implementation/test working tree before commit.
- Scoped `python -m compileall -q app game tests main.py make_snapshot.py settings.py
  test.py` — PASS. 176 documentation paths/heading anchors — PASS;
  `git diff --check` — PASS. Final source/diff review found no remaining issue.
- Native `python -B -m tests.smoke_runtime_startup` — PASS in a fresh process:
  direct Load without New Game, two completed Booking checkpoints/14 bookings,
  UTC `2026-09-02T00:00:30Z`, exact paused save/reload, SDL2 window 2560x1377.
  Temporary KIVY_HOME and KIVY_NO_ARGS/KIVY_NO_FILELOG avoid user log permissions.
  This smoke covers the retained strict GUI startup path, not shared payment GUI
  integration or human responsiveness. Payment runtime is exercised by real-domain
  strict/shared/shadow/oracle tests and the 66-event anniversary control.

No dependencies, production saves or .venv contents changed. Benchmark tooling's
first instrumented draft incorrectly left original proof metadata bound while
wrapping module functions, so that instrumented path conservatively fell back to
strict. Tooling now rebinds the instrumented certificate; only corrected counts/
measurements above are evidence. No production bypass was added.

Next proposed bounded slice: Stage 3C Departure/Completion certification, requiring
separate approval and substantially broader manifest/settlement/maintenance proofs.
No Stage 3C implementation began.

## Runtime shared candidate infrastructure — Stage 3A (2026-10-04 working tree)

Baseline `1682c0b3c47a8a102da2d2ee2ffb172ea237ea29` matched live origin/master
before editing. Approved [canonical transaction amendment](Stage%201%20State%20Schema.md#clock-and-event-contract)
and [Stage 3A technical description](Runtime%20Shared%20Candidate%20Infrastructure.md)
establish identity-bound STRICT/SHARED/FENCE metadata and opt-in bounded private
candidates. Full validation remains mandatory after EVERY candidate transition
and at final flush; strict is the production default and recovery/reference path.

- Only exact built-in NO_OP is shared-classified. Custom names/callables do not
  inherit it. Payment, Departure, Completion and Rotation remain strict; Booking,
  weekly publication and expiry are fences. No domain certification or local
  reduced-validation proof is implemented. Synthetic fixtures require full shadow.
- Candidates never survive a cooperative return or enter saves/read indexes.
  Generated events are selected through the updated canonical heap. Cumulative
  request ceilings survive flushes and management refreshes. Kernel contract
  witnesses are detached simulation/event-history evidence, not whole-world
  clones per event or candidate-versus-itself comparisons.
- Strict recovery reselects the attempted segment, preserves its successful prefix
  and exact failure, or visibly reports optimizer divergence with a disposable
  disable latch. Optional debug shadow compares complete intermediate envelopes.
- Session, terminal, explicit Advance and Kivy pacing remain strict. Save/load,
  autosave, pause, exit, overload and speed behavior are unchanged. Schema stays
  **7** with no persisted resolver fields. Stage 3B–3F remain unimplemented.

### Infrastructure measurements

`python -B -m tests.profile_shared_candidate --repeats 5 --events 64` on Windows
10/Python 3.12.10, batch size 8, in-memory schema-1 infrastructure fixtures.
Five sequential samples per mode; host load/warmup can affect timing. Setup,
comparison and post-validation are excluded; counters/tracemalloc are separate.
Complete output worlds matched. This is NOT a PH flight-engine speedup claim.

| 64 events / mode | Median seconds | Full validations | World clones | Commits | Before-event witnesses | Peak traced bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NO_OP strict | .003825 | 2 | 0 | 0 | 0 | 45,204 |
| NO_OP shared infrastructure | .277392 | 74 | 16 | 8 | 64 | 329,993 |
| NO_OP debug shadow | .454211 | 138 | 24 | 8 | 64 | 338,784 |
| Custom strict | .234830 | 66 | 128 | 64 | 0 | 438,622 |
| Custom opt-in strict fallback | .213788 | 66 | 128 | 64 | 0 | 453,627 |
| Custom shadow-option strict fallback | .203577 | 66 | 128 | 64 | 0 | 437,478 |

Stage 3A adds proof overhead to the existing cheap NO_OP path. Custom fallbacks
retain identical validation/copy boundaries; timing variation is not claimed as
improvement. Whole-world clones include detached commits; witness copies remain
a growing-history cost. These small-fixture allocation peaks do not certify PH
memory use, human responsiveness or 50-aircraft Ultra performance.

### Verification

Verified 2026-10-04 against the Stage 3A source/test working tree:

- Initial affected kernel/startup gate: `python -B -m unittest
  tests.test_stage1_event_kernel tests.test_runtime_startup -q` — 57 PASS,
  10.344 seconds.
- Development affected gate: `python -B -m unittest tests.test_shared_candidate
  tests.test_simulation_resolver tests.test_owned_reads tests.test_stage1_event_kernel
  tests.test_step7_save_load tests.test_stage1_runtime tests.test_advancement_performance
  tests.test_runtime_startup tests.test_player_speeds -q` — 182 PASS,
  592.194 seconds. Included all 23 Stage 1 resolver/oracle and 19 Stage 2 ownership
  tests; five subsequent Stage 3A edge regressions are covered by the final gates.
- Final `python -B -m unittest tests.test_shared_candidate -q` — **36 PASS**,
  37.669 seconds. These are 36 new tests, including exact complete-world gameplay
  equivalence with rolling recurrence and in-flight save continuation.
- Final `python -B -m unittest discover -s tests -q` — **791 PASS**,
  **991.182 seconds**, no failures/errors/skips reported (755 baseline + 36 new).
- `python -m compileall -q app game tests main.py make_snapshot.py settings.py
  test.py` — PASS; only the explicit source scope compiled.
- 170 local documentation paths/heading anchors checked — PASS;
  `git diff --check` — PASS. Complete diff/architecture self-review is clean.

Commands used the existing `.venv/Scripts/python.exe` (Python 3.12.10). The final
full suite used temporary KIVY_HOME plus KIVY_NO_ARGS/KIVY_NO_FILELOG to avoid
user-log-directory permissions. No production saves or dependency changes.

Native existing `python -B -m tests.smoke_runtime_startup`: PASS in a fresh GUI
process, direct Load without New Game, two completed Booking checkpoints/14
bookings, UTC `2026-09-02T00:00:30Z`, exact paused save/reload, SDL2 window
2560x1377. Used `KIVY_NO_ARGS=1`, `KIVY_NO_FILELOG=1` and temporary KIVY_HOME;
the first unconfigured invocation rejected the smoke's --load argument and could
not write the user's Kivy log directory. No smoke source or production data changed.
This is functional native smoke, not human-level responsiveness certification.

Next bounded implementation is Stage 3B contract-payment certification, requiring
its own scope approval and intermediate-invariant proof. No later slice began.

## Runtime trusted reads — Stage 2 (2026-10-03 working tree)

Successor of verified live `6c729ff0d1265f6eef2abac8420f8ed69afca5b5`.
Implemented only session-owned reads and disposable, revision/source-bound
operations lookups. See [Runtime Trusted Reads](Runtime%20Trusted%20Reads.md)
for full before/after tables, profiling, memory and remaining costs.

- New Game/validated Load establish private `app.owned_reads` ownership. Foreign
  world assignment revokes it and requires one complete validation. Successful
  session commands/events and controlled clock changes discard all derived state;
  root/subtree/revision/clock mismatch revalidates before reuse. Borrowed world
  rows must not be mutated by frontends; public arbitrary-world APIs retain gates.
- Fleet/Flights/Finance share original projection/manifest rules. Operations
  views lazily derive immutable booking IDs by flight and next pending event ID
  by flight, then retain at most eight bounded immutable encoded pages. Every
  returned value is detached. Terminal and Kivy use the same session, with no
  screen redesign. Booking package import is deferred until an owned read so
  fresh projection imports cannot conceal missing runtime startup registration.
- No view index enters an event candidate/handler or save. New/loaded worlds
  reconstruct lazily. Schema **7**, templates, histories and save meaning unchanged.
  Resolver/kernel per-event candidate, full result validation and detached commit
  remain unchanged; Stage 3 and overload recovery are **not implemented**.

Frozen latest Divine Air autosave: one aircraft, 718 flights, 21,901 bookings,
117 results. Already-owned cold Flights **4.668 → .08193 s**, Finance/recent
results **3.558 → .02677 s**, Fleet **3.104 → .00019 s**; repeated views below
1 ms. The independent foreign-binding first Fleet read still pays its full gate
(2.314 s). Three-view validations **3 → 0**; cold owned index builds once, visiting
398 relevant manifest bookings rather than 657,030 unrelated-inclusive visits.
Four paired fixtures (Divine Air, starter, aged recurring, ten-aircraft) matched
all view outputs, input hashes and exact next-event/one-hour Advance output hashes.
These are local single samples, not controlled timing medians.

Strict next-departure validation/copy counts stay **2/2**; checkpoints stay **2/5**.
Divine Air next-event time **7.207 → 6.946 s**, one-hour Advance **10.039 → 11.324 s**:
no engine throughput improvement is claimed. Full event validation/copying still
dominate. Reference catalogs were under 1% of its next-event profile and retain
all original integrity checks. Handler-side manifest index reuse is deferred
because the isolated candidate has no proven runtime source-binding contract.
Cold derived storage retained about .307 MB/peaked .936 MB for Divine Air; this
adds bounded presentation storage, not a whole-process memory reduction claim.

Verification uses Python 3.12.10 in the existing `.venv`, with no installation:

- `python -B -m unittest tests.test_stage1_terminal_harness tests.test_stage1_flight_fulfilment -q`:
  **40 passed, 39.810 s** during development.
- `python -B -m unittest tests.test_owned_reads -q` initial ownership subset:
  **15 passed, 38.579 s**; three additional boundary cases were then added.
- `python -B -m unittest tests.test_owned_reads tests.test_simulation_resolver
  tests.test_stage1_terminal_harness tests.test_stage1_flight_fulfilment -q`:
  **81 passed, 328.252 s**, including all 23 Stage 1 oracle cases and all 18 new
  ownership/lookup tests at that revision. Exact worlds agree across checkpoints, rolling publication,
  departure/completion, contract payment/real one-year expiry and save/load.
- `python -B -m unittest tests.test_runtime_startup tests.test_step7_save_load
  tests.test_owned_reads.OwnedReadTests.test_foreign_binding_validates_once_then_owned_reads_need_no_gate
  tests.test_owned_reads.OwnedReadTests.test_new_game_uses_construction_proof -q`:
  **19 passed, 42.099 s** after the lazy-import correction.
- Initial complete discovery/runner: **754 passed, no failures/errors/skips**,
  900.722 s runner time (903.720 s including discovery). The final malformed-root
  guard added one test after this discovery; its focused three-case run passed
  in 3.881 s. Final required command
  `python -B -m unittest discover -s tests -q`: **755 passed, 846.049 s**,
  no failures/errors/skips, final Stage 2 source/test working-tree scope.
- `python -B -m tests.smoke_runtime_startup`: native fresh-process direct Load,
  checkpoint processing and exact paused save/reload **PASS**; 14 bookings/two
  completed checkpoints, final UTC 2026-09-02T00:00:30Z, 2560×1377 SDL2 window.
  This smoke first caught early Booking registration from an eager lookup import;
  the lookup import was deferred and the fresh-process smoke passed unchanged.
- `python -B -m tests.smoke_advancement --fixtures <temporary-fixtures>
  --case observed-save --mode load --view Flights --days 1`: valid **TIME_BUDGET**
  prefix at 120.008 s, 22 events (11 departures/10 completions/one checkpoint).
  Complete world validation, Fleet/Flights/Finance/Schedule rendering and exact
  paused save/reload passed. Longest tick 10.133 s; this was concurrent with full
  verification, not an isolated responsiveness measurement or completed-day claim.
- `python -B -m tests.smoke_player_speeds --seconds 2 --fixture <temporary starter-1.json>`:
  **PASS** for all four named speeds, Pause/Resume, explicit Advance and exact
  paused save/reload. Accounted credit ratios 30/210/900/1800; phases retained
  debt, with 1.301–1.341 s longest ticks. No sustained-speed/human responsiveness
  certification; authoritative heavy transactions still block the event loop.
- Scoped `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`,
  changed-document links and `git diff --check`: PASS.

Source changes are confined to `app/session.py`, new `app/owned_reads.py`, and
`game/aircraft_operations/projections.py`/`fulfilment.py`; tests add
`test_owned_reads.py`/`profile_owned_reads.py`. Directly affected documentation
records ownership, invalidation, persistence, verification and measured limits.
Production saves/reference data, simulation/kernel, RNG/economy/scheduling rules,
canonical schema/template and pre-existing untracked `.venv/` remain untouched.

Next recommendation: Stage 3 needs a separately approved bounded transaction
contract design and exact-prefix/equivalence tests. Read latency is now small;
retained strict validation/copying is the meaningful remaining bottleneck. Stop
at Stage 2, without initiating that implementation.

## Runtime resolver foundation — Stage 1 (2026-10-03 working tree)

Successor of baseline `29761181d9883da8a97eb1fffe80522c6a0f2f8e`, verified
against live origin/master before editing. Scope is only the approved resolver
facade and deterministic equivalence oracle; see
[Runtime Resolution Foundation](Runtime%20Resolution%20Foundation.md).

`game.simulation.resolver` wraps the unchanged strict kernel. Cooperative
`begin_resolution(...).step()`, synchronous `resolve_until(...)` and single
`resolve_next_event(...)` expose real yields/terminal diagnostics without a second
dispatcher. Pacing and shared-session duration/day/UTC/Next Event use this facade;
Kivy and terminal keep their existing application session and visible behavior.
Progress distinguishes current authoritative UTC, the last committed event and
whether equal-time work remains. Boundary inspection is derived/on demand.
Facade requests, progress/target metadata and fences are runtime-only; existing
fast-forward fields stay unchanged. Schema stays **7**.

The oracle compares complete canonical envelopes against strict Next Event,
single target, irregular partitions, cooperative steps and exact paused save/load
continuation. No envelope fields are excluded. Only JSON dictionary ordering is
normalized; file wrapper save time/serial/IDs/integrity are outside the envelope.
Real PH fixtures cover booking/carriage/finance, multiple seeds, finite/continuous
recurrence and weekly extension, same-time ordering, month rotation/payment,
actual one-year contract expiry, booked-flight protection and matching revision
actions. Negative cases retain validation, failed prefixes, unknown/stale handling,
alias isolation and cumulative limits. Existing domain outputs/hashes remain gates.

Affected files: `game/simulation/resolver.py`, `pacing.py`, `__init__.py`;
`app/session.py`; `tests/resolution_oracle.py`, `test_simulation_resolver.py`,
`profile_resolution.py`; this status, runtime specification, foundation document
and Docs index. No kernel, domain formulas, RNG, schema/template, GUI implementation,
production saves or reference data changed. Pre-existing untracked `.venv/` untouched.

Timing sanity, existing busy fixture, setup/copy/hash/post-validation excluded:
pre-edit strict one-day median **3.565 s** (three samples, five events).
After implementation, alternating strict/facade three-sample medians:

| Case | Strict reference | Facade | Events |
| --- | ---: | ---: | ---: |
| Quiet PH career, seven days | 1.527 s | 1.394 s | 7 |
| Busy starter, one day | 3.417 s | 3.399 s | 5 |

All paired complete envelopes/hashes matched. Differences are measurement variation,
not optimization gains. Tool: `python -B -m tests.profile_resolution --repeats 3`.
No large-fleet benchmark or sustainable Ultra certification is claimed.

Verification, 2026-10-03, implementation working-tree scope:

- Existing-interpreter commands used `.venv/Scripts/python.exe` (Python 3.12.10);
  no installation or environment changes. Kivy runs disabled file logging/argument
  parsing through runtime environment variables.
- `python -B -m unittest tests.test_stage1_runtime.RuntimeTests tests.test_player_speeds -q`:
  **17 passed, 4.301 s**.
- `python -B -m unittest tests.test_simulation_resolver.ResolverGameplayEquivalenceTests.test_finite_recurrence_and_different_seed_booking_partitioning tests.test_simulation_resolver.ResolverBoundaryTests -q`:
  **18 passed, 39.338 s**.
- `python -B -m unittest discover -s tests -q`: **PASS, exit 0**.
  Independent discovery confirms **736 tests, no declared/runtime skip sites**.
  KIVY_NO_CONSOLELOG suppressed the unittest console summary; no elapsed time
  is claimed for this full run. All 23 new resolver tests are included.
- Scoped compile command: `python -m compileall -q app game tests main.py
  make_snapshot.py settings.py test.py`: exit 0.
- `python -B -m tests.smoke_runtime_startup`: displayed fresh-process direct
  Load Game, real booking checkpoint, Advance and exact paused save/reload passed.
  Two checkpoint records/14 bookings; final UTC 2026-09-02T00:00:30Z.
- `python -B -m tests.smoke_player_speeds --seconds 2`: all four named controls,
  Pause/Resume, explicit Advance and exact paused save/reload passed in native SDL2
  Kivy 2.3.1. Credit accounting matched literal rates; short phases retained debt.
  Longest ticks were 1.425–1.544 s. This is functional programmatic smoke, not
  sustained throughput or human responsiveness certification.

Changed-document links resolve; scoped compile and `git diff --check` pass.
Final complete-diff review retained exact strict transaction behavior and found
no remaining in-scope authority, persistence, concurrency or scope issue.

No shared multi-event candidates, reduced validation frequency, prefix replay,
incremental validation/indexes, booking/recurrence optimization, new overload
recovery, threads, map/replay or offline progression were implemented. Existing
overload still pauses with retained credit. Protected future fences are booking
checkpoint, weekly publication and contract expiry. Stage 2 implementation is
recorded above; amend the canonical transaction behavior before any shared-candidate
implementation.

## PH named continuous-runtime speeds (2026-10-03 working tree)

Successor of verified live baseline `019daaa4001abfa1eaaedcffb7b7dffbfeef0373`.
Normal Speed now means 30 game days / 24 real hours. Central configuration in
`game/simulation/speeds.py` defines Normal/Fast/Very Fast/Ultra relative 1/7/30/60,
literal 30/210/900/1800, and derived day durations. The shared controller samples
old-rate credit before switching, retains transaction/queue limits, and uses the
current configured literal ratio for processing-delay credit and overload bounds.
Kivy exposes named controls and in-place named status, including visible runtime
diagnostics. Terminal Resume consumes the same boundary; explicit Advance remains.

Selected speed is runtime-only. Save schema/JSON remain unchanged; saved NORMAL
ratios remain literal and are not multiplied on load. New controllers select
Normal Speed; validated load remains paused, retaining the saved literal ratio
until explicit Resume replaces it with 30. Pause/resume within an open session
retains selection. No offline progression, worker threads or gameplay changes.

Displayed native SDL2 Kivy smoke (`python -B -m tests.smoke_player_speeds --seconds 8
--fixture <temporary starter-1.json>`) reloaded the same valid busy starter snapshot
for each speed. It crossed a real daily Booking boundary and operated flights,
then passed Pause/Resume, explicit Advance, manual save and exact paused reload.
Measured on Windows/Intel UHD 630, with one aircraft and existing Booking/history:

| Speed | Requested literal ratio | Active seconds | Processed game seconds | Achieved ratio | Retained game credit | Credit / requested rate (real seconds) | Longest GUI tick |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Normal Speed | 30 | 8.019 | 222 | 27.683 | 18.579 | 0.619 | 1.650 s |
| Fast | 210 | 8.186 | 1587 | 193.856 | 132.163 | 0.629 | 1.546 s |
| Very Fast | 900 | 8.409 | 7091 | 843.247 | 477.247 | 0.530 | 1.208 s |
| Ultra | 1800 | 8.521 | 13801 | 1619.602 | 1537.215 | 0.854 | 1.225 s |

Processed time plus retained credit exactly accounted for each requested ratio
(to floating-point reporting precision). All worlds validated; no overload or
handler error occurred. None had processed its entire requested target at the
measurement stop; all retained less than one real second of work. This short
single-aircraft observation is not sustained throughput certification, especially
for Ultra or large airlines. Atomic transactions still stall Kivy; scalable
runtime/catch-up remains follow-up work, with authoritative validation preserved.
Programmatic displayed smoke does not establish human-perceived responsiveness.
Fixtures/saves/results were temporary; production saves and `.venv/` untouched.

Affected files for this bounded successor:

- Runtime: `game/simulation/speeds.py`, `game/simulation/pacing.py`.
- Shared/frontends: `app/session.py`, `app/gui/app.py`, `app/terminal/main.py`.
- Tests/tools: `tests/test_player_speeds.py`, `tests/test_stage1_runtime.py`,
  `tests/test_gui_foundation.py`, `tests/test_step7_save_load.py`,
  `tests/test_advancement_performance.py`, `tests/smoke_player_speeds.py`,
  `tests/smoke_runtime_startup.py`.
- Authority mirror: `Data/Templates/template_reference.txt` and the canonical
  `Stage 1 State Schema.md` clock policy text; neither adds a field or migration.
- Current documents in `Docs/03 Technical`: this status, `Decision Register.md`,
  `Continuous Runtime Technical Specification.md`,
  `PH GUI Foundation Technical Specification.md`, and
  `Stage 1 Terminal Harness Technical Specification.md`.

Verification on the complete speed-redesign working-tree scope, 2026-10-03:

- `.venv/Scripts/python.exe -m unittest tests.test_player_speeds tests.test_stage1_runtime tests.test_gui_foundation tests.test_step7_save_load tests.test_runtime_startup tests.test_advancement_performance`: **66 passed, 146.038 s**.
- `.venv/Scripts/python.exe -m unittest discover -s tests`: **713 passed, 783.225 s**.
- `.venv/Scripts/python.exe -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`: exit 0.
- `.venv/Scripts/python.exe -B -m tests.smoke_player_speeds --seconds 8 --fixture <temporary starter-1.json>`: all four displayed native speed phases plus Advance/save/paused reload passed; measurements above.
- `.venv/Scripts/python.exe -B -m tests.smoke_runtime_startup`: displayed fresh-process direct Load Game passed, two checkpoints, 14 bookings, exact paused save/reload.
- Documentation file links resolved; `git diff --check` clean. Self-review found
  no remaining in-scope correctness, save, concurrency or authority issue.

Follow-up remains sustainable high-speed runtime/catch-up performance for larger
or denser airlines; this increment exposes rates without certifying throughput.

## Explicit runtime advancement performance successor (2026-10-03 working tree)

Scope is the runtime-performance successor of live baseline
`051561ad59c4c2eaf8f35ec4ddf306264732606f`.
See [Runtime Advancement Performance Investigation](Runtime%20Advancement%20Performance%20Investigation.md)
for reproduction, tooling, complete/partial measurements, profiles and limitations.

Measured flight/Booking CPU work contained nested whole-world transactions,
redundant validations and primitive/subtree rescans. Nested domain commands now
reuse the kernel-owned isolated candidate only with its exact private capability.
Complete kernel result validation, handler contracts, detached commit, public
command validation, Booking preparation/witnesses/provider isolation and rollback
remain. Primitive-tree runtime clones use an internal guarded standard-library
codec; JSON save encoding/schema is unchanged. Validator proof reuse is per
invocation; UTC syntax caching is bounded to immutable strings. No demand,
booking/economy, timing, turnaround, recurrence or authoritative field changes.

Explicit requests retain 10,000 processed/generated-event ceilings across yields;
normal paced runtime keeps its existing 100-generation budget. The historical
measurements in this section used the then-current literal 7× behavior; the named
speed successor above replaces that player rate.
Kivy yields between complete events under a 64-event/15-ms budget and rebuilds
management projections once at completion, with in-place clock/status updates.
One heavy event can exceed the GUI yield budget; no worker thread or frame-time
authority is added. Terminal uses the same optimized session/kernel boundaries.

Final complete busy-starter observations: one day 7.745 → 2.344 s; two days
15.812 → 4.582 s; seven days 70.636 → 18.812 s. Full-state hashes match the archived
baseline for all three. Thirty days completed in 139.458 s, 155 events/60 flights,
including four weekly horizon extensions; the baseline had already hit its 120 s
measurement budget partway through, so no whole-target speedup ratio is claimed.
The detached real gameplay save had one aircraft but 718 published flights and
525 bookings; its engine-only baseline took 119.794 s for two days. That does not
reproduce the reported fifteen-minute GUI interval exactly. Large histories/airlines
and busy 90-day/year catch-up retain material costs and are not certified scalable.

Focused verification command:
`python -m unittest tests.test_advancement_performance tests.test_stage1_event_kernel
 tests.test_runtime_startup tests.test_stage1_booking_checkpoint
 tests.test_stage1_flight_fulfilment tests.test_stage1_runtime
 tests.test_gui_foundation -q`: **135 tests passed in 84.567 s**.

Displayed fresh-process Kivy loaded-save smoke completed 46 events/22 flights/two
Booking checkpoints in **168.009 → 33.074 s**, with the same complete hash and
exact paused manual-save/reload. Flights/header rebuilds fell **48 → 1**; render
time **36.628 → 1.016 s**, longest tick **9.011 → 2.742 s**. Native fresh-career
one/two/seven-day cases also passed, including operations, finance/management views,
validation and exact paused reload. The standalone smoke CLI passed without
external Kivy argument/log environment setup. These are programmatic native-window
checks, not human responsiveness certification; a heavy complete event still stalls.

Quiet valid-career 90 days completed in **12.057 s**, matching the baseline hash;
one year completed in **61.384 s** (365 Booking checkpoints/12 market rotations).
The baseline year's explicit generation limit stopped it after 100 events.
These low-load targets are distinct from busy rolling 90/year attempts, which were
safely budget-limited and did not complete. Aged recurring two-day extension completed
11 events/four flights in 12.189 s. Ten-aircraft day one completed in 61.890 s;
25/50-aircraft and longer dense targets remain budget-limited. Full retained-history
validation is the dominant remaining bottleneck; no successful large-airline
catch-up or dense 50-aircraft 7× gate is claimed by this patch.

`python -m unittest discover -s tests`: **707 tests passed in 436.375 s**.
`python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
exited 0. Verification covers this performance successor working tree; no
schema/template or reference-data changes were made. Final review retained exact
whole-state replay witnesses, complete event rollback/commit isolation, shared
startup registration and paused save/load. The remaining performance work is
retained-history validation/Booking preparation and large dense catch-up, not
unrelated gameplay or a GUI redesign. The pre-existing untracked `.venv/` is preserved.

## Shared runtime handler startup correction (2026-10-03 working tree)

Scope is the startup-fix successor of `186dd7df46c1fb219aba679e24b7f706d006648d`,
verified against live `origin/master` before work. A fresh-process direct Load Game
restored the valid pending `DAILY_BOOKING_CHECKPOINT`, but lacked its runtime
handler. New Game previously imported Booking indirectly and concealed the issue.

`game.simulation.handlers.initialize_runtime_handlers` explicitly binds/verifies
all eight built-in event types during shared `Stage1Session` construction and
standalone default `RuntimeController` construction. Initialization is idempotent;
conflicting bindings fail visibly. Caller-supplied custom registries remain
caller-owned. Domain import registrations remain for direct-command compatibility,
but normal startup no longer depends on them being reached by game creation or
frontend navigation. No save, migration, schema, timing, booking formula, event
ordering or GUI behavior changes are required.

The audited set is NO_OP; flight departure/completion; daily Booking checkpoint;
aircraft market rotation, contract payment/expiry; and weekly schedule publication.
Booking was the missing registration. The other domain modules also use import
registrations and are now explicitly covered by the shared initialization manifest.
A registration inventory regression detects omitted future built-in types.

Fresh subprocess tests load a temporary existing valid career without New Game or
GUI imports, cross the checkpoint, verify completed Booking authority/next event,
compare exact state hashes and completed-event ordering with an explicitly imported
reference process, and validate exact paused save/reload. Separate subprocesses
cover New Game, standalone default runtime, repeated initialization, missing bindings,
conflicting bindings and preservation of custom registries. The fresh-load gate was
observed failing before the fix.

Focused command: `python -m unittest tests.test_runtime_startup tests.test_stage1_runtime
 tests.test_stage1_event_kernel tests.test_step7_save_load tests.test_gui_foundation
 tests.test_stage1_booking_checkpoint -q`: **114 tests passed in 81.733 s**.
`python -m unittest discover -s tests`: **694 tests passed in 539.899 s**.
`python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
exited 0; changed-document links resolved and `git diff --check` passed.
Final review found no save/schema, domain behavior, ordering or unrelated GUI changes.

`python -B -m tests.smoke_runtime_startup` passed a displayed Kivy 2.3.1 fresh-child
process using title Load Game/career/manual-save controls, Resume 7x, Pause and
One day advancement. The September 2 checkpoint completed normally, producing
14 bookings and two total completed checkpoints; time reached
`2026-09-02T00:00:07Z`. Manual Save and direct title reload preserved exact validated
state paused. New Game was forbidden in the child; no unrelated screens were visited.
The maximized SDL2 window was 2560x1377. All career files were temporary. This is
programmatic functional smoke, not human responsiveness certification.

## Scheduling performance investigation (2026-10-03 working tree)

Implementation scope is the performance working-tree successor of
`35ee9b70dd80ebe4eee527e41019c8d14db44ed0`, verified against live `origin/master`
before work. See [Scheduling Performance Investigation](Scheduling%20Performance%20Investigation.md)
for reproducible tooling, all Before/After cases, profiling, memory and limitations.

Profiles confirmed nested per-definition world validation/copying, quadratic
flight/event scans, repeated immutable base projections/reference loading and
redundant graphical rebuilds. Detached definition/revision batches now share one
scheduling transaction; complete input/result and discarded continuity-preview
validation remain. Public single-definition/publisher commands retain their
validated atomic boundaries. Weekly recurrence reconciles inside the existing
kernel-owned candidate rather than creating a nested transaction. Full kernel
validation/commit, deterministic order/IDs, booking protection, timezone/timing,
finite/continuous recurrence and safe revision boundaries remain intact.

The GUI performs one builder refresh, reads a detached session-owned aircraft
row, and renders retained reservation bounds. Publication confirmation paints a
modal notice before one serialized domain command; pending work blocks time
advancement/exit and can be canceled by shutdown before starting. No worker,
speculative global cache, new authoritative field/schema, timing/economy rule,
recurrence scope or other management redesign was introduced. The terminal
continues using the same application/domain boundaries.

Three-repeat local medians: fresh Daily + Return Add **1.4110 -> 0.1424 s**;
real weekly-draft publication creating 560 flights **17.7416 -> 1.1149 s**;
GUI Add with 560 existing flights **10.9426 -> 1.0204 s**; populated-week render
**0.4957 -> 0.0994 s**. The historical weekly extension (84 flights, 28 results,
4,251 bookings) improved **4.1914 -> 2.0453 s**. All 18 scenario input/output
hashes matched exactly. Trace peaks fell for fresh Add, large Publish and
historical recurrence; complete historical validation/copies remain a scaling
limit, and arbitrary-history GUI responsiveness is not proven.

Focused verification passed **199 tests in 173.093 s** using:
`python -m unittest tests.test_scheduling_performance tests.test_stage1_weekly_planner
 tests.test_scheduling_recurrence tests.test_stage1_flight_publication
 tests.test_gui_schedule_polish tests.test_gui_weekly_workspace tests.test_gui_gameplay
 tests.test_gui_foundation tests.test_stage1_flight_fulfilment tests.test_stage1_runtime -q`.
`python -m unittest discover -s tests` passed **690 tests in 540.498 s**.
Required application-scope compilation and `git diff --check` passed.

Displayed native Kivy smoke passed Daily/Daily + Return, publication of 560 flights
(**1.3518 s** actual command plus refresh), navigation/scrolling/protected-block
inspection, rolling extension to 700 flights, execution of two real flight results,
and exact validated paused save/load. The maximized nonexclusive window showed all
seven weekday rows. The maximum measured heartbeat gap was **4.4976 s** during
combined validation/navigation/save-load checks: functional smoke passed, but human
Windows responsiveness is not proven. See the report for isolated event timings
and remaining historical validation/copy costs.

## Airport-local recurring weekly planner (2026-10-03 working tree)

Implementation scope is the working tree based on live `origin/master`
`83cf6921452bc681a335ed24e24a7349172c04df`. This successor replaces the
older past-slot rejection and graphical recurrence deferrals recorded below.
It reuses canonical schedule definitions, effective-dated revisions, retained
planning timing, occurrence keys, the bounded publisher and transactional event
kernel. The existing schema already holds authoritative airport IANA zones and
pinned tzdata; no airport data or GUI timezone map was added.

Scheduling now interprets departure input in the origin's local timezone and
shows arrival in the destination's zone, including midnight/date differences.
The weekly timeline uses the aircraft's explicitly labeled home-airport zone;
the dashboard shows hub-local time alongside UTC. UTC remains the sole engine,
event and save timeline. DST folds are represented by the existing canonical
fold field; nonexistent local slots reject rather than shift. PH controls remain
unchanged where every endpoint shares Asia/Manila.

Every weekday row Add uses the persistent builder through the same atomic
`WeeklyDraft.add_weekdays` path as the main multi-day button, without a second
entry popup. The baseline already contained this correction; it is preserved.
Elapsed slots in the current local week are reusable PATTERN ONLY intent.
Publication creates no past dated flights, bookings, operations, utilization or
financial records. Future slots still obey projected location, reservations,
turnaround and conflict rules. PARKED or IN_FLIGHT aircraft can enter planning;
immediate gameplay actions retain their existing state requirements.

Review & Publish offers This week / one-off, Repeat until date and Continuous
recurring. The finite option enables the existing reusable calendar; editing a
finite pattern retains its end-date/mode defaults. Schema 7 adds optional
`recurrence.publication_policy` and `recurrence.enabled` after updating the
[canonical schema](Stage%201%20State%20Schema.md#approved-airport-local-recurring-weekly-planner-2026-10-03)
and template mirror. No new collection or schema version is needed. The policy
is necessary to distinguish automatic publication from older manually published
schedules; disabled future revisions stop removed movements without cancellation.
The existing generic event queue stores one airline-owned weekly publication
event. At base-local Monday midnight it deterministically extends the current
week plus four future calendar weeks. Only opted-in definitions are extended;
older manual definitions remain manual. Finite recurrence ends inclusively;
continuous recurrence uses no artificial distant end date.

Edit recurring pattern loads the saved aircraft movements into the first safe
unpublished home-local future week. Revisions stage atomically; all existing
published/booked flights remain unchanged. A western origin can still be Sunday
at a home-Monday boundary: whole origin-local revision dates must remain after
protected occurrences, so replacement uses the next safe week when necessary.
Already queued immutable revision weeks are followed by subsequent edits.
Deleting every pattern leg and publishing stops expansion after existing
obligations. Opening the template is not itself an undoable deletion. Pattern
previews, draft selections, clipboard, builder controls and undo stay transient.

A displayed Kivy 2.3.1 temporary-career smoke exercised the actual row Add,
weekday controls, Repeat Until calendar and publication dialogs. A finite
Monday/Wednesday pattern through September 23 published 14 future flights;
continuous Monday/Wednesday/Friday published 28. Past August 31 slots never
operated. Planning during September 2's outbound rejected 09:50 DVO departure
before the authoritative turnaround, and accepted a valid future pair. The
September 7 week boundary extended to 36 retained dated flights, with six real
completed results. A replacement beginning October 12 preserved all published
records and appeared on the next rolling horizon. GUI event-by-event advances
to September 2, 7 and 14 took 1.09, 12.58 and 34.96 seconds locally. Save/reload
matched authoritative bytes exactly and restored paused. Screenshots confirmed
visible Monday blocks and readable PATTERN ONLY labels; unmaterialized services
have distinct PATTERN PREVIEW labels. The desktop window
was maximized, nonexclusive (2560 x 1377 on this machine). Production saves/data
were untouched. These elapsed measurements are observations, not performance
acceptance thresholds; larger history/publication costs remain a separate
profiling task. Published cancellation/refunds/reputation remain out of scope.

Python 3.12.10 / Kivy 2.3.1 verification on this working-tree scope:
`python -m unittest tests.test_scheduling_recurrence
tests.test_stage1_weekly_planner tests.test_stage1_flight_publication
tests.test_gui_schedule_polish tests.test_gui_weekly_workspace
tests.test_gui_gameplay tests.test_gui_foundation
tests.test_stage1_aircraft_acquisition tests.test_stage1_runtime -q`
passed 185 tests in 221.468 s.
`python -m unittest discover -s tests -q` passed 678 tests in 550.342 s.
`python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
and `git diff --check` exited 0. Changed documentation's local links resolved.
The existing untracked `.venv/` was used as an interpreter and left untracked;
no dependency installation or production save change was required.

## Scheduling row Add Flight correction (2026-10-02 working tree)

On the working tree based on `60409e717b0c1496dc5f1724e4697dc54120d93f`,
each Monday-Sunday timeline row's + Add now submits the current persistent
flight builder to that row's PH-local date. The main multi-day button uses
the same detached `WeeklyDraft.add_weekdays()` validation and atomic draft
edit; row buttons supply a single target date without changing checkbox
selection. Successful row edits select the target day and render its new
blocks immediately. The obsolete row-to-form callback and its date-target
branch were removed. The separate Advanced single flight form remains for
explicit positioning and service choices. No scheduling, fare, turnaround,
publication, persistence, or schema rule changed.

Python 3.12.14 / Kivy 2.3.1 verification on this working tree:
`python -m unittest tests.test_gui_schedule_polish
tests.test_gui_weekly_workspace -q` passed 25 tests in 43.557 s; the
additional past-day row regression passed separately in 1.343 s;
`python -m unittest discover -s tests -q` passed 659 tests in 495.842 s.
`python -m compileall -q app game tests main.py make_snapshot.py
settings.py test.py` and `git diff --check` exited 0.
A temporary-career Kivy displayed-widget smoke used the row buttons to add
the 08:00 MNL-DVO return pair on Monday and a changed route/time on Thursday,
used the main builder to add Tuesday and Saturday, then rejected a conflicting
Monday add without changing eight draft legs. No secondary flight-entry form
opened; no authoritative dated flight or production save was changed.

## GUI/runtime scaling correction (2026-10-02 working tree)

On the working tree based on `666300b3af2e7c0b5b10a8c6a0ef9209f89ef877`,
a temporary-career benchmark reproduced history-dependent GUI latency with
one A320neo and 14 published flights. The GUI recomputed the airline overview
and finance projections even for unrelated views; Research requested another
overview. One Research navigation performed four full-world validations.
Booking's isolated daily checkpoint event repeatedly validated nested detached
candidates (16 calls in the Day 1 profile), and the session validated the
kernel's completed event report once more. Validator traversal itself was
linear with accumulated state; the alias check was one contributor, not a
pathological loop. Windows working set grew from about 99 MB at Day 0 to
138 MB at Day 90 as bookings/history accumulated, then the booking count
stabilized at 378. The measured bottleneck was CPU work, not runaway RAM.

The GUI now reads a fresh, bounded airline header and next pending event from
the session-owned world instead of invoking unrelated public projections.
Public arbitrary-envelope projections retain full validation. Successful
kernel reports read bounded event rows from the just-validated transaction.
The built-in Booking event alone carries a private kernel context token through
its nested preparation/allocation/shopping/Model 4 derivations; those intermediate
full-world scans are omitted only for the isolated candidate. The kernel still
validates input, the completed event candidate, and the final clock state.
Public Booking/Model 4 commands and indexes still validate callers. The
event transaction, save schema, deterministic booking/economy rules, history,
and authoritative data were unchanged; no persistent cache or worker thread
was introduced.

The repeatable harness is `python -m tests.profile_gui_growth --max-day 90`.
Baseline and optimized checkpoints contained identical serialized sizes and
counts: 372,156 bytes/0 bookings at Day 0; 699,357/98 at Day 1;
2,292,486/378 at Day 7; 3,567,269/378 at Day 30; 3,629,816/378
at Day 90. With the same one-aircraft schedule, Day 0 to 1 advanced in
1.049 to 0.487 s, Day 1 to 7 in 17.333 to 8.513 s, Day 7 to 30 in
151.819 to 58.918 s, and Day 30 to 90 in 320.438 to 106.378 s. Research
navigation changed from 0.211 to 0.092 s at Day 0, 0.274 to 0.115 s at
Day 1, 0.802 to 0.241 s at Day 7, 0.839 to 0.318 s at Day 30, and
1.053 to 0.325 s at Day 90. Day 90 Overview navigation changed from
0.881 to 0.001 s. Full standalone `validate_world` at Day 90 remained
about 0.26-0.27 s; public projection costs were unchanged.
These are local elapsed measurements, not CI thresholds.

A seven-day aged temporary-career Kivy 7x smoke switched Overview/Fleet/
Research/Schedule in 0.001/0.180/0.259/0.186 s respectively, then paused
successfully with 378 bookings and two completed flight results. Larger jumps
remain CPU-bound: each committed event still requires whole-world transaction
copying and final validation, and public view projections still validate the
growing envelope. Fleet-size and years-long history scaling need a later
bounded-projection/transaction-cost milestone with its own correctness design.

Python 3.12.14 / Kivy 2.3.1 verification on this working tree:
`python -m unittest discover -s tests -q` passed 656 tests in 453.941 s;
the focused booking/Model 4 suite passed 99 tests; the four structural
performance tests passed in 7.584 s. They cover the three remaining
kernel validation calls, public invalid-world rejection, fresh GUI reads,
and byte-equivalent booked event outcomes versus the fully validated
nested path. `python -m compileall -q app game tests main.py
make_snapshot.py settings.py test.py` and `git diff --check` exited 0.
The final Day 90 benchmark used the same harness and schedule as baseline.

## Scheduling workspace playtest polish (2026-10-02)

On the working tree based on `116830faa74ff99b90131c4c6545a98010670155`,
the Kivy Schedule view now starts on the PH-local current Monday-Sunday week,
shows its calendar range, and places a persistent multi-day flight builder above
the timeline. The builder uses searchable airport IDs, the session's editable
suggested Economy fare, 00:00 exact default, optional earliest departure,
optional domain-timed return, weekday presets and manual weekday toggles.
`WeeklyDraft` validates all requested dates on a detached candidate and records
one undo step; past pre-departure work and existing scheduling conflicts reject
the whole request. Current-week future slots remain usable. A selected draft
sequence may be pasted to several weekdays at a chosen time, deleted, or moved
using a horizontal five-minute drag proposal; every change is validated by the
scheduling domain, and published reservations remain protected. GUI clipboard,
selection and builder controls remain outside authoritative state and saves.

The desktop window prefers maximized nonexclusive mode. Axis-aware scroll
containers expose wheel/touch and visible bars, with Shift+wheel on the
horizontal timeline. The airport popup uses the same scroll behavior. A GUI
calendar supplies existing canonical dates for the secondary single-flight and
finite repeat-through forms. No schema, booking, fare formula, scheduling
timing, turnaround, simulation rule, or recurrence contract changed. True
indefinite recurrence and published-flight cancellation remain separate design
work; see the PH GUI Foundation specification for their boundaries.

Python 3.12.14 / Kivy 2.3.1 verification on this working tree:
`python -m unittest tests.test_gui_schedule_polish
tests.test_gui_weekly_workspace tests.test_gui_gameplay -q` passed 32 tests
in 60.181 s; `python -m unittest discover -s tests -q` passed 650 tests
in 603.689 s; `python -m compileall -q app game tests main.py
make_snapshot.py settings.py test.py` and `git diff --check` exited 0.
A temporary-career Kivy smoke opened a maximized 2560x1377 nonexclusive
window, prefilled MNL-DVO USD 116, built MWF 08:00 outbound/10:10 returns,
pasted a copied pair to Tuesday/Thursday, rejected a conflict, moved and
undid a draft leg, deleted and undid a pair, published ten flights, completed
all ten, opened Fleet/Flights/Bookings/Finance, and loaded a valid paused
manual save. Synthetic Kivy touch dispatch also confirmed the dedicated drag
handle receives presses through its scroll container. No production save data
was modified.

## Weekly Schedule row-placement regression correction (2026-10-02)

On the working tree based on `cd42bea135531595b8eb889e3a574369d0b63f28`,
the weekly GUI now uses row-local Kivy coordinates for hour labels and flight
blocks. The prior `FloatLayout` placed block pixels outside their own row and
made Monday flights appear over Sunday. The domain week-date calculation was
correct: the seven controls and rows are Monday 7 Sep through Sunday 13 Sep in
the observed week. Both panes now have equal eight-row heights; choosing a row
highlights and sets its exact PH-local date, row Add Flight sets the same date,
and entering/changing a week brings Monday into view. Copy Day and Paste
use the same seven-date sequence. Scheduling, timing, publication and persistence rules did
not change. Regression coverage exercises all seven row labels, callbacks,
block placement, the Monday/Wednesday paste, and a year-crossing week.

Python 3.12.14 / Kivy 2.3.1 verification on this working tree:
`python -m unittest tests.test_gui_weekly_workspace tests.test_gui_gameplay
tests.test_gui_foundation tests.test_stage1_weekly_planner -q` passed 59 tests
in 75.650 s; `python -m unittest discover -s tests -q` passed 639 tests in
547.982 s; `python -m compileall -q app game tests main.py make_snapshot.py
settings.py test.py` exited 0. A temporary-career Kivy callback smoke selected
Monday, added the 08:00 MNL-DVO and 10:10 DVO-MNL pair through the GUI form,
copied Monday, pasted Wednesday at 14:00, and verified two blocks in each
correct row with block bounds inside their own row. A running Kivy layout
check brought Monday into view at the week start. No production saves changed.

## Weekly Kivy scheduling workspace (2026-10-02 working tree)

On the working tree based on `9d81352f0d87e126e0571a4e667805acb1552cb1`,
the Schedule screen presents a selected aircraft's Monday-Sunday PH-local time
grid, distinguishes unpublished draft blocks from published reservations, and
provides day selection, Add Flight, Copy Selected, Copy Day, relative-time Paste,
Undo, and Review & Publish. Copy/paste uses detached `WeeklyDraft` intent and
replays through the domain's existing validation atomically; it is not saved in
the canonical world. A GUI-local searchable airport selector uses current
projected code, city and display name and is available for New Game base,
Research origin/destination, scheduling endpoints and delivery location.
Acquire's manufacturer/model/product workflow and all scheduling, Booking and
simulation formulas remain unchanged. Weekly repeat retains an explicit finite
end date; indefinite-until-stopped recurrence requires a separate approved
player contract. Python 3.12.14 / Kivy 2.3.1 verification on this working tree:
the affected GUI/scheduling suite passed 56 tests in 68.527 s;
`python -m unittest discover -s tests -q` passed 636 tests in 553.337 s;
`python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py`
exited 0. A temporary-career Kivy smoke searched DVO by code, city and name;
planned Monday 08:00 MNL-DVO and 10:10 return; copied/pasted the pair to
Wednesday 14:00 and 16:10; rejected a conflicting duplicate; published and
completed four flights; inspected Fleet, Flights and Finance; then saved and
reloaded the career paused. The GUI operations used current session/domain
boundaries and no production save data.

## Fresh PH starter grant (2026-10-02 working tree)

On the working tree based on `ba77534091d9e9e746d13ea850938818d38100d6`, the approved schema-7 `STARTER_GRANT` provenance now supplies one player-owned,
catalog-backed `airbus-a320neo` to fresh PH careers. Construction uses the
published catalog maximum-Economy layout and standard lifecycle fields, with
no purchase journal, lease, cash deduction or aircraft-asset ledger entry.
PH Normal starts at USD 300 million. The configured starter uses normal V2
scheduling/maintenance; MNL 08:00 to DVO 09:40 permits a 10:10 return after
30 minutes on the ground. Saved unconfigured A320-200 aircraft and their V1
snapshots remain compatible; the old Quick Rotation command still applies only
to that saved-style aircraft. This is opening-state accounting, not a new
equity/balance-sheet model.

Python 3.12.14 / Kivy 2.3.1 verification on this working tree: the
seven-module affected suite passed 117 tests in 282.299 s; focused grant tests
passed 5 tests in 3.476 s; three additional legacy-compatibility regressions
passed in 7.143 s; `python -m unittest discover -s tests -q` passed 627 tests
in 524.835 s. Application-scope `python -m compileall -q app game tests
main.py make_snapshot.py settings.py test.py` exited 0. A temporary-career
Kivy smoke displayed the A320neo in Fleet, published the 08:00 MNL-DVO leg
and 10:10 return, completed both flights, displayed finance, and restored a
manual save paused. The remaining step is integrated player verification and
future opening-asset accounting design if a balance-sheet system is approved.

## PH 1.0 playtest acquisition and fare guidance

On the working tree based on `35cb29521d21230a3788dc980ed34cf813bbffe8`,
Acquire now navigates current catalog manufacturers, their models, then the
existing new purchase, operating lease, lease-to-own and used-listing preview/
commit paths available for the chosen model. Manufacturer names and model
specifications come from the immutable catalog; active offers/listings come
from the market. No acquisition economics or domain command changed.

A modern `game.economy.fare_reference` helper derives a neutral Economy
suggestion for a directional market from the same 0.001-km authoritative
coordinate distance used by PH market/planning, multiplied by exactly USD
0.12/km and rounded half-even to the nearest whole USD. MNL to DVO currently
suggests USD 116. The shared session exposes the integer-minor-unit value; the
Kivy passenger-leg form displays and can copy it into the editable fare input.
Changing endpoints refreshes the suggestion without overwriting typed fare.
This is view-time guidance, not persisted state, a profit optimum, or a Booking
willingness-to-pay rule. Demand and relative-offer Booking choice are unchanged.

Before the starter-grant decision, the fresh A320-200 starter remained V1.
The current immutable 20-model catalog
excludes it, and schema-7 configuration/provenance validation ties configured
aircraft to catalog-backed specifications and purchase/market lineage. Legacy
A320-200 source values do not establish an approved versioned catalog price,
range, model provenance and free construction-grant configuration contract.
That analysis led to the subsequently approved `STARTER_GRANT` contract and
existing catalog A320neo selection. Existing saves, published V1 timing
snapshots and historical results were untouched. Its V1-specific capacity,
Quick Rotation and maintenance compatibility paths remain for separate review.

Python 3.12.14 / Kivy 2.3.1 verification on that working tree: focused
`python -m unittest tests.test_gui_gameplay tests.test_gui_foundation
tests.test_stage1_terminal_harness -q` passed **35 tests in 79.121 s**;
`python -m unittest discover -s tests -q` passed **622 tests in 526.620 s**;
application-scope `python -m compileall -q app game tests main.py
make_snapshot.py settings.py test.py` exited 0. A temporary-career Kivy widget
smoke navigated Research, catalog manufacturer/model purchase, MNL-DVO
scheduling with USD 116 suggestion and editable override, published two legs,
advanced time and observed two completed flights. This confirms command wiring
and state behavior, not human playtest quality. That verification predates the
fresh A320neo grant; absolute fare sensitivity remains a separate economy
design task.

## PH 1.0 first graphical gameplay action loop

The second bounded Kivy slice adds Research, Acquire and Schedule to the
existing game shell. Market research reads the modern directional opportunity
projection. Acquisition uses modern catalog, lease-offer and used-listing
views, authoritative delivery airport IDs, and the existing preview/commit
commands for new purchases, operating leases, lease-to-own and used purchases.
A rejected or stale preview leaves the world unchanged. Weekly scheduling
holds a detached UI draft by aircraft ID; list/form controls add passenger or
explicit positioning legs, earliest or exact Philippine local departure,
return, copy day, undo and optional repeat-through. Saving calls the shared
session's live-world revalidation and atomic publication. The next-rotation
command is also available. The runtime is paused for management input, and
Kivy's pump and commands remain serialized on one event-loop thread. An
unpublished draft requires an explicit discard choice before leaving or
loading another career; it never enters a game save.

The graphical loop now reaches market research, acquisition, fleet
confirmation, weekly schedule publication, simulation, operations/Bookings,
finance and manual save without the terminal. The terminal remains the
developer/debug frontend. The only shared input change moves exact USD fare
parsing from terminal presentation into frontend-neutral app.inputs; the
session API, canonical schema, template mirror, save format and domain rules
are unchanged. No legacy gameplay or visual assets were restored. Existing
plan editing, sale, cabin reconfiguration, advanced maintenance, map, final
art and mobile packaging remain deferred. Step 8 integrated PH verification
remains the next engine/player verification milestone.

Verified on the working tree based on
d49d02d25b69cfb6972ccc36f13b0d2ac6e8b5fa on 2026-10-01 using
Python 3.12.14 and Kivy 2.3.1: focused
python -m unittest tests.test_gui_gameplay tests.test_gui_foundation
tests.test_stage1_terminal_harness -q passed **32 tests in 84.529 s**;
python -m unittest discover -s tests -q passed **619 tests in
553.425 s** on the final source state; application-scope
python -m compileall -q app game tests main.py make_snapshot.py settings.py
test.py exited 0. An actual Kivy
event-loop smoke created a temporary PH career and navigated Research,
Acquire, Schedule, Fleet, Flights and Finance successfully. A separate
automated Kivy-widget test exercised purchase, scheduling, publication,
cooperative advancement, result inspection, save and paused reload. These
checks confirm command wiring and state behavior, not human usability on a
small display or sustained 50-aircraft GUI frame performance.

## PH 1.0 Kivy GUI foundation

The approved Kivy foundation now uses `app.session.Stage1Session` as the one
application owner shared by `app.gui` and the retained `app.terminal` developer
harness. The historical terminal session import remains a compatibility
re-export. The modern GUI launches with `python -m app.gui` under a
Kivy-compatible Python environment. Development verification used Python
3.12.14 and Kivy 2.3.1; the host's default Python 3.14 environment has no
compatible installed Kivy wheel. `requirements.txt` now specifies Kivy.

The graphical title creates PH Normal careers or loads current airline career
saves, with manual/autosave recovery and bookmark choices. The game shell shows
airline/CEO/base, cash, exact UTC and paused/7x state, with in-place status
refresh. It offers pause/resume and explicit next-event/day/duration/UTC
advancement. Fleet, flights/Bookings/operations and finance are read-only
derived views. Manual save and bookmark create/load/delete use the existing
validated persistence; unsaved return/exit/load offers Save, discard or cancel.
No authoritative schema field or save format changed. The GUI remains a single
world owner with no simulation worker thread; explicit bulk work yields after
complete event transactions. Flight projection paging is a bounded derived
view extension. The old Kivy title stub no longer invokes legacy gameplay.

Verified on the complete working tree based on `20cc38c` on 2026-10-01:
focused GUI tests passed **7 tests**; the earlier focused GUI, runtime, save
and terminal set passed **58 tests in 124.366 s**; the final
`python -m unittest discover -s tests -q` passed **613 tests in 484.746 s**
using the isolated Python 3.12.14 environment with `requirements.txt` installed.
`python -m compileall -q app game tests main.py make_snapshot.py settings.py
test.py` exited 0, and `git diff --check` passed. A Kivy event-loop smoke run
started and stopped. In a newly created PH career, 30 GUI pump callbacks using
an injected fake clock measured **40.173 ms median, 100.315 ms maximum** on
this host. This small-world smoke measure is not a 50-aircraft GUI performance
gate or a mobile measurement. Existing complete-event transaction latency can
still delay UI response until its boundary.

The next bounded GUI gameplay slice is aircraft acquisition, market research
and weekly scheduling actions. Step 8 deterministic engine checks can proceed
independently; the sustained graphical player run needs those GUI actions.
This foundation does not add cabin editing, aircraft sale, advanced maintenance,
AI, a map or extra player speeds.

## PH 1.0 Normal starting-capital correction

New Philippines careers remain `Normal` and start with USD 300,000,000
(30,000,000,000 USD minor units) under reference-data version
`stage1-philippines-v1-recovery-2026-10-01`. This matches the legacy Normal
amount for integrated player-simulation verification; it is not final economy
or difficulty balancing. Existing careers retain their saved cash. Schema 7,
aircraft prices, acquisition and economy rules, and difficulty selection are
unchanged. The next PH roadmap step remains Step 8 integrated player-simulation
verification.

Verified on the working tree based on `464cf04` on 2026-10-01:
`python -m unittest tests.test_stage1_terminal_harness.Stage1BootstrapTests
tests.test_stage1_aircraft_acquisition.AcquisitionTests
tests.test_step7_save_load -q` passed **37 tests in 65.554 s**;
`python -m unittest discover -s tests -q` passed **606 tests in 454.297 s**;
`python -m compileall -q app game tests main.py make_snapshot.py settings.py
test.py` exited 0. The career bootstrap test checks the Normal difficulty,
revised reference version, and exact cash account balance.

## PH 1.0 Step 7 save/load completion

The schema-7 whole world now saves durably at completed transaction boundaries.
An opaque file-level career ID keeps each airline game separate even if display
names collide or change. One explicit current manual save, three rotating
autosaves and player-named, explicitly deletable bookmarks belong to the career.
Autosaves use the first of 15 active real minutes or seven simulated days of
ordinary continuous runtime; nearby triggers coalesce. Explicit bulk advancement
does not produce intermediate weekly saves. There are no before-action or exit
autosaves. Unsaved exit and return-to-title paths offer Save, discard or cancel.

Loads check container integrity, run adjacent migrations on a detached candidate,
validate the complete world, rebuild the event queue index, and replace the active
world only on success. Restoration is paused at the exact saved UTC second, with
no offline progress. Schemas 2–7 migrate automatically; schema 1 requires its
matching approved foundation snapshot and otherwise reports a compatibility
failure. Newer schemas and unversioned legacy saves are not loaded. A previous
valid recovery copy protects replaced files. Autosave and bookmark loads do not
change the manual file; a newer autosave offers a recovery choice.

The verified implementation scope is the working tree based on
`fcb6aa73a9e10e3f01d7c738e26bad08662f3251`. The focused save, terminal and
runtime run passed **51 tests in 109.607 s**. After the final source changes,
`python -m unittest discover -s tests -q` passed **606 tests in 454.170 s**.
The application-scope `python -m compileall -q app game tests main.py
make_snapshot.py settings.py test.py` exited 0. Local links in the six changed
technical documents passed target validation, and `git diff --check` passed.
A representative 50-aircraft scheduled PH world with 102 pending events and
672,851 serialized JSON bytes saved in **0.203 s** and loaded in **0.171 s**
with exact world equality on this host. This measures the bounded scheduled
workload, not a multi-week processed-history scale claim.
The next PH roadmap step is Step 8 integrated player-simulation verification.
Disk layout, save serials, integrity metadata, autosave timers and recovery
copies add no authoritative world field or schema version.

## PH 1.0 Step 6 completion

Simple routine maintenance expenses are implemented as save schema 7 on the
working tree based on `768556c56a52d3c4600e4037f02e11836d40791d`.
The versioned dimensional classification reference covers all 20 catalog
models plus the legacy A320-200 starter. New departures freeze the authoritative
timing-snapshot distance or the shared geographic fallback and the actual
aircraft's A–G class/rate. Successful completion, including deadheads, adds
`ceil(distance_m × class_factor_minor_per_km / 1000)` to the unchanged base
operating cost. The single existing fulfilment journal posts the combined
operating expense and cash cost; per-flight projections and the terminal show
the components separately. Negative cash, replay, event-step/bulk/7×
equivalence and existing lifetime counters are covered by regressions.

Detached schema 6→7 migration adds the maintenance configuration only. V1
historical results and journals remain unchanged; locked V1 flights finish on
V1 rules, while only new departures receive Step 6. There is no backfill or
new maintenance account/event. The next PH roadmap step is Step 7 save/load.
Scheduled checks, condition deterioration, facilities, downtime, failures,
reserves, PBH and monthly maintenance settlement remain deferred.

| Step 6 verification, 2026-10-01 | Result |
| --- | --- |
| `python -m unittest tests.test_step6_maintenance tests.test_stage1_aircraft_acquisition.AcquisitionTests.test_booking_fulfilment_mixed_fleet_deadhead_and_replay -q` | 11 passed in 131.210 s |
| `python -m unittest tests.test_step6_maintenance -q` after detached-reference hardening | 10 passed in 108.609 s |
| `python -m unittest discover -s tests -q` after detached-reference hardening | 593 passed in 451.683 s on the final source state |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
| Changed-document local link-target check | Passed across 6 documents and 122 local targets |
| `git diff --check` | Passed before commit preparation |

The full suite used bundled CPython 3.12.14 and isolated, test-only
`tabulate 0.10.0`/`tzdata 2026.3` outside the repository. An earlier run
without those pinned dependencies had two import/version failures and one
schema-5 fixture failure; the fixture now removes schema-7 configuration
when reconstructing schema 5, and the final full run passed. No dependency
copies are part of this working tree.

## PH 1.0 Step 5 completion

PH 1.0 Step 5 is implemented as save schema 6. The terminal exposes rotating
operating-lease and lease-to-own offers, operating renewal/return, and persistent
used-aircraft listings. Contracts use automatic monthly integer-USD postings that
may make cash negative. Lease-to-own principal and financing are separate;
ownership and ordinary configuration rights transfer after final settlement.
Used purchases retain the exact listed airframe identity, age, block hours,
cycles, condition and registration.

Marketplace rotation, offer inventory and background seller listings are
seed-keyed deterministic authority. Unaccepted lease offers expire; unsold used
listings persist. Lease scheduling is bounded by the confirmed contract horizon,
with payment before flight lifecycle and expiry/return after flight completion at
equal timestamps. Schema-5 migration preserves legacy aircraft and history
without inventing lifecycle facts. Exact formulas, constants, worked settlement
examples and future boundaries are in the
[Aircraft Marketplace Technical Specification](Aircraft%20Marketplace%20Technical%20Specification.md).

The independent review corrected a condition double-counting risk in the first
settlement draft: cancellation equity now uses age-depreciated value while
condition is charged exactly once as restoration. It also added collision probing
for used registrations, current-event cardinality validation to prevent duplicate
payments, allocator checks for embedded airframes, and a genuine schema-5
migration fixture rather than a partial version-number downgrade.

Final verification evidence for this combined Step 4 and Step 5 working tree is
recorded below. The verified scope is the complete working tree based on
`e5c079cc98f931d74456662129ee2661c39d1abb`, including the previously completed
Step 4 increment and Step 5. The next roadmap milestone is Step 6, simple
versioned maintenance expenses. Advanced maintenance, manufacturer installments,
active AI fleet sales, physical delivery/return, banking/loans, bankruptcy rules
and lease-to-own refinancing remain future work.

| Step 5 completion verification, 2026-09-20 | Result |
| --- | --- |
| `python -B -m unittest discover -s tests` | 583 passed in 324.598 s |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
| 50-aircraft live 7× profile, 60 seconds | 60.949 active s; 416 simulation s; raw 6.825×; 10.644 s retained credit; accounted 7.000×; max pump 12.395 s; 4 events; no overload |
| World State validation-first and Simulation-first import probes | Both passed |
| Bulk versus same-timestamp-draining stepped marketplace rotation | Exact authoritative equality |
| Changed-document local Markdown target check | Passed across 9 changed/new documents |
| `git diff --check` | Passed before final commit preparation |

The full suite used bundled CPython 3.12.14 with temporary, test-only
`tabulate 0.10.0` and pinned `tzdata 2026.3`; neither dependency copy is in the
repository. The live profile used the production 43-airport/1,806-market world,
50 aircraft and production runtime controller. Raw clock progress waits for
atomic transactions; retained credit accounts for the difference and is not
discarded.

## PH step 4 working-tree checkpoint

Continuous runtime is implemented against clean starting revision
`e5c079cc98f931d74456662129ee2661c39d1abb` on `master`. The bounded 1/10/50
workloads and retained-credit live gate now pass on the documented host; PH step
4 is complete in this uncommitted working tree. Unpaced throughput alone is not
the acceptance evidence. Live `git ls-remote --heads origin
refs/heads/master` on 2026-09-17 confirmed origin still at that base. No new commit
or push was performed for this increment; the changes remain uncommitted.

The terminal now supports `/resume`, `/pause` and `/status` throughout management
navigation, with an input-only worker and one owner of world mutations. Resume
uses the existing NORMAL ratio of 7. Monotonic active uptime excludes suspension;
fractional credit, input queues and iterators are runtime-only. Schema 5 remained
the authoritative version at that Step 4 checkpoint; Step 5 subsequently adds schema 6.
Kernel iteration yields only between complete events and preserves processing
limits across yields. Manual bulk advancement finishes paused. Live Ctrl+C
requests a boundary stop. Weekly drafts revalidate explicit legs against current
authority; strict purchase-preview freshness and idempotent replay are unchanged.
See the [runtime contract](Continuous%20Runtime%20Technical%20Specification.md).

| Verification, 2026-09-17 | Result |
| --- | --- |
| `python -B -m unittest discover -s tests -p test_stage1_event_kernel.py` | 53 passed, 1.509 s |
| `python -B -m unittest discover -s tests -p test_stage1_aircraft_catalog.py` | 14 passed, 9.974 s |
| `python -B -m unittest discover -s tests` | 569 passed, 486.483 s |
| `python -B -m unittest discover -s tests -p test_stage1_runtime.py` | 21 passed, 83.437 s, including late input-only EOF fix |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 after final source/profiler edits |
| Changed-document link/anchor check | Passed, including final status update |
| `git diff --check` | Passed |
| Actual Windows terminal smoke test | Clock advanced inside Aircraft Catalogue; explicit Pause froze 00:10:10Z through Main Menu and Airline Overview; exit 0 |

The first full run (564 tests) found one controller-binding regression in sessions
whose world was replaced directly. Lazy rebinding fixed it; the subsequent full
run passed. Isolated kernel tests also exposed an existing planning-validation
import cycle, fixed with a local import without changing validation semantics.
The late EOF fix prevents live exit confirmation waiting on an exhausted input
worker and passed the final 21-test runtime run. Tests used bundled Python 3.12.14 and
the existing temporary test-only `tabulate 0.10.0` dependency via `PYTHONPATH`.
No machine-specific dependency path or runtime artifact is committed.

The 2026-09-18 audit follow-up added clean UTC-range failure coverage, historical
purchase-delivery validation coverage and a regression ensuring checkpoint
preparation executes shopping once. Focused runtime (21), acquisition (19) and
shopping (29) suites passed; an allocation rollback regression exposed during
the optimization was corrected before the final 573-test pass. Final whole-suite
and compile results are recorded below.
The World State planning-validation import cycle was rechecked in both import
orders; the existing local import is the minimal correction and no package move
or broader dependency redesign was needed.

| Audit completion verification, 2026-09-18 | Result |
| --- | --- |
| `python -B -m unittest discover -s tests` | 573 passed, 262.030 s |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
| World State planning-first and Scheduling-first import probes | Both passed |
| Changed-document local link/anchor check | Passed |
| `git diff --check` | Passed |

## Runtime performance evidence

Host: Windows 10 build 19045, Core i5-10400 @ 2.90 GHz, 12 logical CPUs,
approximately 16 GB physical RAM, CPython 3.14.6. These are observed desktop
measurements from the 2026-09-18 acceptance rerun.

Commands: `python -B -m tests.profile_ph_runtime --fleets 1 10 50 --days 1`
and `python -B -m tests.profile_ph_runtime --fleets 50 --days 1 --live-only --live-seconds 185`.
The fixture uses the full 43-airport/1,806-market pack, test-only acquisition
funding, one daily return pair per aircraft across five destinations, six days
of Booking and one operating day. All domain processing is production code.

| Aircraft | Processing seconds | Resolved events/history growth | Events/s | Max transaction | Unpaced capacity | Peak process working set | Serialized bytes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 12.179 | 11 | 0.903 | 2.199 s | 49,658x | 48,689,152 B | 1,608,264 |
| 10 | 108.044 | 47 | 0.435 | 8.257 s | 5,598x | 91,869,184 B | 6,089,645 |
| 50 | 660.077 | 207 | 0.314 | 14.056 s | 916x | 139,325,440 B | 12,137,356 |

At 50 aircraft, p95 yielded-transaction latency was 3.437 s. The bulk profiler
hit the generated-event limit once and explicitly continued; the live controller
does not silently retry. Authoritative history and yielded-event count both grew
by 207. Peak memory
includes profiler snapshot copies, not just a single live world.

The 185-second live run crossed the busy final Booking midnight and departures.
Successive raw authoritative-clock windows were **6.822x, 7.007x and 6.994x**.
Overall: 185.254 active seconds, 1,267 simulation seconds advanced, raw **6.839x**,
nine resolved events, 29.775 simulation seconds of retained credit, max pump
11.513 seconds and no overload. Advanced time plus retained credit was 1,296.775
seconds, or **7.000x accounted pacing**. Each window likewise accounts to 7x;
the raw clock can lag only at complete atomic boundaries and later catches up.
No clock-credit discard, event omission, formula change or validation bypass was
used. This satisfies the retained-credit sustained gate defined by the runtime
contract; raw timestamp-only rate remains a latency diagnostic, not a loss metric.

The current overload threshold is 120 active seconds of
backlog persisting for another 30 seconds; the measured 14.056-second burst is
well below it. Overload pauses visibly and retains credit. Input can still wait
for the current transaction. Profiling confirmed redundant preparation: the
checkpoint first ran shopping only to discover inventory revisions, then allocation
immediately reran the same shopping work. Preparation now derives the exact
inventory witness from its validated allocation result. Nested commands reuse an
already validated caller boundary only through private flags and retain their own
authoritative mutation/final validation boundaries. Atomicity, deterministic
results, public invalid-world rejection and rollback coverage remain intact.
Whole-world validation/copying remains the main future scale limitation; broad
redesign was not needed for this milestone.

An exploratory seven-operating-day run completed at one aircraft: 41 events,
127.425 seconds processing, max transaction 13.125 seconds. The denser ten-aircraft
run was stopped before completion to prioritize the bounded 1/10/50 comparison.
No larger-fleet or multi-week sustained-runtime claim is made. The architectural
thousands-of-aircraft objective remains future scale work, not tested capacity.

## Previous completed acquisition checkpoint

PH 1.0 step 3, basic new-aircraft acquisition, is implemented and verified.
Verification base: `8d67ab0c2883247d304f6c622ab780b7a547c764`, the completed
catalog checkpoint (historically 531 tests). The tree began clean on `master`.
Results below cover the acquisition source/tests in this working tree; Git history
identifies the resulting commit. This pre-commit snapshot invents no commit hash
or push outcome. Documentation-only successors do not invalidate source evidence.

On 2026-09-16, `git fetch origin master`, local divergence inspection and live
`git ls-remote --heads origin refs/heads/master` confirmed the remote still
matched that base, with 0/0 local divergence before the milestone commit.

| Verification command | Result, 2026-09-16 |
| --- | --- |
| `python -B -m unittest discover -s tests -p test_stage1_aircraft_acquisition.py` | 18 passed in 48.598 seconds |
| `python -B -m unittest discover -s tests` | 549 passed in 349.439 seconds |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
| Local Markdown link/anchor validator over changed/new documents | Passed |
| `git diff --check` | Exit 0 |

Tests used bundled Python 3.12. The full run used the existing temporary test-only
`tabulate 0.10.0` dependency on `PYTHONPATH` with approved external execution
access. The initial run exposed missing sandbox dependency access and two stale
terminal expectations (the formerly unavailable purchase message and catalog-only
import guard); those were corrected without changing approved gameplay formulas.
No machine-specific dependency paths or tooling artifacts are committed.

## Implemented and available

The state/schema, immutable IDs, deterministic clock/events and dated publication
foundation supports compact Model 4 demand, market-pack lifecycle, direct-Economy
Booking, timed fulfilment and finance. The in-memory terminal exposes the complete
schedule-to-Booking-to-flight-to-finance loop. PH recovery supplies 43 active
commercial airports, 1,806 directional markets, selectable starting base, market
research, versioned air suitability and destination-only tourism.

`python -m app.terminal` starts a paused session with a free, catalog-backed
A320neo (194 maximum-Economy seats) in a fresh career. Saved A320-200 careers
retain their old aircraft and timing.
Weekly Scheduler supports one-way chains, explicit return/positioning, custom
local times, day copy, undo, bounded repeat, Monday-week views and atomic
publication. It validates unpublished recurrences without extending the actual
publication window. Quick Rotation remains the saved A320-200 compatibility path.
Explicit next-event, day, positive-duration/multi-day and exact UTC-target
advancement exist. PHP/EUR conversion remains presentation-only.

Option 11 browses the immutable 20-model aircraft catalog. Option 12 provides
manufacturer/model selection, delivery choice from existing airline bases/hubs,
price/remaining-cash preview and confirmation. One purchase creates one parked
individual aircraft immediately, posts a balanced cash/aircraft-assets journal,
and leaves time unchanged. Exact-balance purchases are valid. Stale/tampered
previews reject; exact successful-command replay does not create a second asset.
Candidate failures preserve IDs, money, RNG and all other authority.

Schema 5 adds compact purchased-aircraft configuration and acquisition journal
provenance. Explicit 4-to-5 migration changes only schema version; existing
starter/published/booked/processed history is not backfilled or rewritten.
Delivery sets physical location separately from the already-required home base.
PH registrations use a seeded expanded numeric namespace with deterministic
collision probing, independent of immutable aircraft identity.

Purchased aircraft use installed maximum Economy capacity, catalog cruise speed,
scalar-range eligibility and versioned V2 timing. Total stand turnaround is counted
once: 30 minutes for turboprops/regional jets/narrowbodies and 45 for widebodies;
taxi remains separate. Starter V1 activity timing and historical witnesses remain
unchanged. Deadheads retain zero passengers/revenue and existing fixed costs.
Fleet display/selection uses derived pages; finance shows aircraft assets and
purchase journals separately from operating contribution.

See the [acquisition specification](Aircraft%20Acquisition%20Technical%20Specification.md),
[canonical schema](Stage%201%20State%20Schema.md),
[Decision Register](Decision%20Register.md) and
[roadmap](Stage%201%20Implementation%20Roadmap.md).

## Limitations and remaining work

- Authoritative file save/load is implemented above. A schema-1 file without a
  matching approved foundation snapshot remains a reported compatibility failure;
  unversioned legacy import is outside PH 1.0 Step 7.
- Runtime controls and the retained-credit performance gate are implemented above.
  Individual event and management transactions can block input until their
  completed boundary.
- Leasing, lease-to-own, used listings and simple routine maintenance are
  implemented. Manufacturer queues/delays, banking/loans, full depreciation and
  editable cabin configuration remain deferred.
- Reconfiguration remains deferred. Before it is implemented, its contract must
  preserve historical installed-configuration witnesses rather than validate old
  purchases, plans or operations against only the aircraft's latest configuration.
- No AI, connecting Booking, detailed disruptions, graphical planner or editing
  of already-published plans. Legacy modules remain migration evidence.
- The approved PH 1.0 Normal starting capital is USD 300 million for newly
  created careers, matching the legacy Normal amount. Reference-data version
  `stage1-philippines-v1-recovery-2026-10-01` distinguishes this scenario
  correction. Existing careers retain saved cash. This is not final economy or
  difficulty balancing; acquisition tests supply funds independently. Current
  new games offer their one established base for delivery.
- PH scalar range is a temporary gameplay ceiling, not a full-load guarantee.
  Airport/runway compatibility is deferred: physically unsuitable airport/aircraft
  combinations are not yet rejected. Payload-range/cargo/weight remain future work.
- Fulfilment cost revision 1 remains simplified and unchanged for purchased models.
  Production-date metadata remains incomplete and never gates availability.
- Compact records, derived pages and expanded registration avoid small fleet caps;
  world copying/hashing/validation, registration scans and fleet sorting remain
  scale limitations. Interactive performance at tens of thousands of aircraft has
  not been established and needs profiling before broad runtime integration.

## Next action

**PH Step 8 integrated verification** follows Step 7. Exercise multiple weeks of
scheduling, Booking, operations, finance, all acquisition modes, maintenance,
runtime controls, multi-day advancement and reload as one player-operated
scenario. AI follows the verified PH player simulation. This status does not
authorize the next implementation increment.
