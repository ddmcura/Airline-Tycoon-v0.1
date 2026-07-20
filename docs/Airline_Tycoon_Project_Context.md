# Airline Tycoon Project Context (Working Summary)

> This document summarizes the current project context I understand. It
> is **not** the source of truth. `template_reference.txt` and the
> codebase remain authoritative.

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

## What Should Be Added Later

As development continues, keep this file updated with: - Major
architecture decisions - New persistent schemas - Gameplay rules -
Economy formulas - Scheduling rules - Save format changes - Design
decisions

## Recommendation

Create a permanent `Documentation/Project_Context.md` in the repository
and update it whenever a major design decision is made. This gives every
future chat (and future versions of ChatGPT) a concise, authoritative
overview without needing to reconstruct months of conversation.
