import logging

from django.http import Http404
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("moldguard.errors")


class BusinessError(APIException):
    status_code = 400
    default_code = "BUSINESS_ERROR"
    default_detail = "业务处理失败"

    def __init__(self, code=None, message=None, *, status_code=None, errors=None):
        super().__init__(detail=message or self.default_detail, code=code or self.default_code)
        self.business_code = code or self.default_code
        self.business_message = message or self.default_detail
        self.errors = errors
        if status_code is not None:
            self.status_code = status_code


def exception_handler(exc, context):
    request = context.get("request")
    request_id = getattr(request, "request_id", "")
    if isinstance(exc, BusinessError):
        payload = {
            "code": exc.business_code,
            "message": exc.business_message,
            "data": None,
            "request_id": request_id,
        }
        if exc.errors is not None:
            payload["errors"] = exc.errors
        from rest_framework.response import Response

        return Response(payload, status=exc.status_code)
    if isinstance(exc, Http404):
        from rest_framework.response import Response

        return Response(
            {"code": "NOT_FOUND", "message": "资源不存在", "data": None, "request_id": request_id},
            status=404,
        )
    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception(
            "unhandled API exception request_id=%s path=%s",
            request_id,
            getattr(request, "path", ""),
        )
        from rest_framework.response import Response

        return Response(
            {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "服务器内部错误",
                "data": None,
                "request_id": request_id,
            },
            status=500,
        )
    if isinstance(exc, ValidationError):
        response.data = {
            "code": "VALIDATION_ERROR",
            "message": "请求参数校验失败",
            "data": None,
            "errors": response.data,
            "request_id": request_id,
        }
    else:
        response.data = {
            "code": getattr(exc, "default_code", "API_ERROR").upper(),
            "message": str(exc.detail),
            "data": None,
            "request_id": request_id,
        }
    return response
