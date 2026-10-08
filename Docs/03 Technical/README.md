# 03 Technical

Documentation for implementation-wide structures and engineering rules.

## Current documents

- [Current Development Status](Current%20Development%20Status.md)
- [Decision Register](Decision%20Register.md)
- [Stage 1 State Schema](Stage%201%20State%20Schema.md)
- [Stage 1 Terminal Harness Technical Specification](Stage%201%20Terminal%20Harness%20Technical%20Specification.md)
- [PH GUI Foundation Technical Specification](PH%20GUI%20Foundation%20Technical%20Specification.md)
- [Scheduling Performance Investigation](Scheduling%20Performance%20Investigation.md)

- [Game State & Save Architecture](Game%20State%20%26%20Save%20Architecture.md)
- [Game State & Save Technical Specification](Game%20State%20%26%20Save%20Technical%20Specification.md)
- [Stage 1 Implementation Roadmap](Stage%201%20Implementation%20Roadmap.md)

## Planned documents

- Serialization.md
- Folder Structure.md
- Coding Standards.md

The Stage 1 State Schema is the canonical persistent-state contract.
`Data/Templates/template_reference.txt` and `docs/template_reference_with_rules.txt`
are subordinate references; follow the authority order in [AGENTS.md](../../AGENTS.md).

## Approved future architecture direction

- [Quarterly Planning, Weekly Services & Bounded Booking Architecture](../01%20Core%20Simulation/Quarterly%20Planning%2C%20Weekly%20Services%20%26%20Bounded%20Booking%20Architecture.md) — approved direction, not implemented; migration audit recorded, implementation approval pending.

- [Quarterly / Weekly Architecture Migration Audit](Quarterly%20Weekly%20Architecture%20Migration%20Audit.md) — audit recommendations, not implementation approval; source mapping, simplification, risks and proposed migration stages.

- [Quarterly Authority and Identity Foundation](Quarterly%20Authority%20and%20Identity%20Foundation.md) — implemented dormant Schema 8 Stage 1; quarterly workflows remain pending.

- [Quarterly Dependency Ownership and Command Contracts](Quarterly%20Dependency%20Ownership%20and%20Command%20Contracts.md) — finalized contracts; Stage 2A reads and Schema 9 prerequisite implemented; 2B and later slices unimplemented.

- [Quarterly Dependency Read Foundation](Quarterly%20Dependency%20Read%20Foundation.md) — Stage 2A read infrastructure implemented; no commands, maintained indexes or quarterly activation; Schema 9 prerequisite now implemented.

- [Quarterly Flight Number Reuse Authority](Quarterly%20Flight%20Number%20Reuse%20Authority.md) - Schema 9 prerequisite implemented; protected reservations, lowest retired suffix and high-water cursor, no 2B commands or quarterly activation.
