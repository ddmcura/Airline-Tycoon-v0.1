# Airline Tycoon Documentation

This directory organizes Airline Tycoon design and development documentation without replacing or deleting existing project documents.

## Working rules

Working rules are in [AGENTS.md](../AGENTS.md). Read documentation according to
the task, rather than following a fixed startup itinerary.

## Persistent-state authority

1. [Stage 1 State Schema](03%20Technical/Stage%201%20State%20Schema.md) is the
   canonical persistent-state and naming contract.
2. [template_reference.txt](../Data/Templates/template_reference.txt) is its
   subordinate implementation mirror.
3. Implementation code must follow both; the canonical schema prevails if they
   conflict. Before implementing a new authoritative persistent field, update
   the canonical schema first and then its template mirror.

This explicitly replaces older template-only authority instructions. Approved
architecture defines behavior and ownership; technical specifications define
domain contracts. Neither historical code nor a template overrides the schema.

## Find the relevant context

- [Current Development Status](03%20Technical/Current%20Development%20Status.md):
  implemented capabilities, limitations, checkpoint, and recorded verification.
- [Stage 1 roadmap](03%20Technical/Stage%201%20Implementation%20Roadmap.md):
  PH 1.0 scope, order, and milestone acceptance; not implementation permission.
- [Aircraft catalog specification](03%20Technical/Aircraft%20Catalog%20Technical%20Specification.md):
  the approved 20-model reference catalog, calibration and compatibility boundary.
- [Aircraft acquisition specification](03%20Technical/Aircraft%20Acquisition%20Technical%20Specification.md):
  atomic purchases, selected delivery, schema 5 and versioned PH performance.
- [Aircraft marketplace specification](03%20Technical/Aircraft%20Marketplace%20Technical%20Specification.md):
  schema-6 operating leases, lease-to-own, rotating offers and persistent used listings.
- [Routine maintenance specification](03%20Technical/Routine%20Maintenance%20Technical%20Specification.md):
  schema-7 aircraft-class expenses, direct settlement and V1 migration boundary.
- [Continuous runtime specification](03%20Technical/Continuous%20Runtime%20Technical%20Specification.md):
  current 30/210/900/1800x pacing, management while running, exclusive world ownership and performance gates.
- [Production cooperative runtime](03%20Technical/Production%20Cooperative%20Runtime.md):
  Stage 3E bounded shared pumping, exact pacing credit, pause/catch-up barriers and production measurements.
- [Atomic boundary cost optimization](03%20Technical/Atomic%20Boundary%20Cost%20Optimization.md):
  Stage 3E.1 exact graph validation, retained-history profiles and the remaining measured runtime gate.
- [Retained Booking validation optimization](03%20Technical/Retained%20Booking%20Validation%20Optimization.md):
  Stage 3E.2 exact validation-local lineage, diagnostics, visit counts and runtime evidence.
- [Runtime scalability forensic audit](03%20Technical/Runtime%20Scalability%20Forensic%20Audit.md):
  Stage 3G-A throughput/main-thread attribution, native OS response evidence,
  exactness baseline and proposed future stages; no production optimization.
- [Runtime local certified proofs](03%20Technical/Runtime%20Local%20Certified%20Proofs.md):
  Stage 3G-B local event/ownership/transition proofs, sealed canonical selection,
  exactness evidence and measured remaining validation/fence costs.
- [Runtime capacity certification](03%20Technical/Runtime%20Capacity%20Certification.md):
  final Stage 3F production measurements, 50-aircraft Ultra failure evidence,
  backlog/overload, exactness, persistence and native Kivy limits.
- [Runtime trusted reads](03%20Technical/Runtime%20Trusted%20Reads.md):
  Stage 2 session ownership, disposable lookup epochs and measured read performance.
- [Runtime shared candidate infrastructure](03%20Technical/Runtime%20Shared%20Candidate%20Infrastructure.md):
  Stage 3A opt-in candidates, per-event shadow proof, strict recovery and rollback.
- [Contract Payment certification](03%20Technical/Contract%20Payment%20Shared%20Certification.md):
  Stage 3B exact transition proof, protected dependencies and payment measurements.
- [Flight shared certification](03%20Technical/Flight%20Shared%20Certification.md):
  Stage 3C separate Departure/Completion proofs, exact flight/finance witnesses and throughput evidence.
- [Flight proof cost optimization](03%20Technical/Flight%20Proof%20Cost%20Optimization.md):
  revised Stage 3D exclusive profiling, exact typed witnesses and narrowed JSON proof.
- [Runtime candidate ownership](03%20Technical/Runtime%20Candidate%20Ownership.md):
  Stage 3D.2 enforced mutation reachability, local alias proofs and measured scaling.
- [Candidate manifest lookup](03%20Technical/Candidate%20Manifest%20Lookup.md):
  Stage 3D.3 protected private Booking IDs, exact coverage/lifetime and measured scaling.
- [Runtime resolution foundation](03%20Technical/Runtime%20Resolution%20Foundation.md):
  shared strict resolver facade, complete boundaries and exact equivalence oracle.
- [PH GUI foundation specification](03%20Technical/PH%20GUI%20Foundation%20Technical%20Specification.md):
  approved Kivy frontend, shared application session and graphical playtest scope.
- [Management GUI architecture and pages](03%20Technical/Management%20GUI%20Architecture%20and%20Pages.md):
  active-page lifecycle, stable tables, Fleet/Details/Research semantics and Patch 2 evidence.
- [Operational management pages](03%20Technical/Operational%20Management%20Pages.md):
  Flights day view, directional Booking week matrix, committed queries and Patch 3 evidence.
- [Decision Register](03%20Technical/Decision%20Register.md):
  durable decisions and links to their canonical definitions.
- [Project Foundation](01%20Core%20Simulation/Project%20Foundation.md):
  product principles and package responsibilities.
- [Game State & Save Architecture](03%20Technical/Game%20State%20%26%20Save%20Architecture.md)
  and [technical specification](03%20Technical/Game%20State%20%26%20Save%20Technical%20Specification.md):
  whole-world persistence, migration, and save/load safety.

Historical documents tracked under lowercase `docs/` preserve earlier designs.
Their authority claims and maintenance instructions are superseded. They are not
current implementation status or permission to begin work.

- [Planning-only reposition feasibility](03%20Technical/Scheduling%20Planning%20Reposition%20Feasibility.md):
  Patch4 physical draft-gap proof, exact readiness and strict publication boundary.

## Domain documents

- [`01 Core Simulation`](./01%20Core%20Simulation/) — passenger demand, scheduling, aircraft operations, and economy systems.
- [`02 Gameplay`](./02%20Gameplay/) — player-facing management systems and progression.
- [`03 Technical`](./03%20Technical/) — game state, saves, serialization, folder structure, and coding standards.
- [`04 Data`](./04%20Data/) — schemas and reference-data documentation.
- [`05 Future`](./05%20Future/) — approved post-v1.0 and long-term systems.

Existing documentation outside this hierarchy should remain in place until it is deliberately reviewed and migrated.

## Approved future architecture direction

- [Quarterly Planning, Weekly Services & Bounded Booking Architecture](01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md) — approved direction, not implemented; migration audit recorded, implementation approval pending.

- [Quarterly / Weekly Architecture Migration Audit](03%20Technical/Quarterly%20Weekly%20Architecture%20Migration%20Audit.md) — audit recommendations, not implementation approval; source mapping, simplification, risks and proposed migration stages.

- [Quarterly Authority and Identity Foundation](03%20Technical/Quarterly%20Authority%20and%20Identity%20Foundation.md) — implemented dormant Schema 8 Stage 1; quarterly workflows remain pending.

- [Quarterly Dependency Ownership and Command Contracts](03%20Technical/Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md) — finalized contracts; Stage 2A–2D implemented; 2E certified; approved reuse/publication rules and schema-first ordering.

- [Quarterly Dependency Read Foundation](03%20Technical/Quarterly%20Dependency%20Read%20Foundation.md) — Stage 2A implemented, dormant direct ownership/dependency reads, compatible with Schema 9; Stage 2B–2E recorded separately; quarterly gameplay remains unimplemented.

- [Quarterly Flight Number Reuse Authority](03%20Technical/Quarterly%20Flight%20Number%20Reuse%20Authority.md) - Schema 9 prerequisite implemented; protected reservations, lowest retired suffix and high-water cursor, historical prerequisite checkpoint; 2B commands now recorded separately, no quarterly activation.

- [Quarterly Restricted Command Foundation](03%20Technical/Quarterly%20Restricted%20Command%20Foundation.md) - Stage 2B implemented: bundled service creation, fare revision, owner-issued freshness and atomic candidate commit; no quarterly activation or complete feasibility.

- [Quarterly Feasibility and Chronology](03%20Technical/Quarterly%20Feasibility%20and%20Chronology.md) - Stage 2C implemented: affected aircraft chains, explicit continuation/frequency edits/removal/retirement; Schema 9 and quarterly dormancy preserved.

- [Quarterly Maintained Dependency Indexes and Freshness](03%20Technical/Quarterly%20Maintained%20Dependency%20Indexes%20and%20Freshness.md) - Stage 2D implemented: private Scheduling indexes, atomic deltas and owner freshness; full gates/copies retained, quarterly gameplay dormant.

- [Quarterly Transaction Certification](03%20Technical/Quarterly%20Transaction%20Certification.md) - Stage 2E certified: adversarial command and independent reference coverage; all gates/copies retained, quarterly gameplay dormant.

- [Quarterly Publication Readiness](03%20Technical/Quarterly%20Publication%20Readiness.md) - Stage 3A diagnostic query: separate publication eligibility, planning feasibility and literal execution readiness; no publication, supply, events or gameplay activation.
