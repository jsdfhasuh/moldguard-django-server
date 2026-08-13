import logging
import re
import uuid

logger = logging.getLogger("moldguard.requests")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,120}$")


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "")
        request.request_id = (
            supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else f"req-{uuid.uuid4().hex}"
        )
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        logger.info(
            "request completed request_id=%s path=%s status=%s",
            request.request_id,
            request.path,
            response.status_code,
        )
        return response
