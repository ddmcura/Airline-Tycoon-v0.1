# Flight Proof Cost Optimization — Revised Stage 3D

Approved bounded scope, 2026-10-04. Baseline
`c3d47de83b9c1d7cce1c1d82fbb48697757da21d` matched local HEAD, upstream and
live origin/master before changes. This replaces additional handler certification
as Stage 3D's scope. Authority: [canonical event contract](Stage%201%20State%20Schema.md#clock-and-event-contract).
[Stage 3C](Flight%20Shared%20Certification.md) and
[Stage 3B](Contract%20Payment%20Shared%20Certification.md) retain their exact
transition contracts. Schema remains **7**. Normal session/Kivy/Advance execution
stays strict; Stages 3E and 3F and overload recovery are unimplemented.

## Stage 3D.2 successor — bounded mutation ownership

[Runtime Candidate Ownership](Runtime%20Candidate%20Ownership.md) documents the
separately approved successor. Exact built-in Payment/Departure/Completion receive
one-event write capsules and recursively read-only protected authority. Genuine
predecessor/selected-output proofs remain; protected JSON/alias validity inherits
from fully validated entry plus enforced write isolation and local output checks.
Full protected/alias oracles remain in shadow mode, with strict replay, final full
validation and detached commit unchanged. Memoized read capabilities end before
flush/recovery; they are neither authority nor Stage 2 indexes. Schema stays 7.
Normal session/Kivy/Advance pacing remains strict; no Stage 3E/3F or new certificate.
Earlier dated sections below retain their historical implementation evidence.

## Reproduction and exclusive measurement

Frozen caller-owned TEMP fixtures from Stage 3C are reused without modifying
production saves or reference data. Fresh pre-change controls run the original
source (and a read-only TEMP archive of the verified baseline). Latency tool:
`python -B -m tests.profile_flight_certification --fixtures <temp> --mode both
--repeats 3 --observed-fixture <detached-temp-world>`.
Setup, input copying, hashing and instrumentation are outside latency samples.
Same target, batch cap 64, generated ceiling 10,000, full-world output oracle and
commit vectors apply before/after. No workload is reduced.

`python -B -m tests.profile_flight_proof --fixtures <temp> --case all`
adds a separate exclusive timing stack. A parent's exclusive seconds subtract
all instrumented descendants; category totals can therefore be summed. Direct
replacement wrappers retain no world arguments, unlike the older mock profiler.
Serialized bytes, actual Booking visits and kernel event records copied are
counted. Collection sizes are reported independently. The total less summed
categories is explicit unattributed work, including uninstrumented dispatch.
Profiler overhead and host contention are distinguished from latency medians.

Measurement tables, commands and limits are recorded below.

## Protected-state audit

Both flight handlers receive a mutable `EventContext.envelope`. Its helpers can
read arbitrary nested authority; the current interface does not enforce a write
barrier. All protected domains are therefore reachable, and future accidental
in-place mutations cannot be excluded merely from today's intended footprint.
No revision counter covers every mutation; object identity remains unchanged
under an in-place write. Neither is an adequate replacement for predecessor
value evidence.

| Protected structure | Why / access / mutation proof | Stage 3D treatment |
| --- | --- | --- |
| Bookings, itineraries, checkpoint/demand state | Frozen carriage, paid/zero partition, inventory/source lineage depend on them. Manifest helpers read them; dictionaries/lists remain mutable and reachable. Booking revisions alone do not certify non-change. | Full genuine before/after typed value witness; inherit JSON compatibility only after equality. |
| Airports, markets, connections, definitions/reservations, acquisition/reference/maintenance sources | Duration, position chain, configuration and historical witnesses rely on them. Reads can obtain nested mutable references; no guaranteed immutable replacement policy. | Same complete protected comparison; no timing/gameplay rule changed. |
| Other aircraft, flights, active operations, results | Exclusive assignment, projected position, latest result and immutable historical carriage. Selected handlers must not mutate unrelated rows. | Exact selected-row proof plus every remaining row/key protected, including new unexpected IDs. |
| Old accounts/journals, other airlines, contracts | Historical settlement/ownership/financial witnesses must remain exact. Completion changes only its owning account set/airline and one journal. | Selected entire records checked; all other rows protected. Payment retains its Stage 3B witness unchanged. |
| RNG, metadata, UI, deterministic facts outside allocator | No certified flight may mutate these; selection never determines simulation ownership. Whole envelope is reachable. | Exact protected bytes; no identity/revision shortcut. |
| Simulation and allocator | They are legitimately changed, so not included in protected bytes. | Entire genuine before simulation/all cursors plus exact approved deltas, and local canonical JSON check. |
| Pending/history | Lifecycle allows only selected archival and one completion successor on Departure. Old events remain immutable. | Existing detached kernel witnesses/topology plus protected nonselected rows and exact selected/generated events. |

All current protected comparisons remain per-event. Selected-row exclusions are
unchanged. No broad check is dropped based on an assumed unreachable reference.
There is no protected-domain cache or revision addition.

## Exact optimizations and correctness arguments

### Protected values: C encoding instead of sorted JSON plus SHA-256

`game/world_state/flight_proof_witness.py` belongs to world-state flight proof,
not generic simulation or game/utils. A private C Pickler emits exact primitive
value bytes with its memo disabled. These bytes are compared, **never decoded**,
never accepted from an external source, and never saved. A reducer override rejects
non-plain custom objects without invoking their reduction. Cycles fail closed.

The before bytes are captured before the handler mutates authority. Equality
preserves integer/boolean/float distinctions, dictionary key types, list versus
tuple, every nested value and structural boundary. This replaces a hash with
actual exact bytes; it does not introduce a hash collision assumption. Memo
suppression removes irrelevant immutable string sharing from the representation.
Mutable sharing is checked separately over the complete candidate.

Dictionary insertion order is retained. Reordering a protected mapping
conservatively fails proof rather than accepting corruption. The exact built-ins
do not reorder protected mappings; insertion-order variation at batch entry
remains supported and is covered by the complete-world oracle. Shallow root/table
views have explicit plain-dictionary guards so they cannot erase invalid types.

### JSON compatibility: changed/excluded records only

A valid batch predecessor is canonical JSON. Every protected value/type is proved
unchanged against detached before bytes. Those values therefore inherit JSON
compatibility. The existing canonical predicate still runs on **every** excluded
record present after the event, entire simulation and entire allocator: selected
flight/aircraft/operation, generated/archived events, owning airline/accounts,
new journal/result as applicable. Missing records are governed by existing exact
topology proofs. Collection/root types erased by shallow views are explicitly
guarded. Unknown added keys/records remain protected and cannot pass equality.

All predicates must pass before the next event; compatibility is not delayed to
flush. A protected mismatch runs the original whole-world JSON predicate only to
provide a useful failure diagnostic. Final complete-world and save validation
remain unchanged, including persistence's canonical sorting/integrity encoding.

### Mutable aliases: retain whole graph, remove unused diagnostic construction

Value equality cannot distinguish two equal-valued lists from one shared list.
An alias may cross changed/protected rows or two old protected rows. Because
handlers receive the whole mutable envelope, a changed-subtree-only alias check
would be insufficient without a separately enforced ownership graph.

The optimized predicate visits **every exact dict/list** and rejects its second
identity encounter, including cycles. It skips primitive stack entries and does
not allocate path strings for every primitive. This is exactly the existing
canonical alias predicate's success/failure property. Canonical diagnostics still
run at full gates; generated-graph tests compare the two predicates. IDs are local
to one traversal with live candidate references; they are not reused as value
or immutability witnesses. No object ID cache survives the event.

## Manifest/history, reuse and mixed-handler audit

Manifest construction still scans all source Booking IDs in both capture and
handler, validates exact checkpoint/sale lineage, capacity and frozen witnesses.
Completion applicability still scans results for latest-aircraft chronology.
Kernel witnesses still detach pending/history records; finance helpers and
selected record comparisons remain exact. Profiling decides whether these costs
justify a subsequent bounded optimization; no Booking/history index is introduced.
No committed Stage 2 cache is passed to the candidate.

There is **no request-level witness reuse** or candidate-local index in this
patch. Mutable reachability requires comparison every event. C encoding makes
that exact conservative proof inexpensive enough to measure before introducing
ownership capabilities or incremental graphs. Consequently no mutation union is
assumed from event names and no stale reuse can cross generated events, Payment,
fences, strict events, commit, cooperative return, load or world/session replacement.

Mixed exact Payment/Departure/Completion continue using their independently bound
callable/version/predicate/proof metadata. Payment code is unchanged. Rotation
remains strict; Booking, weekly publication and expiry remain fences. Unknown,
custom, stale and unsupported inputs retain existing strict fallback. Final full
validation, detached commit, canonical selection/generated-event ordering, strict
successful-prefix replay and optimizer-disable policy are unchanged.

Witness bytes/local alias sets are released when the transition returns or fails.
They retain no world reference after commit/discard, cannot contaminate strict
replay and never enter saves or Stage 2 reads. There is no cross-return cache.

## Measured results (Windows / Python 3.12.10, 2026-10-04)

Three uninstrumented latency samples per flight path; medians in seconds.
Host timing varies; the fresh mixed-ten strict control was especially slow.
Strict engine code is unchanged. Earlier mock-based post-change samples were
discarded because argument retention amplified witness memory; final optimized
medians use the direct non-retaining tool. Original control/optimized input
hashes, all output hashes, event counts and commit vectors are equal. Defensive
root/table type guards are included in final exclusive profiles and verification.

| Fixture | Events | Recorded 3C strict / shared | Fresh pre strict / shared | Optimized shared | Fresh pre / optimized max shared step |
| --- | ---: | ---: | ---: | ---: | ---: |
| one-departure | 1 | 0.414 / 0.518 | 0.316 / 0.368 | 0.369 | 0.275 / 0.278 |
| one-completion | 1 | 0.398 / 0.542 | 0.306 / 0.370 | 0.367 | 0.280 / 0.265 |
| round-trip | 4 | 0.826 / 0.797 | 0.668 / 0.583 | 0.474 | 0.490 / 0.470 |
| dense-departure | 10 | 2.966 / 2.284 | 2.335 / 1.805 | 1.070 | 1.668 / 1.055 |
| dense-completion | 10 | 3.124 / 2.345 | 2.492 / 1.973 | 1.155 | 1.910 / 1.051 |
| mixed-ten | 40 | 11.878 / 7.763 | 21.685 / 5.840 | 3.142 | 5.854 / 2.982 |
| representative-ten | 81 | 39.216 / 24.448 | 30.107 / 18.496 | 10.147 | 10.177 / 4.929 |
| aged-ten | 40 | 15.131 / 8.645 | 11.549 / 7.429 | 3.935 | 7.329 / 3.738 |
| dense-25 | 100 | 61.213 / 30.662 | 44.572 / 24.694 | 12.283 | 14.668 / 7.070 |
| divine-next-departure | 1 | 11.303 / 12.567 | 8.576 / 10.228 | 9.689 | 7.852 / 7.925 |
| divine-short | 3 | 19.756 / 16.910 | 15.940 / 14.012 | 11.484 | 11.938 / 9.018 |

Dense-25 shared median improves **24.694 to 12.283 s (50.3%)** against
fresh pre-change shared, versus recorded 3C 30.662 s. Its maximum latency step
is **7.070 s**, versus recorded 3C 19.798 s. Across all final latency fixtures the
largest shared step is **9.018 s** (Divine-short), not 7.070 s.
One Departure is essentially unchanged/slightly slower (.368 to .369 s);
Divine-next improves 10.228 to 9.689 s but still trails its fresh strict control
8.576 s. Isolated-event regression is reduced, **not eliminated**.
Round-trip shadow median is **1.397 s**, versus optimized .474 s and fresh strict
.668 s. Shadow remains intentionally expensive and verifies each transition.

### Exclusive dense-25 proof pipeline

The following categories do not overlap. Selected encoding includes the small
exact record JSON comparisons; finance/journal/allocator rows show their own
exclusive wrapper work. Manifest includes handler and capture calls. Final/full
gates include request entry, two flushes and final clock gap. Clone time includes
candidate and detached commit copies; commit row excludes nested clone time.

| Category | Fresh pre s | Optimized s | Calls pre / optimized |
| --- | ---: | ---: | ---: |
| full_world_validation | 1.264323 | 1.249459 | 4 / 4 |
| clone | 0.235279 | 0.239683 | 4 / 4 |
| kernel_witness | 0.136581 | 0.134611 | 100 / 100 |
| manifest | 0.837016 | 0.832816 | 200 / 200 |
| protected_encoding | 9.185869 | 5.364678 | 200 / 200 |
| protected_capture | 1.237466 | 0.008327 | 100 / 100 |
| capture_departure | 0.027730 | 0.026366 | 50 / 50 |
| selected_encoding | 0.117644 | 0.127933 | 2400 / 2400 |
| aircraft_reservation | 0.001698 | 0.001887 | 200 / 200 |
| operation_result | 0.002953 | 0.003268 | 400 / 400 |
| event_topology | 0.001369 | 0.001507 | 250 / 250 |
| allocator_revision | 0.001242 | 0.001421 | 200 / 200 |
| canonical_json | 5.007202 | 0.045422 | 100 / 100 |
| mutable_alias | 5.525762 | 3.575622 | 100 / 100 |
| protected_compare | 1.248427 | 0.010272 | 100 / 100 |
| validate_departure | 0.020550 | 0.104058 | 50 / 50 |
| completion_chronology | 0.002937 | 0.003217 | 100 / 100 |
| cost | 0.002847 | 0.002770 | 100 / 100 |
| settlement | 0.048419 | 0.057575 | 100 / 100 |
| capture_completion | 0.055194 | 0.052886 | 50 / 50 |
| finance | 0.000463 | 0.000514 | 100 / 100 |
| journal | 0.000289 | 0.000281 | 50 / 50 |
| validate_completion | 0.023130 | 0.101817 | 50 / 50 |
| detached_commit | 0.006018 | 0.004568 | 2 / 2 |

Exclusive category sum: **24.990 / 11.951 s**;
unattributed dispatch/other work: **0.206 / 0.233 s**.
Total instrumented request: **25.197 / 12.184 s**.
The four capture/validation root regions are independently nonoverlapping;
summing these roots (without adding their descendants again) measures
**capture + proof 22.900 to 9.860 s (56.9%)**.
The recorded 3C instrumented root total was 27.072 s.
Protected construction/comparison still occurs 200 times, JSON 100 times, alias
100 times, manifest 200 times. JSON now traverses changed records only.

### Structural boundaries

| Fixture class | Full gates strict / shared | World clones strict / shared | Shared event commits |
| --- | --- | --- | --- |
| one-departure | 3 / 3 | 2 / 2 | 1 |
| one-completion | 3 / 3 | 2 / 2 | 1 |
| round-trip | 6 / 3 | 8 / 2 | 4 |
| dense-departure | 12 / 3 | 20 / 2 | 10 |
| dense-completion | 12 / 3 | 20 / 2 | 10 |
| mixed-ten | 42 / 3 | 80 / 2 | 40 |
| representative-ten | 83 / 5 | 162 / 6 | 40/1/40 |
| aged-ten | 42 / 3 | 80 / 2 | 40 |
| dense-25 | 102 / 4 | 200 / 4 | 64/36 |
| divine-next-departure | 3 / 3 | 2 / 2 | 1 |
| divine-short | 5 / 3 | 6 / 2 | 3 |

These counts are **unchanged from Stage 3C**. Dense-25 has four full gates,
four world clones and two detached commits (64/36 events), not 100 final-only
or unchecked transitions. Representative-ten still flushes at the real Booking
fence (40/1/40), rather than optimizing across it.

### Work/scaling diagnostics

| Fixture | Aircraft / Bookings / results / event history / journals at entry | Booking visits / manifest rows | Event records copied | Protected bytes emitted |
| --- | --- | ---: | ---: | ---: |
| one-departure | 1/21/0/7/2 | 42 / 14 | 12 | 2,779,634 |
| mixed-ten | 10/680/0/7/15 | 54400 / 2720 | 1718 | 203,059,204 |
| representative-ten | 10/1491/0/7/15 | 244960 / 6284 | 5820 | 638,867,932 |
| aged-ten | 10/680/0/1007/15 | 54400 / 2720 | 41690 | 223,199,410 |
| dense-25 | 25/1776/0/7/30 | 355200 / 7104 | 9100 | 886,445,732 |
| divine-next-departure | 1/21901/117/245/128 | 43802 / 72 | 848 | 68,713,210 |
| divine-short | 1/21901/117/245/128 | 131406 / 198 | 2546 | 206,191,070 |

Dense-25 still visits 355,200 source Booking rows for 7,104 relevant manifest
rows across 200 calls. It scans 2,450 prior-result rows and copies 9,100 pending/
history records. Aged-ten copies 41,690 event rows versus mixed-ten 1,718;
its optimized request is 3.935 versus 3.142 s. Divine-next has 117 genuinely
completed flights and 21,901 Booking rows: 43,802 source visits for 72 relevant
rows. No history is removed or fabricated. These fixtures vary several dimensions;
they are not independent controlled slopes for journals/results/manifests.
Collection/byte/visit counts establish the algorithmic relationships:

- Protected encoding and alias traversal remain **O(events × retained world size)**.
- Manifest lookup remains O(events × (bookings log bookings + relevant lineage work));
  sorting and scanning happen twice, without an index.
- Kernel witnesses remain O(events × pending/history size).
- Completion chronology is O(completions × retained results); measured only .003 s
  in dense-25, so a new index is not justified by this fixture.
- Selected manifest/journal proof scales with relevant manifest rows. No isolated
  manifest-size sweep or journal-only causal speed claim is made.

The next wall is still whole-state protected encoding (5.365 s) and alias traversal
(3.576 s), followed by final full gates (1.249 s). On Divine Air the retained
full validation/copy work dominates total isolated-event latency. No exploratory
50-aircraft run was necessary; formal 50-aircraft Ultra acceptance remains Stage 3F.

### Memory

Fresh dense-25 process peak working set: **79,785,984 to 82,808,832 bytes**
(**76.09 to 78.97 MiB**).
This is a process high-water mark including fixtures/candidates/validation, not
a traced per-witness allocation claim. The exact before witness is now bytes
rather than a 32-byte hash. Dense-25 largest encoded witness is 4,937,655 bytes;
Divine-next 34,356,605 bytes. Before/after buffers overlap temporarily. Witness
and alias-set memory is O(retained world size), bounded to one transition, with
no accumulation across events/batches/requests. Emitted dense-25 bytes are
930,165,900 before versus 886,445,732 after; CPU improvements are mainly cheaper
encoding and eliminated redundant scans, **not** removal of retained authority.

### Payment regression controls

All six original payment fixtures rerun (one latency sample per path, setup and
instrumentation excluded). Payment code/proof is unchanged; these are regression
observations, not a claimed Payment optimization. Strict/shared output hashes
match in every case.

| Fixture | Strict / shared s | Payments / events | Shared full gates / clones |
| --- | ---: | ---: | ---: |
| one | 0.113 / 0.111 | 1 / 1 | 3 / 2 |
| sequential-eight | 0.481 / 0.184 | 8 / 8 | 3 / 2 |
| dense-64 | 4.311 / 1.156 | 64 / 64 | 3 / 2 |
| expiry-two | 0.610 / 0.523 | 2 / 4 | 5 / 6 |
| aged-eight | 1.068 / 0.407 | 8 / 8 | 3 / 2 |
| same-contract-three | 10.314 / 10.277 | 3 / 66 | 68 / 132 |

## Complete-world witnesses

Only dictionary insertion order is normalized; no envelope field is omitted.
Strict / pre-change shared / optimized shared hashes match on every fixture.

| Fixture | SHA-256 |
| --- | --- |
| aged-ten | `9fa843144124d850242b4b58306fe61623ef2666eeb654893531500169a9cded` |
| dense-25 | `81b58ab5340fb59790468e855031e1752d79909a35ce8bb3edd648b9fd23de0c` |
| dense-completion | `0b0717295a901727e6c2020f88e1626de4d0a025e9acbb5656bb90258d5f03c1` |
| dense-departure | `eda36ae619c8f7b004f6cf4ed788da7c4bb560be60000dc2d37a56d04dfcc233` |
| divine-next-departure | `85aff62c20cf92053921eef2e940228e845f2eaa6631d36a4259e5c2073f5d51` |
| divine-short | `c9578420b04edb4b63e98274eb92d26fd53e1899905ec4a9e0896b1e0ad0da37` |
| mixed-ten | `393ddb47218f2427162c0b1a464f463ed75f744c22451823093de5f979d2f726` |
| one-completion | `b2346d27f4cb0c75b68c544fe9e553de140e747f32b9ac3abb4ea80640a1d1b8` |
| one-departure | `5e42898747dea9a5c07d2e34270224dadc854d9579ba8b0bf36b308988364c87` |
| representative-ten | `8eb47f6302cf6bb497c54372e3d504598481693eb5aabd5e70bb4f2687912c43` |
| round-trip | `a74008b1f14e316f320c269a8d0303518780b527c988c4e5fccc56aa657c8a49` |

## Verification and recommendation

Focused Stage 3A/B/C/D: **126 tests PASS in 487.609 s**. This includes 19 new
regressions for exact typed bytes, immutable-string sharing, cycles, custom reducer
rejection, finite floats, canonical alias equivalence, protected/root/table type
corruption, changed-only JSON, equal-valued aliases within/crossing protected
authority, immediate proof/serialization failure recovery, no later repair and
exact paused in-flight save restoration. Existing mixed handlers, fences, batch
1/2/8/64, irregular partitions, multiple seeds/dictionary order, generated completions,
final-gate/strict replay disagreement, shadow divergence and Stage 2 tests are retained.

Full repository command `python -B -m unittest discover -s tests`: **881 PASS,
1327.709 s** (862 baseline + 19 new). This includes the complete Stage 1 oracle,
Stage 2 ownership/invalidation, Booking/manifest, finance/journal, aircraft/
maintenance, simulation/kernel, persistence/save-load and runtime/Advance gates.
No expected authoritative gameplay witness/result was changed.

Native `python -B -m tests.smoke_runtime_startup`: **PASS**, fresh GUI process
without New Game → Load directly → Resume/Advance → two Booking checkpoints /
14 bookings → exact validated paused save/reload. SDL2/GLEW Kivy 2.3.1 on Windows,
2560×1377 window. This confirms the unchanged strict production path; automated
smoke does not prove human-level Windows responsiveness of opt-in shared work.

Scoped `python -m compileall -q app game tests main.py make_snapshot.py settings.py
test.py`, local documentation-link checks and `git diff --check`: **PASS**.
Full diff review corrected shallow-view type-erasure risk with explicit guards
and restored UTF-8 documentation exactly before adding scoped updates. No
unrelated authority/source changes. Schema remains 7. No new handlers certified.
Normal Kivy/session/Advance pacing remains unchanged.

Recommend another bounded proof-cost/ownership investigation **before production
Stage 3E activation**. The throughput improvement is useful, but remaining multi-
second steps and isolated-event regression do not establish responsive continuous
pacing. Potential exact candidate-local write/ownership capabilities need their
own correctness argument; no unchecked identity/revision cache is proposed as
permission to implement. Stage 3E/3F remain unimplemented. Stop after Revised 3D.
