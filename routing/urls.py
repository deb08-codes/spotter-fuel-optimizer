from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health_check, name="health-check"),
    path("route/", views.calculate_route, name="calculate-route"),
    path("map/", views.map_page, name="map"),
]
