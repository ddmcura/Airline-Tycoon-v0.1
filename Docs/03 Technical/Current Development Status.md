# Current Development Status

Last updated: **2026-09-14**. Replace stale facts; this is not a development diary.

## Checkpoint and verification

- Catalog verification base: `a4aa42993f7c126d84dd049c406959c9bd704ab7`, the
  documentation authority cleanup. The results below cover the catalog source
  introduced with this status update. Its eventual commit is identified by Git
  history; this pre-commit record does not invent its hash or claim a pending push.
- The starting tree was clean on `master`, tracking `origin/master`, with local
  divergence 0/0. During final preparation, `git fetch origin master` and live
  `git ls-remote --heads origin refs/heads/master` confirmed that the upstream
  and remote still matched the verification base. Post-push agreement must be
  checked against the resulting commit, not inferred from this pre-commit check.
- Last committed gameplay checkpoint: `300a102a04f367228c027849548a1ebee462e58e`,
  the weekly planner. Its historical verification recorded 517 passing tests.
- Catalog final verification on 2026-09-14: **531 tests passed in 283.099 seconds**,
  including **14 new catalog tests**. Focused catalog verification passed all
  14 in 6.579 seconds. The revised terminal import-boundary check passed separately.
- Tests used bundled Python 3.12 with temporary test-only `tabulate 0.10.0` on
  `PYTHONPATH`. The initial sandboxed full attempt was interrupted after a legacy
  import error because sandboxed Python could not read that temporary dependency.
  The final full run used approved external execution access and passed. No
  repository dependency change or machine-specific runtime path was committed.
- Application compilation and final diff validation passed. These results cover
  the catalog implementation and tests in this working tree; later documentation
  updates record those results and do not change the tested source.

### Recorded catalog verification commands (2026-09-14)

| Command | Result |
| --- | --- |
| `python -B -m unittest discover -s tests -p test_stage1_aircraft_catalog.py` | 14 passed, 6.579 seconds |
| `python -B -m unittest discover -s tests` | 531 passed, 283.099 seconds |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
| Local Markdown link/anchor validator over changed and new documents | Passed |
| `git diff --check` | Exit 0 |

## Implemented and available

Milestones 0–3 establish state/schema, immutable IDs, deterministic clock/events,
and dated-flight publication. Milestone 4, 4.5A, and 4.5B-1/2/3 establish compact
Model 4 demand and market-pack lifecycle. Milestone 5A–D completes direct-Economy
Booking; Milestone 6 completes minimal fulfilment and finance; Milestone 7 adds
the in-memory terminal. See the [existing roadmap](Stage%201%20Implementation%20Roadmap.md).

Recovery Batch 1 supplies 43 active PH airports, 1,806 directional markets,
home-base selection, market research and input/prompt fixes. Batch 2 supplies
versioned air-suitability curves, ground-network selection and destination-only
tourism while preserving Model 4 and processed history. See the
[Decision Register](Decision%20Register.md) and [terminal contract](Stage%201%20Terminal%20Harness%20Technical%20Specification.md).

`python -m app.terminal` creates an airline with a free A320-200 and USD cash,
offers the weekly scheduler under option 3 and the compatible fixed quick rotation
under option 10. The weekly scheduler drafts one-way chains, optional earliest
returns and explicitly confirmed positioning; shows Monday–Sunday reserved blocks;
supports continued scheduling from the last stop, custom day/time, day copy, undo,
and atomic Save with optional bounded weekly repeat. Save checks unpublished
recurrences through the configured horizon in a disposable candidate without
extending the actual publication window. Day copy replaces the draft only after
every copied leg succeeds. Validation rejects occurrences beyond their retained
revision's inclusive recurrence end date. These corrections add no schema fields
and change no approved calibration. It
accumulates Bookings, operates timed flights, and reports finance/fleet/markets.
Explicit next-event, day, positive duration (including multiple days), and exact
UTC-target advancement exist. PHP/EUR conversion is presentation-only.

PH 1.0 step 2 now supplies the [approved aircraft catalog](Aircraft%20Catalog%20Technical%20Specification.md):
5 manufacturer groups, 4 models each, maximum Economy layouts, separate integer
USD reference prices, calibrated reference range/cruise inputs, source notes and
nullable historical production years. Option 11 browses manufacturers and models
without changing the world or session dirty flag. The isolated catalog loader
requires an explicit version, rejects malformed/duplicate-key content and checks
an immutable semantic digest. No legacy purchase/lease flow is connected.

## Not yet available and limitations

- No authoritative file save/load: exiting loses the session. In-memory
  serialization/migrations exist; legacy save menus do not fill this gap.
- No graphical or existing-published-plan editor, purchase/delivery, leasing,
  lease-to-own, used-market transactions, or maintenance expenses.
  Legacy market/fleet modules are migration inputs, not completed Stage 1 features.
- Clock modes and explicit-duration kernel APIs exist, but no continuous 7×
  runtime or interactive running-session pause/resume controls exist.
- No AI, connecting Booking, detailed disruptions, or detailed airport operations.
  Starter aircraft, direct Economy and simplified revision-1
  operating costs are accepted harness limits. Batch 2 values are gameplay calibration.
- Planning supports the starter A320-200 timing profile and all 43 PH airports.
  Handling/taxi ranges are explicit versioned initial gameplay calibration;
  they are not real measured airport performance. Unknown profiles reject.
  Maximum handling/taxi allowances are reserved; random live handling is absent.
  Timed deadheads use zero passengers/revenue and existing fixed flight cost.
  Whole-world candidate copying/validation remains a
  documented scale limitation requiring profiling before broader runtime work.

- Catalog production-date coverage is intentionally incomplete: only the A320neo
  component-production start (2012) and 787-9 final-assembly start (2013) are
  recorded; other starts and all end years remain null/unestablished with notes.
  Null does not imply current production. Dates never gate catalog availability.
- Catalog ranges are configuration-dependent references, not full-load dispatch
  guarantees. Prices/cruise speeds are gameplay calibration. No catalog models
  become operational here; the starter remains the 180-seat A320-200. Handling
  data/math, schema 4, published history, and scenario inputs are unchanged.

## Approved PH 1.0 scope and next action

Follow the [PH 1.0 release sequence](Stage%201%20Implementation%20Roadmap.md#philippines-10-release-sequence):
broader weekly scheduling; manufacturers/curated catalog; basic new-aircraft
acquisition; continuous deterministic 7× runtime with manual pause/resume and
integration of existing multi-day advancement; leasing/lease-to-own/used aircraft;
simple versioned maintenance expenses; save/load; integrated PH 1.0 verification.
AI follows the completed and verified player-operated Philippines simulation.
Leasing, lease-to-own, used aircraft and maintenance may follow the first
minimum-playable checkpoint but remain PH 1.0 requirements. Save/load follows
sufficiently established main authoritative gameplay state and runtime.

The catalog milestone implementation and verification are complete. The next
milestone is **basic new-aircraft acquisition**. Its bounded specification must
settle atomic purchases and affordability, fleet creation/registration, delivery
or entry into service, and binding catalog versions to individual aircraft
configuration. Model-specific capacity/timing integration must replace the
planner's fixed 180-seat assumption before additional models can operate.

The user prefers simplified fixed handling (30 minutes narrowbody, 45 minutes
widebody) for later integration; the final catalog scope explicitly left
scheduling unchanged. Configurable cabin area, seat dimensions/weight/comfort,
Business/suites and payload/cargo-derived range remain future design boundaries.
These preferences do not authorize implementing later milestones now.

No unrelated changes were present during final review. The intended milestone
contains only catalog data, validation/lookup, terminal browsing, tests and
authoritative documentation. No scheduling or existing scenario changes are
included. Actual commit/push outcomes are reported after those operations.
