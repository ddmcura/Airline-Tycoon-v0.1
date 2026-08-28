"""Strict, side-effect-free validation for Stage 1 authoritative worlds."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import reduce
from operator import mul
from zoneinfo import ZoneInfoNotFoundError

from .ids import parse_entity_id
from .booking_validation import validate_schema3_booking_authority
from .demand_fingerprint import (
    calculate_demand_cohort_fingerprint,
    calculate_demand_input_fingerprint,
    calculate_model4_input_fingerprint,
    calculate_model4_cohort_fingerprint,
    calculate_model4_revision_context_fingerprint,
    calculate_market_pack_fingerprint,
)
from .money import is_minor_amount
from .schema import (
    ACCOUNT_CATEGORIES,
    AIRLINE_CONTROL_TYPES,
    AIRLINE_OWNER_TYPES,
    CLOCK_STATES,
    DATED_FLIGHT_STATUSES,
    DEMAND_DESTINATION_TYPES,
    DEMAND_MODEL_VERSION,
    DEMAND_MULTIPLIER_CATEGORIES,
    DEMAND_ROUNDING_POLICY,
    DEFAULT_TRAVEL_SCOPE_PROFILE,
    ENVELOPE_ROOTS,
    ENTITY_COLLECTIONS,
    ENTITY_TYPES,
    LEGACY_MARKET_PACK_CONFIGURATION_VERSION,
    MARKET_PACK_CONFIGURATION_CONTRACT,
    MARKET_PACK_STATUSES,
    MAX_ENTITY_ID_NUMBER,
    MODEL3_PROCESSED_COHORT_V1,
    MODEL4_DEMAND_MODEL_VERSION,
    MODEL4_TRAVEL_SCOPE_COHORT_V1,
    PASSENGER_SERVICE_CLASSIFICATIONS,
    PENDING_EVENT_STATUS,
    PROCESSED_COHORT_SCHEMA_VERSION,
    REQUIRED_ACCOUNT_CODES,
    SCHEMA2_ENTITY_COLLECTIONS,
    SCHEMA2_ENTITY_TYPES,
    SCHEMA2_WORLD_ROOTS,
    SCHEMA3_ENTITY_TYPES,
    SCHEMA3_WORLD_ROOTS,
    SCHEDULE_SERVICE_TYPES,
    SCHEDULE_STATUSES,
    SUPPORTED_SAVE_SCHEMA_VERSIONS,
    TERMINAL_EVENT_STATUSES,
    TRAVEL_SCOPE_POLICY,
    TRAVEL_SCOPE_PROFILE_FIELDS,
    WORLD_ROOTS,
)
from .serialization import json_compatibility_error
from .timezones import load_named_timezone
from .timestamps import is_canonical_utc, parse_canonical_utc


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    recoverable: bool = False

    def as_dict(self):
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "recoverable": self.recoverable,
        }


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[ValidationIssue, ...]

    @property
    def is_valid(self):
        return not self.errors

    def as_dict(self):
        return {"is_valid": self.is_valid, "errors": [error.as_dict() for error in self.errors]}

    def __bool__(self):
        return self.is_valid


def _canonical_utc(value):
    return is_canonical_utc(value)


def _currency_code(value):
    return (
        isinstance(value, str)
        and len(value) == 3
        and value.isascii()
        and value.isalpha()
        and value == value.upper()
    )


def _container_alias_error(value):
    """Return the first repeated mutable-container path in schema-3 authority."""
    seen = {}
    stack = [(value, "$")]
    while stack:
        item, path = stack.pop()
        if type(item) not in (dict, list):
            continue
        marker = id(item)
        previous = seen.get(marker)
        if previous is not None:
            return path, previous
        seen[marker] = path
        if type(item) is dict:
            for key, nested in item.items():
                stack.append((nested, f"{path}.{key}"))
        else:
            for index, nested in enumerate(item):
                stack.append((nested, f"{path}[{index}]"))
    return None


def _local_date(value):
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _local_time(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        return False
    return (
        parsed.tzinfo is None
        and parsed.microsecond == 0
        and parsed.strftime("%H:%M:%S") == value
    )


def _named_timezone(value):
    if not isinstance(value, str) or not value:
        return False
    try:
        load_named_timezone(value)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def _resolved_local_utc(local_date, local_time, fold, timezone_name):
    """Return canonical UTC for valid named local intent, otherwise ``None``."""
    if not _local_date(local_date) or not _local_time(local_time):
        return None
    if isinstance(fold, bool) or fold not in (0, 1) or not _named_timezone(timezone_name):
        return None
    zone = load_named_timezone(timezone_name)
    naive = datetime.combine(date.fromisoformat(local_date), time.fromisoformat(local_time))
    aware = naive.replace(tzinfo=zone, fold=fold)
    resolved = aware.astimezone(timezone.utc)
    round_trip = resolved.astimezone(zone)
    if round_trip.replace(tzinfo=None) != naive or round_trip.fold != fold:
        return None
    return resolved.strftime("%Y-%m-%dT%H:%M:%SZ")


class _Validator:
    def __init__(self, envelope):
        self.envelope = envelope
        self.errors = []
        self.world = {}
        self.schema_version = None

    def add(self, code, path, message, entity_type=None, entity_id=None):
        self.errors.append(ValidationIssue(code, path, message, entity_type, entity_id))

    def require_mapping(self, value, path):
        if type(value) is not dict:
            self.add("invalid_type", path, "must be a dictionary")
            return {}
        return value

    def require_text(self, record, field, path, entity_type=None, entity_id=None):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            self.add("malformed_required_field", f"{path}.{field}", "must be a non-empty string", entity_type, entity_id)
            return None
        return value

    def require_ref(self, record, field, targets, path, entity_type, entity_id, optional=False):
        value = record.get(field)
        if optional and value is None:
            return None
        if not isinstance(value, str) or value not in targets:
            self.add("dangling_reference", f"{path}.{field}", f"must reference an existing {field.removesuffix('_id')}", entity_type, entity_id)
            return None
        return value

    def require_timestamp(self, record, field, path, entity_type=None, entity_id=None, optional=False):
        value = record.get(field)
        if optional and value is None:
            return None
        if not _canonical_utc(value):
            self.add("invalid_timestamp", f"{path}.{field}", "must be canonical UTC YYYY-MM-DDTHH:MM:SSZ", entity_type, entity_id)
            return None
        return value

    def _validate_scope_profile(self, profile, path, *, require_alpha_default=False):
        profile = self.require_mapping(profile, path)
        if set(profile) != set(TRAVEL_SCOPE_PROFILE_FIELDS):
            self.add(
                "invalid_travel_scope_profile",
                path,
                "must contain exactly the three canonical travel-scope weights",
            )
            return
        total = 0
        valid = True
        for field in TRAVEL_SCOPE_PROFILE_FIELDS:
            value = profile.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                valid = False
                self.add(
                    "invalid_travel_scope_profile",
                    f"{path}.{field}",
                    "must be a non-negative integer basis-point weight",
                )
            else:
                total += value
        if valid and total != 10_000:
            self.add(
                "invalid_travel_scope_profile",
                path,
                "the three canonical weights must sum to 10000",
            )
        if require_alpha_default and dict(profile) != DEFAULT_TRAVEL_SCOPE_PROFILE:
            self.add(
                "invalid_travel_scope_profile",
                path,
                "the Alpha V1 default must be exactly 6500/2500/1000",
            )

    def _validate_schema2_demand_configuration(self, demand_configuration):
        market_path = "$.simulation.configuration.demand.market_pack_configuration"
        market = self.require_mapping(
            demand_configuration.get("market_pack_configuration"), market_path
        )
        legacy_market_configuration = (
            market.get("configuration_version")
            == LEGACY_MARKET_PACK_CONFIGURATION_VERSION
            and set(market)
            == {"contract", "configuration_version", "revision", "market_pack_ids"}
        )
        expected_market_fields = {"contract", "configuration_version", "revision", "market_pack_ids"} if legacy_market_configuration else {
            "contract",
            "configuration_version",
            "revision",
            "market_pack_ids",
            "market_packs",
            "configuration_fingerprint",
        }
        if set(market) != expected_market_fields:
            self.add(
                "invalid_market_pack_configuration",
                market_path,
                f"fields must be exactly {sorted(expected_market_fields)}",
            )
        if market.get("contract") != MARKET_PACK_CONFIGURATION_CONTRACT:
            self.add("invalid_market_pack_configuration", f"{market_path}.contract", f"must equal {MARKET_PACK_CONFIGURATION_CONTRACT}")
        self.require_text(market, "configuration_version", market_path)
        revision = market.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            self.add("invalid_market_pack_configuration", f"{market_path}.revision", "must be a positive integer")
        pack_ids = market.get("market_pack_ids")
        packs = market.get("market_packs", {})
        if not isinstance(pack_ids, list) or any(
            not isinstance(pack_id, str) or not pack_id or pack_id != pack_id.strip()
            for pack_id in pack_ids
        ) or (all(isinstance(pack_id, str) for pack_id in pack_ids) and pack_ids != sorted(set(pack_ids))):
            self.add("invalid_market_pack_configuration", f"{market_path}.market_pack_ids", "must be a sorted unique list of non-empty pack IDs")
            pack_ids = []
        if type(packs) is not dict:
            self.add("invalid_market_pack_configuration", f"{market_path}.market_packs", "must be a dictionary keyed by pack ID")
            packs = {}
        if set(pack_ids) != set(packs):
            self.add("invalid_market_pack_configuration", market_path, "market_pack_ids must identify every pack exactly once")
            if pack_ids and not packs:
                self.add("premature_market_pack_activation", f"{market_path}.market_pack_ids", "pack IDs cannot be introduced without complete lifecycle authority")
        countries = self.envelope.get("world_state", {}).get("countries", {})
        airports = self.envelope.get("world_state", {}).get("airports", {})
        country_owners = {}
        reference_owners = {}
        catalog_owners = {}
        mapped_airport_owners = {}
        for pack_id, pack in packs.items():
            path = f"{market_path}.market_packs.{pack_id}"
            fields = {
                "market_pack_id", "country_id", "pack_reference", "pack_version",
                "status", "status_effective_date", "catalog_airport_ids",
                "airport_id_by_catalog_id",
            }
            if type(pack) is not dict or set(pack) != fields:
                self.add("invalid_market_pack_configuration", path, f"fields must be exactly {sorted(fields)}")
                continue
            if pack.get("market_pack_id") != pack_id:
                self.add("id_key_mismatch", f"{path}.market_pack_id", "must equal the collection key")
            country_id = pack.get("country_id")
            if not isinstance(country_id, str) or country_id not in countries:
                self.add("invalid_market_pack_configuration", f"{path}.country_id", "must reference an immutable country ID")
            elif country_id in country_owners:
                self.add("invalid_market_pack_configuration", f"{path}.country_id", "a country may own only one market pack")
            else:
                country_owners[country_id] = pack_id
            for field in ("pack_reference", "pack_version"):
                if (
                    not isinstance(pack.get(field), str)
                    or not pack[field]
                    or pack[field] != pack[field].strip()
                ):
                    self.add("invalid_market_pack_configuration", f"{path}.{field}", "must be a canonical non-empty string")
            reference = pack.get("pack_reference")
            if isinstance(reference, str) and reference:
                previous = reference_owners.get(reference)
                if previous is not None:
                    self.add("invalid_market_pack_configuration", f"{path}.pack_reference", f"pack reference is already owned by {previous}")
                else:
                    reference_owners[reference] = pack_id
            status = pack.get("status")
            if not isinstance(status, str) or status not in MARKET_PACK_STATUSES:
                self.add("invalid_market_pack_configuration", f"{path}.status", f"must be one of {sorted(MARKET_PACK_STATUSES)}")
            effective = pack.get("status_effective_date")
            if effective is not None and not _local_date(effective):
                self.add("invalid_market_pack_configuration", f"{path}.status_effective_date", "must be null or canonical YYYY-MM-DD")
            catalog_ids = pack.get("catalog_airport_ids")
            mapping = pack.get("airport_id_by_catalog_id")
            if not isinstance(catalog_ids, list) or any(
                not isinstance(value, str) or not value or value != value.strip()
                for value in catalog_ids
            ) or catalog_ids != sorted(set(catalog_ids)):
                self.add("invalid_market_pack_configuration", f"{path}.catalog_airport_ids", "must be a sorted unique list of non-empty catalog airport IDs")
                catalog_ids = []
            if type(mapping) is not dict or set(mapping) != set(catalog_ids):
                self.add("invalid_market_pack_configuration", f"{path}.airport_id_by_catalog_id", "must map every catalog airport ID exactly once")
                mapping = {}
            if status == "LATENT" and (catalog_ids or mapping):
                self.add("invalid_market_pack_configuration", path, "a LATENT pack cannot own materialized airport mappings")
            if status != "LATENT" and not catalog_ids:
                self.add("invalid_market_pack_configuration", path, "an ENABLED or DISABLED pack must own at least one airport mapping")
            for catalog_id, airport_id in mapping.items():
                previous_catalog = catalog_owners.get(catalog_id)
                if previous_catalog is not None:
                    self.add("invalid_market_pack_configuration", f"{path}.airport_id_by_catalog_id.{catalog_id}", f"catalog airport ID is already owned by {previous_catalog}")
                else:
                    catalog_owners[catalog_id] = pack_id
                if not isinstance(airport_id, str):
                    previous_airport = None
                    airport = None
                    self.add("invalid_market_pack_configuration", f"{path}.airport_id_by_catalog_id.{catalog_id}", "must reference a materialized airport")
                else:
                    previous_airport = mapped_airport_owners.get(airport_id)
                    if previous_airport is not None:
                        self.add("invalid_market_pack_configuration", f"{path}.airport_id_by_catalog_id.{catalog_id}", f"world airport is already owned by {previous_airport}")
                    else:
                        mapped_airport_owners[airport_id] = pack_id
                    airport = airports.get(airport_id) if isinstance(airports, dict) else None
                if isinstance(airport_id, str) and type(airport) is not dict:
                    self.add("invalid_market_pack_configuration", f"{path}.airport_id_by_catalog_id.{catalog_id}", "must reference a materialized airport")
                elif type(airport) is dict and airport.get("country_id") != country_id:
                    self.add("invalid_market_pack_configuration", f"{path}.airport_id_by_catalog_id.{catalog_id}", "mapped airport must belong to the pack country")
                elif type(airport) is dict and airport.get("demand_allocation_member") is not True:
                    self.add("invalid_market_pack_configuration", f"{path}.airport_id_by_catalog_id.{catalog_id}", "mapped airport must be an allocation member")
        if legacy_market_configuration:
            if pack_ids != []:
                self.add("premature_market_pack_activation", f"{market_path}.market_pack_ids", "legacy pack configuration must remain empty until atomic materialization")
        else:
            fingerprint = market.get("configuration_fingerprint")
            if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(character not in "0123456789abcdef" for character in fingerprint):
                self.add("invalid_market_pack_configuration", f"{market_path}.configuration_fingerprint", "must be lowercase SHA-256 text")
            else:
                try:
                    expected_fingerprint = calculate_market_pack_fingerprint(self.envelope)
                except (KeyError, OverflowError, RecursionError, TypeError, ValueError):
                    expected_fingerprint = None
                if fingerprint != expected_fingerprint:
                    self.add("inconsistent_pack_fingerprint", f"{market_path}.configuration_fingerprint", "stored pack configuration does not match its witness")

        travel_path = "$.simulation.configuration.demand.travel_scope_configuration"
        travel = self.require_mapping(
            demand_configuration.get("travel_scope_configuration"), travel_path
        )
        expected_travel_fields = {
            "policy",
            "configuration_version",
            "revision",
            "reference_snapshot_version",
            "default_profile",
            "country_overrides",
        }
        if set(travel) != expected_travel_fields:
            self.add(
                "invalid_travel_scope_configuration",
                travel_path,
                f"fields must be exactly {sorted(expected_travel_fields)}",
            )
        if travel.get("policy") != TRAVEL_SCOPE_POLICY:
            self.add("invalid_travel_scope_policy", f"{travel_path}.policy", f"must equal {TRAVEL_SCOPE_POLICY}")
        for field in ("configuration_version", "reference_snapshot_version"):
            self.require_text(travel, field, travel_path)
        revision = travel.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            self.add("invalid_travel_scope_configuration", f"{travel_path}.revision", "must be a positive integer")
        self._validate_scope_profile(
            travel.get("default_profile"),
            f"{travel_path}.default_profile",
            require_alpha_default=True,
        )
        overrides = self.require_mapping(
            travel.get("country_overrides"), f"{travel_path}.country_overrides"
        )
        for country_id, profile in overrides.items():
            if not isinstance(country_id, str):
                self.add("invalid_travel_scope_override", f"{travel_path}.country_overrides", "override keys must be immutable country IDs")
                continue
            self._validate_scope_profile(
                profile, f"{travel_path}.country_overrides.{country_id}"
            )

    def _validate_model4_revision_contexts(self, demand):
        contexts = self.require_mapping(
            demand.get("model4_revision_contexts"),
            "$.world_state.demand_state.model4_revision_contexts",
        )
        fields = {
            "revision_context_id",
            "demand_model_version",
            "demand_model_revision",
            "configuration_version",
            "configuration_revision",
            "universe_date",
            "travel_scope_configuration_version",
            "travel_scope_revision",
            "market_pack_configuration_version",
            "market_pack_revision",
            "daily_multiplier_min_bps",
            "daily_multiplier_max_bps",
            "country_reference_snapshot_version",
            "model4_input_fingerprint",
            "context_fingerprint",
        }
        for context_id, context in contexts.items():
            path = f"$.world_state.demand_state.model4_revision_contexts.{context_id}"
            if not isinstance(context_id, str) or type(context) is not dict:
                self.add("invalid_model4_revision_context", path, "must be a string-keyed mapping")
                continue
            if set(context) != fields:
                self.add("invalid_model4_revision_context", path, f"fields must be exactly {sorted(fields)}")
            if context.get("revision_context_id") != context_id:
                self.add("id_key_mismatch", f"{path}.revision_context_id", "must equal the collection key")
            if context.get("demand_model_version") != 4 or isinstance(context.get("demand_model_version"), bool):
                self.add("invalid_model4_revision_context", f"{path}.demand_model_version", "must equal 4")
            for field in ("demand_model_revision", "configuration_revision", "travel_scope_revision", "market_pack_revision"):
                value = context.get(field)
                if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                    self.add("invalid_model4_revision_context", f"{path}.{field}", "must be a positive integer")
            minimum = context.get("daily_multiplier_min_bps")
            maximum = context.get("daily_multiplier_max_bps")
            if (
                isinstance(minimum, bool)
                or not isinstance(minimum, int)
                or minimum < 0
                or isinstance(maximum, bool)
                or not isinstance(maximum, int)
                or maximum < minimum
            ):
                self.add("invalid_model4_revision_context", path, "multiplier bounds must be ordered non-negative integers")
            if not _local_date(context.get("universe_date")):
                self.add("invalid_local_date", f"{path}.universe_date", "must be canonical YYYY-MM-DD")
            for field in (
                "configuration_version",
                "travel_scope_configuration_version",
                "market_pack_configuration_version",
                "country_reference_snapshot_version",
            ):
                self.require_text(context, field, path)
            for field in ("model4_input_fingerprint", "context_fingerprint"):
                value = context.get(field)
                if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                    self.add("invalid_model4_revision_context_fingerprint", f"{path}.{field}", "must be lowercase SHA-256 text")
            if isinstance(context.get("context_fingerprint"), str):
                try:
                    expected = calculate_model4_revision_context_fingerprint(context)
                except (KeyError, OverflowError, RecursionError, TypeError, ValueError):
                    expected = None
                if expected != context.get("context_fingerprint"):
                    self.add("inconsistent_model4_revision_context_fingerprint", f"{path}.context_fingerprint", "stored context does not match its integrity witness")
        return contexts

    def _validate_model4_cohort(self, wrapper, cohort_key, markets, contexts, path):
        payload = self.require_mapping(wrapper.get("payload"), f"{path}.payload")
        fields = {
            "cohort_key",
            "market_id",
            "cohort_date",
            "demand_model_revision",
            "revision_context_id",
            "daily_multipliers_bps",
            "composite_multiplier_ppm",
            "travel_scope_bookers",
            "actual_daily_bookers",
            "rounding_policy",
            "resolution_fingerprint",
        }
        if set(payload) != fields:
            self.add("invalid_demand_cohort", f"{path}.payload", f"fields must be exactly {sorted(fields)}", "demand_cohort", str(cohort_key))
        if payload.get("cohort_key") != cohort_key:
            self.add("id_key_mismatch", f"{path}.payload.cohort_key", "must equal the collection key", "demand_cohort", str(cohort_key))
        market_id = payload.get("market_id")
        cohort_date = payload.get("cohort_date")
        if not isinstance(market_id, str) or market_id not in markets:
            self.add("dangling_reference", f"{path}.payload.market_id", "must reference an existing directional market", "demand_cohort", str(cohort_key))
        if not _local_date(cohort_date):
            self.add("invalid_local_date", f"{path}.payload.cohort_date", "must be canonical YYYY-MM-DD", "demand_cohort", str(cohort_key))
        if isinstance(market_id, str) and _local_date(cohort_date) and cohort_key != f"{market_id}@{cohort_date}":
            self.add("invalid_demand_cohort_key", f"{path}.payload.cohort_key", "must equal market_id@cohort_date", "demand_cohort", str(cohort_key))
        context_id = payload.get("revision_context_id")
        if not isinstance(context_id, str) or context_id not in contexts:
            self.add("dangling_reference", f"{path}.payload.revision_context_id", "must reference a Model 4 revision context", "demand_cohort", str(cohort_key))
        revision = payload.get("demand_model_revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            self.add("invalid_demand_revision", f"{path}.payload.demand_model_revision", "must be a positive integer", "demand_cohort", str(cohort_key))
        elif isinstance(context_id, str) and context_id in contexts and revision != contexts[context_id].get("demand_model_revision"):
            self.add("inconsistent_demand_revision", f"{path}.payload.demand_model_revision", "must equal its revision context", "demand_cohort", str(cohort_key))
        scopes = self.require_mapping(payload.get("travel_scope_bookers"), f"{path}.payload.travel_scope_bookers")
        canonical_scopes = {"DOMESTIC", "HOME_REGION_INTERNATIONAL", "REST_OF_WORLD_INTERNATIONAL"}
        if set(scopes) != canonical_scopes:
            self.add("invalid_travel_scope_cohort", f"{path}.payload.travel_scope_bookers", "must contain exactly the three canonical scopes", "demand_cohort", str(cohort_key))
        for scope, value in scopes.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                self.add("invalid_travel_scope_cohort", f"{path}.payload.travel_scope_bookers.{scope}", "must be a non-negative integer", "demand_cohort", str(cohort_key))
        for field in ("actual_daily_bookers",):
            value = payload.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                self.add("invalid_demand_cohort", f"{path}.payload.{field}", "must be a non-negative integer", "demand_cohort", str(cohort_key))
        multipliers = self.require_mapping(payload.get("daily_multipliers_bps"), f"{path}.payload.daily_multipliers_bps")
        if tuple(multipliers) != DEMAND_MULTIPLIER_CATEGORIES:
            self.add("invalid_demand_multipliers", f"{path}.payload.daily_multipliers_bps", "must contain the canonical multiplier categories in order", "demand_cohort", str(cohort_key))
        context = contexts.get(context_id) if isinstance(context_id, str) else None
        minimum = context.get("daily_multiplier_min_bps") if isinstance(context, dict) else None
        maximum = context.get("daily_multiplier_max_bps") if isinstance(context, dict) else None
        valid_multipliers = tuple(multipliers) == DEMAND_MULTIPLIER_CATEGORIES
        for category, value in multipliers.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not isinstance(minimum, int)
                or isinstance(minimum, bool)
                or not isinstance(maximum, int)
                or isinstance(maximum, bool)
                or value < minimum
                or value > maximum
            ):
                valid_multipliers = False
                self.add("invalid_demand_multipliers", f"{path}.payload.daily_multipliers_bps.{category}", "must be an integer basis-point value within its revision context bounds", "demand_cohort", str(cohort_key))
        composite = payload.get("composite_multiplier_ppm")
        if isinstance(composite, bool) or not isinstance(composite, int) or composite < 0:
            self.add("invalid_demand_cohort", f"{path}.payload.composite_multiplier_ppm", "must be a non-negative integer", "demand_cohort", str(cohort_key))
        elif valid_multipliers:
            numerator = reduce(
                mul,
                (multipliers[category] for category in DEMAND_MULTIPLIER_CATEGORIES),
                1,
            ) * 1_000_000
            denominator = 10_000 ** len(DEMAND_MULTIPLIER_CATEGORIES)
            expected_composite, remainder = divmod(numerator, denominator)
            comparison = remainder * 2 - denominator
            if comparison > 0 or (
                comparison == 0 and expected_composite % 2 == 1
            ):
                expected_composite += 1
            if composite != expected_composite:
                self.add("inconsistent_demand_cohort", f"{path}.payload.composite_multiplier_ppm", "must be the half-even parts-per-million composition of the stored multipliers", "demand_cohort", str(cohort_key))
        if payload.get("rounding_policy") != DEMAND_ROUNDING_POLICY:
            self.add("invalid_demand_rounding_policy", f"{path}.payload.rounding_policy", f"must equal {DEMAND_ROUNDING_POLICY}", "demand_cohort", str(cohort_key))
        try:
            expected = calculate_model4_cohort_fingerprint(self.envelope, wrapper)
        except (KeyError, OverflowError, RecursionError, TypeError, ValueError):
            expected = None
        if payload.get("resolution_fingerprint") != expected:
            self.add("inconsistent_demand_cohort_fingerprint", f"{path}.payload.resolution_fingerprint", "stored Model 4 cohort does not match the V2 integrity witness", "demand_cohort", str(cohort_key))

    def validate_root(self):
        if type(self.envelope) is not dict:
            self.add("invalid_envelope", "$", "world envelope must be a dictionary")
            return False
        serialization_error = json_compatibility_error(self.envelope)
        if serialization_error:
            path, message = serialization_error
            self.add("not_json_compatible", path, message)
        for key in ENVELOPE_ROOTS:
            if key not in self.envelope:
                self.add("missing_root", f"$.{key}", "required root is missing")
        for key in sorted(set(self.envelope) - ENVELOPE_ROOTS, key=repr):
            self.add("unknown_root", f"$.{key}", "field is not part of schema version 1")
        metadata = self.require_mapping(self.envelope.get("metadata"), "$.metadata")
        schema_version = metadata.get("save_schema_version")
        if (
            type(schema_version) is not int
            or schema_version not in SUPPORTED_SAVE_SCHEMA_VERSIONS
        ):
            self.add("unsupported_schema_version", "$.metadata.save_schema_version", f"must be one of {sorted(SUPPORTED_SAVE_SCHEMA_VERSIONS)}")
        else:
            self.schema_version = schema_version
            if schema_version == 3:
                alias = _container_alias_error(self.envelope)
                if alias is not None:
                    path, previous = alias
                    self.add(
                        "invalid_world_state",
                        path,
                        f"authoritative mutable container aliases {previous}",
                    )
        for field in ("game_version", "reference_data_version", "lineage_id"):
            self.require_text(metadata, field, "$.metadata")
        self.require_timestamp(metadata, "world_created_at_utc", "$.metadata")

        simulation = self.require_mapping(self.envelope.get("simulation"), "$.simulation")
        self.require_timestamp(simulation, "time_utc", "$.simulation")
        clock_state = simulation.get("clock_state")
        if not isinstance(clock_state, str) or clock_state not in CLOCK_STATES:
            self.add("invalid_clock_state", "$.simulation.clock_state", "must be a canonical clock mode")
        cursor = simulation.get("event_order_cursor")
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
            self.add("invalid_event_cursor", "$.simulation.event_order_cursor", "must be a non-negative integer")
        configuration = self.require_mapping(simulation.get("configuration"), "$.simulation.configuration")
        configuration_fields = {
            "difficulty",
            "clock_ratios",
            "scheduling",
            "demand",
        }
        if self.schema_version == 3:
            configuration_fields.add("booking")
        for field in sorted(set(configuration) - configuration_fields, key=repr):
            self.add(
                "unknown_authoritative_field",
                f"$.simulation.configuration.{field}",
                f"field is not part of schema version {self.schema_version}",
            )
        self.require_text(configuration, "difficulty", "$.simulation.configuration")
        ratios = self.require_mapping(configuration.get("clock_ratios"), "$.simulation.configuration.clock_ratios")
        for mode in ("NORMAL", "FAST"):
            ratio = ratios.get(mode)
            if isinstance(ratio, bool) or not isinstance(ratio, int) or ratio < 1:
                self.add("invalid_clock_ratio", f"$.simulation.configuration.clock_ratios.{mode}", "must be a positive integer")
        for mode in sorted(set(ratios) - {"NORMAL", "FAST"}, key=repr):
            self.add("unknown_clock_ratio", f"$.simulation.configuration.clock_ratios.{mode}", "ratio is not part of the Stage 1 clock")
        scheduling = self.require_mapping(
            configuration.get("scheduling"),
            "$.simulation.configuration.scheduling",
        )
        horizon = scheduling.get("publication_horizon_days")
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
            self.add(
                "invalid_publication_horizon",
                "$.simulation.configuration.scheduling.publication_horizon_days",
                "must be a positive integer number of days",
            )
        elif _canonical_utc(simulation.get("time_utc")):
            try:
                parse_canonical_utc(simulation["time_utc"]) + timedelta(days=horizon)
            except OverflowError:
                self.add(
                    "invalid_publication_horizon",
                    "$.simulation.configuration.scheduling.publication_horizon_days",
                    "extends beyond the supported timestamp range",
                )
        turnaround = scheduling.get("minimum_turnaround_seconds")
        if (
            isinstance(turnaround, bool)
            or not isinstance(turnaround, int)
            or turnaround < 0
        ):
            self.add(
                "invalid_turnaround",
                "$.simulation.configuration.scheduling.minimum_turnaround_seconds",
                "must be a non-negative integer number of seconds",
            )
        demand_configuration = self.require_mapping(
            configuration.get("demand"),
            "$.simulation.configuration.demand",
        )
        demand_configuration_fields = {
            "model_version",
            "configuration_version",
            "revision",
            "daily_booker_rate_ppm",
            "distance_scale_km",
            "destination_type_weight_bps",
            "same_country_weight_bps",
            "international_weight_bps",
            "relationship_weight_bps",
            "daily_multiplier_min_bps",
            "daily_multiplier_max_bps",
        }
        if self.schema_version in (2, 3):
            demand_configuration_fields.update(
                {"market_pack_configuration", "travel_scope_configuration"}
            )
        for field in sorted(set(demand_configuration) - demand_configuration_fields, key=repr):
            self.add(
                "unknown_authoritative_field",
                f"$.simulation.configuration.demand.{field}",
                "field is not part of the Stage 1 demand configuration",
            )
        supported_models = (
            {DEMAND_MODEL_VERSION, MODEL4_DEMAND_MODEL_VERSION}
            if self.schema_version in (2, 3)
            else {DEMAND_MODEL_VERSION}
        )
        if demand_configuration.get("model_version") not in supported_models or isinstance(
            demand_configuration.get("model_version"), bool
        ):
            self.add(
                "unsupported_demand_model",
                "$.simulation.configuration.demand.model_version",
                f"must be one of {sorted(supported_models)}",
            )
        self.require_text(
            demand_configuration,
            "configuration_version",
            "$.simulation.configuration.demand",
        )
        demand_revision = demand_configuration.get("revision")
        if (
            isinstance(demand_revision, bool)
            or not isinstance(demand_revision, int)
            or demand_revision < 1
        ):
            self.add(
                "invalid_demand_revision",
                "$.simulation.configuration.demand.revision",
                "must be a positive integer",
            )
        for field, minimum in (
            ("daily_booker_rate_ppm", 0),
            ("distance_scale_km", 1),
            ("same_country_weight_bps", 1),
            ("international_weight_bps", 1),
            ("relationship_weight_bps", 1),
            ("daily_multiplier_min_bps", 0),
            ("daily_multiplier_max_bps", 0),
        ):
            value = demand_configuration.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                self.add(
                    "invalid_demand_configuration",
                    f"$.simulation.configuration.demand.{field}",
                    f"must be an integer greater than or equal to {minimum}",
                )
        minimum_multiplier = demand_configuration.get("daily_multiplier_min_bps")
        maximum_multiplier = demand_configuration.get("daily_multiplier_max_bps")
        if (
            isinstance(minimum_multiplier, int)
            and not isinstance(minimum_multiplier, bool)
            and isinstance(maximum_multiplier, int)
            and not isinstance(maximum_multiplier, bool)
            and maximum_multiplier < minimum_multiplier
        ):
            self.add(
                "invalid_demand_configuration",
                "$.simulation.configuration.demand.daily_multiplier_max_bps",
                "must be greater than or equal to the minimum multiplier",
            )
        if (
            isinstance(minimum_multiplier, int)
            and not isinstance(minimum_multiplier, bool)
            and isinstance(maximum_multiplier, int)
            and not isinstance(maximum_multiplier, bool)
            and not minimum_multiplier <= 10_000 <= maximum_multiplier
        ):
            self.add(
                "invalid_demand_configuration",
                "$.simulation.configuration.demand",
                "the configured multiplier range must include neutral 10000",
            )
        type_weights = self.require_mapping(
            demand_configuration.get("destination_type_weight_bps"),
            "$.simulation.configuration.demand.destination_type_weight_bps",
        )
        if set(type_weights) != set(DEMAND_DESTINATION_TYPES):
            self.add(
                "invalid_demand_configuration",
                "$.simulation.configuration.demand.destination_type_weight_bps",
                "must contain exactly the canonical destination types",
            )
        for destination_type, weight in type_weights.items():
            if isinstance(weight, bool) or not isinstance(weight, int) or weight < 1:
                self.add(
                    "invalid_demand_configuration",
                    f"$.simulation.configuration.demand.destination_type_weight_bps.{destination_type}",
                    "weights must be positive integer basis points",
                )
        if self.schema_version in (2, 3):
            self._validate_schema2_demand_configuration(demand_configuration)
        fast_forward = self.require_mapping(simulation.get("fast_forward"), "$.simulation.fast_forward")
        target = fast_forward.get("target_time_utc")
        if clock_state == "FAST_FORWARD":
            if not _canonical_utc(target):
                self.add("invalid_fast_forward_target", "$.simulation.fast_forward.target_time_utc", "FAST_FORWARD requires a canonical UTC target")
            elif _canonical_utc(simulation.get("time_utc")) and target < simulation["time_utc"]:
                self.add("invalid_fast_forward_target", "$.simulation.fast_forward.target_time_utc", "target cannot precede simulation time")
        elif target is not None:
            self.add("invalid_fast_forward_target", "$.simulation.fast_forward.target_time_utc", "target must be null outside FAST_FORWARD")
        revisions = self.require_mapping(simulation.get("operation_revisions"), "$.simulation.operation_revisions")
        for owner_id, revision in revisions.items():
            if not isinstance(owner_id, str):
                self.add("invalid_revision_owner", "$.simulation.operation_revisions", "owner IDs must be strings")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                self.add("invalid_revision", f"$.simulation.operation_revisions.{owner_id}", "must be a non-negative integer")

        deterministic = self.require_mapping(self.envelope.get("deterministic_state"), "$.deterministic_state")
        seed = deterministic.get("world_seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            self.add("invalid_seed", "$.deterministic_state.world_seed", "must be a non-negative integer")
        self.require_mapping(deterministic.get("streams"), "$.deterministic_state.streams")
        self.world = self.require_mapping(self.envelope.get("world_state"), "$.world_state")
        world_roots = (
            SCHEMA3_WORLD_ROOTS
            if self.schema_version == 3
            else SCHEMA2_WORLD_ROOTS
            if self.schema_version in (2, 3)
            else WORLD_ROOTS
        )
        for key in world_roots:
            if key not in self.world:
                self.add("missing_world_root", f"$.world_state.{key}", "required world root is missing")
        for key in sorted(set(self.world) - world_roots, key=repr):
            self.add("unknown_world_root", f"$.world_state.{key}", f"field is not part of schema version {self.schema_version}")
        self.require_mapping(self.envelope.get("ui_state"), "$.ui_state")
        return True

    def validate_collections_and_ids(self):
        seen_primary_ids = {}
        entity_types = (
            SCHEMA2_ENTITY_TYPES
            if self.schema_version in (2, 3)
            else ENTITY_TYPES
        )
        entity_collections = (
            SCHEMA2_ENTITY_COLLECTIONS
            if self.schema_version in (2, 3)
            else ENTITY_COLLECTIONS
        )
        max_issued = {entity_type: 0 for entity_type in entity_types}
        for entity_type, (collection_name, id_field) in entity_collections.items():
            path = f"$.world_state.{collection_name}"
            if collection_name not in self.world:
                self.add("missing_collection", path, "required authoritative collection is missing")
                continue
            collection = self.require_mapping(self.world.get(collection_name), path)
            seen_in_collection = set()
            for key, record in collection.items():
                record_path = f"{path}.{key}"
                if not isinstance(key, str):
                    self.add("invalid_collection_key", record_path, "entity collection keys must be strings", entity_type)
                    continue
                if type(record) is not dict:
                    self.add("invalid_entity", record_path, "entity record must be a dictionary", entity_type, key)
                    continue
                record_id = record.get(id_field)
                if isinstance(record_id, str):
                    if record_id in seen_in_collection:
                        self.add("duplicate_id", f"{record_path}.{id_field}", "duplicate primary ID in collection", entity_type, record_id)
                    else:
                        seen_in_collection.add(record_id)
                if record_id != key:
                    self.add("id_key_mismatch", f"{record_path}.{id_field}", "record ID must equal its collection key", entity_type, str(record_id))
                parsed = parse_entity_id(record_id, entity_type)
                if parsed is None:
                    self.add("malformed_id", f"{record_path}.{id_field}", f"must be a valid {entity_type} ID", entity_type, str(record_id))
                else:
                    max_issued[entity_type] = max(max_issued[entity_type], parsed[1])
                if isinstance(record_id, str):
                    previous = seen_primary_ids.get(record_id)
                    if previous is not None:
                        self.add("duplicate_id", f"{record_path}.{id_field}", f"ID is already used by {previous}", entity_type, record_id)
                    else:
                        seen_primary_ids[record_id] = entity_type

        event_history = self.require_mapping(
            self.world.get("event_history"), "$.world_state.event_history"
        )
        for key, record in event_history.items():
            path = f"$.world_state.event_history.{key}"
            if not isinstance(key, str) or type(record) is not dict:
                self.add("invalid_entity", path, "resolved event must be a keyed dictionary", "event", str(key))
                continue
            event_id = record.get("event_id")
            if event_id != key:
                self.add("id_key_mismatch", f"{path}.event_id", "record ID must equal its collection key", "event", str(event_id))
            parsed = parse_entity_id(event_id, "event")
            if parsed is None:
                self.add("malformed_id", f"{path}.event_id", "must be a valid event ID", "event", str(event_id))
            else:
                max_issued["event"] = max(max_issued["event"], parsed[1])
            if isinstance(event_id, str):
                previous = seen_primary_ids.get(event_id)
                if previous is not None:
                    self.add("duplicate_id", f"{path}.event_id", f"ID is already used by {previous}", "event", event_id)
                else:
                    seen_primary_ids[event_id] = "event_history"

        allocator_entity_types = entity_types
        if self.schema_version == 3:
            allocator_entity_types = SCHEMA3_ENTITY_TYPES
            max_issued["booking_checkpoint"] = 0
            booking_state = self.require_mapping(
                self.world.get("booking_state"), "$.world_state.booking_state"
            )
            checkpoints = self.require_mapping(
                booking_state.get("booking_checkpoints"),
                "$.world_state.booking_state.booking_checkpoints",
            )
            for key, record in checkpoints.items():
                path = f"$.world_state.booking_state.booking_checkpoints.{key}"
                if not isinstance(key, str) or type(record) is not dict:
                    self.add(
                        "invalid_booking_checkpoint",
                        path,
                        "checkpoint must be a keyed dictionary",
                        "booking_checkpoint",
                        str(key),
                    )
                    continue
                checkpoint_id = record.get("booking_checkpoint_id")
                if checkpoint_id != key:
                    self.add(
                        "id_key_mismatch",
                        f"{path}.booking_checkpoint_id",
                        "record ID must equal its collection key",
                        "booking_checkpoint",
                        str(checkpoint_id),
                    )
                parsed = parse_entity_id(checkpoint_id, "booking_checkpoint")
                if parsed is None:
                    self.add(
                        "malformed_id",
                        f"{path}.booking_checkpoint_id",
                        "must be a valid booking_checkpoint ID",
                        "booking_checkpoint",
                        str(checkpoint_id),
                    )
                else:
                    max_issued["booking_checkpoint"] = max(
                        max_issued["booking_checkpoint"], parsed[1]
                    )
                if isinstance(checkpoint_id, str):
                    previous = seen_primary_ids.get(checkpoint_id)
                    if previous is not None:
                        self.add(
                            "duplicate_id",
                            f"{path}.booking_checkpoint_id",
                            f"ID is already used by {previous}",
                            "booking_checkpoint",
                            checkpoint_id,
                        )
                    else:
                        seen_primary_ids[checkpoint_id] = "booking_checkpoint"

        deterministic = self.envelope.get("deterministic_state", {})
        allocator = self.require_mapping(deterministic.get("id_allocator"), "$.deterministic_state.id_allocator")
        next_by_type = self.require_mapping(allocator.get("next_by_type"), "$.deterministic_state.id_allocator.next_by_type")
        for entity_type in allocator_entity_types:
            value = next_by_type.get(entity_type)
            path = f"$.deterministic_state.id_allocator.next_by_type.{entity_type}"
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
                or value > MAX_ENTITY_ID_NUMBER + 1
            ):
                self.add("invalid_id_allocator", path, "next value must be a positive integer")
            elif value <= max_issued[entity_type]:
                self.add("id_allocator_collision", path, "next value would collide with an issued ID")
        unknown = set(next_by_type) - set(allocator_entity_types)
        for entity_type in sorted(unknown, key=repr):
            self.add("unknown_id_namespace", f"$.deterministic_state.id_allocator.next_by_type.{entity_type}", f"namespace is not part of schema version {self.schema_version}")

    def validate_structure(self):
        world = self.world
        player = self.require_mapping(world.get("player"), "$.world_state.player")
        if player.get("player_id") != "player":
            self.add("invalid_player", "$.world_state.player.player_id", "must equal 'player'")
        self.require_text(player, "ceo_display_name", "$.world_state.player")

        def valid_records(value, path):
            collection = self.require_mapping(value, path)
            return {
                key: record
                for key, record in collection.items()
                if isinstance(key, str) and type(record) is dict
            }

        airports = valid_records(world.get("airports"), "$.world_state.airports")
        regions = (
            valid_records(world.get("regions"), "$.world_state.regions")
            if self.schema_version in (2, 3)
            else {}
        )
        countries = (
            valid_records(world.get("countries"), "$.world_state.countries")
            if self.schema_version in (2, 3)
            else {}
        )
        airlines = valid_records(world.get("airlines"), "$.world_state.airlines")
        aircraft = valid_records(world.get("aircraft"), "$.world_state.aircraft")
        markets = valid_records(world.get("directional_markets"), "$.world_state.directional_markets")
        connections = valid_records(world.get("connections"), "$.world_state.connections")
        schedules = valid_records(world.get("schedule_definitions"), "$.world_state.schedule_definitions")
        flights = valid_records(world.get("dated_flights"), "$.world_state.dated_flights")
        itineraries = valid_records(world.get("itineraries"), "$.world_state.itineraries")
        bookings = valid_records(world.get("bookings"), "$.world_state.bookings")
        accounts = valid_records(world.get("financial_accounts"), "$.world_state.financial_accounts")
        transactions = valid_records(world.get("transactions"), "$.world_state.transactions")
        events = valid_records(world.get("pending_events"), "$.world_state.pending_events")
        event_history = valid_records(world.get("event_history"), "$.world_state.event_history")
        operations = self.require_mapping(world.get("active_aircraft_operations"), "$.world_state.active_aircraft_operations")

        if self.schema_version in (2, 3):
            region_codes = {}
            for region_id, record in regions.items():
                path = f"$.world_state.regions.{region_id}"
                allowed = {"region_id", "external_reference_code", "display_name"}
                for field in sorted(set(record) - allowed, key=repr):
                    self.add("unknown_authoritative_field", f"{path}.{field}", "field is not part of the immutable region schema", "region", region_id)
                code = self.require_text(record, "external_reference_code", path, "region", region_id)
                self.require_text(record, "display_name", path, "region", region_id)
                if code:
                    previous = region_codes.get(code)
                    if previous is not None:
                        self.add("duplicate_external_reference_code", f"{path}.external_reference_code", f"already used by {previous}", "region", region_id)
                    else:
                        region_codes[code] = region_id

            country_codes = {}
            for country_id, record in countries.items():
                path = f"$.world_state.countries.{country_id}"
                allowed = {
                    "country_id",
                    "region_id",
                    "external_reference_code",
                    "display_name",
                    "effective_from_date",
                    "effective_until_date",
                    "demand_attractiveness_bps",
                    "relationship_weight_bps",
                    "population",
                    "centroid_latitude_microdegrees",
                    "centroid_longitude_microdegrees",
                    "airport_allocation_revision",
                }
                for field in sorted(set(record) - allowed, key=repr):
                    self.add("unknown_authoritative_field", f"{path}.{field}", "field is not part of the immutable country schema", "country", country_id)
                region_id = record.get("region_id")
                if not isinstance(region_id, str) or region_id not in regions:
                    self.add("dangling_reference", f"{path}.region_id", "must reference an immutable region ID", "country", country_id)
                code = self.require_text(record, "external_reference_code", path, "country", country_id)
                self.require_text(record, "display_name", path, "country", country_id)
                if code:
                    previous = country_codes.get(code)
                    if previous is not None:
                        self.add("duplicate_external_reference_code", f"{path}.external_reference_code", f"already used by {previous}", "country", country_id)
                    else:
                        country_codes[code] = country_id
                for field in ("effective_from_date", "effective_until_date"):
                    value = record.get(field)
                    if value is not None and not _local_date(value):
                        self.add("invalid_local_date", f"{path}.{field}", "must be null or canonical YYYY-MM-DD", "country", country_id)
                effective_from = record.get("effective_from_date")
                effective_until = record.get("effective_until_date")
                if _local_date(effective_from) and _local_date(effective_until) and effective_until <= effective_from:
                    self.add("invalid_effective_window", path, "effective_until_date must follow effective_from_date", "country", country_id)
                active_model = self.envelope.get("simulation", {}).get("configuration", {}).get("demand", {}).get("model_version")
                for field in ("demand_attractiveness_bps", "relationship_weight_bps"):
                    value = record.get(field)
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, int)
                        or value <= 0
                        or (active_model == DEMAND_MODEL_VERSION and value != 10_000)
                    ):
                        self.add("invalid_country_demand_field", f"{path}.{field}", "must be a positive integer basis-point value (neutral 10000 while Model 3 is active)", "country", country_id)
                population = record.get("population")
                latitude = record.get("centroid_latitude_microdegrees")
                longitude = record.get("centroid_longitude_microdegrees")
                required = active_model == MODEL4_DEMAND_MODEL_VERSION
                allocation_revision = record.get("airport_allocation_revision")
                legacy_pack = self.envelope.get("simulation", {}).get("configuration", {}).get("demand", {}).get("market_pack_configuration", {}).get("configuration_version") == LEGACY_MARKET_PACK_CONFIGURATION_VERSION
                if (
                    not legacy_pack
                    and (
                        isinstance(allocation_revision, bool)
                        or not isinstance(allocation_revision, int)
                        or allocation_revision < 1
                    )
                ):
                    self.add("invalid_country_demand_field", f"{path}.airport_allocation_revision", "must be a positive integer", "country", country_id)
                if (population is not None or required) and (isinstance(population, bool) or not isinstance(population, int) or population <= 0):
                    self.add("invalid_country_demand_field", f"{path}.population", "must be a positive integer for Model 4", "country", country_id)
                if (latitude is not None or required) and (isinstance(latitude, bool) or not isinstance(latitude, int) or not -90_000_000 <= latitude <= 90_000_000):
                    self.add("invalid_country_demand_field", f"{path}.centroid_latitude_microdegrees", "must be a valid integer microdegree latitude for Model 4", "country", country_id)
                if (longitude is not None or required) and (isinstance(longitude, bool) or not isinstance(longitude, int) or not -180_000_000 <= longitude <= 180_000_000):
                    self.add("invalid_country_demand_field", f"{path}.centroid_longitude_microdegrees", "must be a valid integer microdegree longitude for Model 4", "country", country_id)

            overrides = self.envelope.get("simulation", {}).get("configuration", {}).get("demand", {}).get("travel_scope_configuration", {}).get("country_overrides", {})
            if type(overrides) is dict:
                for country_id in overrides:
                    if not isinstance(country_id, str) or country_id not in countries:
                        self.add("dangling_reference", f"$.simulation.configuration.demand.travel_scope_configuration.country_overrides.{country_id}", "override key must reference an immutable country ID")

        primary = self.require_ref(player, "primary_airline_id", airlines, "$.world_state.player", "player", "player")
        if primary and airlines.get(primary, {}).get("control_type") != "PLAYER":
            self.add("invalid_ownership", "$.world_state.player.primary_airline_id", "primary airline must be player-controlled", "airline", primary)
        if primary and (
            airlines.get(primary, {}).get("owner_type") != "PLAYER"
            or airlines.get(primary, {}).get("owner_id") != "player"
        ):
            self.add(
                "invalid_ownership",
                "$.world_state.player.primary_airline_id",
                "primary airline must be owned directly by the player",
                "airline",
                primary,
            )

        airport_reference_codes = {}
        for airport_id, record in airports.items():
            path = f"$.world_state.airports.{airport_id}"
            allowed_airport_fields = {
                "airport_id",
                "reference_code",
                "display_name",
                "iata_code",
                "icao_code",
                "timezone",
                "passenger_demand_eligible",
                "population",
                "latitude_microdegrees",
                "longitude_microdegrees",
                "country_reference",
                "demand_destination_type",
                "active_from_date",
                "active_until_date",
                "demand_input_revision",
            }
            if self.schema_version in (2, 3):
                allowed_airport_fields.update(
                    {"country_id", "demand_allocation_member"}
                )
            for field in sorted(set(record) - allowed_airport_fields, key=repr):
                self.add(
                    "unknown_authoritative_field",
                    f"{path}.{field}",
                    "field is not part of the canonical Stage 1 airport schema",
                    "airport",
                    airport_id,
                )
            reference_code = self.require_text(record, "reference_code", path, "airport", airport_id)
            self.require_text(record, "display_name", path, "airport", airport_id)
            airport_timezone = self.require_text(
                record, "timezone", path, "airport", airport_id
            )
            if airport_timezone and not _named_timezone(airport_timezone):
                self.add(
                    "invalid_timezone",
                    f"{path}.timezone",
                    "must be an available named IANA timezone",
                    "airport",
                    airport_id,
                )
            if reference_code:
                if reference_code != reference_code.upper():
                    self.add("malformed_required_field", f"{path}.reference_code", "must be uppercase", "airport", airport_id)
                previous = airport_reference_codes.get(reference_code)
                if previous is not None:
                    self.add("duplicate_airport_reference", f"{path}.reference_code", f"reference code is already used by {previous}", "airport", airport_id)
                else:
                    airport_reference_codes[reference_code] = airport_id
            for field in ("iata_code", "icao_code"):
                if record.get(field) is not None and (not isinstance(record.get(field), str) or not record[field]):
                    self.add("malformed_required_field", f"{path}.{field}", "must be null or a non-empty string", "airport", airport_id)
                elif isinstance(record.get(field), str):
                    expected_length = 3 if field == "iata_code" else 4
                    if len(record[field]) != expected_length or record[field] != record[field].upper():
                        self.add("malformed_required_field", f"{path}.{field}", f"must be an uppercase {expected_length}-character code", "airport", airport_id)
            demand_eligible = record.get("passenger_demand_eligible")
            if type(demand_eligible) is not bool:
                self.add(
                    "invalid_demand_eligibility",
                    f"{path}.passenger_demand_eligible",
                    "must be a boolean",
                    "airport",
                    airport_id,
                )
            population = record.get("population")
            if population is not None and (
                isinstance(population, bool)
                or not isinstance(population, int)
                or population < 0
            ):
                self.add(
                    "invalid_population",
                    f"{path}.population",
                    "must be null or a non-negative integer",
                    "airport",
                    airport_id,
                )
            latitude = record.get("latitude_microdegrees")
            longitude = record.get("longitude_microdegrees")
            if latitude is not None and (
                isinstance(latitude, bool)
                or not isinstance(latitude, int)
                or not -90_000_000 <= latitude <= 90_000_000
            ):
                self.add(
                    "invalid_coordinates",
                    f"{path}.latitude_microdegrees",
                    "must be null or an integer from -90000000 through 90000000",
                    "airport",
                    airport_id,
                )
            if longitude is not None and (
                isinstance(longitude, bool)
                or not isinstance(longitude, int)
                or not -180_000_000 <= longitude <= 180_000_000
            ):
                self.add(
                    "invalid_coordinates",
                    f"{path}.longitude_microdegrees",
                    "must be null or an integer from -180000000 through 180000000",
                    "airport",
                    airport_id,
                )
            country_reference = record.get("country_reference")
            if country_reference is not None and (
                not isinstance(country_reference, str)
                or not country_reference.strip()
            ):
                self.add(
                    "invalid_country_reference",
                    f"{path}.country_reference",
                    "must be null or a non-empty stable reference",
                    "airport",
                    airport_id,
                )
            if self.schema_version in (2, 3):
                country_id = record.get("country_id")
                if not isinstance(country_id, str) or country_id not in countries:
                    self.add("dangling_reference", f"{path}.country_id", "must reference an immutable country ID", "airport", airport_id)
                elif (
                    isinstance(country_reference, str)
                    and countries[country_id].get("external_reference_code")
                    != country_reference
                ):
                    self.add("inconsistent_country_identity", f"{path}.country_id", "country_id and legacy country_reference must identify the same snapshot country", "airport", airport_id)
                if type(record.get("demand_allocation_member")) is not bool:
                    self.add("invalid_demand_allocation_member", f"{path}.demand_allocation_member", "must be a boolean", "airport", airport_id)
            destination_type = record.get("demand_destination_type")
            if destination_type is not None and destination_type not in DEMAND_DESTINATION_TYPES:
                self.add(
                    "invalid_destination_type",
                    f"{path}.demand_destination_type",
                    f"must be null or one of {list(DEMAND_DESTINATION_TYPES)}",
                    "airport",
                    airport_id,
                )
            for field in ("active_from_date", "active_until_date"):
                value = record.get(field)
                if value is not None and not _local_date(value):
                    self.add(
                        "invalid_local_date",
                        f"{path}.{field}",
                        "must be null or canonical YYYY-MM-DD",
                        "airport",
                        airport_id,
                    )
            active_from = record.get("active_from_date")
            active_until = record.get("active_until_date")
            if _local_date(active_from) and _local_date(active_until) and active_until <= active_from:
                self.add(
                    "invalid_active_window",
                    path,
                    "active_until_date must follow active_from_date",
                    "airport",
                    airport_id,
                )
            input_revision = record.get("demand_input_revision")
            current_demand_revision = self.envelope.get("simulation", {}).get(
                "configuration", {}
            ).get("demand", {}).get("revision")
            if (
                isinstance(input_revision, bool)
                or not isinstance(input_revision, int)
                or input_revision < 1
                or (
                    isinstance(current_demand_revision, int)
                    and input_revision > current_demand_revision
                )
            ):
                self.add(
                    "invalid_demand_revision",
                    f"{path}.demand_input_revision",
                    "must be a positive revision no newer than the demand model",
                    "airport",
                    airport_id,
                )
            if demand_eligible is True and not (
                isinstance(population, int)
                and not isinstance(population, bool)
                and population > 0
                and isinstance(latitude, int)
                and not isinstance(latitude, bool)
                and isinstance(longitude, int)
                and not isinstance(longitude, bool)
                and isinstance(country_reference, str)
                and bool(country_reference.strip())
                and destination_type in DEMAND_DESTINATION_TYPES
            ):
                self.add(
                    "invalid_demand_eligibility",
                    path,
                    "eligible airports require positive population, coordinates, country reference, and destination type",
                    "airport",
                    airport_id,
                )

        for airline_id, record in airlines.items():
            path = f"$.world_state.airlines.{airline_id}"
            allowed_airline_fields = {
                "airline_id",
                "display_name",
                "base_currency",
                "control_type",
                "owner_type",
                "owner_id",
                "base_airport_ids",
                "hub_airport_ids",
                "financial_account_ids",
            }
            if self.schema_version == 3:
                allowed_airline_fields.add("finance_revision")
            for field in sorted(set(record) - allowed_airline_fields, key=repr):
                self.add(
                    "unknown_authoritative_field",
                    f"{path}.{field}",
                    f"field is not part of the canonical schema-{self.schema_version} airline record",
                    "airline",
                    airline_id,
                )
            self.require_text(record, "display_name", path, "airline", airline_id)
            if not _currency_code(record.get("base_currency")):
                self.add("invalid_currency", f"{path}.base_currency", "must be a three-letter uppercase currency code", "airline", airline_id)
            control = record.get("control_type")
            if not isinstance(control, str) or control not in AIRLINE_CONTROL_TYPES:
                self.add("invalid_control", f"{path}.control_type", "must be PLAYER or AI", "airline", airline_id)
            owner_type = record.get("owner_type")
            owner_id = record.get("owner_id")
            if not isinstance(owner_type, str) or owner_type not in AIRLINE_OWNER_TYPES:
                self.add("invalid_ownership", f"{path}.owner_type", "invalid owner type", "airline", airline_id)
            elif owner_type == "PLAYER" and owner_id != "player":
                self.add("invalid_ownership", f"{path}.owner_id", "PLAYER ownership must reference player", "airline", airline_id)
            elif owner_type == "INDEPENDENT" and owner_id is not None:
                self.add("invalid_ownership", f"{path}.owner_id", "INDEPENDENT ownership must have null owner_id", "airline", airline_id)
            elif owner_type == "AIRLINE" and (
                not isinstance(owner_id, str)
                or owner_id not in airlines
                or owner_id == airline_id
            ):
                self.add("invalid_ownership", f"{path}.owner_id", "AIRLINE ownership must reference another airline", "airline", airline_id)
            for field in ("base_airport_ids", "hub_airport_ids", "financial_account_ids"):
                values = record.get(field)
                if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                    self.add("malformed_required_field", f"{path}.{field}", "must be a list of IDs", "airline", airline_id)
                    continue
                if len(values) != len(set(values)):
                    self.add("duplicate_reference", f"{path}.{field}", "must not contain duplicate IDs", "airline", airline_id)
                targets = accounts if field == "financial_account_ids" else airports
                for index, value in enumerate(values):
                    if value not in targets:
                        self.add("dangling_reference", f"{path}.{field}[{index}]", "referenced entity does not exist", "airline", airline_id)
                    elif field == "financial_account_ids" and targets[value].get("airline_id") != airline_id:
                        self.add("invalid_ownership", f"{path}.{field}[{index}]", "account belongs to another airline", "airline", airline_id)
            hubs = record.get("hub_airport_ids", [])
            bases = record.get("base_airport_ids", [])
            if (
                isinstance(hubs, list)
                and all(isinstance(value, str) for value in hubs)
                and isinstance(bases, list)
                and all(isinstance(value, str) for value in bases)
                and not set(hubs).issubset(set(bases))
            ):
                self.add("invalid_ownership", f"{path}.hub_airport_ids", "every hub must also be an operating base", "airline", airline_id)

        reported_cycles = set()
        for airline_id in airlines:
            chain = []
            current = airline_id
            while (
                isinstance(current, str)
                and current in airlines
                and airlines[current].get("owner_type") == "AIRLINE"
            ):
                if current in chain:
                    cycle = frozenset(chain[chain.index(current):])
                    if cycle not in reported_cycles:
                        reported_cycles.add(cycle)
                        self.add(
                            "ownership_cycle",
                            f"$.world_state.airlines.{airline_id}.owner_id",
                            "airline ownership must be acyclic",
                            "airline",
                            airline_id,
                        )
                    break
                chain.append(current)
                current = airlines[current].get("owner_id")

        for aircraft_id, record in aircraft.items():
            path = f"$.world_state.aircraft.{aircraft_id}"
            owner = self.require_ref(record, "airline_id", airlines, path, "aircraft", aircraft_id)
            self.require_ref(record, "home_airport_id", airports, path, "aircraft", aircraft_id)
            self.require_ref(record, "current_airport_id", airports, path, "aircraft", aircraft_id, optional=True)
            self.require_text(record, "display_registration", path, "aircraft", aircraft_id)
            self.require_text(record, "model_reference", path, "aircraft", aircraft_id)
            self.require_text(record, "status", path, "aircraft", aircraft_id)
            if owner is None:
                continue

        market_pairs = {}
        for market_id, record in markets.items():
            path = f"$.world_state.directional_markets.{market_id}"
            for field in sorted(
                set(record)
                - {"market_id", "origin_airport_id", "destination_airport_id"},
                key=repr,
            ):
                self.add(
                    "unknown_authoritative_field",
                    f"{path}.{field}",
                    "field is not part of the canonical Stage 1 directional-market schema",
                    "market",
                    market_id,
                )
            origin = self.require_ref(record, "origin_airport_id", airports, path, "market", market_id)
            destination = self.require_ref(record, "destination_airport_id", airports, path, "market", market_id)
            if origin is not None and origin == destination:
                self.add("invalid_market", path, "origin and destination must differ", "market", market_id)
            elif origin is not None and destination is not None:
                pair = (origin, destination)
                previous = market_pairs.get(pair)
                if previous is not None:
                    self.add("duplicate_market", path, f"directional pair is already represented by {previous}", "market", market_id)
                else:
                    market_pairs[pair] = market_id

        airline_markets = {}
        for connection_id, record in connections.items():
            path = f"$.world_state.connections.{connection_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "connection", connection_id)
            market_id = self.require_ref(record, "market_id", markets, path, "connection", connection_id)
            self.require_text(record, "status", path, "connection", connection_id)
            if airline_id and market_id:
                pair = (airline_id, market_id)
                previous = airline_markets.get(pair)
                if previous is not None:
                    self.add("duplicate_connection", path, f"airline market connection already exists as {previous}", "connection", connection_id)
                else:
                    airline_markets[pair] = connection_id

        schedule_revisions = {}

        def reject_unknown_fields(record, allowed, path, entity_type, entity_id):
            for field in sorted(set(record) - set(allowed), key=repr):
                self.add(
                    "unknown_authoritative_field",
                    f"{path}.{field}",
                    "field is not part of the canonical Stage 1 schema",
                    entity_type,
                    entity_id,
                )

        def validate_fare_offer(fare, path, airline_id, entity_type, entity_id):
            fare = self.require_mapping(fare, path)
            reject_unknown_fields(
                fare,
                {"currency", "amount_minor"},
                path,
                entity_type,
                entity_id,
            )
            amount = fare.get("amount_minor")
            if not is_minor_amount(amount) or amount < 0:
                self.add(
                    "invalid_fare_offer",
                    f"{path}.amount_minor",
                    "must be a non-negative integer minor-unit amount",
                    entity_type,
                    entity_id,
                )
            currency = fare.get("currency")
            if not _currency_code(currency):
                self.add(
                    "invalid_fare_offer",
                    f"{path}.currency",
                    "must be a three-letter uppercase currency code",
                    entity_type,
                    entity_id,
                )
            elif airline_id and currency != airlines[airline_id].get("base_currency"):
                self.add(
                    "invalid_fare_offer",
                    f"{path}.currency",
                    "must match the scheduled airline's base currency",
                    entity_type,
                    entity_id,
                )
            return fare

        for schedule_id, record in schedules.items():
            path = f"$.world_state.schedule_definitions.{schedule_id}"
            reject_unknown_fields(
                record,
                {
                    "schedule_id",
                    "airline_id",
                    "status",
                    "current_revision",
                    "revisions",
                },
                path,
                "schedule",
                schedule_id,
            )
            airline_id = self.require_ref(
                record, "airline_id", airlines, path, "schedule", schedule_id
            )
            status = record.get("status")
            if not isinstance(status, str) or status not in SCHEDULE_STATUSES:
                self.add(
                    "invalid_schedule_status",
                    f"{path}.status",
                    f"must be one of {sorted(SCHEDULE_STATUSES)}",
                    "schedule",
                    schedule_id,
                )
            current_revision = record.get("current_revision")
            if (
                isinstance(current_revision, bool)
                or not isinstance(current_revision, int)
                or current_revision < 1
                or current_revision > MAX_ENTITY_ID_NUMBER
            ):
                self.add(
                    "invalid_revision",
                    f"{path}.current_revision",
                    "must be a positive integer",
                    "schedule",
                    schedule_id,
                )
                current_revision = 0
            revisions = self.require_mapping(record.get("revisions"), f"{path}.revisions")
            expected_keys = {str(number) for number in range(1, len(revisions) + 1)}
            if current_revision != len(revisions) or set(revisions) != expected_keys:
                self.add(
                    "invalid_revision_sequence",
                    f"{path}.revisions",
                    "revision keys must be contiguous canonical decimal strings through current_revision",
                    "schedule",
                    schedule_id,
                )
            previous_start = None
            previous_end = None
            valid_revisions = {}
            for revision_key in sorted(
                revisions,
                key=lambda value: int(value)
                if isinstance(value, str) and value.isdigit()
                else MAX_ENTITY_ID_NUMBER + 1,
            ):
                revision = self.require_mapping(
                    revisions.get(revision_key), f"{path}.revisions.{revision_key}"
                )
                revision_path = f"{path}.revisions.{revision_key}"
                reject_unknown_fields(
                    revision,
                    {
                        "revision",
                        "effective_from_local_date",
                        "effective_until_local_date",
                        "connection_id",
                        "planned_aircraft_id",
                        "origin_airport_id",
                        "destination_airport_id",
                        "service_type",
                        "recurrence",
                        "capacity",
                        "fare_offer",
                        "passenger_service_classification",
                    },
                    revision_path,
                    "schedule",
                    schedule_id,
                )
                revision_number = revision.get("revision")
                if (
                    isinstance(revision_number, bool)
                    or not isinstance(revision_number, int)
                    or str(revision_number) != revision_key
                    or revision_number < 1
                ):
                    self.add(
                        "invalid_revision",
                        f"{revision_path}.revision",
                        "must equal its positive canonical revision key",
                        "schedule",
                        schedule_id,
                    )
                else:
                    valid_revisions[revision_number] = revision

                start_text = revision.get("effective_from_local_date")
                end_text = revision.get("effective_until_local_date")
                if not _local_date(start_text):
                    self.add(
                        "invalid_local_date",
                        f"{revision_path}.effective_from_local_date",
                        "must be canonical YYYY-MM-DD",
                        "schedule",
                        schedule_id,
                    )
                if end_text is not None and not _local_date(end_text):
                    self.add(
                        "invalid_local_date",
                        f"{revision_path}.effective_until_local_date",
                        "must be null or canonical YYYY-MM-DD",
                        "schedule",
                        schedule_id,
                    )
                if _local_date(start_text) and _local_date(end_text) and start_text > end_text:
                    self.add(
                        "invalid_effective_window",
                        revision_path,
                        "effective end date cannot precede its start date",
                        "schedule",
                        schedule_id,
                    )
                if previous_start is not None and _local_date(start_text):
                    if start_text <= previous_start:
                        self.add(
                            "invalid_revision_sequence",
                            f"{revision_path}.effective_from_local_date",
                            "revision effective dates must increase",
                            "schedule",
                            schedule_id,
                        )
                    expected_previous_end = (
                        date.fromisoformat(start_text) - timedelta(days=1)
                    ).isoformat()
                    if previous_end != expected_previous_end:
                        self.add(
                            "invalid_revision_sequence",
                            f"{revision_path}.effective_from_local_date",
                            "the prior revision must end on the preceding local date",
                            "schedule",
                            schedule_id,
                        )
                if _local_date(start_text):
                    previous_start = start_text
                previous_end = end_text

                planned = self.require_ref(
                    revision,
                    "planned_aircraft_id",
                    aircraft,
                    revision_path,
                    "schedule",
                    schedule_id,
                )
                origin = self.require_ref(
                    revision,
                    "origin_airport_id",
                    airports,
                    revision_path,
                    "schedule",
                    schedule_id,
                )
                destination = self.require_ref(
                    revision,
                    "destination_airport_id",
                    airports,
                    revision_path,
                    "schedule",
                    schedule_id,
                )
                if origin and destination and origin == destination:
                    self.add(
                        "invalid_schedule_endpoints",
                        revision_path,
                        "origin and destination must differ",
                        "schedule",
                        schedule_id,
                    )
                if planned and airline_id and aircraft[planned].get("airline_id") != airline_id:
                    self.add(
                        "invalid_ownership",
                        f"{revision_path}.planned_aircraft_id",
                        "aircraft belongs to another airline",
                        "schedule",
                        schedule_id,
                    )

                service_type = revision.get("service_type")
                if (
                    not isinstance(service_type, str)
                    or service_type not in SCHEDULE_SERVICE_TYPES
                ):
                    self.add(
                        "invalid_service_type",
                        f"{revision_path}.service_type",
                        f"must be one of {sorted(SCHEDULE_SERVICE_TYPES)}",
                        "schedule",
                        schedule_id,
                    )
                connection_id = revision.get("connection_id")
                if connection_id is not None and (
                    not isinstance(connection_id, str) or connection_id not in connections
                ):
                    self.add(
                        "dangling_reference",
                        f"{revision_path}.connection_id",
                        "must be null or reference an existing connection",
                        "schedule",
                        schedule_id,
                    )
                    connection_id = None
                if connection_id and airline_id and connections[connection_id].get("airline_id") != airline_id:
                    self.add(
                        "invalid_ownership",
                        f"{revision_path}.connection_id",
                        "connection belongs to another airline",
                        "schedule",
                        schedule_id,
                    )
                if connection_id and origin and destination:
                    market_id = connections[connection_id].get("market_id")
                    market = markets.get(market_id, {})
                    if (
                        market.get("origin_airport_id") != origin
                        or market.get("destination_airport_id") != destination
                    ):
                        self.add(
                            "inconsistent_reference",
                            f"{revision_path}.connection_id",
                            "connection market must match schedule endpoints",
                            "schedule",
                            schedule_id,
                        )

                recurrence = self.require_mapping(
                    revision.get("recurrence"), f"{revision_path}.recurrence"
                )
                reject_unknown_fields(
                    recurrence,
                    {
                        "frequency",
                        "weekdays",
                        "departure_local_time",
                        "departure_local_fold",
                        "arrival_local_time",
                        "arrival_day_offset",
                        "arrival_local_fold",
                    },
                    f"{revision_path}.recurrence",
                    "schedule",
                    schedule_id,
                )
                if recurrence.get("frequency") != "WEEKLY":
                    self.add(
                        "invalid_recurrence",
                        f"{revision_path}.recurrence.frequency",
                        "Milestone 3 supports WEEKLY recurrence",
                        "schedule",
                        schedule_id,
                    )
                weekdays = recurrence.get("weekdays")
                if (
                    not isinstance(weekdays, list)
                    or not weekdays
                    or any(
                        isinstance(value, bool)
                        or not isinstance(value, int)
                        or value < 0
                        or value > 6
                        for value in weekdays
                    )
                    or weekdays != sorted(set(weekdays))
                ):
                    self.add(
                        "invalid_recurrence",
                        f"{revision_path}.recurrence.weekdays",
                        "must be sorted unique weekday integers from Monday=0 through Sunday=6",
                        "schedule",
                        schedule_id,
                    )
                for field in ("departure_local_time", "arrival_local_time"):
                    if not _local_time(recurrence.get(field)):
                        self.add(
                            "invalid_local_time",
                            f"{revision_path}.recurrence.{field}",
                            "must be whole-second HH:MM:SS",
                            "schedule",
                            schedule_id,
                        )
                for field in ("departure_local_fold", "arrival_local_fold"):
                    if recurrence.get(field) not in (0, 1) or isinstance(
                        recurrence.get(field), bool
                    ):
                        self.add(
                            "invalid_local_fold",
                            f"{revision_path}.recurrence.{field}",
                            "must be 0 or 1",
                            "schedule",
                            schedule_id,
                        )
                day_offset = recurrence.get("arrival_day_offset")
                if (
                    isinstance(day_offset, bool)
                    or not isinstance(day_offset, int)
                    or day_offset < -7
                    or day_offset > 7
                ):
                    self.add(
                        "invalid_recurrence",
                        f"{revision_path}.recurrence.arrival_day_offset",
                        "must be an integer from -7 through 7",
                        "schedule",
                        schedule_id,
                    )

                capacity = revision.get("capacity")
                if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
                    self.add(
                        "invalid_capacity",
                        f"{revision_path}.capacity",
                        "must be a non-negative integer",
                        "schedule",
                        schedule_id,
                    )
                fare = validate_fare_offer(
                    revision.get("fare_offer"),
                    f"{revision_path}.fare_offer",
                    airline_id,
                    "schedule",
                    schedule_id,
                )
                classification = revision.get("passenger_service_classification")
                if (
                    not isinstance(classification, str)
                    or classification not in PASSENGER_SERVICE_CLASSIFICATIONS
                ):
                    self.add(
                        "invalid_passenger_service_classification",
                        f"{revision_path}.passenger_service_classification",
                        f"must be one of {sorted(PASSENGER_SERVICE_CLASSIFICATIONS)}",
                        "schedule",
                        schedule_id,
                    )
                valid_capacity = (
                    isinstance(capacity, int) and not isinstance(capacity, bool)
                )
                if service_type == "PASSENGER" and (
                    connection_id is None
                    or connections.get(connection_id, {}).get("status") != "ACTIVE"
                    or not valid_capacity
                    or capacity < 1
                    or classification != "ECONOMY"
                ):
                    self.add(
                        "invalid_passenger_service",
                        revision_path,
                        "passenger service requires an active connection, positive capacity, and ECONOMY classification",
                        "schedule",
                        schedule_id,
                    )
                if service_type == "DEADHEAD" and (
                    connection_id is not None
                    or capacity != 0
                    or classification != "NON_PASSENGER"
                    or fare.get("amount_minor") != 0
                ):
                    self.add(
                        "invalid_deadhead_service",
                        revision_path,
                        "deadhead requires no connection, zero capacity and fare, and NON_PASSENGER classification",
                        "schedule",
                        schedule_id,
                    )
            if (
                current_revision in valid_revisions
                and valid_revisions[current_revision].get(
                    "effective_until_local_date"
                )
                is not None
            ):
                self.add(
                    "invalid_revision_sequence",
                    f"{path}.revisions.{current_revision}.effective_until_local_date",
                    "the current revision must have an open-ended effective window",
                    "schedule",
                    schedule_id,
                )
            persisted_schedule_revision = self.envelope.get("simulation", {}).get(
                "operation_revisions", {}
            ).get(schedule_id)
            if persisted_schedule_revision != current_revision:
                self.add(
                    "invalid_revision",
                    f"$.simulation.operation_revisions.{schedule_id}",
                    "schedule operation revision must equal current_revision",
                    "schedule",
                    schedule_id,
                )
            schedule_revisions[schedule_id] = valid_revisions

        occurrence_keys = {}
        for flight_id, record in flights.items():
            path = f"$.world_state.dated_flights.{flight_id}"
            reject_unknown_fields(
                record,
                {
                    "dated_flight_id",
                    "occurrence_key",
                    "schedule_id",
                    "schedule_revision",
                    "airline_id",
                    "connection_id",
                    "planned_aircraft_id",
                    "origin_airport_id",
                    "destination_airport_id",
                    "service_type",
                    "scheduled_departure_local_date",
                    "scheduled_off_block_utc",
                    "scheduled_in_block_utc",
                    "capacity",
                    "fare_offer",
                    "passenger_service_classification",
                    "status",
                    "published_at_utc",
                    "superseded_by_schedule_revision",
                }
                | ({"inventory_revision"} if self.schema_version == 3 else set()),
                path,
                "dated_flight",
                flight_id,
            )
            airline_id = self.require_ref(record, "airline_id", airlines, path, "dated_flight", flight_id)
            schedule_id = self.require_ref(record, "schedule_id", schedules, path, "dated_flight", flight_id)
            connection_id = record.get("connection_id")
            if connection_id is not None and (
                not isinstance(connection_id, str) or connection_id not in connections
            ):
                self.add("dangling_reference", f"{path}.connection_id", "must be null or reference an existing connection", "dated_flight", flight_id)
                connection_id = None
            planned = self.require_ref(record, "planned_aircraft_id", aircraft, path, "dated_flight", flight_id)
            origin = self.require_ref(record, "origin_airport_id", airports, path, "dated_flight", flight_id)
            destination = self.require_ref(record, "destination_airport_id", airports, path, "dated_flight", flight_id)
            start = self.require_timestamp(record, "scheduled_off_block_utc", path, "dated_flight", flight_id)
            end = self.require_timestamp(record, "scheduled_in_block_utc", path, "dated_flight", flight_id)
            if start and end and start >= end:
                self.add("invalid_timestamp_order", path, "scheduled arrival must be after departure", "dated_flight", flight_id)
            local_date = record.get("scheduled_departure_local_date")
            if not _local_date(local_date):
                self.add("invalid_local_date", f"{path}.scheduled_departure_local_date", "must be canonical YYYY-MM-DD", "dated_flight", flight_id)
            occurrence_key = self.require_text(record, "occurrence_key", path, "dated_flight", flight_id)
            if schedule_id and _local_date(local_date):
                expected_key = f"{schedule_id}@{local_date}"
                if occurrence_key != expected_key:
                    self.add("invalid_occurrence_key", f"{path}.occurrence_key", "must equal schedule_id@scheduled_departure_local_date", "dated_flight", flight_id)
            if occurrence_key:
                previous = occurrence_keys.get(occurrence_key)
                if previous is not None:
                    self.add("duplicate_occurrence", f"{path}.occurrence_key", f"occurrence is already represented by {previous}", "dated_flight", flight_id)
                else:
                    occurrence_keys[occurrence_key] = flight_id

            revision_number = record.get("schedule_revision")
            revision = (
                schedule_revisions.get(schedule_id, {}).get(revision_number)
                if isinstance(revision_number, int)
                and not isinstance(revision_number, bool)
                else None
            )
            if revision is None:
                self.add("dangling_revision", f"{path}.schedule_revision", "must reference a retained schedule revision", "dated_flight", flight_id)
            status = record.get("status")
            if not isinstance(status, str) or status not in DATED_FLIGHT_STATUSES:
                self.add("invalid_dated_flight_status", f"{path}.status", f"must be one of {sorted(DATED_FLIGHT_STATUSES)}", "dated_flight", flight_id)
            self.require_timestamp(record, "published_at_utc", path, "dated_flight", flight_id)
            superseded_by = record.get("superseded_by_schedule_revision")
            if superseded_by is not None and (
                isinstance(superseded_by, bool)
                or not isinstance(superseded_by, int)
                or superseded_by < 1
                or superseded_by not in schedule_revisions.get(schedule_id, {})
            ):
                self.add("dangling_revision", f"{path}.superseded_by_schedule_revision", "must be null or reference a retained schedule revision", "dated_flight", flight_id)

            service_type = record.get("service_type")
            if (
                not isinstance(service_type, str)
                or service_type not in SCHEDULE_SERVICE_TYPES
            ):
                self.add("invalid_service_type", f"{path}.service_type", "invalid dated-flight service type", "dated_flight", flight_id)
            capacity = record.get("capacity")
            if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
                self.add("invalid_capacity", f"{path}.capacity", "must be a non-negative integer", "dated_flight", flight_id)
            fare = validate_fare_offer(record.get("fare_offer"), f"{path}.fare_offer", airline_id, "dated_flight", flight_id)
            classification = record.get("passenger_service_classification")
            if (
                not isinstance(classification, str)
                or classification not in PASSENGER_SERVICE_CLASSIFICATIONS
            ):
                self.add("invalid_passenger_service_classification", f"{path}.passenger_service_classification", "invalid Stage 1 passenger classification", "dated_flight", flight_id)
            if origin and destination and origin == destination:
                self.add("invalid_schedule_endpoints", path, "origin and destination must differ", "dated_flight", flight_id)
            if planned and airline_id and aircraft[planned].get("airline_id") != airline_id:
                self.add("invalid_ownership", f"{path}.planned_aircraft_id", "aircraft belongs to another airline", "dated_flight", flight_id)
            if connection_id and airline_id and connections[connection_id].get("airline_id") != airline_id:
                self.add("invalid_ownership", f"{path}.connection_id", "connection belongs to another airline", "dated_flight", flight_id)
            if revision is not None:
                trace_fields = (
                    "connection_id",
                    "planned_aircraft_id",
                    "origin_airport_id",
                    "destination_airport_id",
                    "service_type",
                    "capacity",
                    "fare_offer",
                    "passenger_service_classification",
                )
                for field in trace_fields:
                    if record.get(field) != revision.get(field):
                        self.add("inconsistent_schedule_trace", f"{path}.{field}", "must equal the referenced schedule revision", "dated_flight", flight_id)
                recurrence = revision.get("recurrence", {})
                day_offset = recurrence.get("arrival_day_offset")
                if (
                    origin
                    and destination
                    and _local_date(local_date)
                    and isinstance(day_offset, int)
                    and not isinstance(day_offset, bool)
                ):
                    departure_expected = _resolved_local_utc(
                        local_date,
                        recurrence.get("departure_local_time"),
                        recurrence.get("departure_local_fold"),
                        airports[origin].get("timezone"),
                    )
                    try:
                        arrival_local_date = (
                            date.fromisoformat(local_date)
                            + timedelta(days=day_offset)
                        ).isoformat()
                    except OverflowError:
                        arrival_expected = None
                    else:
                        arrival_expected = _resolved_local_utc(
                            arrival_local_date,
                            recurrence.get("arrival_local_time"),
                            recurrence.get("arrival_local_fold"),
                            airports[destination].get("timezone"),
                        )
                    if departure_expected is None or arrival_expected is None:
                        self.add(
                            "invalid_local_occurrence",
                            path,
                            "local schedule intent must resolve through named airport timezone rules",
                            "dated_flight",
                            flight_id,
                        )
                    else:
                        if start != departure_expected:
                            self.add(
                                "inconsistent_schedule_time",
                                f"{path}.scheduled_off_block_utc",
                                "must equal the referenced local departure intent",
                                "dated_flight",
                                flight_id,
                            )
                        if end != arrival_expected:
                            self.add(
                                "inconsistent_schedule_time",
                                f"{path}.scheduled_in_block_utc",
                                "must equal the referenced local arrival intent",
                                "dated_flight",
                                flight_id,
                            )

        minimum_turnaround = self.envelope.get("simulation", {}).get(
            "configuration", {}
        ).get("scheduling", {}).get("minimum_turnaround_seconds")
        simulation_time = self.envelope.get("simulation", {}).get("time_utc")
        if isinstance(minimum_turnaround, int) and not isinstance(
            minimum_turnaround, bool
        ) and minimum_turnaround >= 0 and _canonical_utc(simulation_time):
            active_statuses = {"PLANNED", "OPERATIONALLY_LOCKED"}
            future_by_aircraft = {aircraft_id: [] for aircraft_id in aircraft}
            for record in flights.values():
                aircraft_id = record.get("planned_aircraft_id")
                if (
                    isinstance(aircraft_id, str)
                    and aircraft_id in future_by_aircraft
                    and isinstance(record.get("status"), str)
                    and record.get("status") in active_statuses
                    and _canonical_utc(record.get("scheduled_off_block_utc"))
                    and record["scheduled_off_block_utc"] >= simulation_time
                ):
                    future_by_aircraft[aircraft_id].append(record)
            for aircraft_id, aircraft_record in aircraft.items():
                future = sorted(
                    future_by_aircraft[aircraft_id],
                    key=lambda item: (
                        item["scheduled_off_block_utc"],
                        item.get("dated_flight_id", ""),
                    ),
                )
                previous = None
                expected_origin = aircraft_record.get("current_airport_id")
                for record in future:
                    flight_id = record.get("dated_flight_id")
                    path = f"$.world_state.dated_flights.{flight_id}"
                    if record.get("origin_airport_id") != expected_origin:
                        location = expected_origin or "an unknown location"
                        self.add(
                            "physical_discontinuity",
                            f"{path}.origin_airport_id",
                            f"aircraft is expected at {location}; explicit repositioning is required",
                            "dated_flight",
                            flight_id,
                        )
                    if previous is not None and _canonical_utc(
                        previous.get("scheduled_in_block_utc")
                    ):
                        gap = (
                            parse_canonical_utc(record["scheduled_off_block_utc"])
                            - parse_canonical_utc(
                                previous["scheduled_in_block_utc"]
                            )
                        ).total_seconds()
                        if gap < 0:
                            self.add(
                                "aircraft_overlap",
                                path,
                                f"overlaps {previous.get('dated_flight_id')}",
                                "dated_flight",
                                flight_id,
                            )
                        elif gap < minimum_turnaround:
                            self.add(
                                "insufficient_turnaround",
                                path,
                                f"requires at least {minimum_turnaround} seconds after {previous.get('dated_flight_id')}",
                                "dated_flight",
                                flight_id,
                            )
                    previous = record
                    expected_origin = record.get("destination_airport_id")

        for itinerary_id, record in itineraries.items():
            if self.schema_version == 3:
                continue
            path = f"$.world_state.itineraries.{itinerary_id}"
            reject_unknown_fields(
                record,
                {"itinerary_id", "airline_id", "dated_flight_ids"},
                path,
                "itinerary",
                itinerary_id,
            )
            airline_id = self.require_ref(record, "airline_id", airlines, path, "itinerary", itinerary_id)
            flight_ids = record.get("dated_flight_ids")
            if not isinstance(flight_ids, list) or not flight_ids:
                self.add("malformed_required_field", f"{path}.dated_flight_ids", "must be a non-empty list", "itinerary", itinerary_id)
            else:
                valid_flight_ids = [flight_id for flight_id in flight_ids if isinstance(flight_id, str)]
                if len(valid_flight_ids) != len(flight_ids):
                    self.add("malformed_required_field", f"{path}.dated_flight_ids", "must contain only string IDs", "itinerary", itinerary_id)
                if len(valid_flight_ids) != len(set(valid_flight_ids)):
                    self.add("duplicate_reference", f"{path}.dated_flight_ids", "itinerary must not repeat a dated flight", "itinerary", itinerary_id)
                for index, flight_id in enumerate(valid_flight_ids):
                    if flight_id not in flights:
                        self.add("dangling_reference", f"{path}.dated_flight_ids[{index}]", "dated flight does not exist", "itinerary", itinerary_id)
                    elif airline_id and flights[flight_id].get("airline_id") != airline_id:
                        self.add("invalid_ownership", f"{path}.dated_flight_ids[{index}]", "dated flight belongs to another airline", "itinerary", itinerary_id)

        for booking_id, record in bookings.items():
            if self.schema_version == 3:
                continue
            path = f"$.world_state.bookings.{booking_id}"
            reject_unknown_fields(
                record,
                {
                    "booking_id",
                    "airline_id",
                    "itinerary_id",
                    "passenger_count",
                    "booked_at_utc",
                    "total_fare_minor",
                    "currency",
                    "status",
                },
                path,
                "booking",
                booking_id,
            )
            airline_id = self.require_ref(record, "airline_id", airlines, path, "booking", booking_id)
            itinerary_id = self.require_ref(record, "itinerary_id", itineraries, path, "booking", booking_id)
            self.require_timestamp(record, "booked_at_utc", path, "booking", booking_id)
            count = record.get("passenger_count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                self.add("invalid_passenger_count", f"{path}.passenger_count", "must be a positive integer", "booking", booking_id)
            if not is_minor_amount(record.get("total_fare_minor")) or record.get("total_fare_minor", -1) < 0:
                self.add("invalid_money", f"{path}.total_fare_minor", "must be a non-negative integer minor-unit amount", "booking", booking_id)
            if not _currency_code(record.get("currency")):
                self.add("invalid_currency", f"{path}.currency", "must be a three-letter uppercase currency code", "booking", booking_id)
            self.require_text(record, "status", path, "booking", booking_id)
            if itinerary_id and airline_id and itineraries[itinerary_id].get("airline_id") != airline_id:
                self.add("invalid_ownership", f"{path}.itinerary_id", "itinerary belongs to another airline", "booking", booking_id)

        account_ids_by_airline = {airline_id: set() for airline_id in airlines}
        account_codes_by_airline = {airline_id: {} for airline_id in airlines}
        for account_id, record in accounts.items():
            path = f"$.world_state.financial_accounts.{account_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "account", account_id)
            code = self.require_text(record, "code", path, "account", account_id)
            currency = record.get("currency")
            if not _currency_code(currency):
                self.add("invalid_currency", f"{path}.currency", "must be a three-letter uppercase currency code", "account", account_id)
            category = record.get("category")
            if not isinstance(category, str) or category not in ACCOUNT_CATEGORIES:
                self.add("invalid_account_category", f"{path}.category", "unknown account category", "account", account_id)
            if not is_minor_amount(record.get("balance_minor")):
                self.add("invalid_money", f"{path}.balance_minor", "must be an integer minor-unit amount", "account", account_id)
            if airline_id:
                account_ids_by_airline[airline_id].add(account_id)
                if currency != airlines[airline_id].get("base_currency"):
                    self.add("invalid_currency", f"{path}.currency", "must match the owning airline's base currency", "account", account_id)
                if code:
                    previous = account_codes_by_airline[airline_id].get(code)
                    if previous is not None:
                        self.add("duplicate_account_code", f"{path}.code", f"account code is already used by {previous}", "account", account_id)
                    else:
                        account_codes_by_airline[airline_id][code] = account_id
        for airline_id, actual in account_ids_by_airline.items():
            listed = airlines.get(airline_id, {}).get("financial_account_ids", [])
            if (
                isinstance(listed, list)
                and all(isinstance(value, str) for value in listed)
                and set(listed) != actual
            ):
                self.add("account_index_mismatch", f"$.world_state.airlines.{airline_id}.financial_account_ids", "must list exactly the airline's accounts", "airline", airline_id)
            codes = account_codes_by_airline[airline_id]
            for code, category in REQUIRED_ACCOUNT_CODES.items():
                account_id = codes.get(code)
                if account_id is None:
                    self.add("missing_financial_account", f"$.world_state.airlines.{airline_id}.financial_account_ids", f"required account code '{code}' is missing", "airline", airline_id)
                elif accounts[account_id].get("category") != category:
                    self.add("invalid_account_category", f"$.world_state.financial_accounts.{account_id}.category", f"account '{code}' must use category {category}", "account", account_id)

        for transaction_id, record in transactions.items():
            path = f"$.world_state.transactions.{transaction_id}"
            airline_id = self.require_ref(record, "airline_id", airlines, path, "transaction", transaction_id)
            self.require_timestamp(record, "occurred_at_utc", path, "transaction", transaction_id)
            self.require_text(record, "description", path, "transaction", transaction_id)
            entries = record.get("entries")
            if not isinstance(entries, list) or len(entries) < 2:
                self.add("invalid_transaction", f"{path}.entries", "must contain at least two entries", "transaction", transaction_id)
                continue
            total = 0
            amounts_valid = True
            for index, entry in enumerate(entries):
                entry_path = f"{path}.entries[{index}]"
                if type(entry) is not dict:
                    self.add("invalid_transaction", entry_path, "entry must be a dictionary", "transaction", transaction_id)
                    amounts_valid = False
                    continue
                account_id = entry.get("account_id")
                if not isinstance(account_id, str) or account_id not in accounts:
                    self.add("dangling_reference", f"{entry_path}.account_id", "account does not exist", "transaction", transaction_id)
                elif airline_id and accounts[account_id].get("airline_id") != airline_id:
                    self.add("invalid_ownership", f"{entry_path}.account_id", "account belongs to another airline", "transaction", transaction_id)
                amount = entry.get("amount_minor")
                if not is_minor_amount(amount):
                    self.add("invalid_money", f"{entry_path}.amount_minor", "must be an integer minor-unit amount", "transaction", transaction_id)
                    amounts_valid = False
                else:
                    total += amount
            if amounts_valid and total != 0:
                self.add("unbalanced_transaction", f"{path}.entries", "entry amounts must sum to zero", "transaction", transaction_id)

        owner_targets = {
            "airline": airlines,
            "aircraft": aircraft,
            "connection": connections,
            "schedule": schedules,
            "dated_flight": flights,
            "booking": bookings,
        }
        revisions = self.envelope.get("simulation", {}).get("operation_revisions", {})
        simulation_time = self.envelope.get("simulation", {}).get("time_utc")
        cursor = self.envelope.get("simulation", {}).get("event_order_cursor")
        seen_sequences = {}

        def validate_event(event_id, record, path, pending):
            self.require_text(record, "event_type", path, "event", event_id)
            due = self.require_timestamp(record, "due_at_utc", path, "event", event_id)
            if pending and due and _canonical_utc(simulation_time) and due < simulation_time:
                self.add("event_scheduled_in_past", f"{path}.due_at_utc", "pending event cannot precede simulation time", "event", event_id)
            owner_type = record.get("owner_type")
            owner_id = record.get("owner_id")
            if (
                not isinstance(owner_type, str)
                or owner_type not in owner_targets
                or not isinstance(owner_id, str)
                or owner_id not in owner_targets.get(owner_type, {})
            ):
                self.add("dangling_reference", f"{path}.owner_id", "event owner does not exist", "event", event_id)
            revision = record.get("operation_revision")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                self.add("invalid_revision", f"{path}.operation_revision", "must be a non-negative integer", "event", event_id)
            elif isinstance(owner_id, str):
                current_revision = revisions.get(owner_id) if type(revisions) is dict else None
                if current_revision is None:
                    self.add("missing_operation_revision", f"$.simulation.operation_revisions.{owner_id}", "event owner must have a persisted revision", "event", event_id)
                elif isinstance(current_revision, int) and revision > current_revision:
                    self.add("invalid_revision", f"{path}.operation_revision", "cannot exceed the owner's current revision", "event", event_id)
            order_key = record.get("order_key")
            if (
                not isinstance(order_key, list)
                or len(order_key) != 2
                or any(
                    isinstance(value, bool) or not isinstance(value, int) or value < 0
                    for value in order_key
                )
            ):
                self.add("invalid_event_order", f"{path}.order_key", "must be [non-negative priority, non-negative sequence]", "event", event_id)
            else:
                sequence = order_key[1]
                previous = seen_sequences.get(sequence)
                if previous is not None:
                    self.add("duplicate_event_order", f"{path}.order_key", f"sequence is already used by {previous}", "event", event_id)
                else:
                    seen_sequences[sequence] = event_id
                if isinstance(cursor, int) and sequence >= cursor:
                    self.add("invalid_event_cursor", f"{path}.order_key", "sequence must be below the next ordering cursor", "event", event_id)
            payload = self.require_mapping(record.get("payload"), f"{path}.payload")
            payload_error = json_compatibility_error(payload)
            if payload_error:
                _payload_path, message = payload_error
                self.add("not_json_compatible", f"{path}.payload", message, "event", event_id)
            expected_statuses = {PENDING_EVENT_STATUS} if pending else TERMINAL_EVENT_STATUSES
            status = record.get("status")
            if not isinstance(status, str) or status not in expected_statuses:
                self.add("invalid_event_status", f"{path}.status", f"must be one of {sorted(expected_statuses)}", "event", event_id)
            if pending:
                if "resolved_at_utc" in record:
                    self.add("invalid_event_status", f"{path}.resolved_at_utc", "pending event cannot have a resolution timestamp", "event", event_id)
            else:
                resolved_at = self.require_timestamp(record, "resolved_at_utc", path, "event", event_id)
                if resolved_at and _canonical_utc(simulation_time) and resolved_at > simulation_time:
                    self.add("invalid_event_resolution", f"{path}.resolved_at_utc", "cannot be later than simulation time", "event", event_id)
                if (
                    resolved_at
                    and due
                    and isinstance(status, str)
                    and status in {"COMPLETED", "STALE"}
                    and resolved_at != due
                ):
                    self.add("invalid_event_resolution", f"{path}.resolved_at_utc", "completed and stale events resolve at their due timestamp", "event", event_id)

        for event_id, record in events.items():
            validate_event(event_id, record, f"$.world_state.pending_events.{event_id}", True)
        for event_id, record in event_history.items():
            validate_event(event_id, record, f"$.world_state.event_history.{event_id}", False)

        valid_owner_ids = set().union(*(set(target) for target in owner_targets.values()))
        if type(revisions) is dict:
            for owner_id in revisions:
                if isinstance(owner_id, str) and owner_id not in valid_owner_ids:
                    self.add("dangling_reference", f"$.simulation.operation_revisions.{owner_id}", "revision owner does not exist")

        for key, record in operations.items():
            path = f"$.world_state.active_aircraft_operations.{key}"
            if type(record) is not dict:
                self.add("invalid_entity", path, "operation must be a dictionary", "operation", str(key))
                continue
            if key not in flights or record.get("dated_flight_id") != key:
                self.add("dangling_reference", f"{path}.dated_flight_id", "operation key and dated flight reference must match", "operation", str(key))
            aircraft_id = record.get("aircraft_id")
            if not isinstance(aircraft_id, str) or aircraft_id not in aircraft:
                self.add("dangling_reference", f"{path}.aircraft_id", "aircraft does not exist", "operation", str(key))
            elif key in flights and aircraft[aircraft_id].get("airline_id") != flights[key].get("airline_id"):
                self.add("invalid_ownership", f"{path}.aircraft_id", "operation aircraft belongs to another airline", "operation", str(key))
            self.require_text(record, "state", path, "operation", str(key))
            revision = record.get("revision")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                self.add("invalid_revision", f"{path}.revision", "must be a non-negative integer", "operation", str(key))

        demand = self.require_mapping(world.get("demand_state"), "$.world_state.demand_state")
        demand_fields = {
            "demand_model_revision",
            "universe_date",
            "input_fingerprint",
            "rounding_policy",
            "processed_cohorts",
        }
        if self.schema_version in (2, 3):
            demand_fields.update(
                {
                    "processed_cohort_schema_version",
                    "model3_terminal_demand_revision",
                    "model4_revision_contexts",
                }
            )
        for field in sorted(set(demand) - demand_fields, key=repr):
            code = (
                "derived_demand_cache_persisted"
                if field
                in {
                    "market_demand",
                    "fractional_accumulators",
                    "origin_pools",
                    "raw_pair_scores",
                    "destination_pair_shares",
                    "base_daily_bookers",
                    "indexes",
                    "cache",
                }
                else "unknown_authoritative_field"
            )
            self.add(
                code,
                f"$.world_state.demand_state.{field}",
                "field is not persistent Milestone 4 demand authority",
                "demand",
            )
        demand_revision = demand.get("demand_model_revision")
        configured_demand_revision = self.envelope.get("simulation", {}).get(
            "configuration", {}
        ).get("demand", {}).get("revision")
        if (
            isinstance(demand_revision, bool)
            or not isinstance(demand_revision, int)
            or demand_revision < 1
        ):
            self.add(
                "invalid_demand_revision",
                "$.world_state.demand_state.demand_model_revision",
                "must be a positive integer",
                "demand",
            )
        elif demand_revision != configured_demand_revision:
            self.add(
                "inconsistent_demand_revision",
                "$.world_state.demand_state.demand_model_revision",
                "must equal simulation.configuration.demand.revision",
                "demand",
            )
        if not _local_date(demand.get("universe_date")):
            self.add(
                "invalid_local_date",
                "$.world_state.demand_state.universe_date",
                "must be canonical YYYY-MM-DD",
                "demand",
            )
        input_fingerprint = demand.get("input_fingerprint")
        if (
            not isinstance(input_fingerprint, str)
            or len(input_fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in input_fingerprint)
        ):
            self.add(
                "invalid_demand_input_fingerprint",
                "$.world_state.demand_state.input_fingerprint",
                "must be lowercase SHA-256 text",
                "demand",
            )
        else:
            try:
                active_model = self.envelope.get("simulation", {}).get("configuration", {}).get("demand", {}).get("model_version")
                fingerprint_calculator = (
                    calculate_model4_input_fingerprint
                    if active_model == MODEL4_DEMAND_MODEL_VERSION
                    else calculate_demand_input_fingerprint
                )
                expected_fingerprint = fingerprint_calculator(self.envelope)
            except (KeyError, OverflowError, RecursionError, TypeError, ValueError):
                expected_fingerprint = None
                self.add(
                    "invalid_demand_fingerprint_input",
                    "$.world_state.demand_state.input_fingerprint",
                    "demand inputs cannot be encoded by the canonical fingerprint contract",
                    "demand",
                )
            if expected_fingerprint is not None and input_fingerprint != expected_fingerprint:
                self.add(
                    "inconsistent_demand_revision",
                    "$.world_state.demand_state.input_fingerprint",
                    "demand inputs changed outside an explicit revision boundary",
                    "demand",
                )
        if demand.get("rounding_policy") != DEMAND_ROUNDING_POLICY:
            self.add(
                "invalid_demand_rounding_policy",
                "$.world_state.demand_state.rounding_policy",
                f"must equal {DEMAND_ROUNDING_POLICY}",
                "demand",
            )
        contexts = {}
        if self.schema_version in (2, 3):
            if demand.get("processed_cohort_schema_version") != PROCESSED_COHORT_SCHEMA_VERSION or isinstance(demand.get("processed_cohort_schema_version"), bool):
                self.add("invalid_processed_cohort_schema_version", "$.world_state.demand_state.processed_cohort_schema_version", f"must equal {PROCESSED_COHORT_SCHEMA_VERSION}", "demand")
            contexts = self._validate_model4_revision_contexts(demand)
            active_model = self.envelope.get("simulation", {}).get("configuration", {}).get("demand", {}).get("model_version")
            terminal = demand.get("model3_terminal_demand_revision")
            if active_model == DEMAND_MODEL_VERSION:
                if terminal is not None:
                    self.add("premature_model4_activation", "$.world_state.demand_state.model3_terminal_demand_revision", "must remain null while Model 3 is active", "demand")
                if contexts:
                    self.add("premature_model4_activation", "$.world_state.demand_state.model4_revision_contexts", "must remain empty while Model 3 is active", "demand")
            elif active_model == MODEL4_DEMAND_MODEL_VERSION:
                if isinstance(terminal, bool) or not isinstance(terminal, int) or terminal < 1 or not isinstance(demand_revision, int) or terminal >= demand_revision:
                    self.add("inconsistent_demand_revision", "$.world_state.demand_state.model3_terminal_demand_revision", "must identify a positive terminal Model 3 revision before the current Model 4 revision", "demand")
                    self.add("unsupported_demand_model", "$.simulation.configuration.demand.model_version", "Model 4 must be entered through the atomic activation boundary", "demand")
                else:
                    context_revisions = [
                        context.get("demand_model_revision")
                        for context in contexts.values()
                        if isinstance(context, dict)
                    ]
                    valid_context_revisions = [
                        revision
                        for revision in context_revisions
                        if isinstance(revision, int) and not isinstance(revision, bool)
                    ]
                    expected_revisions = list(range(terminal + 1, demand_revision + 1))
                    if (
                        len(valid_context_revisions) != len(context_revisions)
                        or sorted(valid_context_revisions) != expected_revisions
                    ):
                        self.add("invalid_model4_revision_context", "$.world_state.demand_state.model4_revision_contexts", "must contain exactly one context for every Model 4 demand revision and no other revisions", "demand")
                current_contexts = [context for context in contexts.values() if isinstance(context, dict) and context.get("demand_model_revision") == demand_revision]
                if len(current_contexts) != 1:
                    self.add("invalid_model4_revision_context", "$.world_state.demand_state.model4_revision_contexts", "must contain exactly one context for the current Model 4 revision", "demand")
                elif current_contexts[0].get("model4_input_fingerprint") != demand.get("input_fingerprint"):
                    self.add("inconsistent_demand_fingerprint", "$.world_state.demand_state.model4_revision_contexts", "current revision context must reference the current Model 4 input fingerprint", "demand")
                else:
                    current_context = current_contexts[0]
                    configuration = self.envelope["simulation"]["configuration"]["demand"]
                    travel = configuration["travel_scope_configuration"]
                    market_pack = configuration["market_pack_configuration"]
                    expected_context_values = {
                        "demand_model_version": MODEL4_DEMAND_MODEL_VERSION,
                        "configuration_version": configuration["configuration_version"],
                        "configuration_revision": configuration["revision"],
                        "universe_date": demand.get("universe_date"),
                        "travel_scope_configuration_version": travel["configuration_version"],
                        "travel_scope_revision": travel["revision"],
                        "daily_multiplier_min_bps": configuration["daily_multiplier_min_bps"],
                        "daily_multiplier_max_bps": configuration["daily_multiplier_max_bps"],
                        "country_reference_snapshot_version": travel["reference_snapshot_version"],
                    }
                    for field, expected in expected_context_values.items():
                        if current_context.get(field) != expected:
                            self.add("inconsistent_demand_revision", f"$.world_state.demand_state.model4_revision_contexts.{current_context.get('revision_context_id')}.{field}", "current revision context witness does not match current demand authority", "demand")
        cohorts = self.require_mapping(
            demand.get("processed_cohorts"),
            "$.world_state.demand_state.processed_cohorts",
        )
        cohort_fields = {
            "cohort_key",
            "market_id",
            "cohort_date",
            "demand_model_revision",
            "daily_multipliers_bps",
            "composite_multiplier_ppm",
            "actual_daily_bookers",
            "rounding_policy",
            "resolution_fingerprint",
        }
        for cohort_key, record in cohorts.items():
            path = f"$.world_state.demand_state.processed_cohorts.{cohort_key}"
            if not isinstance(cohort_key, str) or type(record) is not dict:
                self.add(
                    "invalid_demand_cohort",
                    path,
                    "cohort must be a string-keyed dictionary",
                    "demand_cohort",
                    str(cohort_key),
                )
                continue
            if self.schema_version in (2, 3):
                wrapper_fields = {"contract", "payload"}
                for field in sorted(set(record) - wrapper_fields, key=repr):
                    self.add("unknown_authoritative_field", f"{path}.{field}", "field is not part of a processed-cohort wrapper", "demand_cohort", cohort_key)
                contract = record.get("contract")
                if contract not in {
                    MODEL3_PROCESSED_COHORT_V1,
                    MODEL4_TRAVEL_SCOPE_COHORT_V1,
                }:
                    self.add("unknown_processed_cohort_contract", f"{path}.contract", "must name one of the two supported cohort contracts", "demand_cohort", cohort_key)
                    continue
                if contract == MODEL4_TRAVEL_SCOPE_COHORT_V1:
                    self._validate_model4_cohort(record, cohort_key, markets, contexts, path)
                    if self.envelope.get("simulation", {}).get("configuration", {}).get("demand", {}).get("model_version") == DEMAND_MODEL_VERSION:
                        self.add("premature_model4_activation", path, "Model 4 cohorts cannot exist while Model 3 is active", "demand_cohort", cohort_key)
                    continue
                record = self.require_mapping(record.get("payload"), f"{path}.payload")
                path = f"{path}.payload"
            for field in sorted(set(record) - cohort_fields, key=repr):
                self.add(
                    "unknown_authoritative_field",
                    f"{path}.{field}",
                    "field is not part of a processed demand cohort",
                    "demand_cohort",
                    cohort_key,
                )
            if record.get("cohort_key") != cohort_key:
                self.add(
                    "id_key_mismatch",
                    f"{path}.cohort_key",
                    "cohort_key must equal its collection key",
                    "demand_cohort",
                    cohort_key,
                )
            market_id = record.get("market_id")
            if not isinstance(market_id, str) or market_id not in markets:
                self.add(
                    "dangling_reference",
                    f"{path}.market_id",
                    "must reference an existing directional market",
                    "demand_cohort",
                    cohort_key,
                )
            cohort_date = record.get("cohort_date")
            if not _local_date(cohort_date):
                self.add(
                    "invalid_local_date",
                    f"{path}.cohort_date",
                    "must be canonical YYYY-MM-DD",
                    "demand_cohort",
                    cohort_key,
                )
            if isinstance(market_id, str) and _local_date(cohort_date):
                expected_key = f"{market_id}@{cohort_date}"
                if cohort_key != expected_key:
                    self.add(
                        "invalid_demand_cohort_key",
                        f"{path}.cohort_key",
                        "must equal market_id@cohort_date",
                        "demand_cohort",
                        cohort_key,
                    )
            record_revision = record.get("demand_model_revision")
            if (
                isinstance(record_revision, bool)
                or not isinstance(record_revision, int)
                or record_revision < 1
                or (
                    isinstance(demand_revision, int)
                    and record_revision > demand_revision
                )
            ):
                self.add(
                    "invalid_demand_revision",
                    f"{path}.demand_model_revision",
                    "must identify a positive applied demand revision",
                    "demand_cohort",
                    cohort_key,
                )
            multipliers = self.require_mapping(
                record.get("daily_multipliers_bps"),
                f"{path}.daily_multipliers_bps",
            )
            if set(multipliers) != set(DEMAND_MULTIPLIER_CATEGORIES):
                self.add(
                    "invalid_demand_multipliers",
                    f"{path}.daily_multipliers_bps",
                    "must contain exactly the canonical multiplier categories",
                    "demand_cohort",
                    cohort_key,
                )
            configured_min = self.envelope.get("simulation", {}).get(
                "configuration", {}
            ).get("demand", {}).get("daily_multiplier_min_bps")
            configured_max = self.envelope.get("simulation", {}).get(
                "configuration", {}
            ).get("demand", {}).get("daily_multiplier_max_bps")
            for category, value in multipliers.items():
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                    or (
                        record_revision == demand_revision
                        and (
                            not isinstance(configured_min, int)
                            or not isinstance(configured_max, int)
                            or value < configured_min
                            or value > configured_max
                        )
                    )
                ):
                    self.add(
                        "invalid_demand_multipliers",
                        f"{path}.daily_multipliers_bps.{category}",
                        "must be an integer basis-point value in the configured range",
                        "demand_cohort",
                        cohort_key,
                    )
            if (
                set(multipliers) == set(DEMAND_MULTIPLIER_CATEGORIES)
                and all(
                    isinstance(multipliers.get(category), int)
                    and not isinstance(multipliers.get(category), bool)
                    and multipliers[category] >= 0
                    for category in DEMAND_MULTIPLIER_CATEGORIES
                )
            ):
                numerator = (
                    reduce(
                        mul,
                        (
                            multipliers[category]
                            for category in DEMAND_MULTIPLIER_CATEGORIES
                        ),
                        1,
                    )
                    * 1_000_000
                )
                denominator = 10_000 ** len(DEMAND_MULTIPLIER_CATEGORIES)
                expected_composite, remainder = divmod(numerator, denominator)
                comparison = remainder * 2 - denominator
                if comparison > 0 or (
                    comparison == 0 and expected_composite % 2 == 1
                ):
                    expected_composite += 1
                if record.get("composite_multiplier_ppm") != expected_composite:
                    self.add(
                        "inconsistent_demand_cohort",
                        f"{path}.composite_multiplier_ppm",
                        "must be the half-even parts-per-million composition of the stored multipliers",
                        "demand_cohort",
                        cohort_key,
                    )
            for field in ("composite_multiplier_ppm", "actual_daily_bookers"):
                value = record.get(field)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    self.add(
                        "invalid_demand_cohort",
                        f"{path}.{field}",
                        "must be a non-negative integer",
                        "demand_cohort",
                        cohort_key,
                    )
            if record.get("rounding_policy") != DEMAND_ROUNDING_POLICY:
                self.add(
                    "invalid_demand_rounding_policy",
                    f"{path}.rounding_policy",
                    f"must equal {DEMAND_ROUNDING_POLICY}",
                    "demand_cohort",
                    cohort_key,
                )
            resolution_fingerprint = record.get("resolution_fingerprint")
            if (
                not isinstance(resolution_fingerprint, str)
                or len(resolution_fingerprint) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in resolution_fingerprint
                )
            ):
                self.add(
                    "invalid_demand_cohort_fingerprint",
                    f"{path}.resolution_fingerprint",
                    "must be lowercase SHA-256 text",
                    "demand_cohort",
                    cohort_key,
                )
            else:
                try:
                    expected_resolution_fingerprint = (
                        calculate_demand_cohort_fingerprint(self.envelope, record)
                    )
                except (
                    KeyError,
                    OverflowError,
                    RecursionError,
                    TypeError,
                    ValueError,
                ):
                    expected_resolution_fingerprint = None
                if expected_resolution_fingerprint != resolution_fingerprint:
                    self.add(
                        "inconsistent_demand_cohort_fingerprint",
                        f"{path}.resolution_fingerprint",
                        "stored cohort contents do not match their integrity witness",
                        "demand_cohort",
                        cohort_key,
                    )
        history = self.require_mapping(world.get("history"), "$.world_state.history")
        for field in ("operations", "financial", "world_events"):
            if not isinstance(history.get(field), list):
                self.add("invalid_type", f"$.world_state.history.{field}", "must be a list")

        ui = self.require_mapping(self.envelope.get("ui_state"), "$.ui_state")
        focus = ui.get("current_focus_airline_id")
        if focus is not None and (not isinstance(focus, str) or focus not in airlines):
            self.add("dangling_reference", "$.ui_state.current_focus_airline_id", "focused airline does not exist")
        selected_screen = ui.get("selected_screen")
        if selected_screen is not None and not isinstance(selected_screen, str):
            self.add("invalid_type", "$.ui_state.selected_screen", "must be null or a string")
        if type(ui.get("filters")) is not dict:
            self.add("invalid_type", "$.ui_state.filters", "must be a dictionary")
        if self.schema_version == 3:
            validate_schema3_booking_authority(self)

    def validate_no_name_references_or_float_money(self):
        forbidden = {
            "airline_name",
            "aircraft_registration",
            "assigned_aircraft_registration",
            "assigned_aircraft",
            "current_focus",
            "origin_iata",
            "destination_iata",
            "route_id",
        }

        stack = [(self.world, "$.world_state")]
        seen_containers = set()
        while stack:
            value, path = stack.pop()
            if type(value) is dict:
                marker = id(value)
                if marker in seen_containers:
                    continue
                seen_containers.add(marker)
                for key, nested in value.items():
                    child_path = f"{path}.{key}"
                    if key in forbidden:
                        self.add("name_based_authoritative_reference", child_path, "legacy/name-based authoritative field is forbidden")
                    if isinstance(key, str) and key.endswith("_minor") and not is_minor_amount(nested):
                        self.add("invalid_money", child_path, "authoritative money must be integer minor units")
                    if (
                        isinstance(key, str)
                        and key.endswith("_utc")
                        and nested is not None
                        and not _canonical_utc(nested)
                    ):
                        self.add("invalid_timestamp", child_path, "authoritative timestamp must be canonical UTC YYYY-MM-DDTHH:MM:SSZ")
                    stack.append((nested, child_path))
            elif type(value) is list:
                marker = id(value)
                if marker in seen_containers:
                    continue
                seen_containers.add(marker)
                for index, nested in enumerate(value):
                    stack.append((nested, f"{path}[{index}]"))

    def run(self):
        if self.validate_root():
            self.validate_collections_and_ids()
            self.validate_structure()
            self.validate_no_name_references_or_float_money()
        return ValidationResult(tuple(self.errors))


def validate_world(envelope):
    """Return structured errors without repairing or mutating ``envelope``."""
    return _Validator(envelope).run()
