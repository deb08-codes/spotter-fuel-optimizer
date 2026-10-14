import requests
from django.core.cache import cache

from .geocoding import geocode_address

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"


class RoutingError(Exception):
    """Raised when a driving route cannot be calculated."""


def get_driving_route(start_location, finish_location):
    """
    Exactly ONE call to the routing API (plus up to two geocoding lookups,
    which are cached; 'lat,lng' inputs need none).
    """
    key = "route:" + "|".join(" ".join(v.lower().split()) for v in (start_location, finish_location))
    cached = cache.get(key)
    if cached:
        return cached

    start = geocode_address(start_location)
    finish = geocode_address(finish_location)
    coordinates = f"{start['longitude']},{start['latitude']};{finish['longitude']},{finish['latitude']}"

    try:
        response = requests.get(
            f"{OSRM_URL}/{coordinates}",
            params={"overview": "full", "geometries": "geojson", "steps": "false"},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RoutingError("The routing service is currently unavailable.") from exc

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError("A driving route could not be found for these locations.")

    route = data["routes"][0]
    result = {
        "distance_miles": round(route["distance"] / 1609.344, 2),
        "duration_minutes": round(route["duration"] / 60, 2),
        "geometry": route["geometry"],
    }
    cache.set(key, result, 60 * 60 * 24)
    return result
