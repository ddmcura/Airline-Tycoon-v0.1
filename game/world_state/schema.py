"""Concrete constants for the authoritative Stage 1 world schema."""

SAVE_SCHEMA_VERSION = 1
DEFAULT_GAME_VERSION = "0.1"
DEFAULT_REFERENCE_DATA_VERSION = "stage1-reference-v1"
MAX_ENTITY_ID_NUMBER = 999_999_999_999

ENTITY_TYPES = (
    "airline",
    "aircraft",
    "airport",
    "market",
    "connection",
    "schedule",
    "dated_flight",
    "booking",
    "itinerary",
    "transaction",
    "event",
    "account",
)

ENTITY_COLLECTIONS = {
    "airline": ("airlines", "airline_id"),
    "aircraft": ("aircraft", "aircraft_id"),
    "airport": ("airports", "airport_id"),
    "market": ("directional_markets", "market_id"),
    "connection": ("connections", "connection_id"),
    "schedule": ("schedule_definitions", "schedule_id"),
    "dated_flight": ("dated_flights", "dated_flight_id"),
    "booking": ("bookings", "booking_id"),
    "itinerary": ("itineraries", "itinerary_id"),
    "transaction": ("transactions", "transaction_id"),
    "event": ("pending_events", "event_id"),
    "account": ("financial_accounts", "account_id"),
}

WORLD_COLLECTIONS = tuple(
    collection for collection, _id_field in ENTITY_COLLECTIONS.values()
)

ACCOUNT_CATEGORIES = frozenset({"CASH", "ASSET", "LIABILITY", "REVENUE", "EXPENSE"})
REQUIRED_ACCOUNT_CODES = {
    "cash": "CASH",
    "aircraft_assets": "ASSET",
    "debt": "LIABILITY",
    "unflown_tickets": "LIABILITY",
    "passenger_revenue": "REVENUE",
    "operating_expenses": "EXPENSE",
}
AIRLINE_CONTROL_TYPES = frozenset({"PLAYER", "AI"})
AIRLINE_OWNER_TYPES = frozenset({"PLAYER", "INDEPENDENT", "AIRLINE"})

ENVELOPE_ROOTS = frozenset(
    {"metadata", "simulation", "deterministic_state", "world_state", "ui_state"}
)
WORLD_ROOTS = frozenset(
    {
        "player",
        "airports",
        "airlines",
        "aircraft",
        "directional_markets",
        "connections",
        "schedule_definitions",
        "dated_flights",
        "demand_state",
        "bookings",
        "itineraries",
        "active_aircraft_operations",
        "pending_events",
        "financial_accounts",
        "transactions",
        "history",
    }
)
