"""Find stations along a route and where they sit on it (mile marker)."""
import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import LineString

from routing.models import Station

METERS_PER_MILE = 1609.344

# Equal-area projection in metres for the USA (EPSG:5070).
_to_metres = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)

_index = None


class StationIndex:
    """All stations loaded once into memory, with projected coordinates."""

    def __init__(self, stations):
        self.stations = stations
        lons = np.array([s["longitude"] for s in stations], dtype=float)
        lats = np.array([s["latitude"] for s in stations], dtype=float)
        if len(stations):
            self.x, self.y = _to_metres.transform(lons, lats)
        else:
            self.x = self.y = np.array([])
        self.points = shapely.points(self.x, self.y)


def get_station_index():
    global _index
    if _index is None:
        rows = list(
            Station.objects.values(
                "opis_id", "name", "address", "city", "state", "price", "latitude", "longitude"
            )
        )
        _index = StationIndex(rows)
    return _index


def reset_station_index():
    global _index
    _index = None


def find_stations_along_route(route_coordinates, route_distance_miles, max_distance_miles=10):
    """
    Return stations within `max_distance_miles` of the route.

    Each result carries:
      distance_from_route_miles - sideways distance to the road
      distance_from_start_miles - mile marker along the route (what the optimizer needs)

    The route line is built once per request; the work is vectorised, so a
    cross-country route over ~6.7k stations takes tens of milliseconds.
    """
    if len(route_coordinates) < 2:
        raise ValueError("At least two route coordinates are required.")
    if max_distance_miles < 0:
        raise ValueError("Maximum distance cannot be negative.")

    index = get_station_index()
    if not len(index.stations):
        return []

    lons, lats = zip(*route_coordinates)
    rx, ry = _to_metres.transform(np.array(lons), np.array(lats))
    # Simplify to 100 m: far below the 10-mile search radius, much faster.
    line = LineString(np.column_stack([rx, ry])).simplify(100)
    if line.length == 0:
        return []

    max_m = max_distance_miles * METERS_PER_MILE

    # Cheap bounding-box cut first, then an exact test against the buffered route.
    minx, miny, maxx, maxy = line.bounds
    box = (
        (index.x >= minx - max_m) & (index.x <= maxx + max_m)
        & (index.y >= miny - max_m) & (index.y <= maxy + max_m)
    )
    candidate_ids = np.flatnonzero(box)
    if not len(candidate_ids):
        return []

    zone = line.buffer(max_m)
    shapely.prepare(zone)
    points = index.points[candidate_ids]
    inside = shapely.contains(zone, points)
    hit_ids = candidate_ids[inside]
    hit_points = points[inside]
    if not len(hit_ids):
        return []

    sideways = shapely.distance(hit_points, line) / METERS_PER_MILE
    fraction = shapely.line_locate_point(line, hit_points) / line.length

    results = []
    for i, sideways_miles, frac in zip(hit_ids, sideways, fraction):
        station = dict(index.stations[i])
        station["distance_from_route_miles"] = round(float(sideways_miles), 2)
        station["distance_from_start_miles"] = round(float(frac) * route_distance_miles, 2)
        results.append(station)

    results.sort(key=lambda s: s["distance_from_start_miles"])
    return results
