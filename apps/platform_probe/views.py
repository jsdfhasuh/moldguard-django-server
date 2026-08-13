from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from .exceptions import ProbeAPIException
from .models import MaintenanceAlert, Mold, WorkOrder
from .responses import success_response
from .serializers import (
    AlertScanSerializer,
    AssignSerializer,
    AutoAssignSerializer,
    CreateWorkOrderSerializer,
    EmployeeSerializer,
    MaintenanceAlertSerializer,
    MoldSerializer,
    WorkOrderEventSerializer,
    WorkOrderSerializer,
)
from .services.alert_service import create_work_order, scan_molds
from .services.assignment_service import (
    assign_employee,
    auto_assign_employee,
    candidates_for,
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
        return success_response(
            {
                "work_order_id": work_order.work_order_id,
                "events": WorkOrderEventSerializer(work_order.events.all(), many=True).data,
            },
            request=request,
        )
