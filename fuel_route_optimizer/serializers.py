
from rest_framework import serializers


class FuelRouteRequestSerializer(serializers.Serializer):
    start_latitude = serializers.FloatField(min_value=-90,max_value=90,)
    start_longitude = serializers.FloatField(min_value=-180,max_value=180,)
    end_latitude = serializers.FloatField(min_value=-90, max_value=90,)
    end_longitude = serializers.FloatField(min_value=-180, max_value=180,)
    mpg = serializers.FloatField(min_value=0.1,default=10,)
    max_range_miles = serializers.FloatField(min_value=1, default=500,)