"""Offline city -> (lat, lng) lookup, so no geocoding API is needed per request."""
import re
from pathlib import Path

import pandas as pd

CITIES_PATH = Path(__file__).resolve().parents[2] / "fuel_data" / "us_cities.csv"


def city_key(city, state):
    name = str(city).lower().replace(".", "")
    name = re.sub(r"\bsaint\b", "st", name)
    name = re.sub(r"\bft\b", "fort", name)
    name = re.sub(r"[^a-z0-9 ]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name + "|" + str(state).strip().upper()


def load_city_index(path=CITIES_PATH):
    """Return {city_key: (latitude, longitude)}."""
    cities = pd.read_csv(path)
    index = {}
    for city, state, lat, lng in zip(
        cities["CITY"], cities["STATE_CODE"], cities["LATITUDE"], cities["LONGITUDE"]
    ):
        index.setdefault(city_key(city, state), (float(lat), float(lng)))
    return index
