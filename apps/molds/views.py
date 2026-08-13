from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.common.exceptions import BusinessError
from apps.common.idempotency import replay_or_execute
from apps.common.responses import success_payload, success_response
from apps.common.serializers import OpenAPIEnvelopeSerializer
from apps.common.views import EnvelopeAPIView
from apps.molds.models import Alert, Mold
from apps.molds.presentation import alert_data, mold_data
from apps.molds.serializers import AlertScanSerializer
from apps.molds.services.scan_service import scan_molds
from apps.molds.services.trigger_service import evaluate_trigger


def get_mold(mold_id):
    try:
        return Mold.objects.get(pk=mold_id)
    except Mold.DoesNotExist:
        raise BusinessError("MOLD_NOT_FOUND", "模具不存在", status_code=404) from None


class MoldListView(EnvelopeAPIView):
    @extend_schema(operation_id="list_molds", responses=OpenAPIEnvelopeSerializer)
    def get(self, request):
        queryset = Mold.objects.order_by("mold_id")
        if request.query_params.get("mold_type"):
            queryset = queryset.filter(mold_type=request.query_params["mold_type"])
        if request.query_params.get("status"):
            queryset = queryset.filter(status=request.query_params["status"])
        return success_response(
            {"count": queryset.count(), "results": [mold_data(item) for item in queryset]},
            request=request,
        )


class MoldDetailView(EnvelopeAPIView):
    @extend_schema(operation_id="retrieve_mold", responses=OpenAPIEnvelopeSerializer)
    def get(self, request, mold_id):
        return success_response(mold_data(get_mold(mold_id)), request=request)


class MoldMaintenanceStatusView(EnvelopeAPIView):
    def get(self, request, mold_id):
        mold = get_mold(mold_id)
        return success_response(evaluate_trigger(mold), request=request)


class AlertScanView(EnvelopeAPIView):
    serializer_class = AlertScanSerializer

    @extend_schema(request=AlertScanSerializer, responses=OpenAPIEnvelopeSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        mold_ids = payload.get("mold_ids")

        def operation():
            data = scan_molds(mold_ids=mold_ids)
            return 200, success_payload(data, "扫描完成", request)

        status_code, response_payload = replay_or_execute(
            action="ALERT_SCAN",
            object_id="SELECTED_MOLDS" if mold_ids is not None else "ALL_MOLDS",
            payload=payload,
            current_request_id=request.request_id,
            operation=operation,
        )
        return Response(response_payload, status=status_code)


class AlertListView(EnvelopeAPIView):
    def get(self, request):
        queryset = Alert.objects.prefetch_related("work_orders").order_by("-triggered_at")
        if request.query_params.get("status"):
            queryset = queryset.filter(status=request.query_params["status"])
        if request.query_params.get("mold_id"):
            queryset = queryset.filter(mold_id=request.query_params["mold_id"])
        return success_response(
            {"count": queryset.count(), "results": [alert_data(item) for item in queryset]},
            request=request,
        )
