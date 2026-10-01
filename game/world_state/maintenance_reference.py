"""Versioned aircraft classification and schema-7 maintenance configuration."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

CLASSIFICATION_VERSION = "ph-aircraft-aerodrome-class-v1"
FACTORS = MappingProxyType({"A": 15, "B": 35, "C": 80, "D": 130, "E": 200, "F": 300, "G": 450})
_DATA = Path(__file__).resolve().parents[2] / "Data" / "Stage1"

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate classification key: {key}")
        result[key] = value
    return result

def class_for_wingspan(value):
    if type(value) is not int or value <= 0:
        raise ValueError("wingspan must be positive integer millimetres")
    for limit, code in ((15000, "A"), (24000, "B"), (36000, "C"),
                        (52000, "D"), (65000, "E"), (80000, "F")):
        if value < limit:
            return code
    return "G"

def validate_classification(pack, catalog_ids):
    if type(pack) is not dict or set(pack) != {"contract", "classification_version", "band_basis", "models"}:
        raise ValueError("classification fields invalid")
    if (pack["contract"] != "PH_AIRCRAFT_AERODROME_CLASS_V1"
            or pack["classification_version"] != CLASSIFICATION_VERSION
            or pack["band_basis"] != "ICAO_WINGSPAN_WITH_PROJECT_G_EXTENSION"):
        raise ValueError("classification version invalid")
    models = pack["models"]
    if type(models) is not dict or set(models) != set(catalog_ids) | {"A320-200"}:
        raise ValueError("classification coverage invalid")
    for model_id, record in models.items():
        if type(record) is not dict or set(record) != {"wingspan_mm", "aerodrome_class", "source_url"}:
            raise ValueError(f"{model_id}: invalid fields")
        if record["aerodrome_class"] != class_for_wingspan(record["wingspan_mm"]):
            raise ValueError(f"{model_id}: incorrect dimensional class")
        url = record["source_url"]
        if type(url) is not str or urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
            raise ValueError(f"{model_id}: invalid source URL")

@lru_cache(maxsize=1)
def _cached_classification():
    catalog = json.loads((_DATA / "aircraft_catalog_v1.json").read_text(encoding="utf-8"), object_pairs_hook=_unique)
    pack = json.loads((_DATA / "aircraft_aerodrome_class_v1.json").read_text(encoding="utf-8"), object_pairs_hook=_unique)
    validate_classification(pack, catalog["models"])
    return pack

def load_classification():
    """Return a detached view; callers cannot mutate cached reference authority."""
    return deepcopy(_cached_classification())

def new_maintenance_configuration():
    source = {
        "contract": "PH_ROUTINE_MAINTENANCE_CONFIGURATION_V1",
        "configuration_version": "ph-routine-maintenance-v1",
        "classification_version": CLASSIFICATION_VERSION,
        "factor_minor_per_km_by_class": dict(FACTORS),
    }
    source["configuration_fingerprint"] = hashlib.sha256(json.dumps(
        source, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("ascii")).hexdigest()
    return source

def validate_maintenance_configuration(configuration):
    if configuration != new_maintenance_configuration():
        raise ValueError("maintenance configuration or fingerprint invalid")
    _cached_classification()

def class_for_model(model_id):
    try:
        return _cached_classification()["models"][model_id]["aerodrome_class"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported aircraft model: {model_id}") from exc
