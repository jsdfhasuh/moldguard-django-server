from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.common.responses import error_response, success_response
from apps.common.serializers import OpenAPIEnvelopeSerializer


class EnvelopeAPIView(APIView):
    serializer_class = OpenAPIEnvelopeSerializer


class HealthView(EnvelopeAPIView):
    @extend_schema(responses=OpenAPIEnvelopeSerializer)
    def get(self, request):
        return success_response(
            {
                "service": "moldguard-competition-server",
                "status": "ok",
                "version": "1.0.0",
                "time": timezone.localtime().isoformat(),
                "authentication_required": False,
            },
            request=request,
        )


class MetaView(EnvelopeAPIView):
    @extend_schema(responses=OpenAPIEnvelopeSerializer)
    def get(self, request):
        return success_response(
            {
                "service": "moldguard-competition-server",
                "version": "1.0.0",
                "knowledge_snapshot_version": settings.MOLDGUARD_KNOWLEDGE_VERSION,
                "report_form_schema_version": settings.MOLDGUARD_REPORT_SCHEMA_VERSION,
                "default_port": 18080,
                "authentication_required": False,
                "data_classification": "DEMO_ONLY",
                "implementation_status": "BACKEND_P0_IMPLEMENTED_AWAITING_TEST_DEBUG",
            },
            request=request,
        )


@extend_schema(exclude=True)
class ApiNotFoundView(EnvelopeAPIView):
    def get(self, request, unmatched_path=""):
        return error_response("NOT_FOUND", "API路径不存在", request, status=404)

    post = get
    put = get
    patch = get
    delete = get
