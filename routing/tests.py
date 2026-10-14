import random
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from routing.models import Station
from routing.services.fuel_optimizer import NoFeasibleRouteError, optimize_fuel_stops
from routing.services.station_matcher import find_stations_along_route, reset_station_index


def st(d, price, name="S"):
    return {"distance_from_start_miles": d, "price": price, "name": name, "city": "C", "state": "XX"}


def brute_force_cost(route, stations, start_fuel, tank=50, mpg=10):
    """Exact DP over whole gallons; distances must be multiples of 10 miles."""
    nodes = [(0, None)] + [(s["distance_from_start_miles"], s["price"]) for s in sorted(stations, key=lambda s: s["distance_from_start_miles"])] + [(route, None)]
    inf = float("inf")
    best = [[inf] * (tank + 1) for _ in nodes]
    best[0][start_fuel] = 0
    for i, (d, p) in enumerate(nodes[:-1]):
        for f in range(tank + 1):
            if best[i][f] == inf:
                continue
            for k in range(0, (tank - f) + 1 if p is not None else 1):
                cost = best[i][f] + k * (p or 0)
                for j in range(i + 1, len(nodes)):
                    need = (nodes[j][0] - d) // mpg
                    if need > f + k:
                        break
                    nf = f + k - need
                    best[j][nf] = min(best[j][nf], cost)
    return min(best[-1])


class OptimizerTests(TestCase):
    def test_short_trip_needs_no_stop(self):
        plan = optimize_fuel_stops(300, [st(100, 3.0)])
        self.assertEqual(plan["fuel_stops"], [])
        self.assertEqual(plan["total_fuel_cost"], 0)

    def test_buys_only_enough_to_reach_cheaper_station(self):
        # 20 gal = 200 mi of range: must stop at A (150 mi, $4) but B (450 mi, $3) is cheaper.
        plan = optimize_fuel_stops(800, [st(150, 4.0, "A"), st(450, 3.0, "B")], starting_fuel_gallons=20)
        self.assertEqual([s["station_name"] for s in plan["fuel_stops"]], ["A", "B"])
        self.assertAlmostEqual(plan["fuel_stops"][0]["fuel_purchased_gallons"], 25.0)  # 30 gal to reach B minus 5 left
        self.assertAlmostEqual(plan["fuel_stops"][1]["fuel_purchased_gallons"], 35.0)  # exactly the last 350 miles
        self.assertAlmostEqual(plan["total_fuel_cost"], 25 * 4.0 + 35 * 3.0)

    def test_skips_expensive_station_when_cheaper_one_is_in_range(self):
        plan = optimize_fuel_stops(800, [st(300, 3.8, "A"), st(450, 3.2, "B")])
        self.assertEqual([s["station_name"] for s in plan["fuel_stops"]], ["B"])
        self.assertAlmostEqual(plan["fuel_stops"][0]["fuel_purchased_gallons"], 30.0)

    def test_does_not_fill_tank_at_destination(self):
        plan = optimize_fuel_stops(600, [st(400, 3.0)])
        self.assertAlmostEqual(plan["fuel_stops"][0]["fuel_purchased_gallons"], 10.0)
        self.assertAlmostEqual(plan["arrival_fuel_gallons"], 0.0, places=5)

    def test_gap_longer_than_range_raises(self):
        with self.assertRaises(NoFeasibleRouteError):
            optimize_fuel_stops(1200, [st(100, 3.0), st(700, 3.0)])

    def test_matches_exact_dp_on_random_routes(self):
        rng = random.Random(7)
        checked = 0
        for _ in range(300):
            route = rng.randrange(60, 200) * 10
            stations = [st(rng.randrange(1, route // 10) * 10, rng.choice([2.5, 3.0, 3.25, 3.5, 4.0, 4.5])) for _ in range(rng.randrange(1, 12))]
            start = rng.randrange(0, 51)
            try:
                got = optimize_fuel_stops(route, stations, starting_fuel_gallons=start)["total_fuel_cost"]
            except NoFeasibleRouteError:
                self.assertEqual(brute_force_cost(route, stations, start), float("inf"))
                continue
            self.assertAlmostEqual(got, brute_force_cost(route, stations, start), places=1)
            checked += 1
        self.assertGreater(checked, 100)


class MatcherTests(TestCase):
    def setUp(self):
        reset_station_index()
        # A straight west-east route along latitude 40 N from -90 to -80.
        self.route = [[-90 + i * 0.1, 40.0] for i in range(101)]
        Station.objects.create(opis_id=1, name="ON", city="a", state="OH", price=3, latitude=40.02, longitude=-85.0)
        Station.objects.create(opis_id=2, name="FAR", city="b", state="OH", price=3, latitude=42.0, longitude=-85.0)
        Station.objects.create(opis_id=3, name="NEAR_START", city="c", state="OH", price=3, latitude=40.0, longitude=-89.5)

    def tearDown(self):
        reset_station_index()

    def test_filters_by_distance_and_orders_by_mile_marker(self):
        found = find_stations_along_route(self.route, 500, max_distance_miles=10)
        self.assertEqual([s["name"] for s in found], ["NEAR_START", "ON"])
        self.assertAlmostEqual(found[1]["distance_from_start_miles"], 250, delta=3)
        self.assertLess(found[1]["distance_from_route_miles"], 3)


class ApiTests(TestCase):
    def setUp(self):
        reset_station_index()
        Station.objects.create(opis_id=1, name="MID", city="a", state="OH", price=3.0, latitude=40.0, longitude=-85.0)
        self.route = {"distance_miles": 700.0, "duration_minutes": 600.0,
                      "geometry": {"type": "LineString", "coordinates": [[-90 + i * 0.1, 40.0] for i in range(101)]}}

    def test_returns_stops_and_total_cost(self):
        with patch("routing.services.trip_planner.get_driving_route", return_value=self.route):
            res = APIClient().post("/api/route/", {"start_location": "A", "finish_location": "B"}, format="json")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body["fuel_stops"]), 1)
        self.assertGreater(body["total_fuel_cost"], 0)
        self.assertEqual(body["route"]["type"], "LineString")

    def test_rejects_same_start_and_finish(self):
        res = APIClient().post("/api/route/", {"start_location": "A", "finish_location": "a"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_missing_field_is_400(self):
        res = APIClient().post("/api/route/", {"start_location": "A"}, format="json")
        self.assertEqual(res.status_code, 400)
