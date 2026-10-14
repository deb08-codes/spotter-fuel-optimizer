from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import RouteRequestSerializer
from .services.fuel_optimizer import MILES_PER_GALLON, TANK_GALLONS, NoFeasibleRouteError
from .services.geocoding import GeocodingError
from .services.route_service import RoutingError
from .services.trip_planner import plan_trip


@api_view(["GET"])
def health_check(request):
    return Response({"status": "success", "message": "Spotter Fuel Optimizer API is running"})


@api_view(["POST"])
def calculate_route(request):
    serializer = RouteRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"status": "error", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    try:
        result = plan_trip(data["start_location"], data["finish_location"], data["starting_fuel_gallons"])
    except GeocodingError as exc:
        return Response({"status": "error", "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except NoFeasibleRouteError as exc:
        return Response({"status": "error", "message": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except RoutingError as exc:
        return Response({"status": "error", "message": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    plan, route = result["plan"], result["route"]
    return Response(
        {
            "status": "success",
            "start_location": data["start_location"],
            "finish_location": data["finish_location"],
            "distance_miles": route["distance_miles"],
            "duration_minutes": route["duration_minutes"],
            "route": route["geometry"],  # GeoJSON LineString, ready for Leaflet/Mapbox
            "fuel_stops": plan["fuel_stops"],
            "total_fuel_cost": plan["total_fuel_cost"],
            "fuel_purchased_gallons": plan["fuel_purchased_gallons"],
            "fuel_used_gallons": plan["fuel_used_gallons"],
            "assumptions": {
                "max_range_miles": TANK_GALLONS * MILES_PER_GALLON,
                "miles_per_gallon": MILES_PER_GALLON,
                "starting_fuel_gallons": plan["starting_fuel_gallons"],
                "cost_counts": "only fuel bought at the listed stops (starting fuel is not charged)",
                "station_search_radius_miles": result["search_radius_miles"],
                "station_locations": "city-level coordinates",
            },
        },
        status=status.HTTP_200_OK,
    )

def landing_page(request):
    return render(request, "routing/landing.html")

def map_page(request):
    return render(request, "routing/map.html")
