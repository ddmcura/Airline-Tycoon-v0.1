# Airline Tycoon — Project Foundation

> **Status:** Working foundation. This document records the project-level principles currently agreed during documentation consolidation. Individual system designs remain open to review as the legacy documentation is migrated.

## 1. Project Philosophy

**Airline Tycoon is a management tycoon game built on believable aviation principles, not a full airline simulator.**

The game should make the player feel like they are running an airline without requiring professional airline-operations knowledge. Real-world aviation informs the rules and relationships between systems, but gameplay takes priority when realism would create unnecessary complexity, repetitive work, or little strategic value.

The guiding question for a mechanic is not whether it perfectly reproduces reality, but whether it creates a believable and meaningful management decision.

### Core philosophy

- **Gameplay first.** Realism should support interesting decisions rather than create tedious micromanagement.
- **Believable aviation logic.** Aircraft range, airport importance, demand, fuel, slots, schedules, reputation, and other systems should behave in ways that make intuitive real-world sense.
- **Realistic-adjacent, not exact replication.** The simulation may simplify real systems and data when exact realism would add complexity without improving the tycoon experience.
- **Gameplay over unnecessary complexity.** A system should be as detailed as necessary to produce meaningful strategy, and no more complicated simply for realism's sake.
- **Intuitive outcomes.** Players should generally be able to look at a result and think, “Yes, that makes sense.”

## 2. Vision and Scope

Airline Tycoon is an open-ended business simulation about designing, operating, and expanding a profitable airline network.

The player takes the role of the airline's CEO. Early in the game, the CEO may personally make many operational decisions because the airline is small. As the company grows, the player's role becomes increasingly strategic: managing hubs, fleets, networks, subsidiaries or sister airlines, partnerships, alliances, infrastructure, and global expansion.

The long-term fantasy is to grow from a small airline into a global aviation group while allowing the player to define what success means.

### No predefined endgame

Airline Tycoon has no required final victory condition.

The player defines their own end goal. Examples may include building the largest airline, connecting every feasible route, creating a highly profitable regional carrier, operating a specialized fleet, developing major airport hubs, building an international airline group, or simply continuing to expand the network indefinitely.

The game should support an **expand, expand, expand** sandbox mentality rather than forcing the player toward a single ending.

### Complete first, then expand the world

Development should prioritize a complete gameplay experience before geographic scale.

The initial Philippines-focused game is not intended to be a disposable miniature version of the final game. It should establish the complete core airline-management loop on a manageable geographic scale. Once the systems work together properly, additional countries and airports can expand the world without requiring the core game to be redesigned.

In short:

> **Build a complete airline game, build systems that can naturally grow, then expand the world.**

### Scale, do not replace

Growth is not limited to geographic expansion. Major systems should be capable of growing with the player.

Examples include:

- A small airport can develop into a major or mega hub.
- One aircraft can become a fleet of hundreds.
- One hub can become a multi-hub global network.
- A domestic airline can become an international airline group.
- Manual management can evolve into higher-level management tools and automation.
- One country's network can expand into worldwide operations.

Progression should feel like the same game becoming larger and deeper, rather than old systems being discarded and replaced by unrelated late-game systems.

## 3. Core Gameplay Loop

The central gameplay objective is:

> **Design, optimize, and expand a profitable global airline network.**

Aircraft, airports, hubs, schedules, finances, reputation, infrastructure, and future systems all support this objective.

The fundamental growth loop is:

```text
Build and improve the network
        ↓
Carry passengers and generate activity
        ↓
Earn revenue and manage costs
        ↓
Expand the fleet and infrastructure
        ↓
Develop hubs and enter new markets
        ↓
Expand the airline's geographic reach
        ↓
Create an even stronger network
        ↓
Repeat
```

### Interconnected business simulation

Airline Tycoon is not primarily a fleet simulator, airport builder, financial simulator, or route planner in isolation.

It is a business simulation in which these systems reinforce one another. Success comes from balancing them effectively.

Aircraft are tools for building the network. Airports and hubs provide infrastructure. Money enables growth. Scheduling determines how effectively resources are used. Passenger and market systems determine whether the network creates value.

No single system should become so dominant that the rest of the airline business becomes irrelevant.

### Gameplay pace

The intended pace combines several styles of management gameplay.

The game is primarily an open-ended sandbox in the spirit of a transport tycoon: the player builds systems, allows the simulation to operate, observes the results, and makes strategic adjustments.

Route creation, scheduling, fleet selection, and infrastructure planning provide more hands-on optimization challenges. Strategic decisions remain necessary even when the simulation is allowed to run without constant intervention.

The player should spend more time **planning and improving the business** than babysitting routine aircraft actions.

### Progressive management

As the airline grows, the nature of the player's decisions should evolve.

Early gameplay may involve direct decisions about individual aircraft, routes, schedules, and prices. Larger airlines should increasingly rely on management tools, grouping, delegation, and optional automation so that growth creates strategic complexity rather than repetitive clicking.

The player's journey should therefore evolve from hands-on airline management toward CEO-level network and business strategy.

## 4. Development Principles

### Complete before expand

Finish the core gameplay systems and make them work together before using geographic content as a substitute for gameplay depth.

Adding another country should eventually be primarily an expansion of data and world opportunities, not a reason to redesign the core game.

### Complete before complex

A simple, complete, usable version of a system is preferable to an ambitious system that prevents the core game from becoming playable.

Advanced realism and additional depth can be layered onto a functioning foundation later.

### Modular systems

Major systems should have clear responsibilities and boundaries. Fleet management, route management, scheduling, finance, hubs, passengers, airports, and other packages should be capable of evolving without unnecessary coupling.

Functions used only by one game package should remain local to that package. Functions genuinely shared across packages should live in `game/utils`.

### Data-driven design

Game content and configurable simulation values should be data-driven wherever practical rather than unnecessarily hardcoded.

This includes airports, aircraft, countries, templates, demand modifiers, performance data, and other expandable world content.

A data-driven foundation makes geographic and content expansion easier while keeping game logic consistent.

### Progressive complexity

The game should introduce complexity in layers.

Players should not need to manage late-game levels of detail when operating a tiny airline. As the company grows, additional management capabilities, strategic decisions, and automation can become relevant.

Complexity should grow with the player's organization.

### One source of truth

Authoritative game-state structures and naming conventions must remain consistent.

`Data/Templates/template_reference.txt` (or its current canonical template-reference successor) is the source of truth for `game_state` naming and schema. The current folder tree must be respected when adding or modifying modules.

Avoid duplicate authoritative representations of the same state unless a system explicitly requires them and defines how synchronization is guaranteed.

### Build for expansion without premature complexity

Systems should not be intentionally limited to today's content, but future features should not be implemented before they are needed merely to make the architecture appear future-proof.

The goal is to provide clean extension points rather than speculative complexity.

### Build once, scale forward

Core systems should be architected so their underlying concepts remain useful as the player's airline grows from a small operation to a massive network.

This does not mean optimizing every feature for the final possible scale immediately. It means avoiding assumptions that would force the entire system to be replaced simply because the player acquired more aircraft, opened more hubs, or entered more countries.

## 5. Design Decision Test

When evaluating a new mechanic or major design choice, use the following questions as a guide:

1. Does it create an interesting business or management decision?
2. Does it behave in a believable way using recognizable aviation logic?
3. Can a player understand and enjoy it without professional aviation expertise?
4. Can the concept scale from a small airline toward a much larger operation?
5. Does it fit the broader Airline Tycoon architecture rather than overpowering unrelated systems?
6. Is the implementation complexity justified by the gameplay value it creates?

A feature does not need perfect realism. It needs enough realism to make its gameplay consequences believable.

---

## Foundation Summary

Airline Tycoon is an open-ended airline business tycoon built around the creation of profitable, scalable transportation networks. The player acts as CEO and may grow from direct management of a small airline into strategic control of a global aviation group, including future sister airlines, alliances, and large-scale infrastructure.

The game has no predefined ending. Growth itself is the sandbox: stronger networks, larger fleets, bigger hubs, new markets, and an increasingly interconnected world.

Real-world aviation provides the logic behind the simulation, but the project deliberately favors understandable gameplay, meaningful decisions, maintainable systems, and scalable architecture over unnecessary realism.

**Build a complete airline game. Build it to grow. Then keep expanding.**
