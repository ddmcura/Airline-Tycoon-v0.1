# Current Development Status

Last updated: **2026-09-14**. Replace stale facts; this is not a development diary.

## Checkpoint and verification

- Last gameplay implementation checkpoint:
  `300a102a04f367228c027849548a1ebee462e58e` —
  `feat: add verified weekly flight planner`, committed on 2026-09-10.
- On 2026-09-14, before this documentation cleanup, HEAD was that checkpoint
  and the working tree was clean. Branch `master` tracks `origin/master`;
  the local upstream ref matched HEAD. A live `git ls-remote --heads origin
  refs/heads/master` check on the same date also returned this checkpoint.
- Recorded final planner working-tree verification on 2026-09-10:
  **517 tests passed in 256.955 seconds**, including **31 planner regressions**.
  The focused planner run passed 31 tests in 30.667 seconds. Compilation and
  diff validation passed. These are historical results, not a new test run.
- Verification used bundled Python and a temporary test-only `PYTHONPATH`
  providing `tabulate 0.10.0`; the WindowsApps Python alias could not launch.
  No machine-specific interpreter path or dependency change was committed.
- The verified planner source was subsequently committed at the checkpoint
  above. The prior record identifies only documentation and whitespace changes
  after the full suite, with compilation and staged diff validation repeated.
  No gameplay or persistent-state contract changes are part of this cleanup.

### Recorded planner verification commands (2026-09-10)

| Command | Result |
| --- | --- |
| `python -B -m unittest discover -s tests -p test_stage1_weekly_planner.py` | 31 passed, 30.667 seconds |
| `python -B -m unittest discover -s tests` | 517 passed, 256.955 seconds |
| `python -m compileall -q app game tests main.py make_snapshot.py settings.py test.py` | Exit 0 |
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

## Not yet available and limitations

- No authoritative file save/load: exiting loses the session. In-memory
  serialization/migrations exist; legacy save menus do not fill this gap.
- No graphical or existing-published-plan editor, curated authoritative manufacturer/model market,
  purchase/delivery, leasing, lease-to-own, used market, or maintenance expenses.
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

Next proposed development work is the bounded aircraft manufacturers and
curated model catalog milestone. Its implementation is not authorized by the
weekly planner approval. Use the PH 1.0 roadmap for scope and dependencies.

## Documentation maintenance scope (2026-09-14)

This cleanup establishes contextual reading, explicit schema/mirror authority,
proportional verification, milestone completion authority, and historical labels.
It changes repository instructions and documentation only. Canonical schema
contents, the template mirror, code, tests, formulas, and runtime data are unchanged.
No repository-local skills are introduced. Protections remain in AGENTS.md.

The starting tree had no unrelated changes. The documentation successor is
separate from the gameplay checkpoint above; its own hash and Git outcomes are
not claimed here. No development work beyond this cleanup is implied.

Documentation validation on 2026-09-14 covered the 29-file working-tree cleanup:

- An inline PowerShell validator using `git ls-files` and `git diff --name-only`
  checked 123 local Markdown links and 20 heading anchors, including tracked-path
  casing: passed. The same check confirmed documentation-only changed paths.
- Authority and final-diff review confirmed the approved schema hierarchy,
  proportional testing, explicit Git authorization, and preserved domain contracts.
- `git diff --check`: passed (exit 0).
- Gameplay tests and compilation: not run; this is documentation-only work.
