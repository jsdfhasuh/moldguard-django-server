from django.urls import path

from apps.molds.views import (
    AlertListView,
    AlertScanView,
    MoldDetailView,
    MoldListView,
    MoldMaintenanceStatusView,
)

urlpatterns = [
    path("molds", MoldListView.as_view(), name="mold-list"),
    path("molds/<str:mold_id>", MoldDetailView.as_view(), name="mold-detail"),
    path(
        "molds/<str:mold_id>/maintenance-status",
        MoldMaintenanceStatusView.as_view(),
        name="mold-maintenance-status",
    ),
    path("alerts/scan", AlertScanView.as_view(), name="alert-scan"),
    path("alerts", AlertListView.as_view(), name="alert-list"),
]
