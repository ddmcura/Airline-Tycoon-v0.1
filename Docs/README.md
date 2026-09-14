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

## Domain documents

- [`01 Core Simulation`](./01%20Core%20Simulation/) — passenger demand, scheduling, aircraft operations, and economy systems.
- [`02 Gameplay`](./02%20Gameplay/) — player-facing management systems and progression.
- [`03 Technical`](./03%20Technical/) — game state, saves, serialization, folder structure, and coding standards.
- [`04 Data`](./04%20Data/) — schemas and reference-data documentation.
- [`05 Future`](./05%20Future/) — approved post-v1.0 and long-term systems.

Existing documentation outside this hierarchy should remain in place until it is deliberately reviewed and migrated.
