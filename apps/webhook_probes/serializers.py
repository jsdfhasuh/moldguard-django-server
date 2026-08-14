from rest_framework import serializers


class WebhookProbeCreateSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)

    def validate(self, attrs):
        if "webhook_url" in self.initial_data:
            raise serializers.ValidationError(
                {"webhook_url": ["Webhook地址只能由服务器配置，不能通过请求传入"]}
            )
        return attrs


class WebhookProbeCallbackSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)
    challenge = serializers.CharField(max_length=64)
    platform_name = serializers.CharField(
        max_length=80,
        default="competition-agent-platform",
    )
    evidence = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
