# PH 1.0 Runtime Capacity Certification - Stage 3F

Certification baseline **ebdfc1239cb88f2ccd12a481033f1ba236588b04** matched
local HEAD, upstream and live origin/master before measurement. Evidence is on
Windows/Python 3.12.10, Kivy 2.3.1/SDL2/Intel UHD 630, Intel Core i5-10400
@2.90 GHz, 12 logical processors. Timings are host-specific; no worker parallelism.
No production source changes. Schema remains 7; no gameplay/formula/RNG change.

## Approved gate and report interpretation

50 active aircraft must sustain literal **Ultra 1800x**: one game day per
48 real seconds. Bounded temporary backlog is permitted; persistent growth,
repeated overload, dropped credit, false UTC or correctness failure is not.
100 aircraft is optional headroom, not a PH requirement. This supersedes the
historical literal-7x capacity gate for this final named-speed certification.
Throughput and callback responsiveness are reported separately.

**PH 1.0 RUNTIME NOT CERTIFIED.** The representative 50-aircraft day takes
375.151 engine seconds through the existing explicit facade (230.307x unpaced),
against Ultra's 48-second budget. Live debt persistently grows and enters overload.
The project's required capacity gate fails. No speed/threshold/cap changes.
A failed certification completes this measurement task, not the scalability
project. No Stage 3G or further optimization is authorized or implemented here.

## Production harness audit

`tests/certify_runtime_capacity.py` uses **Stage1Session.pump -> RuntimeController
-> existing resolver -> shared/strict/fence -> detached commit -> Stage 2 epoch
notification -> existing autosave**. No dispatch substitution, custom handlers,
validation bypass or gameplay shortcut. Existing cap8 and literal ratios remain.
The instrumentation wraps functions to count/time them; it does not replace
handlers or certification identity. Complete-world validation stays active.

Modes are deliberately separate:

- **Finite throughput:** preload exactly one requested day's finite game credit;
  fake real clock does not advance. Each callback still calls production pump
  once. This amortizes future work optimistically. It is a NECESSARY throughput
  bound, never sufficient proof of continuous pacing. Default cumulative request
  limits stay active; a blocked request is NOT silently retried/partitioned.
- **Live:** controlled idle adds the unoccupied part of the actual .2-second
  callback interval; measured engine duration advances the injected clock during
  each pump. Full session work/autosave is included. There is no real idle sleep,
  but each callback/validation still executes; idle calls are not skipped. Setup,
  output formatting, hashing and telemetry cannot earn credit. Production alone
  samples/earns/consumes credit and chooses overload/drain/error states.
- **Explicit Advance:** real session begin_advance_to/advance_tick, including its
  existing cumulative generation allowance. No realtime pacing requirement.

Ledger instrumentation independently records actual _sample credit additions.
Resolved whole seconds + ending exact nanosecond credit must equal initial
credit + all additions; no debt is discarded. UTC/target/credit and units are
recorded for every callback. Budget stops retain the debt and are explicitly
censored; hard pause closes a private request at a committed boundary. They are
not successful drains or sustainable-operation claims. Final speed is explicitly
selected Normal for complete-world comparisons; no fields are excluded.

A finite live horizon caps pacing input at its exact endpoint (ceiling integer
nanoseconds). Once reached, the player pause path freezes earnings and drains.
Long uncapped-within-budget probes retain the full overload state machine.
Engine wall seconds, simulated real pacing seconds, earned game seconds and
resolved game seconds are separate fields. Capacity rates never use setup time.

## Fixture construction and authority

Fixture caches and every save belong in TEMP. All sizes use current PH scenario,
configured A320neo aircraft, extra **test-only funding** for public purchases,
MNL base and two daily public-planned round trips (four sectors per aircraft).
Outbound local starts are 09:00 and 15:00, staggered by two minutes per aircraft.
DVO/CEB/ILO/BCD/PPS are selected cyclically. Each leg's timing/return/fare comes
from current WeeklyDraft/domain timing and authoritative suggested-fare boundary.
No arbitrary shortened duration, idle fleet, new economy or flight formula.

Public schedule-definition creation plus rolling publication creates seven-day
patterns, current week plus four future weeks. Natural preparation uses the
actual explicit resolver through **2026-09-02T03:00:00Z**. It crosses the first
daily Booking checkpoint and actual flight operations; no synthetic NO_OP history,
fake completed records, disabled history or manufactured journal is used.
An initial preparation ending before the first checkpoint was rejected by fixture
audit (zero Bookings) and aged before certification. No measurements used that
empty-Booking input. Preparation is entirely outside timed work.

The resulting fleet is at mixed operating phases, with real Bookings/itineraries,
financial journals, completed results and pending completion/departure events.
All fixture worlds pass the full validator and have complete source hashes.
Acquisitions are owned purchases (starter grant for first aircraft), so no lease
payment/expiry obligations are fabricated. Flight revenues/expenses/maintenance
and Booking-sale journals remain naturally due. Contract fences are not claimed
exercised if none is due. Market rotation remains queued; rolling weekly events
remain enabled. Longer horizons stop when the shorter gate conclusively fails.

## Reproduction

```powershell
python -B -m tests.certify_runtime_capacity --fixtures $env:TEMP/at-stage3f-fixtures --build
python -B -m tests.certify_runtime_capacity --fixtures $env:TEMP/at-stage3f-fixtures --mode finite --budget 600 --save-check
python -B -m tests.certify_runtime_capacity --fixtures $env:TEMP/at-stage3f-fixtures --mode live --pacing-seconds 60 --speeds "Normal Speed,Fast,Very Fast,Ultra" --budget 120
python -B -m tests.certify_runtime_capacity --fixtures $env:TEMP/at-stage3f-fixtures --fleets 50 --mode advance --days 1 --budget 600 --save-check
python -B -m tests.certify_runtime_capacity --fixtures $env:TEMP/at-stage3f-fixtures --fleets 50 --mode advance --days 1 --budget 600 --instrument
python -B -m tests.certify_runtime_capacity --fixtures $env:TEMP/at-stage3f-fixtures --fleets 50 --mode live --days 7 --budget 220
python -B -m tests.certify_runtime_capacity --fixtures $env:TEMP/at-stage3f-fixtures --fleets 1 --mode finite --days 7 --budget 120 --save-check
python -B -m tests.certify_runtime_capacity --fixtures $env:TEMP/at-stage3f-fixtures --fleets 50 --equivalence --seconds 60 --budget 120
python -B -m tests.smoke_atomic_boundaries --booking-fence
python -B -m tests.smoke_atomic_boundaries --fixture $env:TEMP/at-stage3f-fixtures/fleet-50.json --ultra-seconds 15
```

JSONL records include full callback/credit vectors, strict/fence intervals,
physical commit counts, session notifications, working/peak memory, authority
sizes/hashes and persistence checks. Exclusive profiles are separate diagnostics;
nested cumulative timings are not summed with their children. Any programmatic
native smoke is not a claim of observed human smoothness.

An initial diagnostic wrapped identity-bound certificate entry functions and
therefore accidentally forced strict routing. That run was discarded, not used
as performance evidence. Final instrumentation wraps internal capture/equation/
event-topology dependencies, not certificate entry callables. A regression compares
quiet/profiled routing counts and complete hashes. Attribution is frozen before
post-run validation and persistence verification; those costs cannot inflate the
measured service profile. Unhooked proof/bookkeeping is explicitly residual.

## Fixture audit

All start at **2026-09-02T03:00:00Z** (11:00 PH local). The same four daily
sectors per aircraft are retained at each size. The 1-aircraft sample operates
MNL-DVO/MNL-CEB; larger samples cover all five destinations bidirectionally.

| Aircraft | Sectors/departures/completions per next 24h (each) | Dated flights | Bookings = itineraries | Pending events | History | Results | Journals | Definitions | In-flight |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 4 | 136 | 900 | 134 | 11 | 5 | 6 | 4 | 0 |
| 10 | 40 | 1360 | 5790 | 1313 | 108 | 50 | 60 | 40 | 7 |
| 25 | 100 | 3400 | 7469 | 3281 | 256 | 122 | 147 | 100 | 11 |
| 50 | 200 | 6800 | 7819 | 6580 | 482 | 223 | 273 | 200 | 35 |

50-aircraft detail: 223 COMPLETED, 35 OPERATIONALLY_LOCKED, 6542 PLANNED;
pending 6542 Departures, 35 Completions, one Booking checkpoint, one weekly
publication and one market rotation. Every definition uses ROLLING_FOUR_WEEKS_V1.
No active aircraft contracts; owned fleet cash/journals and routine expenses are
still real authority. No lease anniversary/expiry is due in this fixture.

Next Booking **2026-09-03T00:00:00Z**; weekly publication **2026-09-06T16:00:00Z**;
market rotation **2026-10-01T00:00:00Z**. The 50-aircraft source SHA256 is
`6ad6c18d2ee383a26938a856195c69c59f6c5c2517e614481e4a734c62a6b52d`.
The other hashes and audits are emitted by --build, using the same deterministic
public scenario and warmup. Setup/warmup costs are excluded, including the
312.589-second 50-aircraft natural-history preparation.

## Day-1 escalation and explicit Advance

| Aircraft | Finite paced-pump engine seconds | Resolved game seconds | Events | Result |
| ---: | ---: | ---: | ---: | --- |
| 1 | 1.446 | 86400 | 9 | Complete; optimistic bound, not live certification |
| 10 | 24.228 | 86400 | 81 | Complete; optimistic bound, not live certification |
| 25 | 102.715 | 86220 | 198 | ERROR: cumulative generated-event limit reached |
| 50 | 168.739 | 21420 | 197 | ERROR: cumulative generated-event limit reached |

The finite ordinary controller retains its approved **100 generated events per
request**. A large preloaded target stops after that limit; no silent retries,
limit increase or callback repartitioning is used. 50 stops at Sep2 08:57 UTC with
64,980 owed seconds, before the next Booking fence. This independently exposes a
large-catch-up safety stop; it is not save corruption or evidence that events
were lost. Even treating the whole day as resolved at that point would give an
optimistic upper bound of only 512.03x, below 1800x.

The existing **explicit Advance** facade already allows 10,000 generations.
Its full 50-aircraft day succeeds without changing that policy:

- **375.151 s**, **86400 seconds resolved**, **230.307x** unpaced throughput;
  target/end **2026-09-03T03:00:00Z**, 401 events (200 Departures, 200 Completions,
  one Booking checkpoint), 51 shared units + one strict fence, 52 physical commits.
- This is **7.816x** the Ultra daily processing budget; only **12.795%** of required
  service capacity. It is not claimed as a long-run sustainable rate: a fully
  available target amortizes work more favorably than continuous small targets,
  and future retained history can add cost.
- Booking fence **16.362 s**, enclosing callback **16.382 s**. Thus about
  **358.8 s** remains outside that fence; blaming only daily Booking is incorrect.
- Full-world validation and exact manual save/paused reload/zero debt/resume/
  second exact save/reload and autosave eligibility checks PASS after measurement.
- Complete result hash:
  `dadcf6f513b68409b453c9629633fe603763c2ba84af5de46bd3ed3219dd8fc0`.

**50-aircraft Day3/Day7 and 7-/30-day explicit Advance are NOT RUN.** Day1 already
fails conclusively; extending the expensive fixture cannot turn that evidence
into a pass. 100-aircraft headroom is also NOT RUN because its conditional
50-aircraft pass prerequisite was not met. No claim is made about unmeasured
maximum sustainable speeds or longer-horizon memory stability.

## Longer live Ultra and overload

The separate 50-aircraft probe permits up to seven days of pacing input but has
a **220-engine-second stop budget**. It is a censored failure diagnostic, **not**
a seven-day certification or an earned seven-day horizon.

- Engine **220.649 s**; resolved **24480 game seconds**; ending owed credit
  **274501.0206 s**; maximum measured debt **278521.0206 s**.
- **One overload entry**, **zero observed recoveries**; ending OVERLOAD_DRAIN.
  Earnings freeze at the exact finite target; the remaining credit is retained.
  The budget stop hard-pauses safely, rather than claiming a completed drain.
- Resolved prefix/engine time is **110.945x**, not an estimate of eventual-day
  capacity. The independent ledger asserts no dropped nanosecond credit.
- Authoritative UTC advances only through committed work; it never substitutes
  the much later earned target. Whole-world validation passes at the stopped
  committed prefix. The test never resumes automatically after overload.

This is persistent deficit before the next Booking fence, not a recovered
temporary fence spike. Formal gates 1 (1800x capacity) and 2 (bounded backlog)
fail. One ordinary-work overload is observed; repeated recovery/resume cycles
are not manufactured to infer a recovery count. 50-aircraft live fence recovery
is not established by this prefix. Exactness/persistence safeguards are not
relaxed to change the conclusion.

## Speed matrix: real service window versus later drain

Each row earns **60 seconds of controlled real input**. Actual game horizons are
Normal 1800 s, Fast 12600 s, Very Fast 54000 s, Ultra 108000 s. The later player
drain earns nothing. A drained final credit of zero cannot conceal earlier lag.
These are comparison windows, not long-run certifications of lower speeds.
The early JSON `days` label was corrected in tooling; this table uses actual
target UTC and credit, never the mislabeled metadata. No timed workload changed.

| Aircraft | Speed | Engine s incl. drain | Resolved at last RUNNING sample | Owed then (game s) | Running service fraction | Running debt slope (game s/input s) | Final owed s / state |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Normal | 47.756 | 1795 | 5 | .997 | .01 | 0 / PAUSED |
| 1 | Fast | 47.896 | 12576 | 24 | .998 | -.25 | 0 / PAUSED |
| 1 | Very Fast | 49.371 | 53928 | 72 | .999 | -1.19 | 0 / PAUSED |
| 1 | Ultra | 51.209 | 108000 | 0 | 1.000 | -5.02 | 0 / RUNNING |
| 10 | Normal | 60.886 | 1784 | 16 | .991 | -.16 | 0 / PAUSED |
| 10 | Fast | 60.725 | 12433 | 167 | .987 | -.32 | 0 / PAUSED |
| 10 | Very Fast | 60.907 | 53496 | 504 | .991 | -11.80 | 0 / PAUSED |
| 10 | Ultra | 71.045 | 100920 | 7080 | .934 | 75.57 | 0 / PAUSED |
| 25 | Normal | 64.034 | 1754 | 46 | .974 | -.19 | 0 / PAUSED |
| 25 | Fast | 62.250 | 12301 | 299 | .976 | -1.70 | 0 / PAUSED |
| 25 | Very Fast | 74.592 | 24840 | 29160 | .460 | 463.50 | 0 / PAUSED |
| 25 | Ultra | 123.436 | 26040 | 81960 | .241 | 1342.31 | 17880 / PLAYER_DRAIN |
| 50 | Normal | 73.003 | 1620 | 180 | .900 | 1.21 | 0 / PAUSED |
| 50 | Fast | 118.597 | 3720 | 8880 | .295 | 144.38 | 0 / PAUSED |
| 50 | Very Fast | 126.342 | 4140 | 49860 | .077 | 825.79 | 37680 / PLAYER_DRAIN |
| 50 | Ultra | 127.552 | 4140 | 103860 | .038 | 1725.98 | 91440 / PLAYER_DRAIN |

Running service is resolved / earned at the last RUNNING sample. A short-window
slope uses first-to-last RUNNING samples only; it is not a fitted long-run capacity.
The 120-second engine budget can overshoot by one indivisible safe unit. Censored
tails remain owed. All 16 ledgers balance exactly; no overload is reached inside
these short, capped earning windows. The longer uncapped probe does reach it.

### Backlog curve: 50-aircraft uncapped-within-budget Ultra

| Engine s | Input s | Resolved game s | Owed game s | State |
| ---: | ---: | ---: | ---: | --- |
| 6.47 | 6.67 | 180 | 11781.28 | RUNNING |
| 36.62 | 36.82 | 2220 | 64021.52 | RUNNING |
| 69.77 | 69.97 | 4620 | 121299.12 | RUNNING |
| 102.83 | 103.03 | 10200 | 175216.48 | RUNNING |
| 132.07 | 132.27 | 17400 | 220627.27 | RUNNING |
| 165.90 | 166.10 | 20460 | 278488.26 | RUNNING |
| 199.63 | 199.83 | 23220 | 275761.02 | OVERLOAD_DRAIN |
| 220.65 | 220.85 | 24480 | 274501.02 | OVERLOAD_DRAIN |

Active-accrual input stops around **166.10 s** although elapsed controlled input
continues during drain. Last running service fraction **.06844**; running debt
slope **+1672.89 game seconds/input second**. The frozen earned target is
**2026-09-05T14:03:01Z**, while stopped committed UTC is **2026-09-02T09:48:00Z**.
The drain decreases debt slowly; it does not restore ongoing Ultra service.
Stopped complete hash:
`d1f169e05d179048f9394bf9b21a8a2ab8bca061db3bebf53743991d91a8be01`.

## Exclusive attribution and exact measured blockers

The corrected full 50-aircraft day profile: **373.176 s**, same complete world
and event vector as the 375.151-second quiet run; same 51 shared /1 strict units
and 52 detached commits. Differences are host/timing variation, not optimization.
All figures below are exclusive, not nested totals.

| Category | Exclusive s | Calls | Interpretation |
| --- | ---: | ---: | --- |
| Complete validation, excluding next two subphases | 69.060 | 54 | Identity/domain/topology and remaining validator work |
| Structural JSON/alias graph | 24.961 | 54 | Entire authoritative graph |
| Booking lineage validation | 9.140 | 54 | Retained Booking/itinerary associations |
| Detached candidate/commit clone | 42.669 | 104 | Two copies per published unit |
| Handler dispatch + kernel event contract comparison | 114.000 | 401 | Broken down in independent prefix below |
| Capsule construction/publication | 35.935 | 800 | Exact protected read/write/output ownership |
| Event topology transition proof | 13.914 | 400 | Exact before/after flight event proof |
| Transition equations | 3.028 | 4800 | Exact changed-record equations |
| Manifest work | 2.185 | 800 | Current authoritative carriage |
| Candidate manifest lookup | 2.077 | 51 | Private bounded lookup, still enabled |
| Ownership setup/close | .532 | 102 | Candidate-only lifetime |
| Capture internal subphase | .061 | 400 | Does not claim entire certificate entry time |
| Session notification | 1.063 | 53 | Committed Stage 2 invalidation |

Complete validation aggregate is **103.161 s** (~27.6%); clones ~11.4%; dispatch
category ~30.5%; capsule ~9.6%. Remaining unhooked resolver/proof/domain work is
residual, not silently assigned to a measured child. Detached commit's .0014 s
excludes its clone; calling that the entire commit cost would be misleading.

A second identity-safe **84-event /5400-game-second prefix** isolates kernel
event/history work (75.582 s, 11 shared units, 11 commits; no fence):

- `_event_contract_witness`: **10.769 s /84 calls**, deep-copies pending events
  and event history for genuine predecessor evidence.
- `_handler_contract_error`: **12.774 s /84 calls**, scans/compares retained
  predecessor pending/history records and ID unions for every transition.
- Remaining handler dispatch **8.025 s**; validation aggregate **23.470 s**;
  clones **8.287 s**, capsule **7.225 s**, event topology proof **2.845 s**.

Thus **31.2%** of that measured prefix is the two kernel event/history witness
phases alone. The 400-event day retains O(events x queued/history records) proof
work, plus O(units x whole-world size) validation and cloning. Rolling four-week
dated/event authority grows with aircraft count. These measured costs, not widget
rendering or a disabled Booking checkpoint, explain the large service deficit.
No proof, alias/JSON check, event limit or gameplay behavior is removed here.

Earlier Stage 3E/E.2 sparse 25-aircraft/100-event and Divine timings are not
interchangeable with this four-week, actively booked, 50-aircraft day's workload.
The larger measurements expose capacity; they do not imply a new production
regression in unchanged source. No performance goalpost or workload is adjusted.

## Callback latency and responsiveness

Distribution covers the whole matrix window including commanded drain. p99 is
only emitted for at least 100 callbacks; it is omitted for sparse samples.

| Aircraft | Speed | Median s | p95 s | Max s | Events | Shared /strict units | Physical commits |
| ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |
| 1 | Normal | .158 | .174 | .239 | 1 | 1 /0 | 1 |
| 1 | Fast | .159 | .167 | .236 | 2 | 2 /0 | 2 |
| 1 | Very Fast | .162 | .193 | .284 | 6 | 6 /0 | 6 |
| 1 | Ultra | .162 | .240 | 1.007 | 14 | 13 /1 | 14 |
| 10 | Normal | .807 | .993 | 1.337 | 3 | 3 /0 | 3 |
| 10 | Fast | .816 | 1.379 | 1.498 | 13 | 12 /0 | 12 |
| 10 | Very Fast | .829 | 1.651 | 2.251 | 53 | 16 /0 | 16 |
| 10 | Ultra | .842 | 2.619 | 5.039 | 121 | 21 /1 | 22 |
| 25 | Normal | 1.834 | 3.209 | 3.404 | 17 | 12 /0 | 12 |
| 25 | Fast | 1.847 | 4.091 | 4.353 | 45 | 11 /0 | 11 |
| 25 | Very Fast | 3.475 | 4.363 | 4.430 | 145 | 19 /0 | 19 |
| 25 | Ultra | 3.543 | 4.407 | 10.376 | 226 | 29 /1 | 30 |
| 50 | Normal | 3.736 | 7.611 | 7.870 | 30 | 8 /0 | 8 |
| 50 | Fast | 6.688 | 8.630 | 8.688 | 119 | 16 /0 | 16 |
| 50 | Very Fast | 6.746 | 8.336 | 8.360 | 136 | 18 /0 | 18 |
| 50 | Ultra | 6.713 | 8.302 | 8.567 | 138 | 18 /0 | 18 |

Additional matrix accounting (maximum debt includes the before/after callback
samples; p99 requires at least 100 samples):

| Aircraft | Speed | Callbacks | p99 s | Maximum owed game s |
| ---: | --- | ---: | ---: | ---: |
| 1 | Normal | 300 | .187 | 14.167 |
| 1 | Fast | 300 | .185 | 92.073 |
| 1 | Very Fast | 299 | .234 | 436.377 |
| 1 | Ultra | 281 | .337 | 2173.833 |
| 10 | Normal | 74 | N/A | 59.534 |
| 10 | Fast | 71 | N/A | 654.778 |
| 10 | Very Fast | 66 | N/A | 3805.559 |
| 10 | Ultra | 59 | N/A | 17377.070 |
| 25 | Normal | 33 | N/A | 137.905 |
| 25 | Fast | 29 | N/A | 1618.408 |
| 25 | Very Fast | 24 | N/A | 29160.000 |
| 25 | Ultra | 33 | N/A | 82311.793 |
| 50 | Normal | 17 | N/A | 338.891 |
| 50 | Fast | 20 | N/A | 8880.000 |
| 50 | Very Fast | 20 | N/A | 49860.000 |
| 50 | Ultra | 20 | N/A | 103860.000 |

50 full-day Advance: median **6.791 s**, p95 **8.065 s**, max shared callback
**8.608 s**, max strict/fence callback **16.382 s**. Longer live Ultra: median
**6.678 s**, p95 **7.161 s**, max shared **8.509 s**, no fence reached.
The full-day control has 53 callbacks; the longer live probe has 34. Neither
sample supports a p99 claim.

Responsiveness: starter short native control **EXCELLENT**; ten-aircraft lower
tiers **ACCEPTABLE** with noticeable busy spikes; 25-/50-aircraft measured busy
work **POOR** because repeated multi-second units disrupt interaction. A 16-second
atomic fence is a severe stall. This is measured latency, not a human-playability
survey or a claim that every frame/window is smooth. Capacity failure stands
independently of this responsiveness classification.

## Fence, history, memory and autosave diagnostics

The one-aircraft **seven-day finite production-pump control** completes in
**14.627 s**, 64 events, 8 shared units +8 strict fences, 16 detached commits.
It crosses seven daily checkpoints and the actual Sep6 16:00 UTC rolling
publication; 28 additional dated flights are naturally published. This is a
boundary/retention control, not a live sustained-capacity certification.

- Booking fences: **.834, .881, 1.015, 1.097, 1.239, 1.426, 1.518 s**;
  median **1.097 s**, max **1.518 s**. Same domain work becomes ~82% slower from
  first to seventh as real retained authority grows. This is observed association,
  not an isolated causal microbenchmark of history alone.
- Weekly publication: **one, .383 s**. No 50-aircraft weekly fence was reached
  before the formal capacity failure; its unmeasured cost is not assumed cheap.
- 50-aircraft Day1 Booking: **one, 16.362 s** (same one-event median/max).
  No expiry or market-rotation event occurs in these horizons. Existing full
  regressions cover those strict/fence paths; no timing claim for an absent event.
- Live matrix Booking fences occur only in 1/10/25 Ultra tails, including drains.
  Fence rows record before/after debt and later recovery state. A recovery during
  PLAYER_DRAIN is **not** ongoing sustainable service. The frozen finite controls
  have no new earned credit, so their "recovery" is purely consumption of a
  preloaded target. No 50-aircraft live fence-recovery claim is made.

The matrix's individual Booking fences provide this recovery diagnostic:

| Aircraft / Ultra | Fence s | Debt before s | Debt after s | Later return to pre-fence debt, engine s | Recovery state |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | .922 | 360.425 | 1894.492 | 16.592 | RUNNING |
| 10 | 4.609 | 1635.367 | 9224.581 | 22.097 | PLAYER_DRAIN |
| 25 | 9.422 | 65854.000 | 32400.000 | 4.095 | PLAYER_DRAIN |

These are one-event median/max values per control. The 25-aircraft fence already
consumes debt in a paused earning window; its smaller after value is not live
headroom. The final full-day 50-aircraft control starts with no realtime debt
because explicit Advance is unpaced. No 50-aircraft live fence recovery duration
can therefore be certified from that control.

| Control | Start working MiB | End working MiB | Process peak MiB | Horizon |
| --- | ---: | ---: | ---: | --- |
| 50 live overload diagnostic | 109.23 | 230.51 | 275.31 | 6h48m resolved, censored |
| 50 explicit Advance | 108.86 | 259.68 | 388.64 | One complete game day |
| 50 corrected day profile | 109.05 | 260.31 | 388.34 | One complete game day |
| 1 finite retention control | 38.31 | 91.12 | 130.14 | Seven complete game days |

Peaks are process-lifetime high-water marks, including fixture load/audit and
temporary copies, not retained candidate memory. The 16-row matrix runs in one
process and reaches **490.42 MiB**; earlier high-water marks cannot be assigned
to individual later cases. The harness retains the source fixture alongside the
session copy for exact comparisons; these are harness-process figures, not an
isolated native game's minimum resident memory. No unbounded witness/index
accumulation is introduced.
Memory is sampled outside the service clock; final tooling records every unit.
50 Day3/Day7 memory is **N/A**, not extrapolated, because those horizons are not run.
These short failures do not prove long-horizon leak freedom or stability.

50 Day1 authority grows naturally: Bookings/itineraries **7819 ->15569**,
history **482 ->883**, results **223 ->423**, journals **273 ->474**;
flights remain 6800, pending **6580 ->6380**, active operations 35. Rough working
growth ~151 MiB in that day includes both retained state and allocation high-water
behavior; it must not be labeled a leak without a longer controlled experiment.
Starter seven days: B/I **900 ->5647**, history **11 ->75**, results **5 ->33**,
journals **6 ->41**, flights **136 ->164**. Growing authority explains why Day1
margin alone could not certify arbitrarily long operation. Full-world traversal
and event topology proof remain sensitive to retained/queued history.

Natural seven-game-day autosave: **one save, 1.484 s**, actual committed end
UTC Sep9 03:00; no private request/candidate at that snapshot. Existing thresholds
remain **15 active minutes OR seven game days**. Other short measurement windows
do not reach a natural threshold; no autosave is disabled. Separate persistence
checks inject the 15-minute eligibility threshold while paused, outside measured
service: first eligible autosave succeeds, immediate second is false, autosave
reload is exact/paused. Logs distinguish capacity versus verification saves.
No storm or repeated-save throughput collapse is observed. The natural save is
included in the 14.627-second control, not subtracted from throughput.

## Determinism, saved authority and Stage 2

The representative **50-aircraft 60-game-second equal-time prefix** compares all
four actual speed selections against the independent strict `kernel` oracle.
Every complete authoritative field matches; same two-event ordered vector:

1. event-000000000262 Departure, due Sep2 03:01 UTC, order [100,261].
2. event-000000007033 Completion, same UTC, order [100,7032].

Common explicit final Pause/Normal selection is applied to every path; no clock,
UI, RNG, journal, allocator or history field is excluded. Complete digest:
`b787e6f2434f9d5cadd2d92e0bf003bf39004a4474ac6952c1fe8faceb5e3ae2`.
Normal/Fast/VeryFast/Ultra each take two callbacks and one physical commit;
the independent strict oracle succeeds. This prefix proves exactness, **not**
capacity. The quiet and profiled entire 50-aircraft day also have identical
complete hash and all 401 ordered events. Existing Stage 1/3 shadow/equivalence/
failure/replay suites supply broader partition/save/fence/seed coverage.

The **same 50-aircraft Normal live session** runs, player-pauses/drains, saves,
reloads exact authority PAUSED with zero debt, remains unchanged while closed/
paused elapsed time is injected, explicitly resumes, continues to its exact owed
target, saves/reloads again, and tests autosave eligibility/reload. All PASS.
The separate completed 50-aircraft explicit day also passes those checks.
They occur outside measured capacity time and do not count as throughput work.

Stage 2 reads committed envelopes only. Notification/epoch counts are recorded
per safe unit; private candidates/lookups are released before callbacks return,
and no speculative state reaches header/Fleet/Flights/Finance/saves. No proof,
clipboard, pacing-debt or derived cache is added to saved authority. Schema stays
**7**, migrations/bookmarks/complete-boundary persistence remain unchanged.

## Native Windows Kivy verification

Fresh child processes use actual SDL2/GLEW windows, title **Load Game**, current
validated career/manual storage, and **New Game forbidden**. No unrelated screen
import/navigation is required for registration. All saves are TEMP.

| Fixture | Outcome | Callbacks | Median s | p95 s | Max s | Max tick refresh s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Starter | PASS | 21 | .118 | .230 | .280 | .0247 |
| 50 operational aircraft | PASS functional smoke | 60 | 6.640 | 8.400 | 8.498 | .0649 |

Starter crosses real Departure/Completion and Booking fence, all four speeds,
pause/drain, manual save, exact paused reload/zero debt and no offline progress.
50 crosses Departure/Completion, all four speeds and a requested **15-second
Ultra observation**, then explicitly pauses/drains, saves/reloads, navigates
Fleet/Flights/Finance/Overview, verifies displayed committed UTC, resumes Normal,
and drains/validates again. 44 shared units, zero strict events; no Booking fence
is claimed in this native prefix. 43 samples are PLAYER_DRAIN, 10 RUNNING,
7 PAUSED; no ERROR or overload is observed in this final guarded run. Maximum
credit **27692.299194 game seconds**; final paused UTC **Sep2 12:15:59 UTC**.

An initial long native attempt ended at a generic final paused/validation
assertion without recording which condition failed; it is **not used as capacity
or exactness evidence**. The tool was strengthened to fail immediately on runtime
ERROR, log phases/states/debt, validate explicitly and recognize the approved
RECOVERED paused state. The final fresh guarded repeat passes. This does not
establish repeatable human smoothness or erase the separate finite-request
safety-stop/overload evidence. No production fix is inferred from that diagnostic.

Programmatic controls execute between safe units and demonstrate no apparent
deadlock/UI corruption in the final run. There was no human mouse/visual usability
survey; throughput was formally measured in the production harness. A native
functional PASS with six-second callbacks is emphatically not an Ultra capacity
PASS. The initial finite credit stimulus reaches an event boundary without hours
of waiting; subsequent named-speed observation uses actual production pacing.

## Future bulk/offline relevance and limits

The 375-second one-day explicit Advance is too slow for convenient large bulk
catch-up on this host. No 7-/30-day extrapolation is claimed because historical
growth and strict publication can change the rate. A hypothetical offline-catch-up
feature would inherit these measured throughput/atomic-stall limits and would need
its own approved design and capacity evidence. **PH 1.0 has no offline progression.**
No offline feature, retention redesign, additional certification or optimization
stage is implemented or automatically proposed by this failed certification.

## Verification and self-review

Commands below used the existing project `.venv/Scripts/python.exe` on
2026-10-05; no dependencies were installed or changed.

```powershell
python -B -m unittest tests.test_runtime_capacity tests.test_booking_lineage_optimization tests.test_atomic_boundary_optimization tests.test_cooperative_runtime tests.test_gui_cooperative_runtime -q
python -B -m unittest discover -s tests
python -B -m unittest tests.test_runtime_capacity -q
python -B -m compileall -q app game tests main.py make_snapshot.py settings.py test.py
git diff --check
```

- Affected focused suite: **86 passed in 165.431 seconds**.
- Full repository suite: **1024 passed in 1056.680 seconds**, baseline 1009;
  **15 new tests**. This includes Stage 3A/B/C/D.2/D.3/E/E.1/E.2, Stage 1
  complete-world oracle, Stage 2 ownership/invalidation, Bookings/itineraries,
  finance/journals, aircraft lifecycle, event topology/history, save/migration,
  autosave/bookmarks, explicit Advance and GUI/runtime regressions.
- After the full run imported its source, the test-only output labels for
  explicit Advance were clarified: earned realtime/target are N/A, and every
  callback displays the requested unpaced target. Existing test assertions were
  extended. Final harness suite: **15 passed in 14.394 seconds**. This changes
  neither executed simulation work nor the recorded timing/hash/vector evidence.
- Scoped compilation passes; **228 local file/directory documentation links**
  and the new capacity anchor pass. Diff whitespace checks pass.
- Final native starter and 50-aircraft smoke results are recorded above;
  earlier diagnostic failures and their evidence limitations are retained.

Complete diff review verifies no production source, schema/template, dependency,
speed ratio, cap, overload threshold, handler certificate, validation, RNG,
Booking/publication/history, gameplay or save contract change. Harness clocks
cannot earn setup/telemetry time; ledgers balance without dropping credit. No
drained tail is counted as sustainable live capacity, and no short probe is
called seven-day certification. Source-fixture memory overhead and incomplete
long-horizon memory/capacity evidence are disclosed. No unresolved in-scope
correctness finding requires a production fix. The capacity deficit remains.

Changed files are the certification harness/15 guard tests, native smoke tooling,
this report, Current Development Status, Decision Register, continuous-runtime
capacity contract, roadmap capacity wording, prior report successor link and
documentation index. Generated fixture/save/profile output stays outside the
repository. Pre-existing untracked `.venv/` is not edited or staged.

## Final decision

**PH 1.0 RUNTIME NOT CERTIFIED.** Formal service capacity and bounded-backlog
gates fail at 50 active aircraft: the optimistic completed day achieves only
**230.307x**, versus **1800x required**, while actual continuous Ultra debt grows
and triggers overload. Exactness and persistence checks pass but cannot replace
capacity. Day3/Day7 and optional 100-aircraft escalation are not justified by
the conclusively failed Day1 gate. No further runtime implementation begins.

**STAGE 3 RUNTIME SCALABILITY PROJECT NOT COMPLETE.**

**EXACT BLOCKER:** 50-aircraft production processing consumes 375.151 seconds
per game day against Ultra's 48-second budget (7.816x deficit), with persistent
positive live debt and overload rather than sustainable 1800x service.
