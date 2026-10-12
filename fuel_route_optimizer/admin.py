
from django.contrib import admin

from fuel_route_optimizer.models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = (
        "station_id",
        "name",
        "price_per_gallon",
        "latitude",
        "longitude",
        "state",
    )
    search_fields = ("station_id", "name", "address", "state")
    list_filter = ("state",)
    ordering = ("price_per_gallon",)