"""Cost-optimal refuelling plan along a route (gas-station look-ahead greedy)."""

TANK_GALLONS = 50          # 500 mile range at 10 mpg
MILES_PER_GALLON = 10
MAX_RANGE_MILES = TANK_GALLONS * MILES_PER_GALLON
EPS = 1e-9


class NoFeasibleRouteError(ValueError):
    """The destination cannot be reached with the stations available."""


def optimize_fuel_stops(
    route_distance_miles,
    stations,
    starting_fuel_gallons=TANK_GALLONS,
    tank_gallons=TANK_GALLONS,
    miles_per_gallon=MILES_PER_GALLON,
):
    """
    Each station needs: distance_from_start_miles, price, name, city, state.

    Rule at every stop (this is optimal for a single fuel price per station):
      1. If a cheaper station is reachable on a full tank, buy only enough to get there.
      2. Else if the destination is reachable on a full tank, buy only enough to finish.
      3. Else fill the tank and continue to the cheapest station in range.

    Only fuel bought at stops is charged: the starting fuel is assumed to be
    already in the tank. Nothing is bought "just in case" at the end.
    """
    if route_distance_miles < 0:
        raise ValueError("Route distance cannot be negative.")
    if not 0 <= starting_fuel_gallons <= tank_gallons:
        raise ValueError(f"Starting fuel must be between 0 and {tank_gallons} gallons.")

    full_range = tank_gallons * miles_per_gallon
    ahead = sorted(
        (s for s in stations if 0 < s["distance_from_start_miles"] < route_distance_miles),
        key=lambda s: (s["distance_from_start_miles"], s["price"]),
    )

    position, fuel, total_cost = 0.0, float(starting_fuel_gallons), 0.0
    current = None  # None = still at the start, where nothing can be bought
    stops = []

    while True:
        remaining = route_distance_miles - position
        if remaining <= fuel * miles_per_gallon + EPS:
            fuel -= remaining / miles_per_gallon
            break

        horizon = full_range if current else fuel * miles_per_gallon
        in_range = [
            s for s in ahead
            if position + EPS < s["distance_from_start_miles"] <= position + horizon + EPS
        ]

        buy, target = 0.0, None
        if current is None:
            if not in_range:
                raise NoFeasibleRouteError(
                    "No fuel station is reachable from the start with the starting fuel."
                )
            target = min(in_range, key=lambda s: (s["price"], s["distance_from_start_miles"]))
        else:
            cheaper = next((s for s in in_range if s["price"] < current["price"]), None)
            if cheaper:
                target = cheaper
                buy = max(0.0, (target["distance_from_start_miles"] - position) / miles_per_gallon - fuel)
            elif remaining <= full_range + EPS:
                buy = remaining / miles_per_gallon - fuel   # destination; target stays None
            else:
                if not in_range:
                    raise NoFeasibleRouteError(
                        f"No fuel station within {full_range} miles after mile {position:.0f}."
                    )
                buy = tank_gallons - fuel
                target = min(in_range, key=lambda s: (s["price"], s["distance_from_start_miles"]))

        if buy > EPS:
            price = float(current["price"])
            total_cost += buy * price
            fuel += buy
            stops.append(_describe_stop(current, position, buy, price))

        if target is None:
            fuel -= remaining / miles_per_gallon
            break
        fuel -= (target["distance_from_start_miles"] - position) / miles_per_gallon
        position, current = target["distance_from_start_miles"], target

    gallons_bought = sum(s["fuel_purchased_gallons"] for s in stops)
    return {
        "route_distance_miles": round(route_distance_miles, 2),
        "starting_fuel_gallons": starting_fuel_gallons,
        "fuel_stops": stops,
        "total_fuel_cost": round(total_cost, 2),
        "fuel_purchased_gallons": round(gallons_bought, 2),
        "fuel_used_gallons": round(route_distance_miles / miles_per_gallon, 2),
        "arrival_fuel_gallons": round(max(fuel, 0.0), 2),
    }


def _describe_stop(station, position, gallons, price):
    return {
        "station_name": station["name"],
        "address": station.get("address", ""),
        "city": station["city"],
        "state": station["state"],
        "latitude": station.get("latitude"),
        "longitude": station.get("longitude"),
        "distance_from_start_miles": round(position, 2),
        "fuel_price_per_gallon": round(price, 3),
        "fuel_purchased_gallons": round(gallons, 2),
        "fuel_cost": round(gallons * price, 2),
    }
