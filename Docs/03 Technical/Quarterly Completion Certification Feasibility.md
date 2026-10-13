# Quarterly Completion Certification Feasibility — Stage 3G-B3B

## Executive summary

**2026-10-13; partially proven, with named gaps.** Approved baseline
`5db55d05d46c694b89b0b00a4b05c4d35b049429` matched HEAD, upstream, freshly
fetched origin/master and live remote master, divergence 0/0. Tracked tree/index
were clean, `.venv/` was preserved and stashes were empty. Serena was activated.
Only tests and documentation change. All production copies, gates, strict/shared
support exclusions, Schema 9, templates, economics, budgets and activation remain.

The isolated witness binds exact typed source and expected transition bytes, actual
event/flight/aircraft/Booking/itinerary IDs and one-use lifetime. An independently
assembled transition model agrees with actual strict Completion and the B3A protected
shadow handler. The separate whole-graph alias predicate catches equal-value mutable
sharing that byte equality cannot detect. Malformed lineage is never repaired.

This is **not a localized production certificate**. Capture still validates and
copies the whole world; verification scans source, candidate and mutable aliases.
The model shares manifest, cost and settlement constructors with the handler.
Independent full-world validation checks their outputs in the tests, but an
independent derivation of every constructor equation and complete dependency closure
has not been proved. Performance acceptance for removing repeated gates is not met.
Retain negative feasibility evidence rather than presenting this as production-ready.

## Authority and inspected boundary

The [Schema 9 contract](Stage%201%20State%20Schema.md), subordinate
[template mirror](../../Data/Templates/template_reference.txt) and
[folder guidance](../../Data/Templates/foldertree.txt) prevail. Relevant context:
[B3A](Safe%20Quarterly%20Transaction%20Architecture%20Feasibility.md),
[B2.5 investigation](Quarterly%20Transaction%20Copying%20and%20Validation%20Investigation.md),
[runtime evidence](Quarterly%20Runtime%20Benchmarking.md),
[active/history proposal](Active%20State%20and%20Certified%20History%20Feasibility.md),
[ownership](Runtime%20Candidate%20Ownership.md),
[local proofs](Runtime%20Local%20Certified%20Proofs.md),
[shared execution](Runtime%20Shared%20Candidate%20Infrastructure.md), and
[save specification](Game%20State%20%26%20Save%20Technical%20Specification.md).
AT-058 is future product policy; AT-059 and AT-063 remain Proposed.

The actual path is canonical pending-event selection → strict detached candidate →
`_completion_handler` → `_completion` → manifest reconstruction, pinned configuration
and settlement → kernel-owned event resolution → independent full result gate →
detached commit. Completion failure discards the event candidate and returns BLOCKED
with pending work and source unchanged. Separate quarterly publication failures can
publish their own validated fence; this witness does not certify that workflow.
No speculative successful prefix is discarded. Removing the injected Completion
fault allows an explicit fresh public-kernel retry, which also matches shadow.

The real fixture is Schema 9 quarterly state at `2027-01-02T01:00:00Z`, next Completion
at `2027-01-02T02:40:00Z`, with 1,176 Booking/itinerary pairs and four selected Booking
records. Test setup uses normal strict events. No expensive retained advancement
benchmark is rebuilt or rerun.

## Completion transition map

| Authority | Reads/references | Exact permitted effect |
| --- | --- | --- |
| Pending event and simulation | Canonical minimum, due UTC, owner, revision, payload, queue/order cursor | Remove selected pending event; archive exact COMPLETED row at due UTC; advance simulation UTC and selected operation revision; no generated event or order/event allocator movement |
| Dated flight | Published quarterly lineage, immutable identity, timing, endpoints, connection, capacity, fare, inventory and operation revisions | Status COMPLETED; operation revision +1; all remaining fields unchanged |
| Active operation | Actual aircraft, departure/completion IDs, frozen manifest, configuration/maintenance facts | Delete exactly selected operation; retain frozen facts in result |
| Aircraft | Owning airline, IN_FLIGHT state, lifecycle, actual assignment | PARKED at destination; lifetime cycles +1 and flight seconds +block duration; other fields unchanged |
| Booking and itinerary | Confirmed quantities, actual flight membership, published lineage, sale/checkpoint authority and inventory witnesses | **No Booking/itinerary/status/revision write**; retained carriage witnesses bind existing rows |
| Results and finance | Previous result chronology, account ownership/currency, unflown liability, configuration, ticket sales, allocator | One result keyed by flight; one balanced settlement journal with canonical allocated ID; four account deltas; airline finance revision +1; transaction allocator +1 |
| Protected authority | Airports/markets/connections, plans/services, scheduling commitments, checkpoints/cohorts, other aircraft/results/journals, deterministic configuration and UI | Exact unchanged typed values and topology, including nested lists/dictionaries |

Indirect obligations remain live after Completion: Bookings/itineraries still link
to retained published services, checkpoints and ticket sales. Historical results bind
the latest aircraft destination or later active operation. Financial account validity
cannot be inferred merely from one balanced new journal. Whole-source validity is
therefore a mandatory premise, established freshly during capture.

## Record binding and ownership

[Diagnostic witness](../../tests/quarterly_completion_certificate.py) requires a valid
Schema 9 source, the actual next quarterly Completion and matching frozen operation.
It captures immutable **typed value bytes, not hashes**, the selected IDs, complete
source and complete modeled result. Binding includes every dependency because it
captures the entire world, not because a minimal closure has been established.
Source identity is an additional ownership/lifetime check; it never replaces values
or validation. The test harness forks immutable captured witness bytes into separate
one-attempt instances solely to avoid redundant construction across mutation cases.

Capture builds a private expected world without calling Completion or strict event
execution. It applies account, aircraft, flight, allocator and event lifecycle
equations itself. Manifest/cost/result construction still uses existing pure domain
helpers: this is the explicit independence gap. Expected bytes retain no mutable
model references. The source reference is retained only for a one-attempt lifetime.

Verification consumes the witness on **success or rejection**. It rejects another
source object, another event, altered source bytes, generated events, candidate
aliases, new source aliases, sharing between source and candidate, or any difference
from modeled typed bytes. The alias predicate traverses **both worlds together**;
validating them separately cannot detect a mutable row shared between them.
A fresh equal-valued loaded
world requires new capture. Dictionary insertion reordering conservatively rejects;
it need not change canonical queue semantics. Reflection into private test structures
or hostile monkeypatching is outside this diagnostic trust boundary.

Actual shadow execution uses a separate detached world and closes CandidateOwnership
on every exit. The existing footprint protects Booking/itinerary/publication reads
and permits only selected writable rows, simulation and allocator. The B3A lexical
plain-lineage read bridge remains **test-only**, returns detached dictionaries and
preserves exact primitive types. Retaining and mutating those projections after
publish cannot change source or candidate. Existing B3A tests separately attempt
nested protected writes. No source immutability is assumed: raw source mutation
after capture is detected through a full typed traversal before admission.

## Invariant coverage matrix

“Inherited” means freshly established by full source validation and exact protected
comparison, not a cached valid flag. Independent full validation remains the oracle
for every accepted result and malformed candidate in the experiment.

| Invariant / authoritative source | Records | Witness method | Certificate coverage | Full reference still required / gap |
| --- | --- | --- | --- | --- |
| Flight identity/schedule — Schema 9 / quarterly lineage | Event, flight, plan, service, slot, connection | Whole typed source + exact flight update | Yes, inherited published facts | Yes; no minimal publication closure |
| Aircraft identity/position — fulfilment | Aircraft, operation, prior results | Exact assignment, destination and lifecycle equations | Tested selected aircraft | Yes; broader chronology/substitution cases unproved |
| Eligibility — lifecycle/event contract | Pending minimum, locked flight, frozen operation | Fresh source gate + event/status/time checks | Tested next real Completion | Yes; no generalized selection capability |
| Manifest — Booking/fulfilment | Bookings, itineraries, ticket sales, checkpoints, inventory | Rebuild and typed frozen-list equality | Yes for fixture; shared constructor | Yes; independent reconstruction remains a gap |
| Booking status/lineage — Schema 9 | Selected and other Booking records | Inherited valid source, exact unchanged bytes | Yes, no status writes | Yes; multi-leg/custom future behaviour excluded |
| Itinerary status/lineage — Schema 9 | Itineraries and published flight lineage | Exact unchanged source/candidate bytes | Yes; bool/float mutations reject | Yes; inherited graph validity is global |
| Quantities/capacity — Booking contract | Manifest, flight, inventory witnesses | Shared manifest + protected facts | Tested, not independent formula derivation | Yes |
| Result — fulfilment specification | Operation, flight, result, witnesses, event history | Exact modeled new record | Tested; shared settlement constructor | Yes |
| Finance — integer-minor ledger | Accounts, airline, new/retained journals | Own balance/revision deltas + exact expected journal | Tested; shared cost/journal construction | Yes; complete independent economics proof missing |
| Generation/order — clock contract | Pending/history, allocator, simulation | No generated events; exact lifecycle and all queue bytes | Yes for selected success | Yes; dictionary order rejection is conservative |
| Same-UTC causality — kernel | Queue ordering, publication precedence | Canonical minimum and unchanged ordering | Selected boundary only | Yes; 100-generation/10,000-event and mixed same-UTC flows not certified locally |
| Failure fences — kernel recovery | Pending work, simulation diagnostics | Actual strict-kernel duplicate controls | **No local failure certificate** | Yes; production owns fence validation |
| Retry/rollback — transaction boundary | Complete source/candidate/result | Injected settlement failure; exact source and diagnostic; fresh retry | Tested isolated failure and retry | Yes; all possible failure points not exhausted |
| Save/load — save specification | Complete snapshot and new active object | Production temporary SaveStore round trip; fresh binding | Tested paused success and expiry | Yes; malformed load rejection covered by existing affected regressions |
| Exact types — Schema 9 / B2.3 | Whole tree, lineage, witnesses | Typed bytes + source validator + candidate alias scan | Tested bool/float/missing/extra/source ranges | Yes; trusted constructor shapes inherited/tested |
| Legacy isolation — compatibility contract | Unmarked legacy flight/event | Reject quarterly certificate; unchanged legacy strict success | Tested | Yes; no production enrollment/support change |

No claim of complete invariant closure or independently certified failure fences is
made. Existing full gates are essential to the reference, not redundant by assertion.

## Adversarial results and strict equivalence

[Tests](../../tests/test_quarterly_completion_certificate.py) compare the entire
authoritative envelope, not only results or hashes. Both normal optimized full
validation and the independent detailed Booking relationship path check candidates
and agree on complete diagnostics. The reference graph optimization is bypassed
only to select its unchanged detailed validator; no error predicate is weakened.

Each mutated output is rejected by the certificate. Full-world rejection and
strict-transition mismatch are distinct: a structurally valid alternative world
can still be an unauthorized Completion output. Byte-identical aliases need the
separate full alias predicate. See verification evidence below for final counts.

| Mutation | Certificate | Independent full validator / reference |
| --- | --- | --- |
| Wrong aircraft, flight, timestamp or final position | Reject each | Reject each |
| Missing/duplicate result, missing/duplicate manifest, passenger total | Reject each | Reject each |
| Invalid Booking reference, itinerary revision, bool/False/float lineage, both-side lineage, missing/extra keys | Reject each | Reject each |
| Flight-only bool lineage; Booking-witness bool/float lineage | Reject each | Reject each |
| Unrelated account balance set to zero | Reject | Full world can remain valid; exact strict transition differs |
| Settlement entry amount, missing/duplicate transaction | Reject each | Reject each |
| Queue insertion/deletion | Reject each | Reject each |
| Queue order-key change | Reject | Full world valid; exact selected transition differs |
| Queue dictionary insertion reordering | Reject conservatively | Full world valid; canonical semantics may be equal |
| Unrelated nested plan-list mutation | Reject | Reject |
| Valid unrelated UI selection change | Reject | Full world valid; complete strict world differs |
| Result/flight share the same lineage dictionary | Reject via alias scan | Reject; exact value bytes alone are identical |
| Source operation/flight acquire equal-value lineage alias after capture | Reject via source/candidate graph scan | Reject; source value bytes remain identical |
| Candidate retains an unchanged mutable itinerary from source | Reject via cross-world alias scan | Each world alone remains valid; detached transition ownership fails |
| Foreign equal source, altered source, wrong event, generated event, repeated/expired witness | Reject each | Binding rejection; full validator cannot certify witness provenance |
| Malformed source revision True, False, 1.0, string, null, zero, negative, excessive unmatched revision | Reject before capture | Both full/detailed reject each |
| Settlement exception | No success witness admitted | Shadow/strict failure diagnostics agree; exact source retained |
| Retry after exception | Fresh witness succeeds | Complete world equals fresh strict retry |
| Save/load then old-witness reuse | Reject; fresh binding succeeds | Valid paused round trips and exact completed worlds agree |

First run correctly rejected the alias mutation but its test incorrectly asserted
that aliasing must change value bytes. The assertion was corrected to explicitly
prove **equal bytes plus detected alias**. This was a harness error, not a weakened
certificate. An alternate shell invocation failed before tests because sandbox TEMP
was not propagated; final runs use explicit workspace TEMP/TMP and never player Saves.

## Performance feasibility

Only the small real Completion fixture is measured. Capture includes a full source
gate, full deepcopy, manifest/model work and two complete typed snapshots. Verify
includes two full typed traversals and a mutable-container scan across both worlds.
`record_count` counts top-level keyed records, including singleton dictionaries;
it does not count nested objects or imply selected-record-only work.

The retained witness holds two complete byte snapshots plus a reference to existing
source. Tracemalloc captures additional Python allocation during construction;
already allocated fixture/source memory is excluded. Peak includes the temporary
expected-world copy. These are component diagnostics, not process RSS or a quiet
advancement benchmark. Verification costs do not include the strict/full oracle.

The witness cannot be reused across events, mutations, failure attempts or Load.
Constructing one per event pays the global source gate again. Faster byte comparison
does **not** establish a route to eliminating full traversals in current mutable
ownership or independently proving domain equations. Numerical measurements and
test results are recorded in the final evidence section.

No end-to-end improvement, 50-aircraft capacity, 90-day target, event grouping or
offline/pacing claim is made. The historical retained benchmark remains historical.

## Decision gate and recommended next step

1. **Exact binding?** Yes for this tested one-event success boundary, through exact
   typed world values, selected IDs, alias scanning and one-use source lifetime.
2. **All invariants?** No. Named gaps include independent manifest/cost/result
   derivation, minimal dependency closure, generalized chronology, same-UTC mixed
   events and locally certified failure fences.
3. **Unauthorized writes without full scan?** No in this prototype. Capsules restrict
   handler writes, but externally mutable source lifetime is checked globally.
4. **Independent strict match?** Actual strict complete worlds and independent full
   validation match the tested shadow. The modeled constructor assumptions are
   shared and explicitly prevent a stronger independence claim.
5. **Failure/rollback/retry?** Tested settlement exception diagnostics, retained source,
   fresh deterministic retry and unchanged kernel fences agree. The certificate
   authorizes success only; other failure points remain unproved.
6. **Performance potential?** Typed checks are cheaper than a full validation in the
   small component samples, but capture plus verification exceeds one full gate and
   retains global work and extra memory. No meaningful gate-removal benefit is proved.
7. **Future bounded production experiment justified?** **No at this checkpoint.**
   First require a separately authorized test-only design with enforced source
   lifetime, independently derived selected manifest/finance equations and closure,
   broader failure/chronology coverage and reproducible cost advantage. If that
   cannot avoid equivalent scans, retain the existing strict path.

Classification: **Partially proven, with named gaps**. The complete-snapshot witness
is useful negative/diagnostic evidence; it is not viable as a local gate replacement.
AT-059 remains Proposed. This report approves no subsequent experiment or milestone.

## Verification evidence

Final focused run: **42 tests / 32.877s, exit 0**, including 31 output mutation
cases, all detected. Independent full/detailed validators agree: 27 invalid worlds
reject, four structurally valid alternative outputs require transition comparison.
Median of three small-fixture samples: construction **0.206349s**, verification
**0.054453s**, full result validation **0.117614s**. Capture plus verification is
about 2.22 times this single-gate median; this ratio is descriptive component cost,
not a speedup or a representative workload projection.

The fixture has **4,632 keyed records**, four selected Booking records. Retained
typed snapshot bytes: **4,606,801**. Additional construction allocations measured
by tracemalloc: **4,751,651 retained / 7,861,695 peak bytes**. Three capture samples:
0.194342, 0.215218, 0.206349s; verification: 0.054453, 0.059596, 0.046406s;
full validation: 0.117614, 0.120625, 0.110581s. These samples are diagnostic and
sequential, not fresh-process quiet benchmark certification.

The broader B3B/B3A/backend/Booking-validation/flight-certification/ownership run
passes **198 tests / 937.741s**, exit 0, including the earlier 41-test witness scope.
After that run, the final 42-proof command verifies the source/cross-world alias
strengthening and fresh public-kernel retry. Both additional alias cases preserve
exact value bytes; a source/candidate graph scan rejects them. Production and the
157 affected external tests are unchanged. The expensive full gameplay suite is
not repeated for this isolated task. Scoped compilation passes; all production,
schema and template diffs against baseline are empty. Documentation checks:
**351 local links / 75 heading targets**, zero errors; whitespace check passes.

Four task-owned log readers stalled on the initial large byte assertion diagnostic;
their exact command lines were verified before stopping only those completed-log
readers. Active regressions were preserved. Final component samples were collected
after reader cleanup and broader-test completion. Earlier samples are not substituted
for the final ownership-complete measurement or interpreted as a speedup.

Final commands, counts, component costs and documentation checks are also recorded
in [Current Development Status](Current%20Development%20Status.md). Test-only scope
permits focused/affected regressions without repeating the expensive full gameplay
suite. Production files, Schema 9 and templates must remain identical to baseline.

Eight raw logs/diagnostic scripts are preserved with SHA-verified copies in local
temporary archive `airline-tycoon-b3b-5db55d0-f89c89a5b74741e88d2ce36bec764e5b`.
Only the verified task scratch directory was removed; no generated evidence or
player save is committed.
