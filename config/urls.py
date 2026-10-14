from django.contrib import admin
from django.urls import include, path

from routing.views import landing_page

urlpatterns = [
    path("", landing_page, name="home"),  # menu: Map and Health check
    path("admin/", admin.site.urls),
    path("api/", include("routing.urls")),
]