"""Read-only Stage 1 catalog. No legacy purchase flow or live-world dependency."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from game.world_state.aircraft_catalog import parse_aircraft_catalog, validate_aircraft_catalog


PH_AIRCRAFT_CATALOG_VERSION = "ph-aircraft-catalog-v1"
_DATA = Path(__file__).resolve().parents[2] / "Data" / "Stage1"
# Explicit registry: no file names derived from caller input and no latest fallback.
_VERSIONS = {
    PH_AIRCRAFT_CATALOG_VERSION: ("aircraft_catalog_v1.json", "256f6603af3f242f55a6ce17572f8dc61f6abaf90da6d56773cb522ede97d4f8"),
}


def _encoded(pack):
    return json.dumps(pack, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


@dataclass(frozen=True, init=False)
class AircraftCatalog:
    """An immutable value; every returned dictionary is a detached projection."""

    _json: str

    def __init__(self, pack):
        validate_aircraft_catalog(pack)
        object.__setattr__(self, "_json", _encoded(pack))

    @property
    def version(self):
        return json.loads(self._json)["catalog_version"]

    def manufacturers(self):
        records = json.loads(self._json)["manufacturers"]
        return tuple(sorted(records.values(), key=lambda row: (
            row["display_name"].casefold(), row["manufacturer_id"])))

    def models(self, manufacturer_id):
        pack = json.loads(self._json)
        if type(manufacturer_id) is not str or manufacturer_id not in pack["manufacturers"]:
            raise ValueError("unknown catalog manufacturer identifier")
        return tuple(sorted(
            (row for row in pack["models"].values() if row["manufacturer_id"] == manufacturer_id),
            key=lambda row: (row["display_name"].casefold(), row["model_id"])))

    def model(self, model_id):
        pack = json.loads(self._json)
        if type(model_id) is not str or model_id not in pack["models"]:
            raise ValueError("unknown catalog model identifier")
        row = pack["models"][model_id]
        return {
            "catalog_version": pack["catalog_version"],
            "model": row,
            "manufacturer": pack["manufacturers"][row["manufacturer_id"]],
            "reference_price": pack["reference_prices"][model_id],
            "sources": tuple(pack["sources"][key] for key in sorted(row["source_ids"])),
        }


def load_aircraft_catalog(*, catalog_version):
    """Resolve and verify one published version before exposing any content."""
    if type(catalog_version) is not str or catalog_version not in _VERSIONS:
        raise ValueError("unsupported aircraft catalog version")
    filename, expected_digest = _VERSIONS[catalog_version]
    pack = parse_aircraft_catalog((_DATA / filename).read_text(encoding="utf-8"))
    if pack["catalog_version"] != catalog_version:
        raise ValueError("aircraft catalog version mismatch")
    if sha256(_encoded(pack).encode("ascii")).hexdigest() != expected_digest:
        raise ValueError("published aircraft catalog content mismatch")
    return AircraftCatalog(pack)
