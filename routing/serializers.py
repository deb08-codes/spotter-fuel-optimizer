from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start_location = serializers.CharField(max_length=200)
    finish_location = serializers.CharField(max_length=200)
    # Optional: fuel already in the tank at departure (default: full 50 gal tank).
    starting_fuel_gallons = serializers.FloatField(required=False, min_value=0, max_value=50, default=50)

    def validate(self, attrs):
        if " ".join(attrs["start_location"].lower().split()) == " ".join(attrs["finish_location"].lower().split()):
            raise serializers.ValidationError("Start and finish must be different locations.")
        return attrs
