# Production Cooperative Runtime — Stage 3E

Approved bounded integration, 2026-10-04. Initial local HEAD, upstream and live
origin/master matched `94c53db7b86b04eea117ad696819909cf2515534`.
Authority remains [Stage 1 State Schema](Stage%201%20State%20Schema.md#clock-and-event-contract)
and [Continuous Runtime](Continuous%20Runtime%20Technical%20Specification.md).
Schema remains **7**; no persistent fields, migrations or gameplay changes.
Only existing Payment/Departure/Completion certification is activated. NO_OP
retains its prior fully gated infrastructure path. No additional certification,
threading, multiprocessing, offline progress, map/replay or Stage 3F is introduced.

## Previous production path

Active suspension-safe monotonic elapsed → old-rate integer nanosecond credit
→ finite whole-second target → strict `begin_resolution` → one isolated event
per pump → session progression/Stage 2 epoch notification → existing autosave
threshold → in-place header/clock and throttled management projection refresh.
Processing uptime also earned credit. Paused callbacks did no work. Confirmed
120-rate-normalized-real-second backlog over a 30-active-second grace stopped
processing entirely, retaining debt with no catch-up. Explicit GUI Advance could
chain up to 64 isolated events under a 15-ms between-events time check.

## New production path and routing

The same elapsed/credit/finite-target calculation enters the already-certified
shared resolver. **One `step()` per ordinary or explicit GUI callback**, candidate
cap **8 events**. A certified prefix receives its exact per-event proofs and full
final validation/detached publication, then control returns. Fences/strict/custom/
stale/unsupported events execute using existing strict transactions on separate
steps. No private candidate, ownership capsule, Booking lookup or proof memo
survives that return. The request retains only committed-source heap, finite
target, IDs and cumulative safety counters. No lookahead/history scan is added.

Routing always enters the shared facade, which already performs exact identity/
input/fence dispatch. Isolated production controls are near parity; an extra
one-versus-two routing policy has no clear measured benefit. The strict facade
remains available for public compatibility/oracles/debug. Shared disable latches
are controller-owned and reused by continuous and explicit requests; custom
handlers never acquire certification from a name or copied metadata.

### Work-budget evidence

Two repeats on the SAME frozen inputs, production `Stage1Session.pump` with
zero-cost fake monotonic time, finite earned target and separate strict/shared
routes. Construction/input cloning/hashing/post-validation are excluded. No GUI
rendering is included. Seconds are medians; max callback below is one repeat.

| Work | Route / cap | Total | Max callback | Callbacks |
| --- | --- | ---: | ---: | ---: |
| one Departure | strict /1 | .450 | .32 | 2 |
| one Departure | shared /8 | .38 | .27 | 2 |
| one Completion | strict /1 | .38 | .26 | 2 |
| one Completion | shared /8 | .40 | .28 | 2 |
| dense-25 /100 events | strict /1 | 54.92 | .88 | 101 |
| dense-25 /100 events | shared /1 | 55.24 | .71 | 101 |
| dense-25 /100 events | shared /8 | 10.63 | 1.04 | 14 |
| dense-25 /100 events | shared /64 | 4.91 | 2.65 | 3 |
| Divine-next | strict /1 | 9.58 | 6.78 | 2 |
| Divine-next | shared /8 | 10.04 | 6.91 | 2 |

Eight retains a substantial dense throughput gain with shorter returns than 64,
without speculative persistence or speculative wall-time interruption. This is a
count bound, not a promise of millisecond latency. Full input/final validation,
cloning, history proof and a single strict/fence event remain indivisible. There
is no CPU-specific millisecond admission threshold or weakened validator.

## Pacing accounting and state machine

`credit_ns += active_elapsed_ns * selected_literal_ratio` while RUNNING.
Each committed UTC increment subtracts exactly those whole simulation seconds.
Event count alone consumes no credit; equal-time events still must resolve.
Fractional credit is retained across pauses/speed changes in the open controller.
Request target never moves; additional earnings remain credit for later requests.
`earned_target_utc = committed UTC + floor(credit_ns / 1e9)` describes the whole
currently earned horizon, not display-clock authority. Pending target/backlog
and controller state are runtime-only, never new save fields.

| State | Accrues | Processes | Completion / player action |
| --- | --- | --- | --- |
| RUNNING | Yes | One safe unit/pump | Continue while healthy |
| PLAYER_DRAIN | No | Existing finite work and remaining earned credit | Fully paused when target drained |
| OVERLOAD_DRAIN | No | Same exact owed finite horizon | RECOVERED, no automatic Resume |
| RECOVERED | No | No | Explicit Resume required |
| PAUSED | No | No | Explicit Resume starts accrual |
| ERROR | No | No | Stable diagnostic; explicit retry only |
| CLOSED | No | No | Old callbacks cannot process replacement world |

During draining the canonical clock mode remains NORMAL until the earned request
is resolved: changing it halfway through a retained request would falsely look
like an event-requested stop. Accrual uses runtime state, so it stops immediately.
The GUI accurately labels this as pausing/catching up, not ordinary running.
Fully drained completion changes canonical mode to PAUSED. Management edit
callbacks reject until the pause barrier completes; read navigation remains safe.

### Overload rule and recovery

The existing centralized policy is retained: credit must exceed
`120 * current literal ratio` simulation seconds throughout a **30-active-second**
grace. This normalizes backlog by requested player rate and was the repository's
existing allowance, not a constant chosen from this CPU's measurements. A single
expensive callback is insufficient. Processing continues during the grace.
Whenever a unit services credit back below the threshold, grace resets immediately,
even if no next callback occurs before another independently earned burst.

Confirmed overload freezes new accrual, preserves the whole finite earned horizon
and drains it cooperatively. Target is unchanged as committed time consumes credit.
Processing time/idle time during drain earns none. Completion remains PAUSED with
`Overload recovered`, retaining subsecond credit in memory. Only explicit Resume
restarts earning. Speed changes/Resume during drain reject clearly. Speed ratios
remain **30/210/900/1800** (relative **1/7/30/60**). No speed reduction hides lag.

### Manual pause and hard pause

Player Pause samples elapsed time immediately, stops new accrual and drains owed
whole seconds plus due work in the retained request. It preserves request-wide
limits. This is the approved change from old suspended ordinary pause.
Hard pause stops immediately at the last committed event boundary, closes the
request and preserves in-memory credit. Error/debug/shutdown/replacement use it.
Explicit Advance retains its existing approved target-replacement policy: hard
pause, replace pacing debt with the explicit request, finish paused. Next Event
remains exactly one strict event. No pacing credit determines explicit outcomes.
A raw unexpected exception samples processing uptime before freezing, consumes any
valid committed prefix and surfaces an error rather than retrying every tick.

## Persistence, exit and derived reads

Manual save/bookmark invokes a shared session pause barrier. If debt is draining,
the API returns `RUNTIME_DRAINING` for a later retry. Kivy queues one transient
action and calls the SAME existing save method when fully paused. No GUI-specific
writer, schema migration or asynchronous world owner exists. Deferred actions are
cleared on runtime failure/shutdown; a failed drain cannot silently save/exit.

Autosave retains the first-of-15-active-minutes/seven-game-days policy and snapshots
only committed authority after a unit; thresholds reset after one save or throttled
storage failure. Internal logical events do not individually invoke autosave or
GUI refresh. Explicit Advance still coalesces its crossed simulation thresholds.

Loading uses detached validated SaveStore candidates and opens PAUSED at exact
saved UTC with zero debt, Normal selected, no elapsed/offline time. A successful
replacement releases old requests; failed load never exposes a partial candidate.
GUI Load/title/exit first drains active owed work, then applies the existing explicit
Save/discard/cancel unsaved guard. Forced shutdown closes at committed authority;
runtime-only debt is not saved/restored under the existing no-offline contract.

Each safe unit notifies progression/Stage 2 once, including clock-only commits and
failure prefixes. Private candidates never invalidate/publish speculative pages.
Committed root/epoch witnesses still reject old pages; Fleet/Flights/Finance lazily
rebuild after commit. Kivy keeps existing .75-second throttled view refresh and
in-place status. It shows resolved UTC separately from labelled earned target/debt.

## Errors, divergence and fences

The existing resolver discards invalid private candidates and strictly replays the
successful prefix. Deterministic failure keeps the failing event pending, freezes
accrual and enters stable ERROR. No automatic retry loop. OPTIMIZER_DIVERGENCE
retains its strict recovered prefix, disables shared execution for this controller,
pauses visibly and requires explicit continuation. Replay never gets lookup state.
Shadow remains fully available as diagnostic strict per-event reference verification.

Booking, weekly publication and contract expiry retain FENCE behavior: shared
prefix flush → strict event → later new candidate. Market rotation/custom/replacement/
unsupported inputs remain strict. No lookup or proof memo crosses those boundaries.

## Tooling and verification

`tests/profile_cooperative_runtime.py` measures actual session pumps, finite-target
routing controls or all speed tiers with real measured processing costs and ideal
200-ms idle intervals. Controlled intervals are short capacity probes, not sustained
Stage 3F certification. Native callback timing is measured separately by
`tests/smoke_cooperative_runtime.py` in a fresh child GUI with TEMP saves.
All tests use injected monotonic clocks/TEMP persistence, not CPU-sensitive gates.
The capacity clock includes measured synchronous pump cost plus ideal 200-ms idle
intervals, beginning one second before the same first event. The quiet gap is
resolved by the strict kernel outside timing; no historical outcomes are fabricated.
The probes exclude GUI rendering and storage I/O. Inputs are frozen validated TEMP
worlds, not production save edits. Each probe hard-pauses at its final committed
boundary; requested time equals resolved time plus exact retained credit, including
fractional credit. No tail is discarded to make the resolved rate look better.

### Production service capacity

One sample per fixture/speed, nominal 20 active seconds; a non-preemptible final
unit can overshoot. Requested/resolved/backlog are simulation seconds. Median/p95/max
are whole pump callback seconds, including session epoch notification. Physical
commit counts below do not include pure clock boundaries. All 20 worlds validate.
P95 is omitted for fewer than 20 calls (all Divine samples have five).
No probe entered overload or failed. These short probes cannot establish the
30-second production grace behavior; deterministic tests cover that state machine.


| Fixture | Speed | Active / processing s | Requested | Resolved | Backlog | Events | Calls | Median / p95 / max callback s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| starter | Normal Speed | 20.06 / 10.02 | 601.7 | 595 | 6.7 | 1 | 51 | 0.196 / 0.204 / 0.274 |
| starter | Fast | 20.37 / 10.17 | 4278.4 | 4237 | 41.4 | 1 | 52 | 0.194 / 0.204 / 0.311 |
| starter | Very Fast | 20.18 / 9.97 | 18157.5 | 17981 | 176.5 | 4 | 52 | 0.195 / 0.223 / 0.247 |
| starter | Ultra | 20.19 / 9.99 | 36347.4 | 35995 | 352.4 | 4 | 52 | 0.197 / 0.226 / 0.237 |
| 10 aircraft | Normal Speed | 20.23 / 13.79 | 606.8 | 593 | 13.8 | 4 | 33 | 0.431 / 0.535 / 0.542 |
| 10 aircraft | Fast | 20.40 / 13.99 | 4283.5 | 4187 | 96.5 | 10 | 33 | 0.455 / 0.570 / 0.600 |
| 10 aircraft | Very Fast | 20.54 / 14.54 | 18482.6 | 18021 | 461.6 | 40 | 31 | 0.505 / 0.715 / 0.787 |
| 10 aircraft | Ultra | 20.15 / 14.55 | 36273.2 | 35377 | 896.2 | 40 | 29 | 0.509 / 0.727 / 0.912 |
| aged 10 | Normal Speed | 20.04 / 13.41 | 601.3 | 589 | 12.3 | 10 | 34 | 0.385 / 0.400 / 0.846 |
| aged 10 | Fast | 20.59 / 13.98 | 4323.1 | 4241 | 82.1 | 10 | 34 | 0.394 / 0.479 / 0.827 |
| aged 10 | Very Fast | 20.33 / 14.13 | 18295.4 | 17911 | 384.4 | 40 | 32 | 0.414 / 0.881 / 0.948 |
| aged 10 | Ultra | 20.03 / 14.03 | 36051.0 | 35290 | 761.0 | 40 | 31 | 0.422 / 0.875 / 0.967 |
| 25 aircraft | Normal Speed | 20.74 / 15.50 | 622.1 | 605 | 17.1 | 25 | 27 | 0.581 / 0.612 / 0.830 |
| 25 aircraft | Fast | 20.75 / 15.55 | 4357.7 | 4235 | 122.7 | 25 | 27 | 0.578 / 0.603 / 0.865 |
| 25 aircraft | Very Fast | 20.25 / 15.45 | 18226.2 | 14437 | 3789.2 | 100 | 25 | 0.601 / 0.933 / 1.064 |
| 25 aircraft | Ultra | 20.42 / 15.82 | 36749.0 | 35555 | 1194.0 | 100 | 24 | 0.685 / 0.853 / 1.011 |
| Divine Air | Normal Speed | 23.80 / 22.97 | 714.1 | 577 | 137.1 | 1 | 5 | 4.854 / — / 6.202 |
| Divine Air | Fast | 23.55 / 22.74 | 4944.6 | 3963 | 981.6 | 1 | 5 | 4.690 / — / 6.260 |
| Divine Air | Very Fast | 24.42 / 23.62 | 21980.5 | 15901 | 6079.5 | 4 | 5 | 6.255 / — / 6.341 |
| Divine Air | Ultra | 24.61 / 23.81 | 44297.7 | 31801 | 12496.7 | 9 | 5 | 6.210 / — / 6.617 |

The end-of-probe backlog is not lost time. At the unchanged literal rate, the
starter owes about .20 seconds of active uptime, representative ten about
.44–.51 seconds, aged ten .39–.43 seconds, and dense-25 .57/.58/4.21/.66 seconds
(Normal/Fast/Very Fast/Ultra). Dense Very Fast finishes with a larger retained
finite-target tail; Ultra being smaller is a partition/work-window effect, not
proof that the faster tier is universally more sustainable. Divine Air owes
4.57/4.67/6.76/6.94 active-equivalent seconds, with only five callbacks observed.

| Fixture | Normal 30× | Fast 210× | Very Fast 900× | Ultra 1800× |
| --- | --- | --- | --- | --- |
| Starter | Kept up in short probe | Kept up in short probe | Kept up in short probe | Kept up in short probe |
| 10 aircraft | Bounded short tail | Bounded short tail | Bounded short tail | Bounded short tail |
| Aged 10 | Bounded short tail | Bounded short tail | Bounded short tail | Bounded short tail |
| 25 aircraft | Bounded short tail | Bounded short tail | Significant unfinished target tail | Bounded short tail after dense work |
| Divine Air | Multi-second stalls/tail | Multi-second stalls/tail | Multi-second stalls/larger tail | Multi-second stalls/larger tail |

**Sustained capacity is not certified for any fixture/tier by a 20-second probe.**
The first four fixtures service their measured bursts; Divine's clock-only pumps
still take about 4.6–5 seconds. Its service/display lag is material even at Normal.
A callback cap cannot subdivide one complete-world validation or one strict fence.
Maximum measured service callback is **6.617 s** (Divine Ultra). The finite routing
control observed **7.82 s** at cap 64 in one Divine repeat. Neither is smooth UI.

### Routing/commit counts and remaining costs

Starter Normal/Fast use one shared batch, one detached commit and 49/50 clock
boundaries; Very Fast/Ultra use four batches/commits and 47 clock boundaries.
Representative ten uses 4/8/9/9 shared batches and 28/24/21/19 clock boundaries.
Aged ten uses 2/2/8/8 batches and 31/31/22/22 clock boundaries. Dense-25 uses
4/4/16/15 batches and 22/22/8/8 clock boundaries. Divine uses 1/1/3/3 batches and
3/3/1/1 clock boundaries. These windows contain no strict event; mixed/fence tests
exercise the production strict routes independently. Existing shared infrastructure
retains entry validation, one owned clone per candidate and final complete-world
validation/detached commit, rather than reintroducing per-flight world copies.

No new history index, cache or retained candidate is added. Candidate memory is
bounded by the existing one-private-world/cap-eight proof lifetime; the request's
heap and accumulated IDs remain bounded by existing request safety limits. This
slice does not claim a new isolated peak-memory measurement: Stage 3D.3's earlier
82.45 MiB dense /372.94 MiB Divine peaks are historical evidence, not new results.

Retained-history whole-world entry/final validation, cloning/detached commit,
clock-only full validation, strict Booking/publication/expiry work and occasional
strict recovery remain the next scaling wall. Stage 3D.3 already profiled Divine's
validation/cloning dominance; this slice leaves those proofs unchanged. UI reads
and autosave I/O can add cost beyond the domain capacity table. A cap of eight
improves dense amortization but cannot guarantee an atomic latency ceiling.

### Native Windows Kivy smoke

`python -B -m tests.smoke_cooperative_runtime`: **PASS**. A genuinely fresh child
process opens Load Game directly with New Game forbidden, loads a valid TEMP
career, runs Normal/Fast/Very Fast/Ultra, requests Pause, drains, saves and reloads
exactly paused. A separately labelled controlled 20-NO_OP/300-game-second backlog
uses reduced diagnostic overload/grace settings, drains in separate safe units,
remains RECOVERED until explicit Resume, validates and saves/reloads exactly.
No production overload threshold is changed by the smoke.

Native callback sample: **65 callbacks**, median **.194 s**, p95 **.225 s**, maximum
**1.064 s**, final saved UTC `2026-09-07T02:36:00Z`. Python 3.12.10/Kivy 2.3.1,
SDL2/OpenGL on Windows. Programmatic controls were serviced between units; human
mouse/scroll smoothness and large-fleet responsiveness are not established.

### Regression coverage and gate

New tests cover all literal ratios; exact credit/fractions; finite targets and
request limits; budgets 1/2/8/64; elapsed partitions; mixed Payment/Departure/
Completion plus Booking/Expiry/rotation; temporary backlog, persistent overload,
grace reset, player/hard pause, no drain accrual or auto-resume; strict custom
handlers; stable event failure; strict-prefix divergence/latch; private lookup
release; Stage 2 committed-only reads; explicit Advance; save/bookmark/autosave;
paused zero-debt reload; deferred save/exit and session-replacement revocation.
The full Stage 1 oracle and prior Stage 2/3 certification suites remain required.

**NOT READY FOR STAGE 3F** as a responsiveness/capacity acceptance gate. The
integration is bounded and correct, but Divine's 6–7-second units and dense-ten/
25 callback costs show that whole-world/clock-only validation must be investigated
before claiming responsive 50-aircraft Ultra. A separately approved next task
should profile those remaining committed-boundary costs without weakening proofs.
No Stage 3F implementation or new 50-aircraft certification is included here.

### Reproduction commands

Create/reuse validated frozen fixtures outside the repository with the existing
`tests.profile_flight_certification` tool (`--fixtures <TEMP-dir> --case <name>
--mode both --repeats 1`). Its `--observed-fixture` option accepts an explicitly
provided validated observed world for Divine controls. Do not commit those files.
Then use the SAME frozen directory for these measurements:

```text
python -B -m tests.profile_cooperative_runtime --fixtures <TEMP-dir> --cases one-departure,one-completion,dense-25,divine-next-departure --batches 1,8,64 --mode both --repeats 2
python -B -m tests.profile_cooperative_runtime --fixtures <TEMP-dir> --cases one-departure,representative-ten,aged-ten,dense-25,divine-short --batches 8 --mode shared --service-seconds 20
python -B -m tests.smoke_cooperative_runtime
python -B -m unittest tests.test_cooperative_runtime tests.test_gui_cooperative_runtime -q
python -B -m unittest discover -s tests
python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py
```

Finite controls compare complete-world hashes across strict/shared routes and
budgets. Different-speed capacity endpoints intentionally differ because actual
measured CPU uptime earns different targets; those endpoints are validated, not
claimed equal. CPU measurements are diagnostic evidence, never test assertions.

### Final verification and self-review

- New focused runtime/GUI suite: **32 passed in 129.299 s**.
- Broader affected runtime/resolver/shared/advancement/GUI suite: **114 passed in
  250.199 s**; the final new run also covers later scoped action/status guards.
- Full `python -B -m unittest discover -s tests`: **970 passed in 1435.903 s**
  (previous total 938). All prior Stage 1 complete-world oracle, Stage 2 ownership,
  Stage 3A–D.3 certification/corruption/alias/serialization/replay, Booking/manifest,
  finance/journal, aircraft/maintenance, runtime/Advance and save/load tests pass.
- Scoped application compilation: passed. No production or regression-test source changed during
  the full run. Diagnostic benchmark argument/hash assertions were verified by
  subsequent finite control runs; no authority/proof code was changed for them.
- Scoped documentation local-link checks and `git diff --check`: passed.

Complete diff review confirms: no dropped events/credit, unresolved target display
substitution, private state across returns/fences/saves, Stage 2 speculative reads,
new drain earnings, automatic recovery Resume, retry storm, stale deferred action,
threading, schema/gameplay/speed change, new certification or Stage 3F activation.
Explicit Advance's documented existing target replacement remains independent of
pacing debt. A rare strict recovery may replay the bounded attempted prefix in one
unit; it is exact but is not promised to be cheap/preemptible. Unavoidable atomic
stalls and short-probe capacity limitations remain disclosed rather than hidden.

### Final controller repeat on the same finite inputs

Two post-integration samples per fixture, shared cap eight, zero-cost fake pacing
clock and identical finite targets. All complete-world hashes match EVERY pre-change
strict/shared/budget control. Small control repeats also match strict versus shared
at caps 1/2/8/64. Timing variation includes normal host noise; no additional proof
optimization is attributed to this integration.

| Fixture | Pre-change production strict /1 s | Pre-change shared /8 s | Final shared /8 s | Final maximum callback s |
| --- | ---: | ---: | ---: | ---: |
| one-departure | 0.447 | 0.381 | 0.341 | 0.250 |
| one-completion | 0.382 | 0.399 | 0.337 | 0.241 |
| dense-25 | 54.922 | 10.626 | 9.192 | 0.956 |
| divine-next-departure | 9.583 | 10.036 | 8.657 | 6.579 |

Dense final cap-eight execution uses **13 candidates/commits, 14 callbacks** for
100 events, versus 100 strict event transactions/101 callbacks. Divine-next still
uses one event candidate plus one final target boundary, not a magically cheaper
partial validator. Candidate proofs/entry/final validation and detached publication
remain the existing infrastructure; this slice changes production routing/returns.
