from django.urls import path

from apps.analytics.views import (
    AnalyticsSummaryView,
    MoldRecordsView,
    OrderCompletionAnalyticsView,
    WorkHoursAnalyticsView,
)

urlpatterns = [
    path("molds/<str:mold_id>/records", MoldRecordsView.as_view(), name="mold-records"),
    path("analytics/summary", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("analytics/work-hours", WorkHoursAnalyticsView.as_view(), name="analytics-work-hours"),
    path(
        "analytics/order-completion",
        OrderCompletionAnalyticsView.as_view(),
        name="analytics-order-completion",
    ),
]
