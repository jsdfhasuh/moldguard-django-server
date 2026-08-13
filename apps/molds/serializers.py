from rest_framework import serializers


class AlertScanSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)
    mold_ids = serializers.ListField(
        child=serializers.CharField(max_length=64), required=False, allow_empty=True
    )

    def validate_mold_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("mold_ids不允许重复")
        return value
