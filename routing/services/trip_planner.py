from .fuel_optimizer import NoFeasibleRouteError, optimize_fuel_stops
from .route_service import get_driving_route
from .station_matcher import find_stations_along_route

# Widen the search only if a sparse stretch of road has no station in range.
SEARCH_RADII_MILES = (10, 25, 50)


def plan_trip(start_location, finish_location, starting_fuel_gallons=50):
    route = get_driving_route(start_location, finish_location)
    coordinates = route["geometry"]["coordinates"]

    last_error = None
    for radius in SEARCH_RADII_MILES:
        stations = find_stations_along_route(coordinates, route["distance_miles"], radius)
        try:
            plan = optimize_fuel_stops(
                route["distance_miles"], stations, starting_fuel_gallons=starting_fuel_gallons
            )
        except NoFeasibleRouteError as exc:
            last_error = exc
            continue
        return {
            "route": route,
            "plan": plan,
            "search_radius_miles": radius,
            "stations_considered": len(stations),
        }
    raise last_error
