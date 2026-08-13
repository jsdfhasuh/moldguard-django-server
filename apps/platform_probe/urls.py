from django.urls import path

from .views import (
    AlertDetailView,
    AlertListView,
    AlertScanView,
    HealthView,
    MetaView,
    MoldDetailView,
    MoldListView,
    MoldMaintenanceStatusView,
)

app_name = "platform_probe"

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("meta", MetaView.as_view(), name="meta"),
    path("molds", MoldListView.as_view(), name="mold-list"),
    path("molds/<str:mold_id>", MoldDetailView.as_view(), name="mold-detail"),
    path(
        "molds/<str:mold_id>/maintenance-status",
        MoldMaintenanceStatusView.as_view(),
        name="mold-maintenance-status",
    ),
    path("alerts/scan", AlertScanView.as_view(), name="alert-scan"),
    path("alerts", AlertListView.as_view(), name="alert-list"),
    path("alerts/<str:alert_id>", AlertDetailView.as_view(), name="alert-detail"),
]
