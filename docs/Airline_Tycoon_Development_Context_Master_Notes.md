# Airline Tycoon -- Development Context Master Notes

> **Purpose:** This document captures the major design decisions,
> architecture, gameplay philosophy, and roadmap discussed throughout
> the development of Airline Tycoon. It is intended as a persistent
> reference for future development and for any AI assistant working on
> the project.

------------------------------------------------------------------------

# Project Philosophy

The project follows a **"build the playable game first, then scale"**
philosophy.

The primary goal is not to implement every planned feature immediately,
but to establish a solid, expandable architecture.

Core principles:

-   Modular codebase
-   Schema-first development
-   Hybrid game_state
-   Easy expansion without major rewrites
-   Terminal-first development before GUI
-   Data-driven gameplay

------------------------------------------------------------------------

# V1.0 Core Gameplay Loop

1.  Create airline
2.  Choose first hub
3.  Buy aircraft
4.  Create routes
5.  Schedule flights
6.  Advance game days
7.  Earn revenue
8.  Expand fleet
9.  Expand hubs
10. Repeat

Everything else is designed to layer on top of this loop.

------------------------------------------------------------------------

# Hybrid Game State

The game uses a hybrid architecture:

-   player_info
-   airline_list
    -   hubs
    -   fleet
    -   routes
    -   finances
    -   subsidiaries
-   global references/indexes where appropriate

The active airline is determined by `current_focus`, making future
subsidiaries possible without redesigning saves.

------------------------------------------------------------------------

# Major Systems Discussed

## Hub Management

-   Hub-centric gameplay.
-   Aircraft belong to hubs.
-   Expansion through purchasing additional hubs.

## Fleet Management

-   Aircraft lifetime statistics.
-   Maintenance history.
-   Seat configuration.
-   Cargo/passenger balance.
-   Future freighter conversion.

## Route Management

-   Route creation.
-   Demand estimation.
-   Pricing.
-   Profitability.
-   Multiple aircraft assignment.

## Scheduling

Aircraft-centric schedule is the primary source.

Route schedule is maintained as a mirrored index for dashboards.

Future: - conflicts - delays - turnaround - maintenance blocks - flight
IDs

------------------------------------------------------------------------

# Demand Model

Base Demand:

Origin Population × Destination Population ÷ Distance Factor

Modifiers:

-   Tourism
-   Business activity
-   Luxury score
-   Seasonality
-   Holidays
-   Reputation
-   Difficulty
-   Ticket pricing

Longer routes have lower raw demand because fewer passengers naturally
travel very long distances, but revenue per passenger is higher.

------------------------------------------------------------------------

# Ticket Pricing (2020 Baseline)

Economy: - USD 0.12 per km

Multipliers:

-   Business ×2.2
-   First ×5.0

Future: - Inflation engine adjusts historical and future prices
automatically.

------------------------------------------------------------------------

# Inflation Engine

A single global economic model will influence:

-   Ticket prices
-   Aircraft prices
-   Fuel
-   Salaries
-   Airport fees
-   Maintenance
-   Taxes

Calculated yearly for performance.

Future volatility: - Fuel market ±50% - World events

------------------------------------------------------------------------

# Fuel System (Future)

Players may purchase:

-   Fuel tanks
-   Storage facilities

Fuel can be purchased during market lows and consumed over time.

Benefits:

-   Hedging
-   Bulk discounts
-   Airline influence discounts

------------------------------------------------------------------------

# Seat Configuration

Aircraft define cabin dimensions.

Seat types define:

-   width
-   pitch
-   comfort

Comfort affects:

-   reputation
-   premium demand
-   airline attractiveness

Cargo and passenger layouts are fully configurable in future versions.

------------------------------------------------------------------------

# Subsidiaries

Parent airlines may create subsidiaries.

Rules:

-   Separate finances
-   Fleet transfer allowed
-   Parent retains ownership

Future:

AI COO

AI CEO

Autonomous airline management

------------------------------------------------------------------------

# Online Vision

Standalone first.

Later:

-   Private multiplayer
-   Alliances
-   Shared demand
-   MMO worlds
-   Prestige seasons

Online ideas should never block offline development.

------------------------------------------------------------------------

# GUI

Backend first.

GUI stack:

-   Kivy

Future:

-   Interactive world map
-   Aircraft animation
-   Endless horizontal scrolling map

------------------------------------------------------------------------

# Coding Standards

-   Template-first development.
-   Data/Templates acts as source of truth.
-   Shared utilities belong in game/utils.
-   Package-specific functions remain inside their own package.
-   Avoid hardcoded values.
-   Expand through schemas, not ad hoc fields.

------------------------------------------------------------------------

# Current Development Priority

1.  Finish playable V1.0
2.  Polish scheduling
3.  Airport licensing
4.  Financial reports
5.  GUI
6.  AI competitors
7.  Prestige
8.  Online features

------------------------------------------------------------------------

# Notes

The project intentionally separates: - Current implementation - Planned
systems - Long-term ideas

Future additions should extend the architecture rather than replace it.
