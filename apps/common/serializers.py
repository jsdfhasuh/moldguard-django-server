from rest_framework import serializers


class OpenAPIEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = serializers.JSONField(required=False, allow_null=True)
    errors = serializers.JSONField(required=False)
    request_id = serializers.CharField()
