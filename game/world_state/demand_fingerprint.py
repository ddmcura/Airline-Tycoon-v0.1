"""Canonical fingerprint for persistent Milestone 4 demand inputs."""

import hashlib
import json


DEMAND_INPUT_FINGERPRINT_CONTRACT = "STAGE1_DEMAND_INPUT_SHA256_JSON_V1"
DEMAND_COHORT_FINGERPRINT_CONTRACT = "STAGE1_DEMAND_COHORT_SHA256_JSON_V1"
MODEL4_COHORT_FINGERPRINT_CONTRACT = "STAGE1_DEMAND_COHORT_SHA256_JSON_V2"
MODEL4_REVISION_CONTEXT_FINGERPRINT_CONTRACT = (
    "STAGE1_DEMAND_REVISION_CONTEXT_SHA256_JSON_V1"
)

MODEL3_CONFIGURATION_FINGERPRINT_FIELDS = (
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
)


AIRPORT_DEMAND_FINGERPRINT_FIELDS = (
    "passenger_demand_eligible",
    "population",
    "latitude_microdegrees",
    "longitude_microdegrees",
    "country_reference",
    "demand_destination_type",
    "active_from_date",
    "active_until_date",
    "demand_input_revision",
)


def _fingerprint(material, label):
    try:
        encoded = json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ValueError(
            f"{label} inputs must be finite canonical JSON values"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def calculate_demand_input_fingerprint(envelope):
    state = envelope["world_state"]
    configuration = envelope["simulation"]["configuration"]["demand"]
    if envelope.get("metadata", {}).get("save_schema_version") == 2:
        configuration = {
            field: configuration[field]
            for field in MODEL3_CONFIGURATION_FINGERPRINT_FIELDS
        }
    material = {
        "fingerprint_contract": DEMAND_INPUT_FINGERPRINT_CONTRACT,
        "configuration": configuration,
        "universe_date": state["demand_state"]["universe_date"],
        "airports": {
            airport_id: {
                field: state["airports"][airport_id].get(field)
                for field in AIRPORT_DEMAND_FINGERPRINT_FIELDS
            }
            for airport_id in sorted(state["airports"])
        },
    }
    return _fingerprint(material, "demand fingerprint")


def calculate_model4_input_fingerprint(envelope):
    """Fingerprint every continuation-critical Model 4 allocation input."""
    state = envelope["world_state"]
    configuration = envelope["simulation"]["configuration"]["demand"]
    material = {
        "fingerprint_contract": "STAGE1_MODEL4_DEMAND_INPUT_SHA256_JSON_V1",
        "lineage_id": envelope["metadata"]["lineage_id"],
        "configuration": configuration,
        "universe_date": state["demand_state"]["universe_date"],
        "countries": {
            country_id: state["countries"][country_id]
            for country_id in sorted(state["countries"])
        },
        "airports": {
            airport_id: state["airports"][airport_id]
            for airport_id in sorted(state["airports"])
        },
        "markets": {
            market_id: state["directional_markets"][market_id]
            for market_id in sorted(state["directional_markets"])
        },
    }
    return _fingerprint(material, "Model 4 demand fingerprint")


def calculate_demand_cohort_fingerprint(envelope, cohort_record):
    material = {
        "fingerprint_contract": DEMAND_COHORT_FINGERPRINT_CONTRACT,
        "world_seed": envelope["deterministic_state"]["world_seed"],
        "cohort": {
            key: cohort_record[key]
            for key in sorted(cohort_record)
            if key != "resolution_fingerprint"
        },
    }
    return _fingerprint(material, "demand cohort fingerprint")


def calculate_model4_revision_context_fingerprint(context):
    material = {
        "fingerprint_contract": MODEL4_REVISION_CONTEXT_FINGERPRINT_CONTRACT,
        "revision_context": {
            key: context[key]
            for key in sorted(context)
            if key != "context_fingerprint"
        },
    }
    return _fingerprint(material, "Model 4 revision context fingerprint")


def calculate_model4_cohort_fingerprint(envelope, wrapper):
    payload = wrapper["payload"]
    context = envelope["world_state"]["demand_state"]["model4_revision_contexts"][
        payload["revision_context_id"]
    ]
    material = {
        "fingerprint_contract": MODEL4_COHORT_FINGERPRINT_CONTRACT,
        "lineage_id": envelope["metadata"]["lineage_id"],
        "world_seed": envelope["deterministic_state"]["world_seed"],
        "contract": wrapper["contract"],
        "revision_context_fingerprint": context["context_fingerprint"],
        "cohort": {
            key: payload[key]
            for key in sorted(payload)
            if key != "resolution_fingerprint"
        },
    }
    return _fingerprint(material, "Model 4 cohort fingerprint")
