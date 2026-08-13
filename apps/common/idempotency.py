import copy
import hashlib
import json

from django.db import IntegrityError, transaction

from apps.common.exceptions import BusinessError
from apps.common.models import ClientRequestRecord


def canonical_hash(action, object_id, payload):
    canonical = json.dumps(
        {"action": action, "object_id": object_id or "", "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def require_client_request_id(payload):
    value = payload.get("client_request_id")
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        raise BusinessError(
            "VALIDATION_ERROR",
            "client_request_id为必填字段且最长120字符",
            errors={"client_request_id": ["无效的幂等ID"]},
        )
    return value.strip()


def replay_or_execute(*, action, object_id, payload, current_request_id, operation):
    request_id = require_client_request_id(payload)
    request_hash = canonical_hash(action, object_id, payload)
    with transaction.atomic():
        try:
            with transaction.atomic():
                record = ClientRequestRecord.objects.create(
                    client_request_id=request_id,
                    action=action,
                    object_id=object_id or "",
                    request_hash=request_hash,
                    response_status=0,
                    response_json={},
                )
            is_new = True
        except IntegrityError:
            record = ClientRequestRecord.objects.select_for_update().get(pk=request_id)
            is_new = False
        if not is_new:
            if (
                record.action != action
                or record.object_id != (object_id or "")
                or record.request_hash != request_hash
            ):
                raise BusinessError(
                    "CLIENT_REQUEST_CONFLICT", "相同client_request_id对应不同请求", status_code=409
                )
            response = copy.deepcopy(record.response_json)
            if isinstance(response.get("data"), dict):
                response["data"]["replayed"] = True
            response["request_id"] = current_request_id
            return record.response_status, response

        status_code, response = operation()
        stored = copy.deepcopy(response)
        if isinstance(stored.get("data"), dict):
            stored["data"]["replayed"] = False
        stored["request_id"] = current_request_id
        record.response_status = status_code
        record.response_json = stored
        record.save(update_fields=["response_status", "response_json"])
        return status_code, stored
