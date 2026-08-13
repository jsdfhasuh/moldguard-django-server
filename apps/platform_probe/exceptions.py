from rest_framework import exceptions, status
from rest_framework.views import exception_handler

from .responses import error_response


class ProbeAPIException(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "请求无法处理"
    default_code = "INVALID_REQUEST"

    def __init__(self, code=None, message=None, *, status_code=None, errors=None):
        super().__init__(detail=message or self.default_detail, code=code or self.default_code)
        self.probe_code = code or self.default_code
        self.probe_message = message or self.default_detail
        self.probe_errors = errors or []
        if status_code is not None:
            self.status_code = status_code


def _validation_errors(detail):
    if isinstance(detail, dict):
        return [
            {"field": str(field), "messages": [str(item) for item in messages]}
            for field, messages in detail.items()
        ]
    if isinstance(detail, list):
        return [str(item) for item in detail]
    return [str(detail)]


def probe_exception_handler(exc, context):
    request = context.get("request")
    if isinstance(exc, ProbeAPIException):
        return error_response(
            exc.probe_code,
            exc.probe_message,
            errors=exc.probe_errors,
            request=request,
            status=exc.status_code,
        )

    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, exceptions.ValidationError):
        code = "VALIDATION_ERROR"
        message = "请求参数校验失败"
        errors = _validation_errors(exc.detail)
    elif isinstance(exc, exceptions.ParseError):
        code = "INVALID_JSON"
        message = "请求体不是有效的JSON"
        errors = []
    elif isinstance(exc, exceptions.NotFound):
        code = "NOT_FOUND"
        message = "请求的资源不存在"
        errors = []
    elif isinstance(exc, exceptions.MethodNotAllowed):
        code = "METHOD_NOT_ALLOWED"
        message = "请求方法不允许"
        errors = []
    else:
        code = "API_ERROR"
        message = str(exc.detail)
        errors = []

    return error_response(
        code,
        message,
        errors=errors,
        request=request,
        status=response.status_code,
    )
