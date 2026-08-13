def test_health_is_open_and_returns_envelope(api_client):
    response = api_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.data["code"] == "SUCCESS"
    assert response.data["data"]["status"] == "ok"
    assert response.data["data"]["authentication_required"] is False
    assert response.data["request_id"].startswith("req-")
    assert response["X-Request-ID"] == response.data["request_id"]


def test_request_id_can_be_propagated_for_tracing(api_client):
    response = api_client.get("/api/v1/meta", HTTP_X_REQUEST_ID="req-platform-test")

    assert response.status_code == 200
    assert response.data["request_id"] == "req-platform-test"
    assert response["X-Request-ID"] == "req-platform-test"


def test_meta_documents_open_demo_server(api_client):
    response = api_client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.data["data"]["authentication"] == "NONE"
    assert response.data["data"]["data_classification"] == "DEMO_ONLY"
    assert response.data["data"]["default_port"] == 18080


def test_wrong_method_uses_unified_error_envelope(api_client):
    response = api_client.post("/api/v1/health", {}, format="json")

    assert response.status_code == 405
    assert response.data["code"] == "METHOD_NOT_ALLOWED"
    assert response.data["data"] is None
    assert response.data["errors"] == []
    assert response.data["request_id"].startswith("req-")
