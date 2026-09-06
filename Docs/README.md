# Airline Tycoon Documentation

This directory organizes Airline Tycoon design and development documentation without replacing or deleting existing project documents.

## Structure

Fresh Codex tasks start with repository [AGENTS.md](../AGENTS.md), then
[Current Development Status](03%20Technical/Current%20Development%20Status.md),
the [development roadmap](03%20Technical/Stage%201%20Implementation%20Roadmap.md),
and the [Decision Register](03%20Technical/Decision%20Register.md).
These provide recovery context without an external handoff prompt; architecture
and the canonical Stage 1 schema remain authoritative for design and state.
The older project-context and development-context master notes are historical
working summaries, not current checkpoint, roadmap, or decision authorities.

- [`01 Core Simulation`](./01%20Core%20Simulation/) — passenger demand, scheduling, aircraft operations, and economy systems.
- [`02 Gameplay`](./02%20Gameplay/) — player-facing management systems and progression.
- [`03 Technical`](./03%20Technical/) — game state, saves, serialization, folder structure, and coding standards.
- [`04 Data`](./04%20Data/) — schemas and reference-data documentation.
- [`05 Future`](./05%20Future/) — approved post-v1.0 and long-term systems.

Existing documentation outside this hierarchy should remain in place until it is deliberately reviewed and migrated.
