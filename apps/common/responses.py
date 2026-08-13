from rest_framework.response import Response


def success_payload(data=None, message="success", request=None):
    return {
        "code": "SUCCESS",
        "message": message,
        "data": {} if data is None else data,
        "request_id": getattr(request, "request_id", ""),
    }


def success_response(data=None, message="success", request=None, status=200):
    return Response(success_payload(data, message, request), status=status)


def error_response(code, message, request=None, *, errors=None, status=400):
    payload = {
        "code": code,
        "message": message,
        "data": None,
        "request_id": getattr(request, "request_id", ""),
    }
    if errors is not None:
        payload["errors"] = errors
    return Response(payload, status=status)
