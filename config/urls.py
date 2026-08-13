from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.views import ApiNotFoundView, HealthView, MetaView
from apps.workorders.web_views import WorkOrderReportPageView

urlpatterns = [
    path("api/v1/health", HealthView.as_view(), name="health"),
    path("api/v1/meta", MetaView.as_view(), name="meta"),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path(
        "report/<str:work_order_id>",
        WorkOrderReportPageView.as_view(),
        name="work-order-report-page",
    ),
    path("api/v1/", include("apps.molds.urls")),
    path("api/v1/", include("apps.workorders.urls")),
    path("api/v1/", include("apps.analytics.urls")),
    re_path(r"^api/(?P<unmatched_path>.*)$", ApiNotFoundView.as_view(), name="api-not-found"),
]
