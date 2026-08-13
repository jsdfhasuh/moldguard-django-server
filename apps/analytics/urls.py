from django.urls import path

from apps.analytics.views import AnalyticsSummaryView, MoldRecordsView

urlpatterns = [
    path("molds/<str:mold_id>/records", MoldRecordsView.as_view(), name="mold-records"),
    path("analytics/summary", AnalyticsSummaryView.as_view(), name="analytics-summary"),
]
