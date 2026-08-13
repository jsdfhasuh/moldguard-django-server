import uuid

from rest_framework.response import Response


def get_request_id(request=None):
    if request is not None and hasattr(request, "probe_request_id"):
        return request.probe_request_id
    return f"req-{uuid.uuid4().hex}"


def success_response(data=None, *, message="success", request=None, status=200):
    return Response(
        {
            "code": "SUCCESS",
            "message": message,
            "data": {} if data is None else data,
            "request_id": get_request_id(request),
        },
        status=status,
    )


def error_response(
    code,
    message,
    *,
    errors=None,
    request=None,
    status=400,
):
    return Response(
        {
            "code": code,
            "message": message,
            "data": None,
            "errors": [] if errors is None else errors,
            "request_id": get_request_id(request),
        },
        status=status,
    )


class RequestIDMiddleware:
    """Attach a trace-only request ID without treating it as authentication."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "").strip()
        request.probe_request_id = supplied or f"req-{uuid.uuid4().hex}"
        response = self.get_response(request)
        response["X-Request-ID"] = request.probe_request_id
        return response
