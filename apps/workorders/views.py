from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.common.exceptions import BusinessError
from apps.common.idempotency import replay_or_execute
from apps.common.responses import success_payload, success_response
from apps.common.serializers import OpenAPIEnvelopeSerializer
from apps.common.views import EnvelopeAPIView
from apps.workorders.models import WorkOrder
from apps.workorders.serializers import (
    AssignSerializer,
    EmailResultSerializer,
    KnowledgeSerializer,
    ReportSerializer,
)
from apps.workorders.services.assignment_service import (
    assign_work_order,
    candidate_data,
)
from apps.workorders.services.knowledge_service import (
    email_context,
    knowledge_context,
    record_email_result,
    save_knowledge_package,
)
from apps.workorders.services.presentation import work_order_data
from apps.workorders.services.report_service import submit_report


def get_work_order(work_order_id):
    try:
        return WorkOrder.objects.select_related("mold", "alert", "assignee").get(pk=work_order_id)
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None


def idempotent_response(request, *, action, object_id, payload, message, operation):
    def wrapped():
        data = operation()
        return 200, success_payload(data, message, request)

    status_code, response_payload = replay_or_execute(
        action=action,
        object_id=object_id,
        payload=payload,
        current_request_id=request.request_id,
        operation=wrapped,
    )
    return Response(response_payload, status=status_code)


class WorkOrderListView(EnvelopeAPIView):
    @extend_schema(operation_id="list_work_orders", responses=OpenAPIEnvelopeSerializer)
    def get(self, request):
        queryset = WorkOrder.objects.select_related("mold", "alert", "assignee").order_by(
            "-created_at"
        )
        for field in ("status", "mold_id", "work_order_type", "assignee_id"):
            value = request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        return success_response(
            {
                "count": queryset.count(),
                "results": [work_order_data(item) for item in queryset],
            },
            request=request,
        )


class WorkOrderDetailView(EnvelopeAPIView):
    @extend_schema(operation_id="retrieve_work_order", responses=OpenAPIEnvelopeSerializer)
    def get(self, request, work_order_id):
        return success_response(
            work_order_data(get_work_order(work_order_id), include_knowledge=True),
            request=request,
        )


class WorkOrderCandidatesView(EnvelopeAPIView):
    def get(self, request, work_order_id):
        return success_response(candidate_data(get_work_order(work_order_id)), request=request)


class WorkOrderAssignView(EnvelopeAPIView):
    @extend_schema(request=AssignSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="ASSIGN_WORK_ORDER",
            object_id=work_order_id,
            payload=payload,
            message="派工成功",
            operation=lambda: assign_work_order(
                work_order_id,
                payload["employee_id"],
                client_request_id=payload["client_request_id"],
            ),
        )


class WorkOrderTimelineView(EnvelopeAPIView):
    def get(self, request, work_order_id):
        work_order = get_work_order(work_order_id)
        events = work_order.events.order_by("occurred_at", "event_id")
        return success_response(
            {
                "work_order_id": work_order.work_order_id,
                "count": events.count(),
                "events": [
                    {
                        "event_id": item.event_id,
                        "event_type": item.event_type,
                        "from_status": item.from_status,
                        "to_status": item.to_status,
                        "operator_id": item.operator_id,
                        "remarks": item.remarks,
                        "event_data": item.event_data_json,
                        "occurred_at": item.occurred_at.isoformat(),
                    }
                    for item in events
                ],
            },
            request=request,
        )


class KnowledgeContextView(EnvelopeAPIView):
    def get(self, request, work_order_id):
        return success_response(knowledge_context(get_work_order(work_order_id)), request=request)


class KnowledgeView(EnvelopeAPIView):
    @extend_schema(request=KnowledgeSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = KnowledgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="SAVE_KNOWLEDGE_PACKAGE",
            object_id=work_order_id,
            payload=payload,
            message="知识包已保存",
            operation=lambda: save_knowledge_package(
                work_order_id,
                payload,
                client_request_id=payload["client_request_id"],
            ),
        )


class EmailContextView(EnvelopeAPIView):
    def get(self, request, work_order_id):
        return success_response(email_context(get_work_order(work_order_id)), request=request)


class EmailResultView(EnvelopeAPIView):
    @extend_schema(request=EmailResultSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = EmailResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="RECORD_EMAIL_RESULT",
            object_id=work_order_id,
            payload=payload,
            message="邮件结果已记录",
            operation=lambda: record_email_result(
                work_order_id,
                payload,
                client_request_id=payload["client_request_id"],
            ),
        )


class WorkOrderReportView(EnvelopeAPIView):
    @extend_schema(request=ReportSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="SUBMIT_WORK_ORDER_REPORT",
            object_id=work_order_id,
            payload=payload,
            message="报工提交成功",
            operation=lambda: submit_report(
                work_order_id,
                payload,
                client_request_id=payload["client_request_id"],
            ),
        )
