from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from .exceptions import ProbeAPIException
from .models import MaintenanceAlert, Mold
from .responses import success_response
from .serializers import AlertScanSerializer, MaintenanceAlertSerializer, MoldSerializer
from .services.alert_service import scan_molds
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
