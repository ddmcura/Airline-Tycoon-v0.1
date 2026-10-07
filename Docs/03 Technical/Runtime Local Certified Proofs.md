# Runtime Local Certified Proofs — Stage 3G-B

Implemented scope: local certified proofs and sealed canonical selection only.
Baseline local HEAD, upstream and live origin/master were verified as
`8b12fdd5e53390cad1fb0b541475febcc22ef912` on 2026-10-07.

Authority: [canonical event contract](Stage%201%20State%20Schema.md#clock-and-event-contract),
[ownership boundary](Runtime%20Candidate%20Ownership.md),
[production runtime](Production%20Cooperative%20Runtime.md), and
[causal safety](Runtime%20Causal%20Generation%20Accounting.md).
The [Stage 3G-A audit](Runtime%20Scalability%20Forensic%20Audit.md) preserves the
historical baseline. This report does not authorize Stage 3G-C or later work.

## Measured paths and minimal boundary

The preserved exclusive 50-aircraft day measured 283.683 engine seconds, including
111.096 seconds of event/history, ownership and transition proof work (39.2%).
Quiet day: 280.155 seconds, 401 events, 54 complete gates, 104 kernel world copies.
A fresh pre-change two-event probe reproduced 5.760 seconds /4.403 maximum unit.

| Path | Old day exclusive s / calls | Repeated authority | Classification and replacement |
| --- | --- | --- | --- |
| `kernel._event_contract_witness` | 30.379 /400 | Copies all pending/history per event | Local selected/permitted event IDs, genuine detached predecessor |
| `kernel._handler_contract_error` | 47.670 /401 | Compares existing event rows and complete ID unions | Local event outputs under enforced protection; strict remains global |
| `CandidateOwnership.begin` | 10.000 /400 | Copies/wraps entire footprint tables | Store only approved writable rows; protected source remains read-only |
| `WriteCapsule.checked_outputs` | 16.219 /800 | Protected key-set/identity walks | Check every stored output key against exact sealed footprint |
| `CandidateOwnership.publish` | 2.939 /400 | Detached output pack and exact bridge | Retained; predecessor/current generation now also enforced |
| flight `_kernel_transition` / `_exact` | 2.007 /400; 1.459 /4800 | Repeated global event topology plus exact equations | Event topology local; all affected-domain equations retained |
| ownership close / flight capture | .378 /51; .047 /400 | Release bounded capabilities /selected lineage | Retained |
| fulfilment `_matching_event` / `_next_event` | Separate handler bucket | Whole queue matching/minimum despite selected event | Selected event local match; certified minimum reused |

The fresh probe measured pending matching .01476s and minimum .13858s for two
events, witness .14904s and kernel comparison .24566s. This reproduces actual
paths rather than assuming all of the handler bucket is arithmetic.

## Ownership and exact protected-state induction

The fully validated entry and detached outer candidate remain mandatory. Previously
`_WriteTable` held a shallow copy of a whole source collection, with writable rows
deep-copied and protected rows wrapped. The broad output check had to detect
base-class insertions and replacement of protected entries in that shallow copy.

Production capsules now use `_LocalWriteTable`. Its dict storage contains only
approved writable IDs. Other reads delegate to the existing recursively immutable
`ReadOnlyDict` source. No raw protected dict/list is returned. Every stored key is
checked, including keys inserted through `dict.__setitem__` or other base mutators.
Protected keys cannot be changed through normal setters; a base-class insertion
of a protected key is an illegal stored output and is rejected. Changing the
protected source facade, footprint or table/root identity is also rejected.

Consequently there is no mutable protected collection to scan for changes. This
proves unchanged authority structurally, rather than trusting revision counters,
identity of mutable records, handler intent, or a candidate compared to itself.
For valid input, all protected values and topology inherit entry validity. Exact
equations independently check every permitted record and deletion. JSON/plain-type
and whole-output alias checks remain; protected read views cannot enter output.
Publication still deep-copies the validated output pack and compares actual inserted
authority with its pre-copy canonical encoding. Retained handler references cannot
mutate the candidate after publication or the twice-detached committed world.

This is localization of the existing one-event proof surface, **not Stage 3G-D**:
the complete outer candidate and detached commit copies are unchanged. There is
no new persistent index, structural sharing between committed worlds, or save format.
Standalone/global ownership remains available for the broader reference tests.

## Local event/history and transition proof

`_event_contract_witness(..., ownership=capsule)` verifies genuine predecessor
identity/liveness and copies only the exact pending/history IDs in that capsule's
certified footprint. Without a capsule it retains the full historical witness.
`_event_proof_world` obtains only structurally writable event records, checking
the table/source/footprint seals. Kernel immutability, fresh generated IDs, order
cursor and event allocator equations operate on those genuine before/after records.
All other events/history are unreachable mutable authority, so the local ID union
is equivalent to subtracting unchanged protected IDs from both global unions.

Flight and Payment proofs use that same event scope. They still verify selected
event lifecycle, generated successor contents, allocator cursors, complete
simulation facts and exact affected domain records. Flight ownership uses actual
airline/flight/aircraft IDs; result/operation existence checks remain direct.
The full entry validator proves exactly one current departure per eligible flight,
one completion per locked operation and global ID/order uniqueness. Unrelated
events cannot introduce another matching lifecycle event during a capsule. Exact
new successor and result identities preserve those constraints by induction.
Completion chronology/latest-result and Payment journal-history applicability
scans are intentionally retained; no speculative lookup is substituted.

## Sealed canonical selection lifecycle

There remains one order: `kernel._event_key`, `(UTC, priority, sequence, ID)`.
The validated request builds the canonical derived heap, and a shared batch copies
that heap along with its complete detached candidate. Only an internal kernel
queue can mint `_CanonicalSelection`; a plain list, raw event, foreign candidate
or ordinary constructor cannot grant this capability.

The selection binds the capsule/source identity, canonical heap head and selected
event contents. It retains only the local pending output rows, their identities
and exact JSON encoding, cursor and selected UTC. It does not copy the world or
queue into a certificate. Domain matching checks the selected event's exact owner,
revision, type, payload and timestamp; it reuses canonical precedence instead of
calling the whole-queue minimum. This is not a second gameplay implementation.

Lifetime: mint immediately before one synchronous handler invocation; kernel sets
its due UTC; consume through the handler's private context; revoke in `finally`,
including handler/contract failure; then perform proof/publication. Removing,
replacing (even equal-value), modifying the selected row, inserting a permitted
child, moving the heap head, changing UTC/cursor, consuming/closing the capsule or
publishing any other capsule rejects reuse. Unapproved earlier/equal-time queue
writes are forbidden by the source boundary itself. An owner generation expires
other outstanding capsules after publication. Generated children enter the heap
only after the transition and obtain a fresh selection when next processed.

The exclusive-owner contract prohibits external raw mutation during a live event.
Validated management commands occur between safe steps, signal the existing heap
rebuild, and cannot overlap a live selection. No certificate survives a handler,
step return, rollback/replay, fence, commit, save/load or rebind. This ordinary
Python capability API is not a security sandbox against private-token access,
closure introspection or monkeypatching; that is the existing ownership contract.

## Global authority and reference deliberately retained

- Full entry, final batch and clock-gap validation, Save/Load validation.
- Both complete outer copies, strict handler isolation and final detached commit.
- Full simulation/configuration/revision witnesses and exact typed comparison.
- Current manifest/checkpoint/sale/carriage and finance/journal equations.
- Latest-result and payment chronology applicability scans.
- Strict global handler contract; shadow's complete protected-state proof and
  independently selected strict kernel event/full-world comparison.
- Strict successful-prefix replay, failure rollback, optimizer disable/diagnostic.
- Existing candidate manifest lookup, separate committed-only Stage 2 reads.

Mixed Payment/Departure/Completion eligibility remains exact callable/version/
support/proof identity. Unknown/custom/unsupported handlers remain strict.
Booking/weekly/expiry fences flush before execution; no scope crosses a fence.
No new handler is certified. Same-UTC causal accounting is untouched: default100,
processed10000, counts retained across yields/flushes, reset on UTC progress;
later children remain queued without charge. Explicit Advance retains its existing
causal limit10000. No pacing credit/event is discarded.

## Measurement

Same frozen real Stage 3F worlds, one game day, actual production session/resolver
cap8. Preserved 3G-A controls and new quiet samples are serialized; no concurrent
suite/benchmark in the final measurements. Existing unrelated host processes were
not stopped. These are single samples, not statistically controlled medians.

| Aircraft | Events | Before s | After s | Reduction | Optimistic after speed | Max callback before → after s |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 9 | 1.142 | 1.083 | 5.2% | 79792.7× | .628 → .600 |
| 10 | 81 | 17.992 | 13.256 | 26.3% | 6517.8× | 3.434 → 3.392 |
| 25 | 201 | 78.870 | 47.189 | 40.2% | 1830.9× | 7.013 → 7.059 |
| 50 | 401 | 280.155 | 138.925 | 50.4% | 621.9× | 12.467 → 12.392 |

Fifty saves **141.229 seconds**. Required Ultra remains1800×/48s per day;
138.925s is still2.89 times that budget. This finite-target comparison is not
sustained certification. Ten→25 cost3.56× for2.5× aircraft;25→50 cost2.94× for2×
aircraft, improving the observed curve but still superlinear on coupled worlds.

Separate exclusive after run: **138.754s**, exact same authority and event vector.
New selection/topology costs are included in the proof group, not hidden elsewhere.

| Exclusive group | Before s | After s | After share |
| --- | ---: | ---: | ---: |
| Event/history/ownership/transition +sealed selection | 111.096 | **12.826** | 9.2% |
| Complete-world validation | 77.975 | **78.402** | 56.5% |
| Outer candidate/commit copies | 25.933 | 25.793 | 18.6% |
| GC | 27.354 | 8.394 | 6.0% |
| Flight handler residual (old included queue scans) | 27.212 | .114 | .08% |
| Booking preparation/process including probe/allocation subregions | 8.473 | 8.565 | 6.2% |
| Manifest/index | 3.088 | 3.059 | 2.2% |

After proof components: witness1.438, kernel comparison.015, capsule begin3.105,
output checks2.292, publish2.882, close.056, flight capture.043, topology1.468,
equations1.472, local event scopes.022, selection mint.020/read.013 seconds.
Proof decreases **88.5%**. Residual outside all instrumented groups is .886s;
queue build/copy and notifications remain separately attributed. The whole-world
graph/domain gates and copy costs did not migrate into an unlabelled proof region.

| Operation / volume | Before | After |
| --- | ---: | ---: |
| Complete validations | 54 | 54 |
| Outer candidate / commit copies | 52 /52 | 52 /52 |
| Commits (shared /strict) | 51 /1 | 51 /1 |
| Flight witnesses | 400 global | 400 local |
| Pending /history rows copied by those witnesses | 2590948 /272681 | **400 /0** |
| Handler pending minimum scans | 400 (inside old residual) | **0 certified scans** |
| Handler matching calls | 400 whole-queue scans | 400 single selected-event matches |
| Output checks | 800 broad protected walks | 800 local store/output checks |
| Manifest lookup /manifest checks | 51 /800 | 51 /800 |
| GC collections | 32710 | 7403 |

Baseline row visits are computed exactly from the preserved ordered401-event
vector, initial pending6580/history482 and actual generated-child increments.
New witness volume is instrumented directly. Local event topology is called2000
times (bounded permitted keys), selection mint/read400 each. No full history copy
occurs on the certified production path. Full diagnostic shadow remains expensive.

Fresh50 two-event control: **5.760 →4.841s**, max4.403→3.488s. Aged50 same next
two events: preserved7.292→6.094s, max5.434→4.459s. Divine's retained one-plane
21901-Booking next Departure: **3.675→3.511s**, max2.837→2.695s. Every prefix hash
and ordered event vector matches. Divine's modest gain reflects dominant untouched
Booking graph/full-world validation/copies; aircraft count is not world size.

Memory: quiet50 process peak388.73MiB versus preserved389.0MiB; working set after
service263.80MiB, versus265.5MiB baseline. Exclusive after peak388.74MiB, post-service
277.16MiB. Input, verification and both outer world copies are included. This is
not a large peak-memory reduction or a multi-week leak certification. New stores
contain only footprint rows and live for one event; owner generation/selection
state is released on publication/failure/close. Legitimate retained history grows
by the same7750 Bookings/itineraries,200 results,201 journals and401 history rows.

## Exactness and remaining boundary

All four quiet-day complete-world hashes and event vectors equal preserved3G-A.
Fifty raw hash remains
`2368617d74d6da1acaf9c166037170ce64d8cef629211ea0a5089805c20550f4`;
the same explicit final Normal30 action yields
`dadcf6f513b68409b453c9629633fe603763c2ba84af5de46bd3ed3219dd8fc0`.
Results/journals/history/Bookings/itineraries/RNG/configuration/recurrence/pending
and aircraft are included, with no field exclusions. The fixed50 prefix remains
`b787e6f2434f9d5cadd2d92e0bf003bf39004a4474ac6952c1fe8faceb5e3ae2`.

Ranked remaining bottlenecks: complete validation, outer copies, residual proof
(principally whole simulation/revision witnesses and output packs), strict Booking
work and GC. Protected operation/result/journal chronology scans remain. No new
candidate-local index was necessary; the existing manifest service is unchanged.
The measured next proposal, requiring separate approval, is **3G-C dependency-complete
boundary validation**, preserving exact inverse/time-dependent closures and global
foreign-input/Save/Load gates. It alone is not promised to achieve Ultra or smooth
callbacks. Outer copies and indivisible fences remain further boundaries.

## Verification tooling

### Native Windows observations

Fresh processes, Kivy2.3.1/SDL2/OpenGL, real direct TEMP Load initially paused,
actual Ultra pump and a50ms heartbeat. Same50 source one second before Booking;
same Divine source and60-second observation budgets. Setup/save/load work is
excluded from active Windows samples using the existing Unix phase markers.

| Comparable input | Callbacks before → after | Median s | p95 s | Max s | Heartbeat max s |
| --- | --- | --- | --- | --- | --- |
| 50 at Booking | 10 →17 | 5.528 →2.899 | 7.004 →4.426 | 13.508 →13.895 | 13.580 →13.975 |
| Divine phase-marked60s | 29 →29 | 2.704 →2.655 | 3.357 →3.320 | 5.034 →4.967 | 5.042 →4.976 |

No p99 is claimed for these small samples. Fifty's Booking callback:13.891s
engine/.00339s presentation, versus13.504s/.00295s baseline. Its strict work is
unchanged; single-run variation is not an improvement claim. Subsequent flight
units are mostly2.8–3.1s. Active Windows not-responding samples: **34/50** versus
55/56 for50; Divine **2/31** versus0/29. Query samples are uneven and not wall-time
percentages. Whole-process counts (including Load/post-snapshot) are not used.
These observations establish **POOR responsiveness**, not deadlock, smoothness
or a human mouse/paint survey. Event processing and committed UTC continue.

Both observations validate and reload exact paused committed-prefix snapshots.
They retain outstanding credit at observation stop (50 approximately95880 game
seconds), so diagnostic SaveStore snapshots are explicitly **not player Save/drain
claims**. No credit is dropped to make the observations pass. Standard player
pause/drain/manual save and reload are verified separately by native cooperative
smoke and regression tests. No production save is touched.

Starter native cooperative smoke also **PASS**: fresh direct TEMP Load, all four
speeds, flight processing, player pause/drain/manual save/exact paused reload,
and controlled overload stimulus/drain/recovered pause.66 callbacks, median.0927s,
p95.1227s, max.4884s. It is a policy/functional smoke, not capacity certification.
Four-speed finite50 target plus independent strict reference all produce the
same `b787e6...ae2` complete hash and two-event vector, with one shared commit.

Focused verification:138 existing ownership/Flight/Payment/shared cases PASS;
20 new locality/selection regressions plus7 profiler guards PASS (27 in21.912s);
110 additional causal/cooperative GUI/Stage2/manifest/scheduling activation/Earliest
cases PASS (247.439s). These include100-generation direct/indirect runaway and
retry, future113-publication fanout, processed-limit bounds, exact retained credit,
overload semantics, untouched recurring behavior and all existing protection paths.
The138-case run predates the additive foreign-source queue seal; the new guards
and complete final suite exercise that seal. No expected gameplay result changes.

Full `python -B -m unittest discover -s tests`: **1136 passed in1206.751s**,
baseline1116 plus20 new tests. Production/test source stayed frozen during this
run; subsequent changes record documentation evidence only. Includes complete
Stage1/2/3 strict/oracle/shadow/recovery, Booking/manifest/finance/aircraft,
event/history/safety, persistence/migrations/autosave/bookmarks, continuous
recurrence, scheduling activation/Earliest and GUI regression suites.

Commands use the project Python3.12 environment:

```text
python -B -m unittest tests.test_candidate_ownership tests.test_flight_certification tests.test_payment_certification tests.test_shared_candidate -q
python -B -m unittest tests.test_local_runtime_proofs tests.test_runtime_forensics -q
python -B -m unittest tests.test_causal_generation tests.test_cooperative_runtime tests.test_gui_cooperative_runtime tests.test_owned_reads tests.test_candidate_manifest_lookup tests.test_scheduling_activation tests.test_scheduling_earliest_activation -q
python -B -m unittest discover -s tests
python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py
python -B -m tests.smoke_cooperative_runtime
python -B -m tests.profile_runtime_forensics --fixture <temp>/fleet-50.json --seconds 86400 --budget 600 --quiet
python -B -m tests.profile_runtime_forensics --fixture <temp>/fleet-50.json --seconds 86400 --budget 600
git diff --check
```

Scoped compilation and Windows observer PowerShell AST parsing PASS. Affected
local documentation links resolve; historical status body remains unchanged.
Instrumentation cleanup/identity/quiet versus profiled exactness guards PASS.
Final full diff review checks local source protection and base-mutator rejection,
genuine predecessor/output separation, no stale/forged public selection, typed
equality/aliases/serialization, exact generated-child accounting, custom strict
fallback, mixed certification/fences, first-invalid/recovery/disable, Stage2
committed-only reads, complete saves, schema and scope. No ordinary findings remain.

## Changed files and delivery boundary

Production (six): `game/simulation/kernel.py`, `shared_candidate.py`,
`candidate_ownership.py`; `game/world_state/flight_transition_validation.py`,
`payment_validation.py`; `game/aircraft_operations/fulfilment.py`.
Testing (two): `tests/test_local_runtime_proofs.py`, `profile_runtime_forensics.py`.
Documentation (six): this report, Current Development Status, Decision Register,
Runtime Candidate Ownership, Runtime Scalability Forensic Audit and Docs/README.

Only this Stage3G-B scope is committed; actual commit/push/live verification is
reported at delivery. Pre-existing untracked `.venv/` remains untouched.
**PH 1.0 runtime remains NOT CERTIFIED. Stop after Stage3G-B.**
Tooling: [exclusive profiler](../../tests/profile_runtime_forensics.py),
[new regressions](../../tests/test_local_runtime_proofs.py),
[Windows observer](../../tests/observe_runtime_window.ps1).
New exclusive categories explicitly include selection mint/read, local event
topology and queue copy. Witness counts/record volume are reported separately;
nested timings are never summed with their parents. GC remains enabled.

All fixtures/snapshots/output stay in caller-owned TEMP, never production Saves.
Single samples are host observations, not statistical guarantees. Setup,
hashing/post-validation and diagnostic memory collection are outside engine time.
Schema **7**, ratios **30/210/900/1800**, cap **8**, one safe unit per callback,
exact credit/drains, recurrence, RNG, formulas and no offline progress remain.
No Stage 3G-C/D/E/F or unrelated GUI/gameplay work is implemented.
