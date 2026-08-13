from django.urls import path

from .views import (
    AlertCreateWorkOrderView,
    AlertDetailView,
    AlertListView,
    AlertScanView,
    HealthView,
    MetaView,
    MoldDetailView,
    MoldListView,
    MoldMaintenanceStatusView,
    ProbeRunContextView,
    ProbeRunCreateView,
    ProbeRunReportView,
    ProbeSchedulerHeartbeatView,
    ProbeVariableTestView,
    WorkOrderAbnormalReportView,
    WorkOrderAssignView,
    WorkOrderAutoAssignView,
    WorkOrderCandidatesView,
    WorkOrderCompleteReportView,
    WorkOrderDetailView,
    WorkOrderEmailContextView,
    WorkOrderHistoryView,
    WorkOrderKnowledgeContextView,
    WorkOrderKnowledgeSnapshotView,
    WorkOrderListView,
    WorkOrderNotificationView,
    WorkOrderPauseView,
    WorkOrderResumeView,
    WorkOrderStartView,
)

app_name = "platform_probe"

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("meta", MetaView.as_view(), name="meta"),
    path("probe/runs", ProbeRunCreateView.as_view(), name="probe-run-create"),
    path(
        "probe/runs/<str:run_id>/context",
        ProbeRunContextView.as_view(),
        name="probe-run-context",
    ),
    path(
        "probe/runs/<str:run_id>/variable-test",
        ProbeVariableTestView.as_view(),
        name="probe-variable-test",
    ),
    path(
        "probe/scheduler-heartbeat",
        ProbeSchedulerHeartbeatView.as_view(),
        name="probe-scheduler-heartbeat",
    ),
    path(
        "probe/runs/<str:run_id>/report",
        ProbeRunReportView.as_view(),
        name="probe-run-report",
    ),
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
    path(
        "alerts/<str:alert_id>/create-work-order",
        AlertCreateWorkOrderView.as_view(),
        name="alert-create-work-order",
    ),
    path("work-orders", WorkOrderListView.as_view(), name="work-order-list"),
    path(
        "work-orders/<str:work_order_id>",
        WorkOrderDetailView.as_view(),
        name="work-order-detail",
    ),
    path(
        "work-orders/<str:work_order_id>/candidates",
        WorkOrderCandidatesView.as_view(),
        name="work-order-candidates",
    ),
    path(
        "work-orders/<str:work_order_id>/assign",
        WorkOrderAssignView.as_view(),
        name="work-order-assign",
    ),
    path(
        "work-orders/<str:work_order_id>/auto-assign",
        WorkOrderAutoAssignView.as_view(),
        name="work-order-auto-assign",
    ),
    path(
        "work-orders/<str:work_order_id>/history",
        WorkOrderHistoryView.as_view(),
        name="work-order-history",
    ),
    path(
        "work-orders/<str:work_order_id>/knowledge-context",
        WorkOrderKnowledgeContextView.as_view(),
        name="work-order-knowledge-context",
    ),
    path(
        "work-orders/<str:work_order_id>/knowledge-snapshot",
        WorkOrderKnowledgeSnapshotView.as_view(),
        name="work-order-knowledge-snapshot",
    ),
    path(
        "work-orders/<str:work_order_id>/email-context",
        WorkOrderEmailContextView.as_view(),
        name="work-order-email-context",
    ),
    path(
        "work-orders/<str:work_order_id>/notifications",
        WorkOrderNotificationView.as_view(),
        name="work-order-notifications",
    ),
    path(
        "work-orders/<str:work_order_id>/start",
        WorkOrderStartView.as_view(),
        name="work-order-start",
    ),
    path(
        "work-orders/<str:work_order_id>/pause",
        WorkOrderPauseView.as_view(),
        name="work-order-pause",
    ),
    path(
        "work-orders/<str:work_order_id>/resume",
        WorkOrderResumeView.as_view(),
        name="work-order-resume",
    ),
    path(
        "work-orders/<str:work_order_id>/report-complete",
        WorkOrderCompleteReportView.as_view(),
        name="work-order-report-complete",
    ),
    path(
        "work-orders/<str:work_order_id>/report-abnormal",
        WorkOrderAbnormalReportView.as_view(),
        name="work-order-report-abnormal",
    ),
]
