import re

import requests
from django.core.cache import cache

GEOCODING_URL = "https://nominatim.openstreetmap.org/search"
LATLNG = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


class GeocodingError(Exception):
    """Raised when an address cannot be geocoded."""


def geocode_address(address):
    """Resolve a US address to coordinates. Accepts 'lat,lng' too (no API call)."""
    match = LATLNG.match(address)
    if match:
        lat, lng = float(match.group(1)), float(match.group(2))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise GeocodingError(f"Invalid coordinates: {address}")
        return {"latitude": lat, "longitude": lng}

    key = "geo:" + " ".join(address.lower().split())
    cached = cache.get(key)
    if cached:
        return cached

    try:
        response = requests.get(
            GEOCODING_URL,
            params={"q": address, "format": "jsonv2", "countrycodes": "us", "limit": 1},
            headers={"User-Agent": "SpotterFuelOptimizer/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GeocodingError("The geocoding service is currently unavailable.") from exc

    if not results:
        raise GeocodingError(f"Could not find a US location matching: {address}")

    point = {"latitude": float(results[0]["lat"]), "longitude": float(results[0]["lon"])}
    cache.set(key, point, 60 * 60 * 24 * 30)
    return point
