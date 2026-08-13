from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from .exceptions import ProbeAPIException
from .idempotency import idempotent
from .models import KnowledgeSnapshot, MaintenanceAlert, Mold, NotificationReceipt, WorkOrder
from .responses import success_response
from .serializers import (
    AbnormalReportCreateSerializer,
    AlertScanSerializer,
    AssignSerializer,
    AutoAssignSerializer,
    CompleteReportSerializer,
    CreateWorkOrderSerializer,
    EmployeeActionSerializer,
    EmployeeSerializer,
    KnowledgeSnapshotCreateSerializer,
    KnowledgeSnapshotSerializer,
    MaintenanceAlertSerializer,
    MaintenanceHistorySerializer,
    MoldSerializer,
    NotificationCreateSerializer,
    NotificationReceiptSerializer,
    PauseActionSerializer,
    PauseSegmentSerializer,
    WorkOrderEventSerializer,
    WorkOrderSerializer,
    WorkReportSerializer,
)
from .services.alert_service import create_work_order, scan_molds
from .services.assignment_service import (
    assign_employee,
    auto_assign_employee,
    candidates_for,
)
from .services.reporting_service import (
    abnormal_work_order,
    complete_work_order,
    pause_work_order,
    resume_work_order,
    start_work_order,
)
from .services.trigger_service import calculate_maintenance_status


class HealthView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        return success_response(
            {
                "service": "moldguard-platform-capability-probe",
                "status": "ok",
                "version": "1.0.0",
                "time": timezone.now().isoformat(),
                "authentication_required": False,
            },
            request=request,
        )


class MetaView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        return success_response(
            {
                "service": "MoldGuard Platform Capability Probe",
                "api_prefix": "/api/v1",
                "timezone": "Asia/Shanghai",
                "default_port": 18080,
                "authentication": "NONE",
                "data_classification": "DEMO_ONLY",
                "deployment_status": "IMPLEMENTING",
                "openapi_schema": "/api/schema",
                "openapi_docs": "/api/docs",
            },
            request=request,
        )


class MoldListView(APIView):
    def get(self, request):
        molds = Mold.objects.all()
        return success_response({"molds": MoldSerializer(molds, many=True).data}, request=request)


class MoldDetailView(APIView):
    def get(self, request, mold_id):
        try:
            mold = Mold.objects.get(mold_id=mold_id)
        except Mold.DoesNotExist as exc:
            raise ProbeAPIException("MOLD_NOT_FOUND", "模具不存在", status_code=404) from exc
        return success_response(MoldSerializer(mold).data, request=request)


class MoldMaintenanceStatusView(APIView):
    def get(self, request, mold_id):
        try:
            mold = Mold.objects.get(mold_id=mold_id)
        except Mold.DoesNotExist as exc:
            raise ProbeAPIException("MOLD_NOT_FOUND", "模具不存在", status_code=404) from exc
        status = calculate_maintenance_status(mold)
        return success_response(status.to_dict(), request=request)


class AlertScanView(APIView):
    @idempotent("ALERT_SCAN")
    def post(self, request):
        serializer = AlertScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = scan_molds(serializer.validated_data.get("mold_ids"))
        return success_response(result, message="扫描完成", request=request)


class AlertListView(APIView):
    def get(self, request):
        alerts = MaintenanceAlert.objects.select_related("mold")
        alert_type = request.query_params.get("alert_type")
        status_value = request.query_params.get("status")
        mold_id = request.query_params.get("mold_id")
        if alert_type:
            alerts = alerts.filter(alert_type=alert_type)
        if status_value:
            alerts = alerts.filter(status=status_value)
        if mold_id:
            alerts = alerts.filter(mold_id=mold_id)
        return success_response(
            {"alerts": MaintenanceAlertSerializer(alerts, many=True).data},
            request=request,
        )


class AlertDetailView(APIView):
    def get(self, request, alert_id):
        try:
            alert = MaintenanceAlert.objects.select_related("mold").get(alert_id=alert_id)
        except MaintenanceAlert.DoesNotExist as exc:
            raise ProbeAPIException("ALERT_NOT_FOUND", "预警不存在", status_code=404) from exc
        return success_response(MaintenanceAlertSerializer(alert).data, request=request)


def get_work_order(work_order_id):
    try:
        return WorkOrder.objects.select_related("alert", "mold", "assigned_employee").get(
            work_order_id=work_order_id
        )
    except WorkOrder.DoesNotExist as exc:
        raise ProbeAPIException("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from exc


class AlertCreateWorkOrderView(APIView):
    @idempotent("CREATE_WORK_ORDER", "alert_id")
    def post(self, request, alert_id):
        serializer = CreateWorkOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = create_work_order(alert_id)
        work_order = get_work_order(work_order.work_order_id)
        return success_response(
            WorkOrderSerializer(work_order).data,
            message="工单创建成功",
            request=request,
            status=201,
        )


class WorkOrderListView(APIView):
    def get(self, request):
        queryset = WorkOrder.objects.select_related("alert", "mold", "assigned_employee")
        status_value = request.query_params.get("status")
        mold_id = request.query_params.get("mold_id")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if mold_id:
            queryset = queryset.filter(mold_id=mold_id)
        return success_response(
            {"work_orders": WorkOrderSerializer(queryset, many=True).data},
            request=request,
        )


class WorkOrderDetailView(APIView):
    def get(self, request, work_order_id):
        return success_response(
            WorkOrderSerializer(get_work_order(work_order_id)).data,
            request=request,
        )


class WorkOrderCandidatesView(APIView):
    def get(self, request, work_order_id):
        work_order = get_work_order(work_order_id)
        candidates = candidates_for(work_order)
        return success_response(
            {
                "work_order_id": work_order.work_order_id,
                "mold_type": work_order.mold.mold_type,
                "candidates": EmployeeSerializer(candidates, many=True).data,
            },
            request=request,
        )


class WorkOrderAssignView(APIView):
    @idempotent("ASSIGN_WORK_ORDER", "work_order_id")
    def post(self, request, work_order_id):
        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = assign_employee(work_order_id, serializer.validated_data["employee_id"])
        return success_response(
            WorkOrderSerializer(get_work_order(work_order.work_order_id)).data,
            message="派工成功",
            request=request,
        )


class WorkOrderAutoAssignView(APIView):
    @idempotent("AUTO_ASSIGN_WORK_ORDER", "work_order_id")
    def post(self, request, work_order_id):
        serializer = AutoAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = auto_assign_employee(work_order_id)
        return success_response(
            WorkOrderSerializer(get_work_order(work_order.work_order_id)).data,
            message="自动派工成功",
            request=request,
        )


class WorkOrderHistoryView(APIView):
    def get(self, request, work_order_id):
        work_order = get_work_order(work_order_id)
        data = {
            "work_order_id": work_order.work_order_id,
            "events": WorkOrderEventSerializer(work_order.events.all(), many=True).data,
            "pause_segments": PauseSegmentSerializer(
                work_order.pause_segments.all(), many=True
            ).data,
            "work_report": None,
            "abnormal_report": None,
            "maintenance_history": None,
        }
        if hasattr(work_order, "work_report"):
            data["work_report"] = WorkReportSerializer(work_order.work_report).data
        if hasattr(work_order, "abnormal_report"):
            from .serializers import AbnormalReportSerializer

            data["abnormal_report"] = AbnormalReportSerializer(work_order.abnormal_report).data
        if hasattr(work_order, "maintenance_history_entry"):
            data["maintenance_history"] = MaintenanceHistorySerializer(
                work_order.maintenance_history_entry
            ).data
        return success_response(data, request=request)


def ensure_assigned(work_order):
    if work_order.assigned_employee_id is None:
        raise ProbeAPIException("EMPLOYEE_NOT_ASSIGNED", "工单尚未派工", status_code=409)


class WorkOrderKnowledgeContextView(APIView):
    def get(self, request, work_order_id):
        work_order = get_work_order(work_order_id)
        ensure_assigned(work_order)
        is_injection = work_order.mold.mold_type == Mold.MoldType.INJECTION
        mold_label = "注塑模具" if is_injection else "钣金模具"
        return success_response(
            {
                "work_order_id": work_order.work_order_id,
                "mold_id": work_order.mold_id,
                "mold_type": work_order.mold.mold_type,
                "rule_id": "MAINT_TRIGGER_TONNAGE_V1",
                "knowledge_profile_code": work_order.knowledge_profile_code,
                "query_keywords": [mold_label, "周期保养", "点检标准", "安全要求"],
                "required_types": [
                    "MAINTENANCE_STANDARD",
                    "INSPECTION_STANDARD",
                    "SAFETY",
                ],
            },
            request=request,
        )


class WorkOrderKnowledgeSnapshotView(APIView):
    @idempotent("SAVE_KNOWLEDGE_SNAPSHOT", "work_order_id")
    def post(self, request, work_order_id):
        work_order = get_work_order(work_order_id)
        ensure_assigned(work_order)
        serializer = KnowledgeSnapshotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        snapshot = KnowledgeSnapshot.objects.create(
            work_order=work_order,
            catalog_version=serializer.validated_data["catalog_version"],
            items_json=serializer.validated_data["items"],
        )
        return success_response(
            KnowledgeSnapshotSerializer(snapshot).data,
            message="知识快照保存成功",
            request=request,
            status=201,
        )


class WorkOrderEmailContextView(APIView):
    def get(self, request, work_order_id):
        work_order = get_work_order(work_order_id)
        ensure_assigned(work_order)
        if not work_order.knowledge_snapshots.exists():
            raise ProbeAPIException(
                "KNOWLEDGE_SNAPSHOT_REQUIRED",
                "生成邮件上下文前必须先回写知识快照",
                status_code=409,
            )
        alert = work_order.alert
        return success_response(
            {
                "to": [work_order.assigned_employee.email],
                "subject": f"【MoldGuard】{work_order.work_order_id} 模具保养任务",
                "template_variables": {
                    "employee_name": work_order.assigned_employee.employee_name,
                    "mold_name": work_order.mold.mold_name,
                    "work_order_id": work_order.work_order_id,
                    "development_tonnage": work_order.mold.development_tonnage,
                    "trigger_threshold": alert.threshold_snapshot,
                    "current_cycle_count": alert.cycle_count_snapshot,
                },
            },
            request=request,
        )


class WorkOrderNotificationView(APIView):
    @idempotent("SAVE_NOTIFICATION_RECEIPT", "work_order_id")
    def post(self, request, work_order_id):
        work_order = get_work_order(work_order_id)
        ensure_assigned(work_order)
        serializer = NotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supplied_recipient = serializer.validated_data.get("recipient")
        expected_recipient = work_order.assigned_employee.email
        if supplied_recipient and supplied_recipient != expected_recipient:
            raise ProbeAPIException(
                "EMPLOYEE_NOT_ASSIGNED",
                "邮件结果收件人必须是被派工人员",
                status_code=409,
            )
        receipt = NotificationReceipt.objects.create(
            work_order=work_order,
            recipient=expected_recipient,
            status=serializer.validated_data["status"],
            message_id=serializer.validated_data.get("message_id", ""),
            error_message=serializer.validated_data.get("error_message", ""),
            sent_at=serializer.validated_data.get("sent_at"),
        )
        return success_response(
            NotificationReceiptSerializer(receipt).data,
            message="邮件发送结果已保存",
            request=request,
            status=201,
        )


class WorkOrderStartView(APIView):
    @idempotent("START_WORK_ORDER", "work_order_id")
    def post(self, request, work_order_id):
        serializer = EmployeeActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = start_work_order(
            work_order_id,
            serializer.validated_data["employee_id"],
            serializer.validated_data.get("occurred_at"),
        )
        return success_response(
            WorkOrderSerializer(get_work_order(work_order.work_order_id)).data,
            message="工单已开工",
            request=request,
        )


class WorkOrderPauseView(APIView):
    @idempotent("PAUSE_WORK_ORDER", "work_order_id")
    def post(self, request, work_order_id):
        serializer = PauseActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = pause_work_order(
            work_order_id,
            serializer.validated_data["employee_id"],
            serializer.validated_data.get("reason", ""),
            serializer.validated_data.get("occurred_at"),
        )
        return success_response(
            WorkOrderSerializer(get_work_order(work_order.work_order_id)).data,
            message="工单已暂停",
            request=request,
        )


class WorkOrderResumeView(APIView):
    @idempotent("RESUME_WORK_ORDER", "work_order_id")
    def post(self, request, work_order_id):
        serializer = EmployeeActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        work_order = resume_work_order(
            work_order_id,
            serializer.validated_data["employee_id"],
            serializer.validated_data.get("occurred_at"),
        )
        return success_response(
            WorkOrderSerializer(get_work_order(work_order.work_order_id)).data,
            message="工单已恢复",
            request=request,
        )


class WorkOrderCompleteReportView(APIView):
    @idempotent("COMPLETE_WORK_ORDER", "work_order_id")
    def post(self, request, work_order_id):
        serializer = CompleteReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = complete_work_order(work_order_id, serializer.validated_data)
        return success_response(result, message="报工完成", request=request)


class WorkOrderAbnormalReportView(APIView):
    @idempotent("ABNORMAL_WORK_ORDER", "work_order_id")
    def post(self, request, work_order_id):
        serializer = AbnormalReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = abnormal_work_order(work_order_id, serializer.validated_data)
        return success_response(result, message="异常报工已保存", request=request)
