import hashlib
import json
import urllib.error
from datetime import timedelta
from urllib.parse import urlsplit

import pytest
from django.utils import timezone

from apps.webhook_probes import services
from apps.webhook_probes.models import WebhookProbe


class FakeResponse:
    def __init__(self, status_code=204):
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getcode(self):
        return self.status_code


def configure_probe(settings):
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://public.moldguard.example"
    settings.MOLDGUARD_WEBHOOK_PROBE_URL = "https://platform.example/webhook-test"
    settings.MOLDGUARD_WEBHOOK_PROBE_TIMEOUT = 7
    settings.MOLDGUARD_WEBHOOK_PROBE_TTL_SECONDS = 600


def test_webhook_probe_redirect_handler_does_not_follow_redirects():
    handler = services._NoRedirectHandler()

    assert handler.redirect_request(None, None, 302, "Found", {}, "http://127.0.0.1") is None


@pytest.mark.django_db
def test_webhook_probe_completes_real_roundtrip(api_client, settings, monkeypatch):
    configure_probe(settings)
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data)
        payload = captured["payload"]
        callback = api_client.post(
            urlsplit(payload["callback_url"]).path,
            {
                "client_request_id": f"callback-{payload['probe_id']}",
                "challenge": payload["challenge"],
                "platform_name": "competition-agent-platform",
                "evidence": "flow-execution-001",
            },
            format="json",
            HTTP_X_MOLDGUARD_CALLBACK_TOKEN=payload["callback_token"],
        )
        captured["callback"] = callback
        return FakeResponse()

    monkeypatch.setattr("apps.webhook_probes.services._open_webhook_request", fake_urlopen)

    request_body = {"client_request_id": "create-webhook-roundtrip-001"}
    created = api_client.post("/api/v1/webhook-probes", request_body, format="json")
    replayed = api_client.post("/api/v1/webhook-probes", request_body, format="json")

    assert created.status_code == replayed.status_code == 201
    assert captured["url"] == settings.MOLDGUARD_WEBHOOK_PROBE_URL
    assert captured["timeout"] == 7
    assert captured["callback"].status_code == 200
    assert created.data["data"]["dispatch_status"] == "DELIVERED"
    assert created.data["data"]["roundtrip_status"] == "COMPLETED"
    assert replayed.data["data"]["probe_id"] == created.data["data"]["probe_id"]
    assert replayed.data["data"]["replayed"] is True

    webhook_payload = captured["payload"]
    assert set(webhook_payload) == {
        "event",
        "probe_id",
        "challenge",
        "callback_url",
        "callback_token",
        "callback_token_header",
        "expires_at",
        "client_request_id",
    }
    assert webhook_payload["event"] == "WEBHOOK_ROUNDTRIP_PROBE"
    assert webhook_payload["callback_token_header"] == "X-MoldGuard-Callback-Token"
    assert webhook_payload["callback_url"].startswith(settings.MOLDGUARD_PUBLIC_BASE_URL)

    probe = WebhookProbe.objects.get(pk=created.data["data"]["probe_id"])
    assert (
        probe.callback_token_hash
        == hashlib.sha256(webhook_payload["callback_token"].encode()).hexdigest()
    )
    assert webhook_payload["callback_token"] not in json.dumps(created.data)
    assert probe.callback_payload_json["evidence"] == "flow-execution-001"

    detail = api_client.get(f"/api/v1/webhook-probes/{probe.probe_id}")
    assert detail.status_code == 200
    assert detail.data["data"]["callback_status"] == "COMPLETED"


@pytest.mark.django_db
def test_webhook_probe_callback_rejects_bad_token_and_consumes_token_once(
    api_client, settings, monkeypatch
):
    configure_probe(settings)
    captured = {}

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr("apps.webhook_probes.services._open_webhook_request", fake_urlopen)
    created = api_client.post(
        "/api/v1/webhook-probes",
        {"client_request_id": "create-webhook-token-001"},
        format="json",
    )
    callback_path = urlsplit(captured["callback_url"]).path
    callback_body = {
        "client_request_id": "callback-webhook-token-001",
        "challenge": captured["challenge"],
        "platform_name": "competition-agent-platform",
        "evidence": "flow-execution-002",
    }

    rejected = api_client.post(
        callback_path,
        callback_body,
        format="json",
        HTTP_X_MOLDGUARD_CALLBACK_TOKEN="wrong-token",
    )
    accepted = api_client.post(
        callback_path,
        callback_body,
        format="json",
        HTTP_X_MOLDGUARD_CALLBACK_TOKEN=captured["callback_token"],
    )
    replayed = api_client.post(
        callback_path,
        callback_body,
        format="json",
        HTTP_X_MOLDGUARD_CALLBACK_TOKEN=captured["callback_token"],
    )
    reused = api_client.post(
        callback_path,
        {**callback_body, "client_request_id": "callback-webhook-token-002"},
        format="json",
        HTTP_X_MOLDGUARD_CALLBACK_TOKEN=captured["callback_token"],
    )

    assert created.status_code == 201
    assert rejected.status_code == 403
    assert rejected.data["code"] == "WEBHOOK_PROBE_CALLBACK_REJECTED"
    assert accepted.status_code == replayed.status_code == 200
    assert accepted.data["data"]["roundtrip_status"] == "COMPLETED"
    assert replayed.data["data"]["replayed"] is True
    assert reused.status_code == 403
    assert reused.data["code"] == "WEBHOOK_PROBE_CALLBACK_REJECTED"


@pytest.mark.django_db
def test_webhook_probe_callback_rejects_expired_probe(api_client, settings, monkeypatch):
    configure_probe(settings)
    captured = {}

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr("apps.webhook_probes.services._open_webhook_request", fake_urlopen)
    created = api_client.post(
        "/api/v1/webhook-probes",
        {"client_request_id": "create-webhook-expired-001"},
        format="json",
    )
    WebhookProbe.objects.filter(pk=created.data["data"]["probe_id"]).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    callback = api_client.post(
        urlsplit(captured["callback_url"]).path,
        {
            "client_request_id": "callback-webhook-expired-001",
            "challenge": captured["challenge"],
            "evidence": "late-callback",
        },
        format="json",
        HTTP_X_MOLDGUARD_CALLBACK_TOKEN=captured["callback_token"],
    )
    detail = api_client.get(f"/api/v1/webhook-probes/{created.data['data']['probe_id']}")

    assert callback.status_code == 403
    assert detail.data["data"]["callback_status"] == "EXPIRED"
    assert detail.data["data"]["roundtrip_status"] == "EXPIRED"


@pytest.mark.django_db
def test_webhook_probe_records_not_configured_without_network_call(
    api_client, settings, monkeypatch
):
    settings.MOLDGUARD_WEBHOOK_PROBE_URL = ""

    def fail_if_called(*args, **kwargs):
        raise AssertionError("urlopen must not be called without a configured probe URL")

    monkeypatch.setattr("apps.webhook_probes.services._open_webhook_request", fail_if_called)
    created = api_client.post(
        "/api/v1/webhook-probes",
        {"client_request_id": "create-webhook-unconfigured-001"},
        format="json",
    )

    assert created.status_code == 201
    assert created.data["data"]["dispatch_status"] == "NOT_CONFIGURED"
    assert created.data["data"]["roundtrip_status"] == "FAILED"
    assert created.data["data"]["dispatch_error"] == "URL_NOT_CONFIGURED"


@pytest.mark.django_db
def test_webhook_probe_records_platform_http_failure(api_client, settings, monkeypatch):
    configure_probe(settings)
    captured = {}

    def fake_urlopen(request, timeout):
        payload = json.loads(request.data)
        captured["callback"] = api_client.post(
            urlsplit(payload["callback_url"]).path,
            {
                "client_request_id": "callback-before-http-failure-001",
                "challenge": payload["challenge"],
                "evidence": "callback-arrived-before-502",
            },
            format="json",
            HTTP_X_MOLDGUARD_CALLBACK_TOKEN=payload["callback_token"],
        )
        raise urllib.error.HTTPError(request.full_url, 502, "bad gateway", None, None)

    monkeypatch.setattr("apps.webhook_probes.services._open_webhook_request", fake_urlopen)
    created = api_client.post(
        "/api/v1/webhook-probes",
        {"client_request_id": "create-webhook-http-failure-001"},
        format="json",
    )

    assert created.status_code == 201
    assert created.data["data"]["dispatch_status"] == "FAILED"
    assert created.data["data"]["dispatch_http_status"] == 502
    assert created.data["data"]["dispatch_error"] == "HTTP_502"
    assert captured["callback"].status_code == 200
    assert created.data["data"]["callback_status"] == "COMPLETED"
    assert created.data["data"]["roundtrip_status"] == "FAILED"


@pytest.mark.django_db
def test_webhook_probe_rejects_request_supplied_target(api_client, settings, monkeypatch):
    settings.MOLDGUARD_WEBHOOK_PROBE_URL = ""

    def fail_if_called(*args, **kwargs):
        raise AssertionError("request-supplied target must never be called")

    monkeypatch.setattr("apps.webhook_probes.services._open_webhook_request", fail_if_called)
    response = api_client.post(
        "/api/v1/webhook-probes",
        {
            "client_request_id": "create-webhook-ssrf-001",
            "webhook_url": "http://127.0.0.1:1/internal",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "服务器配置" in response.data["errors"]["webhook_url"][0]
    assert not WebhookProbe.objects.exists()
