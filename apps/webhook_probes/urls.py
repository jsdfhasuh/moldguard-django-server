from django.urls import path

from apps.webhook_probes.views import (
    WebhookProbeCallbackView,
    WebhookProbeCollectionView,
    WebhookProbeDetailView,
)

urlpatterns = [
    path("webhook-probes", WebhookProbeCollectionView.as_view(), name="webhook-probe-create"),
    path(
        "webhook-probes/<str:probe_id>/callback",
        WebhookProbeCallbackView.as_view(),
        name="webhook-probe-callback",
    ),
    path(
        "webhook-probes/<str:probe_id>",
        WebhookProbeDetailView.as_view(),
        name="webhook-probe-detail",
    ),
]
