from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import RouteRequestSerializer
from .services import build_route_result, ExternalServiceError

@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok", "service": "fuel-route-optimizer"})

@api_view(["POST"])
def route_optimizer(request):
    serializer = RouteRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Invalid request", "details": serializer.errors}, status=400)
    try:
        return Response(build_route_result(**serializer.validated_data), status=200)
    except ExternalServiceError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
