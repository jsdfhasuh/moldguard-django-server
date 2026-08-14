import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.common.idempotency import (
    finalize_external_request,
    replay_or_execute,
    reserve_external_request,
)
from apps.common.responses import success_payload
from apps.webhook_probes.models import WebhookProbe

CREATE_PROBE_ACTION = "CREATE_WEBHOOK_PROBE"
COMPLETE_PROBE_ACTION = "COMPLETE_WEBHOOK_PROBE"
CALLBACK_TOKEN_HEADER = "X-MoldGuard-Callback-Token"


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_webhook_request(request, timeout):
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _callback_status(probe, *, now=None):
    if probe.callback_received_at:
        return "COMPLETED"
    if probe.expires_at <= (now or timezone.now()):
        return "EXPIRED"
    return "WAITING_FOR_CALLBACK"


def _roundtrip_status(probe, *, callback_status):
    if probe.dispatch_status in {
        WebhookProbe.DispatchStatus.FAILED,
        WebhookProbe.DispatchStatus.NOT_CONFIGURED,
    }:
        return "FAILED"
    if callback_status == "COMPLETED":
        return "COMPLETED"
    if callback_status == "EXPIRED":
        return "EXPIRED"
    return "WAITING_FOR_CALLBACK"


def probe_result(probe):
    callback_status = _callback_status(probe)
    return {
        "probe_id": probe.probe_id,
        "client_request_id": probe.client_request_id,
        "roundtrip_status": _roundtrip_status(probe, callback_status=callback_status),
        "dispatch_status": probe.dispatch_status,
        "dispatch_http_status": probe.dispatch_http_status,
        "dispatch_error": probe.dispatch_error or None,
        "callback_status": callback_status,
        "callback_received_at": (
            probe.callback_received_at.isoformat() if probe.callback_received_at else None
        ),
        "callback_payload": probe.callback_payload_json or None,
        "expires_at": probe.expires_at.isoformat(),
        "created_at": probe.created_at.isoformat(),
        "updated_at": probe.updated_at.isoformat(),
    }


def _reserve_probe(client_request_id):
    probe_id = f"WHP-{uuid4().hex.upper()}"
    challenge = secrets.token_urlsafe(24)
    callback_token = secrets.token_urlsafe(32)
    probe = WebhookProbe.objects.create(
        probe_id=probe_id,
        client_request_id=client_request_id,
        challenge=challenge,
        callback_token_hash=_token_hash(callback_token),
        dispatch_status=WebhookProbe.DispatchStatus.SENDING,
        expires_at=timezone.now() + timedelta(seconds=settings.MOLDGUARD_WEBHOOK_PROBE_TTL_SECONDS),
    )
    return {
        "probe_id": probe.probe_id,
        "challenge": challenge,
        "callback_token": callback_token,
        "expires_at": probe.expires_at,
    }


def _webhook_payload(reserved):
    probe_id = reserved["probe_id"]
    return {
        "event": "WEBHOOK_ROUNDTRIP_PROBE",
        "probe_id": probe_id,
        "challenge": reserved["challenge"],
        "callback_url": (
            f"{settings.MOLDGUARD_PUBLIC_BASE_URL}/api/v1/webhook-probes/{probe_id}/callback"
        ),
        "callback_token": reserved["callback_token"],
        "callback_token_header": CALLBACK_TOKEN_HEADER,
        "expires_at": reserved["expires_at"].isoformat(),
        "client_request_id": f"webhook-probe-dispatch-{probe_id}",
    }


def _dispatch_webhook(reserved):
    webhook_url = settings.MOLDGUARD_WEBHOOK_PROBE_URL
    if not webhook_url:
        return WebhookProbe.DispatchStatus.NOT_CONFIGURED, None, "URL_NOT_CONFIGURED"

    parsed_url = urlsplit(webhook_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return WebhookProbe.DispatchStatus.FAILED, None, "INVALID_WEBHOOK_URL"

    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(_webhook_payload(reserved), separators=(",", ":")).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "MoldGuard-Webhook-Probe/1.0",
        },
        method="POST",
    )
    try:
        with _open_webhook_request(
            request,
            settings.MOLDGUARD_WEBHOOK_PROBE_TIMEOUT,
        ) as response:
            http_status = response.getcode()
    except urllib.error.HTTPError as exc:
        return WebhookProbe.DispatchStatus.FAILED, exc.code, f"HTTP_{exc.code}"
    except urllib.error.URLError as exc:
        return (
            WebhookProbe.DispatchStatus.FAILED,
            None,
            f"URL_{type(exc.reason).__name__}"[:80],
        )
    except (TimeoutError, OSError, ValueError) as exc:
        return WebhookProbe.DispatchStatus.FAILED, None, type(exc).__name__[:80]

    if 200 <= http_status < 300:
        return WebhookProbe.DispatchStatus.DELIVERED, http_status, ""
    return WebhookProbe.DispatchStatus.FAILED, http_status, f"HTTP_{http_status}"


def _complete_dispatch(probe_id, *, dispatch_status, http_status, dispatch_error):
    probe = WebhookProbe.objects.select_for_update().get(pk=probe_id)
    probe.dispatch_status = dispatch_status
    probe.dispatch_http_status = http_status
    probe.dispatch_error = dispatch_error
    probe.save(
        update_fields=[
            "dispatch_status",
            "dispatch_http_status",
            "dispatch_error",
            "updated_at",
        ]
    )
    return 201, success_payload(probe_result(probe), "Webhook往返探测已创建")


def _finalize_dispatch(
    reservation,
    *,
    probe_id,
    dispatch_status,
    http_status,
    dispatch_error,
    current_request_id,
):
    return finalize_external_request(
        request_id=reservation["request_id"],
        action=CREATE_PROBE_ACTION,
        object_id="",
        request_hash=reservation["request_hash"],
        current_request_id=current_request_id,
        completion_operation=lambda: _complete_dispatch(
            probe_id,
            dispatch_status=dispatch_status,
            http_status=http_status,
            dispatch_error=dispatch_error,
        ),
    )


def _recover_stale_probe(reservation, *, current_request_id):
    age_seconds = (timezone.now() - reservation["created_at"]).total_seconds()
    if age_seconds <= settings.MOLDGUARD_WEBHOOK_PROBE_TIMEOUT + 5:
        raise BusinessError(
            "WEBHOOK_PROBE_IN_PROGRESS",
            "相同client_request_id的Webhook探测正在发送",
            status_code=409,
        )
    probe = WebhookProbe.objects.get(client_request_id=reservation["request_id"])
    return _finalize_dispatch(
        reservation,
        probe_id=probe.probe_id,
        dispatch_status=WebhookProbe.DispatchStatus.FAILED,
        http_status=None,
        dispatch_error="DELIVERY_OUTCOME_UNKNOWN",
        current_request_id=current_request_id,
    )


def create_webhook_probe(payload, *, current_request_id):
    reservation = reserve_external_request(
        action=CREATE_PROBE_ACTION,
        object_id="",
        payload=payload,
        current_request_id=current_request_id,
        reservation_operation=_reserve_probe,
    )
    if reservation["state"] == "REPLAY":
        return reservation["status_code"], reservation["response"]
    if reservation["state"] == "IN_PROGRESS":
        return _recover_stale_probe(reservation, current_request_id=current_request_id)

    reserved = reservation["reservation"]
    dispatch_status, http_status, dispatch_error = _dispatch_webhook(reserved)
    return _finalize_dispatch(
        reservation,
        probe_id=reserved["probe_id"],
        dispatch_status=dispatch_status,
        http_status=http_status,
        dispatch_error=dispatch_error,
        current_request_id=current_request_id,
    )


def _callback_rejected():
    raise BusinessError(
        "WEBHOOK_PROBE_CALLBACK_REJECTED",
        "Webhook探测回调未通过校验",
        status_code=403,
    )


def _complete_callback(probe_id, payload, *, callback_token_hash):
    try:
        probe = WebhookProbe.objects.select_for_update().get(pk=probe_id)
    except WebhookProbe.DoesNotExist:
        _callback_rejected()

    if not hmac.compare_digest(probe.callback_token_hash, callback_token_hash):
        _callback_rejected()
    if probe.expires_at <= timezone.now():
        _callback_rejected()
    if probe.callback_received_at:
        _callback_rejected()
    if not hmac.compare_digest(probe.challenge, payload["challenge"]):
        _callback_rejected()

    probe.callback_received_at = timezone.now()
    probe.callback_payload_json = payload
    probe.save(update_fields=["callback_received_at", "callback_payload_json", "updated_at"])
    return 200, success_payload(probe_result(probe), "Webhook往返探测已闭环")


def complete_webhook_probe(probe_id, payload, *, callback_token, current_request_id):
    if not callback_token or len(callback_token) > 200:
        _callback_rejected()
    callback_token_hash = _token_hash(callback_token)
    idempotency_payload = {
        **payload,
        "callback_token_hash": callback_token_hash,
    }
    return replay_or_execute(
        action=COMPLETE_PROBE_ACTION,
        object_id=probe_id,
        payload=idempotency_payload,
        current_request_id=current_request_id,
        operation=lambda: _complete_callback(
            probe_id,
            payload,
            callback_token_hash=callback_token_hash,
        ),
    )


def get_webhook_probe(probe_id):
    try:
        probe = WebhookProbe.objects.get(pk=probe_id)
    except WebhookProbe.DoesNotExist:
        raise BusinessError(
            "WEBHOOK_PROBE_NOT_FOUND",
            "Webhook探测不存在",
            status_code=404,
        ) from None
    return probe_result(probe)
