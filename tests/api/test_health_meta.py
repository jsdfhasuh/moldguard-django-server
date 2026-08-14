def test_health_and_meta_use_uniform_envelope(api_client):
    health = api_client.get("/api/v1/health", HTTP_X_REQUEST_ID="req-explicit-001")
    assert health.status_code == 200
    assert health.data["request_id"] == "req-explicit-001"
    assert health.data["data"]["status"] == "ok"
    assert health.data["data"]["authentication_required"] is False

    meta = api_client.get("/api/v1/meta")
    assert meta.status_code == 200
    assert meta.data["data"]["knowledge_snapshot_version"] == "MOLDGUARD-KB-1.2"
    assert meta.data["data"]["report_form_schema_version"] == "REPORT-FORM-1.1"
    assert meta.data["data"]["data_classification"] == "DEMO_ONLY"
    assert meta.data["data"]["smtp_backend_configured"] is False
    assert meta.data["data"]["smtp_delivery_verified"] is False
    assert meta.data["data"]["implementation_status"] == "SMTP_CONFIGURATION_REQUIRED"
    assert meta.data["request_id"].startswith("req-")


def test_meta_requires_manual_delivery_verification_before_competition_ready(api_client, settings):
    settings.MOLDGUARD_REQUIRE_SMTP = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.MOLDGUARD_SMTP_DELIVERY_VERIFIED = False

    unverified = api_client.get("/api/v1/meta")
    assert unverified.status_code == 200
    assert unverified.data["data"]["smtp_backend_configured"] is True
    assert unverified.data["data"]["smtp_delivery_verified"] is False
    assert unverified.data["data"]["implementation_status"] == "READY_FOR_SMTP_DELIVERY_TEST"

    settings.MOLDGUARD_SMTP_DELIVERY_VERIFIED = True
    verified = api_client.get("/api/v1/meta")
    assert verified.status_code == 200
    assert verified.data["data"]["smtp_delivery_verified"] is True
    assert verified.data["data"]["implementation_status"] == "READY_FOR_COMPETITION"


def test_unknown_api_path_returns_json_not_html(api_client):
    response = api_client.get("/api/v1/not-a-real-endpoint")
    assert response.status_code == 404
    assert response.data["code"] == "NOT_FOUND"
    assert response.data["data"] is None
    assert response.data["request_id"].startswith("req-")
