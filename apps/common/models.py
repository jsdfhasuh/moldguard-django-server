from django.db import models


class ClientRequestRecord(models.Model):
    client_request_id = models.CharField(max_length=120, primary_key=True)
    action = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80, blank=True, default="")
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField()
    response_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["action", "object_id"])]

    def __str__(self):
        return self.client_request_id
