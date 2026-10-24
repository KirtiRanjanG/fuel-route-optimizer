from django.urls import path
from .views import health_check, route_optimizer
urlpatterns = [
    path("health/", health_check, name="health"),
    path("route-optimizer/", route_optimizer, name="route-optimizer"),
]
