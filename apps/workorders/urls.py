from django.urls import path

from apps.workorders.views import (
    EmailContextView,
    EmailResultView,
    KnowledgeContextView,
    KnowledgeView,
    WorkOrderAssignView,
    WorkOrderCandidatesView,
    WorkOrderDetailView,
    WorkOrderListView,
    WorkOrderReportView,
    WorkOrderTimelineView,
)

urlpatterns = [
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
        "work-orders/<str:work_order_id>/timeline",
        WorkOrderTimelineView.as_view(),
        name="work-order-timeline",
    ),
    path(
        "work-orders/<str:work_order_id>/knowledge-context",
        KnowledgeContextView.as_view(),
        name="knowledge-context",
    ),
    path(
        "work-orders/<str:work_order_id>/knowledge",
        KnowledgeView.as_view(),
        name="knowledge",
    ),
    path(
        "work-orders/<str:work_order_id>/email-context",
        EmailContextView.as_view(),
        name="email-context",
    ),
    path(
        "work-orders/<str:work_order_id>/email-result",
        EmailResultView.as_view(),
        name="email-result",
    ),
    path(
        "work-orders/<str:work_order_id>/report",
        WorkOrderReportView.as_view(),
        name="work-order-report",
    ),
]
