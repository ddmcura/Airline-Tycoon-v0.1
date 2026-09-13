> **Historical reference — superseded for current development.**
> This file preserves earlier design and implementation context. Its authority
> claims, progress statements, roadmap, and assistant workflow instructions are
> historical, not current instructions. Use [AGENTS.md](../AGENTS.md) and the
> [documentation index](../Docs/README.md) for current authority and routing. Do not
> maintain this file as a parallel current specification or handoff.

# Airline Tycoon Project Context (Working Summary)

> Historical working summary. Current authority is defined in AGENTS.md.

## Project Vision

Airline Tycoon is a management simulation centered around building an
airline from a single hub into a global airline group.

Planned progression includes: - Single airline - Airline group /
subsidiaries - Fleet growth - Route expansion - Leasing - Maintenance -
Prestige - Airport licensing - Slot management - AI competitors - Billie
assistant - Future Kivy GUI

## Architecture

Current major modules: - Hub Management - Fleet Management - Aircraft
Market - Route Management - Scheduling - Airport browsing - Save/Load -
Game Loop

Design rules: - `template_reference.txt` is the schema source of
truth. - Package-specific helpers stay inside their package. - Shared
helpers belong in `game/utils`. - Follow the folder tree. - Update
schema before adding new persistent data.

## Game State

Hybrid game_state structure supporting: - airline_list - active
airline - room for future subsidiaries - centralized persistent save
data

## Gameplay Loop

1.  New Game
2.  Select Hub
3.  Buy Aircraft
4.  Create Routes
5.  Schedule Flights
6.  Advance Day
7.  Save / Load

## Data

Current understanding: - Airport reference data - Aircraft templates -
Airline save schema - Registration generation - Hub extraction

## Planned Systems

-   Leasing
-   Maintenance
-   Overhaul
-   Fuel economy
-   Inflation
-   Airport licensing
-   Slot purchasing
-   Prestige
-   AI COO / CEO
-   Billie assistant

## Coding Preferences

-   Keep naming consistent with templates.
-   Avoid duplicate schemas.
-   Prefer reusable utilities.
-   Keep package boundaries clean.

## What I Am Confident About

-   Overall architecture
-   Folder organization
-   Game state direction
-   Existing gameplay flow
-   Module responsibilities

## Current documentation

Current durable memory is maintained in the canonical documentation linked above.
