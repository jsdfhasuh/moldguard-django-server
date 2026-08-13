from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response

from apps.common.exceptions import BusinessError
from apps.common.idempotency import replay_or_execute
from apps.common.responses import success_payload, success_response
from apps.common.serializers import OpenAPIEnvelopeSerializer
from apps.common.views import EnvelopeAPIView
from apps.workorders.models import WorkOrder
from apps.workorders.serializers import (
    AssignSerializer,
    ClientRequestSerializer,
    KnowledgeSerializer,
    PauseSerializer,
    RemarksSerializer,
    ReportSerializer,
    SendEmailSerializer,
)
from apps.workorders.services.assignment_service import (
    assign_work_order,
    auto_assign_work_order,
    candidate_data,
)
from apps.workorders.services.email_service import send_work_order_email
from apps.workorders.services.execution_service import (
    continue_processing,
    pause_work_order,
    resume_work_order,
    start_work_order,
)
from apps.workorders.services.knowledge_service import (
    email_context,
    knowledge_context,
    save_knowledge_package,
)
from apps.workorders.services.presentation import work_order_data
from apps.workorders.services.repair_service import (
    completed_repair_result,
    create_repair_task,
)
from apps.workorders.services.report_service import submit_report
from apps.workorders.services.tracking_service import list_overdue, scan_overdue


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


class WorkOrderAutoAssignView(EnvelopeAPIView):
    @extend_schema(request=ClientRequestSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = ClientRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="AUTO_ASSIGN_WORK_ORDER",
            object_id=work_order_id,
            payload=payload,
            message="自动派工成功",
            operation=lambda: auto_assign_work_order(
                work_order_id, client_request_id=payload["client_request_id"]
            ),
        )


class WorkOrderStartView(EnvelopeAPIView):
    @extend_schema(request=ClientRequestSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = ClientRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="START_WORK_ORDER",
            object_id=work_order_id,
            payload=payload,
            message="工单已开工",
            operation=lambda: start_work_order(
                work_order_id, client_request_id=payload["client_request_id"]
            ),
        )


class WorkOrderPauseView(EnvelopeAPIView):
    @extend_schema(request=PauseSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = PauseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="PAUSE_WORK_ORDER",
            object_id=work_order_id,
            payload=payload,
            message="工单已暂停",
            operation=lambda: pause_work_order(
                work_order_id,
                client_request_id=payload["client_request_id"],
                reason=payload["reason"],
            ),
        )


class WorkOrderResumeView(EnvelopeAPIView):
    @extend_schema(request=ClientRequestSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = ClientRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="RESUME_WORK_ORDER",
            object_id=work_order_id,
            payload=payload,
            message="工单已恢复",
            operation=lambda: resume_work_order(
                work_order_id, client_request_id=payload["client_request_id"]
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


class SendEmailView(EnvelopeAPIView):
    @extend_schema(
        request=SendEmailSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenAPIEnvelopeSerializer, description="派工邮件发送成功"
            ),
            400: OpenApiResponse(
                response=OpenAPIEnvelopeSerializer, description="请求字段校验失败"
            ),
            404: OpenApiResponse(response=OpenAPIEnvelopeSerializer, description="工单不存在"),
            409: OpenApiResponse(
                response=OpenAPIEnvelopeSerializer, description="邮件发送前置条件冲突"
            ),
            502: OpenApiResponse(
                response=OpenAPIEnvelopeSerializer,
                description="SMTP明确失败或发送结果无法确认",
            ),
        },
    )
    def post(self, request, work_order_id):
        serializer = SendEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        status_code, response_payload = send_work_order_email(
            work_order_id,
            payload,
            current_request_id=request.request_id,
        )
        return Response(response_payload, status=status_code)


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


class ContinueProcessingView(EnvelopeAPIView):
    @extend_schema(request=RemarksSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = RemarksSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="CONTINUE_ABNORMAL_PROCESSING",
            object_id=work_order_id,
            payload=payload,
            message="工单已恢复处理",
            operation=lambda: continue_processing(
                work_order_id,
                client_request_id=payload["client_request_id"],
                remarks=payload["remarks"],
            ),
        )


class CreateRepairTaskView(EnvelopeAPIView):
    @extend_schema(request=RemarksSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        serializer = RemarksSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="CREATE_REPAIR_TASK",
            object_id=work_order_id,
            payload=payload,
            message="关联修模任务已创建",
            operation=lambda: create_repair_task(
                work_order_id,
                client_request_id=payload["client_request_id"],
                remarks=payload["remarks"],
            ),
        )


class RepairCompletedView(EnvelopeAPIView):
    @extend_schema(responses=OpenAPIEnvelopeSerializer)
    def post(self, request, work_order_id):
        work_order = get_work_order(work_order_id)
        if work_order.work_order_type != WorkOrder.Type.REPAIR_TASK:
            raise BusinessError("INVALID_WORK_ORDER_TYPE", "目标工单不是修模任务", status_code=409)
        if "report_type" in request.data:
            serializer = ReportSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            payload = serializer.validated_data
            if payload["report_type"] != WorkOrder.ReportType.NORMAL:
                raise BusinessError("VALIDATION_ERROR", "repair-completed只接受NORMAL报工")
            return idempotent_response(
                request,
                action="SUBMIT_WORK_ORDER_REPORT",
                object_id=work_order_id,
                payload=payload,
                message="修模任务已完成",
                operation=lambda: submit_report(
                    work_order_id,
                    payload,
                    client_request_id=payload["client_request_id"],
                ),
            )
        serializer = ClientRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="CONFIRM_REPAIR_COMPLETED",
            object_id=work_order_id,
            payload=payload,
            message="修模任务完成状态已确认",
            operation=lambda: completed_repair_result(get_work_order(work_order_id)),
        )


class TrackingScanView(EnvelopeAPIView):
    @extend_schema(request=ClientRequestSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request):
        serializer = ClientRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return idempotent_response(
            request,
            action="TRACKING_SCAN",
            object_id="ALL_WORK_ORDERS",
            payload=payload,
            message="过程追踪扫描完成",
            operation=scan_overdue,
        )


class WorkOrderOverdueView(EnvelopeAPIView):
    def get(self, request):
        return success_response(list_overdue(), request=request)
