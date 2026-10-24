from django.contrib import admin
from .models import FuelStation
@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = ("opis_id", "name", "city", "state", "retail_price")
    search_fields = ("name", "city", "state")
    list_filter = ("state",)
