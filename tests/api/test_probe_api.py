import pytest

from apps.platform_probe.models import ProbeRun, ProbeStep


def create_run(api_client, *, mode="STRICT", request_id="probe-create"):
    return api_client.post(
        "/api/v1/probe/runs",
        {
            "platform_name": "competition-agent-platform",
            "tester": "platform-integration-test",
            "mode": mode,
            "client_request_id": request_id,
        },
        format="json",
    )


@pytest.mark.django_db
def test_probe_run_context_verifies_dynamic_get_path(api_client):
    created = create_run(api_client)
    run_id = created.data["data"]["run_id"]

    context = api_client.get(f"/api/v1/probe/runs/{run_id}/context")

    assert created.status_code == 201
    assert created.data["data"]["mode"] == "STRICT"
    assert context.status_code == 200
    assert context.data["data"]["challenge"]["dynamic_variables"]["run_id"] == run_id
    assert (
        context.data["data"]["challenge"]["nested_json"]["mold"]["maintenance"]["threshold"]
        == 50_000
    )
    assert len(context.data["data"]["challenge"]["array_items"]) == 3
    assert set(
        ProbeStep.objects.filter(run_id=run_id).values_list("capability_code", flat=True)
    ) == {
        "P01_GET",
        "P01_POST",
    }


@pytest.mark.django_db
def test_variable_test_roundtrips_nested_json_and_array(api_client):
    created = create_run(api_client)
    run_id = created.data["data"]["run_id"]
    context = api_client.get(f"/api/v1/probe/runs/{run_id}/context").data["data"]["challenge"]
    payload = {
        **context,
        "capability_results": [
            {
                "capability_code": "P05",
                "status": "PASS_NATIVE",
                "evidence": "状态流转实际调用成功",
                "impact": "无",
            },
            {
                "capability_code": "P08",
                "status": "EXTERNAL_REQUIRED",
                "evidence": "邮件由比赛平台服务发送",
                "impact": "正式方案需要外部邮件服务",
            },
        ],
        "client_request_id": "variable-test-001",
    }

    response = api_client.post(f"/api/v1/probe/runs/{run_id}/variable-test", payload, format="json")

    assert response.status_code == 200
    assert response.data["data"]["matched"] is True
    assert response.data["data"]["verified_capabilities"] == ["P02", "P03", "P04"]
    assert response.data["data"]["roundtrip"]["array_items"] == context["array_items"]
    steps = {item.capability_code: item.status for item in ProbeStep.objects.filter(run_id=run_id)}
    assert steps["P02"] == "PASS_NATIVE"
    assert steps["P03"] == "PASS_NATIVE"
    assert steps["P04"] == "PASS_NATIVE"
    assert steps["P05"] == "PASS_NATIVE"
    assert steps["P08"] == "EXTERNAL_REQUIRED"


@pytest.mark.django_db
def test_variable_mismatch_does_not_create_pass_steps(api_client):
    created = create_run(api_client)
    run_id = created.data["data"]["run_id"]
    context = api_client.get(f"/api/v1/probe/runs/{run_id}/context").data["data"]["challenge"]
    context["array_items"] = list(reversed(context["array_items"]))

    response = api_client.post(
        f"/api/v1/probe/runs/{run_id}/variable-test",
        {**context, "client_request_id": "variable-mismatch"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "PROBE_VARIABLE_MISMATCH"
    assert not ProbeStep.objects.filter(run_id=run_id, capability_code="P04").exists()


@pytest.mark.django_db
def test_strict_mode_rejects_adapter_pass(api_client):
    created = create_run(api_client)
    run_id = created.data["data"]["run_id"]
    context = api_client.get(f"/api/v1/probe/runs/{run_id}/context").data["data"]["challenge"]

    response = api_client.post(
        f"/api/v1/probe/runs/{run_id}/variable-test",
        {
            **context,
            "capability_results": [{"capability_code": "P06", "status": "PASS_WITH_ADAPTER"}],
            "client_request_id": "strict-adapter",
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_compatibility_mode_accepts_adapter_pass(api_client):
    created = create_run(api_client, mode="COMPATIBILITY", request_id="compat-create")
    run_id = created.data["data"]["run_id"]
    context = api_client.get(f"/api/v1/probe/runs/{run_id}/context").data["data"]["challenge"]

    response = api_client.post(
        f"/api/v1/probe/runs/{run_id}/variable-test",
        {
            **context,
            "capability_results": [
                {
                    "capability_code": "P06",
                    "status": "PASS_WITH_ADAPTER",
                    "evidence": "使用明确关键词适配后检索成功",
                }
            ],
            "client_request_id": "compat-variable",
        },
        format="json",
    )

    assert response.status_code == 200
    assert ProbeStep.objects.get(run_id=run_id, capability_code="P06").status == (
        "PASS_WITH_ADAPTER"
    )


@pytest.mark.django_db
def test_scheduler_heartbeat_records_capability(api_client):
    created = create_run(api_client)
    run_id = created.data["data"]["run_id"]

    heartbeat = api_client.post(
        "/api/v1/probe/scheduler-heartbeat",
        {
            "run_id": run_id,
            "platform_name": "competition-agent-platform",
            "heartbeat_at": "2026-08-13T16:00:00+08:00",
            "evidence": "平台定时节点自动触发",
            "client_request_id": "heartbeat-001",
        },
        format="json",
    )

    assert heartbeat.status_code == 200
    assert heartbeat.data["data"]["scheduler_capability"] == "PASS_NATIVE"
    assert ProbeStep.objects.get(run_id=run_id, capability_code="P12").status == "PASS_NATIVE"


@pytest.mark.django_db
def test_report_preserves_not_tested_and_has_full_matrix(api_client):
    created = create_run(api_client)
    run_id = created.data["data"]["run_id"]
    api_client.get(f"/api/v1/probe/runs/{run_id}/context")

    report = api_client.get(f"/api/v1/probe/runs/{run_id}/report")

    assert report.status_code == 200
    data = report.data["data"]
    assert data["run"]["status"] == "RUNNING"
    assert data["summary"]["total"] == 15
    assert data["summary"]["counts"]["NOT_TESTED"] > 0
    matrix = {item["capability_code"]: item for item in data["capabilities"]}
    assert matrix["P01_GET"]["status"] == "PASS_NATIVE"
    assert matrix["P01_POST"]["status"] == "PASS_NATIVE"
    assert matrix["P14"]["status"] == "PASS_NATIVE"
    assert matrix["P06"]["status"] == "NOT_TESTED"
    assert all(
        {"capability", "status", "evidence", "impact"} <= item.keys() for item in matrix.values()
    )


@pytest.mark.django_db
def test_missing_probe_run_uses_named_error(api_client):
    response = api_client.get("/api/v1/probe/runs/PRB-NOT-FOUND/report")

    assert response.status_code == 404
    assert response.data["code"] == "PROBE_RUN_NOT_FOUND"
    assert ProbeRun.objects.count() == 0
