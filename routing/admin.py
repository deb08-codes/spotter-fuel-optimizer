from django.contrib import admin

from .models import Station


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "state", "price")
    list_filter = ("state",)
    search_fields = ("name", "city")
