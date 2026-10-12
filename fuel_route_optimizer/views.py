
from requests import RequestException

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from fuel_route_optimizer.serializers import (
    FuelRouteRequestSerializer,
)
from fuel_route_optimizer.services.fuel_optimizer import (
    optimize_fuel_route,
)


class FuelRouteAPIView(APIView):
    def post(self, request):
        serializer = FuelRouteRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            result = optimize_fuel_route(
                start_latitude=data["start_latitude"],
                start_longitude=data["start_longitude"],
                end_latitude=data["end_latitude"],
                end_longitude=data["end_longitude"],
                mpg=data.get("mpg", 10),
                max_range_miles=data.get("max_range_miles", 500),
            )
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        except RequestException:
            return Response(
                {"error": "The routing service is temporarily unavailable."},
                status=status.HTTP_502_BAD_GATEWAY,
            )