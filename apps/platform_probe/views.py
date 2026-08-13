from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from .responses import success_response


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
