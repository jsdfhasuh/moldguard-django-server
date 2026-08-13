import copy
import functools
import hashlib
import json
import threading

from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.response import Response

from .exceptions import ProbeAPIException
from .models import ClientRequestRecord
from .responses import get_request_id

_lock_registry_guard = threading.Lock()
_request_locks = {}


def _request_lock(client_request_id):
    # The documented deployment uses one threaded worker. This lock also keeps
    # SQLite retries deterministic; the database primary key remains the
    # cross-process source of truth.
    with _lock_registry_guard:
        return _request_locks.setdefault(client_request_id, threading.Lock())


def canonical_request_hash(action, object_id, request_data):
    canonical = json.dumps(
        {
            "action": action,
            "object_id": object_id or "",
            "body": request_data,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _replayed_response(record, request):
    payload = copy.deepcopy(record.response_json)
    data = payload.get("data")
    if isinstance(data, dict):
        data["replayed"] = True
    else:
        payload["data"] = {"result": data, "replayed": True}
    payload["request_id"] = get_request_id(request)
    return Response(payload, status=record.response_status)


def _existing_response(client_request_id, request_hash, request):
    try:
        record = ClientRequestRecord.objects.get(client_request_id=client_request_id)
    except ClientRequestRecord.DoesNotExist:
        return None
    if record.request_hash != request_hash:
        raise ProbeAPIException(
            "CLIENT_REQUEST_CONFLICT",
            "client_request_id已用于不同的请求内容",
            status_code=409,
        )
    return _replayed_response(record, request)


def idempotent(action, object_kwarg=None):
    """Store successful write responses and replay exact retries before mutation."""

    def decorator(view_method):
        @functools.wraps(view_method)
        def wrapped(view, request, *args, **kwargs):
            client_request_id = request.data.get("client_request_id")
            if not client_request_id:
                raise serializers.ValidationError(
                    {"client_request_id": ["所有写接口都必须提供client_request_id"]}
                )
            object_id = kwargs.get(object_kwarg, "") if object_kwarg else ""
            request_hash = canonical_request_hash(action, object_id, request.data)

            with _request_lock(client_request_id):
                existing = _existing_response(client_request_id, request_hash, request)
                if existing is not None:
                    return existing

                try:
                    with transaction.atomic():
                        record = ClientRequestRecord.objects.create(
                            client_request_id=client_request_id,
                            action=action,
                            object_id=object_id,
                            request_hash=request_hash,
                            response_status=0,
                            response_json={},
                        )
                        response = view_method(view, request, *args, **kwargs)
                        if response.status_code < 400:
                            record.response_status = response.status_code
                            record.response_json = copy.deepcopy(response.data)
                            record.save(update_fields=["response_status", "response_json"])
                        else:
                            record.delete()
                        return response
                except IntegrityError:
                    existing = _existing_response(client_request_id, request_hash, request)
                    if existing is not None:
                        return existing
                    raise

        return wrapped

    return decorator
