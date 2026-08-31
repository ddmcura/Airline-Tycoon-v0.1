"""Concrete constants for the authoritative Stage 1 world schema."""

SAVE_SCHEMA_VERSION = 1
LATEST_SAVE_SCHEMA_VERSION = 4
SUPPORTED_SAVE_SCHEMA_VERSIONS = frozenset({1, 2, 3, 4})
DEFAULT_GAME_VERSION = "0.1"
DEFAULT_REFERENCE_DATA_VERSION = "stage1-reference-v1"
MAX_ENTITY_ID_NUMBER = 999_999_999_999

CLOCK_STATES = frozenset({"PAUSED", "NORMAL", "FAST", "FAST_FORWARD"})
DEFAULT_CLOCK_RATIOS = {"NORMAL": 1, "FAST": 60}
DEFAULT_PUBLICATION_HORIZON_DAYS = 90
DEFAULT_MINIMUM_TURNAROUND_SECONDS = 30 * 60
BOOKING_CONFIGURATION_CONTRACT = "STAGE1_BOOKING_CONFIGURATION_V1"
BOOKING_CONFIGURATION_VERSION = "stage1-booking-v1"
BOOKING_CONFIGURATION_FINGERPRINT_CONTRACT = (
    "STAGE1_BOOKING_CONFIGURATION_SHA256_JSON_V1"
)
BOOKING_DESIRED_DATE_POLICY = "STAGE1_DESIRED_DATE_POLICY_V1"
LEGACY_BOOKING_CHOICE_POLICY_CONTRACT = "STAGE1_BOOKING_CHOICE_POLICY_V1"
BOOKING_CHOICE_POLICY_CONTRACT = "STAGE1_BALANCED_FARE_SCHEDULE_CHOICE_V1"
BOOKING_CURRENCY_POLICY = "SINGLE_CURRENCY_ONLY"
BOOKING_CHECKPOINT_STATUSES = frozenset({"PENDING", "COMPLETED"})
DIRECT_ECONOMY_ITINERARY_CONTRACT = "STAGE1_DIRECT_ECONOMY_ITINERARY_V1"
AGGREGATE_BOOKING_CONTRACT = "STAGE1_AGGREGATE_BOOKING_V1"
SCHEMA2_ITINERARY_COMPATIBILITY_CONTRACT = "SCHEMA2_ITINERARY_COMPATIBILITY_V1"
SCHEMA2_BOOKING_COMPATIBILITY_CONTRACT = "SCHEMA2_BOOKING_COMPATIBILITY_V1"
LEGACY_BOOKING_CHOICE_POLICY = {
    "contract": LEGACY_BOOKING_CHOICE_POLICY_CONTRACT,
    "production_input_families": ["FARE", "SCHEDULE"],
    "schedule_inputs": ["DATE_DEVIATION", "DEPARTURE_TIMING", "DURATION"],
    "absent_airline_quality_signals": "NEUTRAL",
    "deterministic_rank_usage": "INTEGER_RESIDUALS_AND_EXACT_TIES_ONLY",
    "currency_policy": BOOKING_CURRENCY_POLICY,
}
DEFAULT_BOOKING_CHOICE_POLICY = {
    "contract": BOOKING_CHOICE_POLICY_CONTRACT,
    "production_input_families": ["FARE", "SCHEDULE"],
    "schedule_inputs": ["DATE_DEVIATION", "DURATION"],
    "component_weights_bps": {
        "fare": 5_000,
        "desired_date_deviation": 3_000,
        "journey_duration": 2_000,
    },
    "outside_option_weight_score_units": 2_500,
    "absent_airline_quality_signals": "NEUTRAL",
    "deterministic_rank_usage": "INTEGER_RESIDUALS_AND_EXACT_TIES_ONLY",
    "currency_policy": BOOKING_CURRENCY_POLICY,
}
DEFAULT_BOOKING_CONFIGURATION = {
    "contract": BOOKING_CONFIGURATION_CONTRACT,
    "configuration_version": BOOKING_CONFIGURATION_VERSION,
    "revision": 2,
    "booking_horizon_days": 365,
    "desired_date_policy": BOOKING_DESIRED_DATE_POLICY,
    "lead_time_buckets": [
        {"minimum_lead_days": 0, "maximum_lead_days": 0, "weight_bps": 500},
        {"minimum_lead_days": 1, "maximum_lead_days": 6, "weight_bps": 1_500},
        {"minimum_lead_days": 7, "maximum_lead_days": 29, "weight_bps": 3_500},
        {"minimum_lead_days": 30, "maximum_lead_days": 89, "weight_bps": 3_000},
        {"minimum_lead_days": 90, "maximum_lead_days": 365, "weight_bps": 1_500},
    ],
    "desired_date_tolerance_days": 3,
    "choice_policy": DEFAULT_BOOKING_CHOICE_POLICY,
    "configuration_fingerprint": "",
}
FLIGHT_FULFILMENT_CONFIGURATION_CONTRACT = (
    "STAGE1_FLIGHT_FULFILMENT_CONFIGURATION_V1"
)
FLIGHT_FULFILMENT_CONFIGURATION_VERSION = "stage1-flight-fulfilment-v1"
FLIGHT_FULFILMENT_CONFIGURATION_FINGERPRINT_CONTRACT = (
    "STAGE1_FLIGHT_FULFILMENT_CONFIGURATION_SHA256_JSON_V1"
)
FLIGHT_FULFILMENT_FORMULA = "FIXED_CAPACITY_SEAT_BLOCK_MINUTE_V1"
FLIGHT_FULFILMENT_OPERATION_CONTRACT = "STAGE1_FLIGHT_FULFILMENT_OPERATION_V1"
FLIGHT_RESULT_CONTRACT = "STAGE1_FLIGHT_RESULT_V1"
FLIGHT_RESULT_VERSION = 1
FLIGHT_DEPARTURE_EVENT_TYPE = "STAGE1_FLIGHT_DEPARTURE"
FLIGHT_COMPLETION_EVENT_TYPE = "STAGE1_FLIGHT_COMPLETION"
FLIGHT_EVENT_PRIORITY = 100
FLIGHT_DEPARTURE_EVENT_CONTRACT = "STAGE1_FLIGHT_DEPARTURE_EVENT_V1"
FLIGHT_COMPLETION_EVENT_CONTRACT = "STAGE1_FLIGHT_COMPLETION_EVENT_V1"

# Revision-1 Balanced profiles are immutable accounting calibration, not FX.
# PHP and EUR use fixed 58/1 and 86/100 minor-unit calibration ratios against
# the USD reference respectively.  No runtime exchange-rate source is read.
DEFAULT_FLIGHT_FULFILMENT_CURRENCY_PROFILES = {
    "EUR": {
        "currency": "EUR",
        "calibration_reference_currency": "USD",
        "calibration_ratio_numerator": 86,
        "calibration_ratio_denominator": 100,
        "fixed_flight_cost_minor": 64_500,
        "capacity_cost_minor_per_seat": 258,
        "seat_block_minute_rate_numerator": 43,
        "seat_block_minute_rate_denominator": 200,
    },
    "PHP": {
        "currency": "PHP",
        "calibration_reference_currency": "USD",
        "calibration_ratio_numerator": 58,
        "calibration_ratio_denominator": 1,
        "fixed_flight_cost_minor": 4_350_000,
        "capacity_cost_minor_per_seat": 17_400,
        "seat_block_minute_rate_numerator": 29,
        "seat_block_minute_rate_denominator": 2,
    },
    "USD": {
        "currency": "USD",
        "calibration_reference_currency": "USD",
        "calibration_ratio_numerator": 1,
        "calibration_ratio_denominator": 1,
        "fixed_flight_cost_minor": 75_000,
        "capacity_cost_minor_per_seat": 300,
        "seat_block_minute_rate_numerator": 25,
        "seat_block_minute_rate_denominator": 100,
    },
}
DEFAULT_FLIGHT_FULFILMENT_CONFIGURATION = {
    "contract": FLIGHT_FULFILMENT_CONFIGURATION_CONTRACT,
    "configuration_version": FLIGHT_FULFILMENT_CONFIGURATION_VERSION,
    "current_revision": 1,
    "revisions": {
        "1": {
            "revision": 1,
            "formula_identifier": FLIGHT_FULFILMENT_FORMULA,
            "block_minute_rounding_policy": "CEILING_WHOLE_MINUTE_V1",
            "variable_cost_rounding_policy": "CEILING_MINOR_UNIT_V1",
            "currency_profiles": DEFAULT_FLIGHT_FULFILMENT_CURRENCY_PROFILES,
        }
    },
    "configuration_fingerprint": "",
}
DEMAND_MODEL_VERSION = 3
DEMAND_CONFIGURATION_VERSION = "stage1-model3-prototype-v1"
MODEL4_DEMAND_MODEL_VERSION = 4
MODEL4_DEMAND_CONFIGURATION_VERSION = "stage1-model4-travel-scope-v1"
DEMAND_ROUNDING_POLICY = "KEYED_SHA256_FRACTION_V1"
MODEL3_PROCESSED_COHORT_V1 = "MODEL3_PROCESSED_COHORT_V1"
MODEL4_TRAVEL_SCOPE_COHORT_V1 = "MODEL4_TRAVEL_SCOPE_COHORT_V1"
PROCESSED_COHORT_SCHEMA_VERSION = 2
TRAVEL_SCOPE_POLICY = "ORIGIN_COUNTRY_TRAVEL_SCOPE_ENVELOPE_V1"
TRAVEL_SCOPE_CONFIGURATION_VERSION = "stage1-alpha-v1"
MARKET_PACK_CONFIGURATION_CONTRACT = "MARKET_PACK_CONFIGURATION_V1"
LEGACY_MARKET_PACK_CONFIGURATION_VERSION = "stage1-empty-v1"
MARKET_PACK_CONFIGURATION_VERSION = "stage1-country-pack-v1"
MARKET_PACK_STATUSES = frozenset({"LATENT", "ENABLED", "DISABLED"})
TRAVEL_SCOPES = (
    "DOMESTIC",
    "HOME_REGION_INTERNATIONAL",
    "REST_OF_WORLD_INTERNATIONAL",
)
TRAVEL_SCOPE_PROFILE_FIELDS = (
    "domestic_weight_bps",
    "home_region_international_weight_bps",
    "rest_of_world_international_weight_bps",
)
DEFAULT_TRAVEL_SCOPE_PROFILE = {
    "domestic_weight_bps": 6_500,
    "home_region_international_weight_bps": 2_500,
    "rest_of_world_international_weight_bps": 1_000,
}
DEFAULT_MARKET_PACK_CONFIGURATION = {
    "contract": MARKET_PACK_CONFIGURATION_CONTRACT,
    "configuration_version": MARKET_PACK_CONFIGURATION_VERSION,
    "revision": 1,
    "market_pack_ids": [],
    "market_packs": {},
    "configuration_fingerprint": "",
}
DEFAULT_TRAVEL_SCOPE_CONFIGURATION = {
    "policy": TRAVEL_SCOPE_POLICY,
    "configuration_version": TRAVEL_SCOPE_CONFIGURATION_VERSION,
    "revision": 1,
    "reference_snapshot_version": None,
    "default_profile": DEFAULT_TRAVEL_SCOPE_PROFILE,
    "country_overrides": {},
}
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

SCHEMA2_ENTITY_TYPES = ENTITY_TYPES + ("region", "country")
SCHEMA3_ENTITY_TYPES = SCHEMA2_ENTITY_TYPES + ("booking_checkpoint",)
SCHEMA4_ENTITY_TYPES = SCHEMA3_ENTITY_TYPES

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

SCHEMA2_ENTITY_COLLECTIONS = {
    **ENTITY_COLLECTIONS,
    "region": ("regions", "region_id"),
    "country": ("countries", "country_id"),
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

SCHEMA2_WORLD_ROOTS = WORLD_ROOTS | frozenset({"regions", "countries"})
SCHEMA3_WORLD_ROOTS = SCHEMA2_WORLD_ROOTS | frozenset({"booking_state"})
SCHEMA4_WORLD_ROOTS = SCHEMA3_WORLD_ROOTS | frozenset({"flight_results"})
