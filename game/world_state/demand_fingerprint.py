"""Canonical fingerprint for persistent Milestone 4 demand inputs."""

import hashlib
import json


DEMAND_INPUT_FINGERPRINT_CONTRACT = "STAGE1_DEMAND_INPUT_SHA256_JSON_V1"
DEMAND_COHORT_FINGERPRINT_CONTRACT = "STAGE1_DEMAND_COHORT_SHA256_JSON_V1"


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
    material = {
        "fingerprint_contract": DEMAND_INPUT_FINGERPRINT_CONTRACT,
        "configuration": envelope["simulation"]["configuration"]["demand"],
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
