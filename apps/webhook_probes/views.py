from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response

from apps.common.responses import success_response
from apps.common.serializers import OpenAPIEnvelopeSerializer
from apps.common.views import EnvelopeAPIView
from apps.webhook_probes.serializers import (
    WebhookProbeCallbackSerializer,
    WebhookProbeCreateSerializer,
)
from apps.webhook_probes.services import (
    CALLBACK_TOKEN_HEADER,
    complete_webhook_probe,
    create_webhook_probe,
    get_webhook_probe,
)


class WebhookProbeCollectionView(EnvelopeAPIView):
    @extend_schema(
        request=WebhookProbeCreateSerializer,
        responses={201: OpenAPIEnvelopeSerializer},
        tags=["Webhook probe"],
    )
    def post(self, request):
        serializer = WebhookProbeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_code, payload = create_webhook_probe(
            serializer.validated_data,
            current_request_id=request.request_id,
        )
        return Response(payload, status=status_code)


class WebhookProbeDetailView(EnvelopeAPIView):
    @extend_schema(responses=OpenAPIEnvelopeSerializer, tags=["Webhook probe"])
    def get(self, request, probe_id):
        return success_response(get_webhook_probe(probe_id), request=request)


class WebhookProbeCallbackView(EnvelopeAPIView):
    @extend_schema(
        request=WebhookProbeCallbackSerializer,
        responses=OpenAPIEnvelopeSerializer,
        parameters=[
            OpenApiParameter(
                name=CALLBACK_TOKEN_HEADER,
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="Django在本次Webhook负载中发送的一次性回调令牌",
            )
        ],
        tags=["Webhook probe"],
    )
    def post(self, request, probe_id):
        serializer = WebhookProbeCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_code, payload = complete_webhook_probe(
            probe_id,
            serializer.validated_data,
            callback_token=request.headers.get(CALLBACK_TOKEN_HEADER, "").strip(),
            current_request_id=request.request_id,
        )
        return Response(payload, status=status_code)
