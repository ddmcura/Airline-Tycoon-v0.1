# Hybrid Quarterly Completion Feasibility — Stage 3G-B3D

## Executive summary

**2026-10-13–14. NO-GO for bounded production integration from this experiment.**
Baseline `24535b5b6f8eca51d27b2bf785d66445be50cf9e` matched HEAD, upstream,
freshly fetched origin/master and live remote master, divergence 0/0. Tracked
tree/index were clean; `.venv/`, protected metadata and empty stashes were preserved.
Only isolated tests/diagnostics and documentation change. All production copies,
gates, budgets, Schema 9/templates, economics, legacy authority and activation remain.

Completion's direct writes are small, but the proposed selected-input boundary is
not closed. An invalid unselected itinerary, an out-of-scope mutable alias, and an
unselected itinerary newly referencing the selected flight leave **exact selected
input bytes unchanged**. Strict/detailed validation rejects those worlds. Thus the
selected frame cannot replace fresh source validation or prove manifest membership.
Even **two valid sources** can have identical selected inputs: removing a
reconstructible future dispatch is allowed, but strict reconciliation then creates
a different event ID/cursor before Completion. The selected frame alone does not
determine complete command-equivalent output in that case either.
Copied selected inputs are detached; they do not enforce ownership of the original
mutable world or prove unchanged authority outside the frame.

The experiment obeys the instruction to stop constructing local execution when
safe closure cannot be established. It retains a **selected-input probe and fail-closed
transaction shell**, not an independently certified local Completion executor.
The shell never admits local writes. Supported calls fall back to the actual strict
Completion command; unsupported handlers/providers/events/legacy inputs are refused.
No matching strict fallback result is presented as a new local-semantics proof.

Whole-command controls on zero-carriage, 1,176-Booking and 42,923-Booking inputs
include all probe and fallback costs. They retain two runtime copies, two
reconciliation world deepcopies and two full gates per successful Completion.
The fast-path acceptance requirements are therefore unmet. Preserve the current
engine and revisit source-ownership/validation and performance-target assumptions;
do **not** automatically schedule another certification experiment. This rejects
the tested standalone boundary, not every conceivable hybrid architecture.

## Authority and scope

[AGENTS](../../AGENTS.md), [Schema 9](Stage%201%20State%20Schema.md),
[template mirror](../../Data/Templates/template_reference.txt) and
[folder guidance](../../Data/Templates/foldertree.txt) govern. Relevant context:
[B3C review](Quarterly%20Runtime%20Architecture%20Review.md),
[B3B certification](Quarterly%20Completion%20Certification%20Feasibility.md),
[B3A](Safe%20Quarterly%20Transaction%20Architecture%20Feasibility.md),
[copy/validation investigation](Quarterly%20Transaction%20Copying%20and%20Validation%20Investigation.md),
[benchmark](Quarterly%20Runtime%20Benchmarking.md),
[ownership](Runtime%20Candidate%20Ownership.md),
[shared recovery](Runtime%20Shared%20Candidate%20Infrastructure.md),
[save specification](Game%20State%20%26%20Save%20Technical%20Specification.md), and
[AT-058 policy](Single%20Speed%2C%20Advancement%20%26%20Offline%20Progression.md).
AT-059 and AT-064 remain Proposed; this result does not approve history redesign.

The only attempted event family is the exact built-in quarterly Completion on
`QUARTERLY_BACKEND_V1` inputs. No local Departure, Booking, publication, route,
custom provider/callback or legacy execution is introduced. Fixture setup and
the unmodified strict oracle necessarily run existing domain paths; that does
not certify those paths as local transactions. No batching or pacing change is made.

## Dependency and ownership map

| Record/dependency | Actual Completion use | Permitted direct effect / ownership finding |
| --- | --- | --- |
| Selected pending event | Canonical minimum, owner, payload, UTC and operation revision | Delete pending row; archive exact COMPLETED event; kernel owns lifecycle/order |
| Selected dated flight | Identity, lineage, endpoints, schedule, capacity, inventory and operation revisions | Status COMPLETED and operation revision +1; other fields unchanged |
| Frozen active operation | Actual aircraft, manifest/witnesses, configuration/maintenance and lifecycle IDs | Delete selected operation; retain exact facts in result |
| Aircraft and result chronology | Ownership, IN_FLIGHT position, counters, last result/other active relationships | PARKED at destination; cycles/flight seconds increment; global chronology/uniqueness inherited only from valid source |
| Current Bookings/itineraries | Confirmed membership, quantities, dates, lineage, sale/checkpoint authority | Read-only; actual manifest reconstructs membership, not just selected frozen IDs |
| Checkpoints, ticket sales, inventory | Booked quantity, purchase/result provenance, current witnesses | Read-only; checkpoint rows can contain large nested collections |
| Airline and accounts | Currency, liability, finance revision, account ownership | One finance revision increment and four account effects; integer-minor equations |
| New result/journal and allocator | Exactly-once settlement, canonical ID, paired lineage/amounts | Create one result and transaction, increment transaction allocator; no local implementation admitted |
| Plans/services/connection/market/airports/configuration | Published commitment, eligibility, timing, fulfilment/maintenance formulas | Protected domain facts; direct source snapshots do not establish their complete invariant closure |
| Queue, reconciliation and UTC-dependent authority | Actual next event, future obligations, publication ordering, validity at changed UTC | Reconciliation precedes selection in the strict command; completeness may concern other aircraft/plans and queues |
| All other authority and aliases | Source validity, cross-record sharing, unchanged status | No write permitted; a selected frame cannot detect corruption/aliasing here |

Actual implementation is `_completion_handler` → `_completion` → current manifest,
cost and settlement → kernel event resolution → result full gate → detached commit.
Completion generates no child events itself; preceding backend/publication
reconciliation can create required work and cannot be omitted without proof.
There is no arbitrary activation provider inside the Completion handler. Registry,
manifest read-capability and helper boundaries still require exact trusted bindings.

Strict manifest reconstruction scans the retained Booking table when no owned
lookup is supplied. CandidateManifestLookup builds and independently verifies
groups over current Booking/itinerary authority. Rebuilding that lookup for one
Completion still costs O(B); trusting caller IDs, frozen manifest IDs, identity or
row counts is insufficient. Reuse requires enforced source lifetime and complete
ownership, not a new persisted cache. No such free lifetime is supplied by the
ordinary borrowed mutable `Stage1Session.world` boundary.

Advancing simulation UTC is also a cross-domain write. Other mandatory publication,
contract, airport/calendar and operational obligations must remain valid at the
new time. Exact selected flight equality is not a proof of those unchanged-but-
time-dependent predicates. The bounded probe does not claim to close them.

## Prototype and decisive negative proof

[Probe/shell](../../tests/hybrid_completion_boundary.py) performs canonical queue
selection, direct selected row lookups, typed-byte checks before copying selected
data, and independent necessary lineage/type/status checks. It returns only detached
selected inputs, never raw authority. Typed queue/row/frame scans and checkpoint
subtrees are actual work, not a constant-size certificate. Necessary checks are
explicitly labelled **not a validity proof**.

[Focused tests](../../tests/test_hybrid_completion_boundary.py) build valid quarterly
state and change one unselected itinerary revision to True. The selected frame is
byte-identical to the valid control and its necessary checks pass, but independent
detailed full validation and strict execution reject it without mutation. A second
case shares equal-valued lineage dictionaries outside the selected frame: even
the complete world's typed value bytes remain identical, while alias validation
rejects it. A third changes an unselected itinerary's flight membership and again
leaves selected frame bytes unchanged while full validation rejects.

A fourth counterexample removes a future dispatch while retaining a valid world.
Detailed validation accepts both sources, their selected frames match exactly,
but reconciliation recreates that event with a fresh ID/allocator/order cursor in
only one command. Strict complete worlds consequently differ. This is evidence
against skipping command-level reconciliation merely because Completion's own
handler does not generate events.

These are concrete missing-read/ownership counterexamples, not a timing failure
or an assertion that every possible private-owner architecture is impossible.
Any admission predicate reading only this frame must make the same decision for
the valid and invalid inputs. A prior valid flag, revision, source object identity
or copied selected rows cannot distinguish them. Enforcing a detached whole-source
owner and proving complete membership would require additional counted global
work or a different, proved source interface/lifetime outside this standalone scope.

Local construction stops at that unmet precondition. The shell marks
`local_admitted=False` and uses the current strict command. Sidecar reasons are
test-only and are not injected into persisted state or gameplay diagnostics.
Strict source errors, successful results and failures therefore remain unchanged.
No independent local manifest/finance/result constructor is built after this
blocker; B3B's shared-constructor assumption is not relabelled as solved.

Scope refuses arbitrary registry protocols before invoking them, callbacks before
calling them, and non-Completion/legacy boundaries before executing them. Nonplain
selected objects are refused before custom deepcopy/reduction methods can run.
This is ordinary audited Python code, not a hostile-reflection security sandbox.

## Correctness and adversarial evidence

Complete authoritative worlds and ProcessingResults are compared with actual strict
execution. The existing detailed Booking validator is selected through its original
reference path; no error predicate is weakened. Full world comparisons and reference
validation are outside candidate timing and reported separately. Fallback equivalence
is expected and is **not** independent local transaction certification.

| Adversarial case | Experimental boundary / strict reference |
| --- | --- |
| Wrong aircraft, wrong flight, wrong UTC, stale position | No local admission; strict/detailed reject; source preserved |
| Missing/duplicate manifest IDs, invalid Booking reference, passenger count | No local admission; strict/detailed reject; source preserved |
| Boolean/float itinerary lineage | No local admission; strict/detailed reject with original diagnostics |
| Missing/duplicate ticket-sale settlement authority | No local admission; strict/detailed reject |
| Nested publication-list mutation, queue order corruption | No local admission; strict/detailed reject |
| Unselected invalid lineage / foreign alias / added flight association | Identical selected frame cannot reject locally; safe shell refuses local admission and strict/detailed reject |
| Valid missing future dispatch | Identical selected frame; strict reconciliation produces a different valid queue/allocator outcome; fallback matches that source's exact reference |
| Retained selected projection mutation | Detached projection cannot mutate source; it still provides no whole-source ownership |
| Mutating/raising provider, custom handler/registry protocol | Rejected outside scope, callback never invoked |
| Custom selected deepcopy callback | Rejected without invocation; strict source validation reports INVALID_WORLD |
| Failure before mutation / after transaction allocation | Actual strict fallback failure matches reference, complete source/prefix preserved; explicit retry matches |
| Failure after all handler writes | Strict diagnostic injection proves detached rollback; no local rollback proof is claimed |
| Save/load/rebind and shared-request control | Paused snapshots and complete resulting worlds match; quarterly Completion remains strict even in shared request |
| Other event family / legacy marker | Not executed by the shell; no authority migration |

Because no local write set is admitted, there is no test evidence for local
successful-prefix recovery or local failure after mutation. Those acceptance
requirements remain unmet, rather than passed by the fallback. The existing strict
prefix and financial/flight outcomes are preserved. Strict/shared and persistence
controls demonstrate compatibility, not admission of a production optimization.

## Whole-command measurement protocol

[Opt-in driver](../../tests/measure_hybrid_completion_boundary.py) measures either
the actual strict Next Event Completion command or selected preparation/ownership
refusal **plus that entire strict command**. It never compares one local helper to
a whole strict operation. All required fallback entry validation, reconciliation,
handler work, result validation and detached commit are inside the timer.

Inputs are generated through existing public fixture paths or read from the retained
Booking-heavy source. Harness input creation/copying is identical and outside both
command timers; the shell does not inherit any external “already valid” exemption.
Strict-reference world construction/execution, full canonical comparison/detailed
validation, instrumentation and Save/Load are separately recorded. Fresh quiet
processes run three alternating strict/attempt pairs per workload, serially.
Separate instrumented controls count runtime/reconciliation copies and kernel full
gates, record failure/retry cost and check temporary SaveStore round trips.
All samples use the same current Windows host: verified Intel i5-1035G1 / eight
logical processors and Python 3.12.10. No GUI throughput, pacing or competing
test run is mixed into these timers.

The zero-carriage control uses the existing public zero-demand configuration in
test setup only. The 1,176-Booking control is the B3A/B3B fixture. The 42,923-Booking
source reuses the retained 75,758,607-byte fixture, without pruning records or
repeating its roughly ten-minute scenario/warmup construction. Two ordinary
preparatory events produce a genuine locked operation and next Completion; setup
cost is separate and repeated for fresh-process equivalence. There is no fleet
or event-budget certification.

The first heavy setup attempted repeated Next Event calls. Reconciliation can
reintroduce the due dispatch while its same-UTC departure remains PLANNED, so it
did not reach Completion within the explicit setup guard. The corrected harness
uses one ordinary through-boundary request for the due dispatch/departure pair.
This is recorded existing behaviour, not a production fix or a new local path.

Peak working set is sampled immediately after the timed command, before oracle
work. Windows process peaks are lifetime maxima: setup can already establish that
peak. Both pre-command and post-command peaks are retained; their difference is
not claimed as exact transaction allocation. Row metrics distinguish selected
record count from whole-gate lower-bound keyed-entry exposure; nested/relationship
predicate visits are not fully enumerated. Source queue typed scanning/minimum and
nested checkpoint data remain additional work. No global cost is declared O(K).

## Decision and future implications

1. **Local processing without copying the whole world?** Direct write effects are
   bounded, but no safely admitted standalone local execution is established.
   The retained shell executes the strict fallback with its full protections.
2. **Independent verification without scanning the whole world?** No for the current
   borrowed mutable source and selected frame. The negative worlds are indistinguishable
   to it; full source/alias checks and manifest membership remain necessary.
3. **Complete dependency identification?** Direct effects and global barriers are
   mapped; a closed bounded invariant/read set is not established. UTC and
   reconciliation prevent assuming selected rows are the complete command.
4. **Strict successful prefix?** Preserved by unchanged strict fallback. No local
   delta/recovery protocol is admitted or certified.
5. **Material complete-command improvement?** No qualifying local result exists;
   retained copies/scans are unchanged. Paired fallback timings cannot establish
   an architectural speedup, even where ordinary sample noise favours the attempt.
6. **Affected-record rather than history scaling?** No. Strict gates, manifest and
   source/commit/reconciliation work still depend on total retained authority.
7. **Complexity justified?** Not for production integration of this boundary. A
   complete owned-source interface, independently derived invariants and valid
   lifecycle reuse would be a different architectural contract, not a free
   Completion-only substitution.
8. **Proceed toward bounded production hybrid integration?** **NO-GO.** Retain the
   current engine. Revisit source ownership/validation requirements and what the
   aspirational performance targets assume; do not revise approved numerical
   targets, relax budgets or automatically recommend another certification series.

The decision is not INCONCLUSIVE: concrete counterexamples reject the selected
admission premise independently of missing timing. It does not claim to rule out
all future hybrid designs. AT-059/064 remain Proposed. No history store, batch,
offline, pacing, new economics or general quarterly activation follows this report.

## Measurements and verification

| Booking pairs | Selected records / manifest Bookings | Strict median s (range) | Refused attempt + strict median s (range) | Quiet command-end process peak MiB, strict / attempt |
| ---: | ---: | --- | --- | --- |
| 0 | 18 / 0 | 0.111619 (0.102953–0.122464) | 0.101694 (0.096210–0.112589) | 40.012–40.293 / 40.008–40.270 |
| 1,176 | 28 / 4 | 0.344074 (0.342427–0.354503) | 0.376557 (0.355758–0.403126) | 54.047–54.641 / 54.098–55.137 |
| 42,923 | 142 / 54 | 9.909159 (9.793763–10.695153) | 10.027956 (9.969816–10.366684) | 697.742–698.738 / 701.738–702.203 |

All 18 quiet outputs equal their strict complete-world reference; all six separate
instrumented controls do too. Every successful control records **two runtime world
copies + two reconciliation world deepcopies + two full gates**. Those counts are
measured inside the command, not inferred from the historical 13-event day.
Minimum full-gate keyed-entry exposures are 3,850 / 9,264 / 177,228, respectively,
from 1,925 / 4,632 / 88,614 top-level keyed entries. This is a lower bound, not a
count of nested/relationship-predicate visits. Queue input rows are 5 / 182 / 367;
probe typed scanning/minimum and selected/checkpoint copies are extra work.

The 0-Booking attempt happens to have a smaller sample median despite doing the
same strict work plus a probe. With overlapping ranges and no removed work, that
is **not evidence of a local optimization**. No percentage improvement is claimed.
The larger controls remain dependent on retained history; differing fixture dates,
configurations, capacity and manifest sizes mean these are three scale observations,
not a fitted causal growth curve or large-fleet certification.

| Separately reported component | 0 Bookings | 1,176 Bookings | 42,923 Bookings |
| --- | --- | --- | --- |
| Fresh harness setup range s | 1.879–2.027 | 2.802–3.117 | 19.991–20.993, including two preparatory strict events |
| Strict oracle construction/execution range s | 0.098–0.119 | 0.385–0.447 | 11.719–12.554 |
| Full comparison/detailed validation range s | 0.040–0.049 | 0.149–0.165 | 3.596–3.858 |
| Instrumented command s, strict / attempt | 0.114236 / 0.124673 | 0.387635 / 0.422722 | 9.794439 / 9.976001 |
| Save/load control s, strict / attempt | 1.200835 / 1.049891 | 2.272789 / 2.217861 | 38.184039 / 37.962068 |
| Failed command s, strict / attempt | 0.058409 / 0.066874 | 0.261655 / 0.268909 | 6.982263 / 7.110255 |
| Explicit retry command s, strict / attempt | 0.091519 / 0.103948 | 0.353194 / 0.384284 | 10.111726 / 10.165962 |

Instrumentation runs are single controls, not an overhead calibration or paired
performance estimate. Their count wrappers are excluded from quiet samples; the
difference between instrumented and quiet timings includes ordinary noise and is
not subtracted as a made-up precise overhead. Failure preserves complete source;
retry produces the exact strict successful world. Save/load uses temporary roots
and preserves paused Schema 9 snapshots. Memory figures exclude later oracle/save
peaks but can include prior setup lifetime peaks; no exact allocation delta is claimed.

Final tests/compilation/link/scope checks are recorded in
[Current Development Status](Current%20Development%20Status.md). No performance
figure for a nonexistent admitted local executor is reported.

Final standalone B3D: **26 tests / 22.755s, exit 0**. Combined B3D/B3A/B3B/detailed
Booking validation/four affected backend regressions: **105 / 168.890s, exit 0**,
104 executed pass, one optional B3B component measurement skips. B3D's own
18 quiet/six instrumented controls are separate completed evidence. Scoped application
compilation passes. Documentation: **365 local links / 78 heading targets**, zero
errors; whitespace and production/schema/template diff checks pass. No expensive
full gameplay suite is repeated for isolated test-only work.
Forty raw diagnostic/test/measurement files are preserved with SHA-verified copies
in local temporary archive `airline-tycoon-b3d-24535b5-644b62cd5b7848a580fd54d0adffb6a7`.
Only the path-verified task scratch directory was removed. The original retained
Booking-heavy source was read, never rewritten; no generated evidence is staged.
