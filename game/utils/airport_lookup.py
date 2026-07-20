"""Load airport reference records and look them up by IATA code."""

import json
from functools import lru_cache
from pathlib import Path


AIRPORT_DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "Data" / "Airports"


@lru_cache(maxsize=1)
def load_airport_index():
    """Return all bundled airports keyed by upper-case IATA code."""
    index = {}
    for path in sorted(AIRPORT_DATA_DIRECTORY.glob("*/*.json")):
        try:
            countries = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for country in countries.values():
            for airport in country.get("airports", []):
                iata = str(airport.get("iata", "")).strip().upper()
                if iata:
                    index[iata] = airport
    return index


def get_airport_by_iata(iata):
    """Return one bundled airport record, or None when it is unknown."""
    return load_airport_index().get(str(iata or "").strip().upper())
