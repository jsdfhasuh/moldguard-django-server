from django.db import models


class WebhookProbe(models.Model):
    class DispatchStatus(models.TextChoices):
        SENDING = "SENDING", "发送中"
        DELIVERED = "DELIVERED", "已送达"
        FAILED = "FAILED", "发送失败"
        NOT_CONFIGURED = "NOT_CONFIGURED", "未配置"

    probe_id = models.CharField(max_length=40, primary_key=True)
    client_request_id = models.CharField(max_length=120, unique=True)
    challenge = models.CharField(max_length=64)
    callback_token_hash = models.CharField(max_length=64)
    dispatch_status = models.CharField(
        max_length=20,
        choices=DispatchStatus.choices,
        default=DispatchStatus.SENDING,
    )
    dispatch_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    dispatch_error = models.CharField(max_length=80, blank=True, default="")
    callback_received_at = models.DateTimeField(null=True, blank=True)
    callback_payload_json = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["dispatch_status", "created_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return self.probe_id
