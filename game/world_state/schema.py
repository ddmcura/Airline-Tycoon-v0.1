"""Concrete constants for the authoritative Stage 1 world schema."""

SAVE_SCHEMA_VERSION = 1
DEFAULT_GAME_VERSION = "0.1"
DEFAULT_REFERENCE_DATA_VERSION = "stage1-reference-v1"
MAX_ENTITY_ID_NUMBER = 999_999_999_999

CLOCK_STATES = frozenset({"PAUSED", "NORMAL", "FAST", "FAST_FORWARD"})
DEFAULT_CLOCK_RATIOS = {"NORMAL": 1, "FAST": 60}
DEFAULT_PUBLICATION_HORIZON_DAYS = 90
DEFAULT_MINIMUM_TURNAROUND_SECONDS = 30 * 60
DEMAND_MODEL_VERSION = 3
DEMAND_CONFIGURATION_VERSION = "stage1-model3-prototype-v1"
DEMAND_ROUNDING_POLICY = "KEYED_SHA256_FRACTION_V1"
DEMAND_DESTINATION_TYPES = (
    "MEGA_GLOBAL_CITY",
    "CAPITAL_MAJOR_CITY",
    "MAJOR_REGIONAL_CITY",
    "NORMAL_CITY",
    "SMALL_REGIONAL_CITY",
    "MINOR_CITY",
)
DEMAND_MULTIPLIER_CATEGORIES = (
    "date_season",
    "holiday",
    "world",
    "other",
)
DEFAULT_DEMAND_CONFIGURATION = {
    "model_version": DEMAND_MODEL_VERSION,
    "configuration_version": DEMAND_CONFIGURATION_VERSION,
    "revision": 1,
    # The legacy Model 3 prototype rate is retained; the approved specification
    # replaces its unnormalised pair-share and distance formulas.
    "daily_booker_rate_ppm": 4_000,
    "distance_scale_km": 2_000,
    "destination_type_weight_bps": {
        "MEGA_GLOBAL_CITY": 14_000,
        "CAPITAL_MAJOR_CITY": 12_500,
        "MAJOR_REGIONAL_CITY": 11_000,
        "NORMAL_CITY": 10_000,
        "SMALL_REGIONAL_CITY": 8_000,
        "MINOR_CITY": 6_500,
    },
    "same_country_weight_bps": 12_500,
    "international_weight_bps": 10_000,
    "relationship_weight_bps": 10_000,
    "daily_multiplier_min_bps": 0,
    "daily_multiplier_max_bps": 100_000,
}
PENDING_EVENT_STATUS = "PENDING"
TERMINAL_EVENT_STATUSES = frozenset(
    {"COMPLETED", "CANCELLED", "SUPERSEDED", "STALE"}
)

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
SCHEDULE_STATUSES = frozenset({"DRAFT", "ACTIVE", "RETIRED"})
DATED_FLIGHT_STATUSES = frozenset(
    {"PLANNED", "SUPERSEDED", "OPERATIONALLY_LOCKED", "COMPLETED", "CANCELLED"}
)
SCHEDULE_SERVICE_TYPES = frozenset({"PASSENGER", "DEADHEAD"})
PASSENGER_SERVICE_CLASSIFICATIONS = frozenset({"ECONOMY", "NON_PASSENGER"})

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
        "event_history",
        "financial_accounts",
        "transactions",
        "history",
    }
)
