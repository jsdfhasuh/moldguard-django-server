from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from .exceptions import ProbeAPIException
from .idempotency import idempotent
from .models import (
    KnowledgeSnapshot,
    MaintenanceAlert,
    Mold,
    NotificationReceipt,
    ProbeRun,
    ProbeStep,
    WorkOrder,
)
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
    ProbeRunCreateSerializer,
    ProbeVariableTestSerializer,
    SchedulerHeartbeatSerializer,
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
from .services.probe_report_service import (
    build_probe_report,
    expected_context,
    get_probe_run,
    record_step,
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


class ProbeRunCreateView(APIView):
    @idempotent("CREATE_PROBE_RUN")
    def post(self, request):
        serializer = ProbeRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = ProbeRun.objects.create(
            platform_name=serializer.validated_data["platform_name"],
            tester=serializer.validated_data["tester"],
            mode=serializer.validated_data["mode"],
        )
        record_step(
            run,
            "P01_POST",
            ProbeStep.Status.PASS_NATIVE,
            request_snapshot=dict(request.data),
            response_snapshot={"run_id": run.run_id},
            evidence="平台成功调用POST /api/v1/probe/runs",
        )
        return success_response(
            {
                "run_id": run.run_id,
                "platform_name": run.platform_name,
                "tester": run.tester,
                "mode": run.mode,
                "status": run.status,
                "started_at": run.started_at.isoformat(),
                "context_url": f"/api/v1/probe/runs/{run.run_id}/context",
            },
            message="探测运行已创建",
            request=request,
            status=201,
        )


class ProbeRunContextView(APIView):
    def get(self, request, run_id):
        run = get_probe_run(run_id)
        context = expected_context(run)
        record_step(
            run,
            "P01_GET",
            ProbeStep.Status.PASS_NATIVE,
            response_snapshot={"context_url": request.path},
            evidence=f"平台成功调用动态GET路径 {request.path}",
        )
        return success_response(
            {
                "run_id": run.run_id,
                "mode": run.mode,
                "challenge": context,
                "instructions": {
                    "variable_test_url": f"/api/v1/probe/runs/{run.run_id}/variable-test",
                    "required_action": "将challenge中的三个字段原样回传",
                },
            },
            request=request,
        )


class ProbeVariableTestView(APIView):
    @idempotent("PROBE_VARIABLE_TEST", "run_id")
    def post(self, request, run_id):
        run = get_probe_run(run_id)
        serializer = ProbeVariableTestSerializer(data=request.data, context={"probe_run": run})
        serializer.is_valid(raise_exception=True)
        expected = expected_context(run)
        submitted = serializer.validated_data
        checks = {
            "P02": submitted["dynamic_variables"] == expected["dynamic_variables"],
            "P03": submitted["nested_json"] == expected["nested_json"],
            "P04": submitted["array_items"] == expected["array_items"],
        }
        failures = [code for code, passed in checks.items() if not passed]
        if failures:
            raise ProbeAPIException(
                "PROBE_VARIABLE_MISMATCH",
                "动态变量、嵌套JSON或数组回传不匹配",
                errors=[{"failed_capabilities": failures, "expected": expected}],
            )
        for code in checks:
            record_step(
                run,
                code,
                ProbeStep.Status.PASS_NATIVE,
                request_snapshot={code: submitted},
                response_snapshot={"matched": True},
                evidence=f"{code}严格模式挑战原样回传成功",
            )
        for item in submitted["capability_results"]:
            record_step(
                run,
                item["capability_code"],
                item["status"],
                request_snapshot=item,
                response_snapshot={"impact": item.get("impact", "")},
                evidence=item.get("evidence", ""),
            )
        return success_response(
            {
                "run_id": run.run_id,
                "matched": True,
                "verified_capabilities": list(checks),
                "roundtrip": {
                    "dynamic_variables": submitted["dynamic_variables"],
                    "nested_json": submitted["nested_json"],
                    "array_items": submitted["array_items"],
                },
            },
            message="变量、嵌套JSON和数组探测通过",
            request=request,
        )


class ProbeSchedulerHeartbeatView(APIView):
    @idempotent("PROBE_SCHEDULER_HEARTBEAT")
    def post(self, request):
        serializer = SchedulerHeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = get_probe_run(serializer.validated_data["run_id"])
        received_at = timezone.now()
        heartbeat_at = serializer.validated_data.get("heartbeat_at", received_at)
        record_step(
            run,
            "P12",
            ProbeStep.Status.PASS_NATIVE,
            request_snapshot=dict(request.data),
            response_snapshot={"received_at": received_at.isoformat()},
            evidence=serializer.validated_data.get("evidence") or "平台成功调用scheduler-heartbeat",
        )
        return success_response(
            {
                "run_id": run.run_id,
                "heartbeat_at": heartbeat_at.isoformat(),
                "received_at": received_at.isoformat(),
                "scheduler_capability": "PASS_NATIVE",
            },
            message="定时心跳已记录",
            request=request,
        )


class ProbeRunReportView(APIView):
    def get(self, request, run_id):
        run = get_probe_run(run_id)
        return success_response(build_probe_report(run), request=request)


class ProbeNotFoundView(APIView):
    def _not_found(self):
        raise ProbeAPIException("NOT_FOUND", "请求的API路径不存在", status_code=404)

    def get(self, request, unmatched=None):
        self._not_found()

    post = get
    put = get
    patch = get
    delete = get
