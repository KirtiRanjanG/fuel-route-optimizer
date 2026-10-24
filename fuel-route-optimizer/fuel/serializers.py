from rest_framework import serializers
class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=200)
    finish = serializers.CharField(max_length=200)
    mpg = serializers.FloatField(default=10, min_value=1, max_value=100)
    max_range_miles = serializers.FloatField(default=500, min_value=50, max_value=1000)
    def validate_start(self, value): return value.strip()
    def validate_finish(self, value): return value.strip()
