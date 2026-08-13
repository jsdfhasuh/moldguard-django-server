import pytest

from apps.common.models import ClientRequestRecord
from apps.molds.models import Alert
from apps.workorders.models import MaintenanceRecord, WorkOrder
from tests.helpers import assigned_with_knowledge, normal_report_payload


@pytest.mark.django_db
def test_same_client_request_replays_with_current_request_id(api_client, seeded_demo):
    payload = {
        "client_request_id": "idempotent-scan-001",
        "mold_ids": ["DEMO-STAMP-PUNCH"],
    }
    first = api_client.post(
        "/api/v1/alerts/scan", payload, format="json", HTTP_X_REQUEST_ID="req-first"
    )
    second = api_client.post(
        "/api/v1/alerts/scan", payload, format="json", HTTP_X_REQUEST_ID="req-second"
    )
    assert first.data["data"]["replayed"] is False
    assert second.data["data"]["replayed"] is True
    assert second.data["request_id"] == "req-second"
    assert (
        first.data["data"]["results"][0]["work_order_id"]
        == second.data["data"]["results"][0]["work_order_id"]
    )
    assert Alert.objects.count() == WorkOrder.objects.count() == 1
    assert ClientRequestRecord.objects.count() == 1


@pytest.mark.django_db
def test_same_client_request_with_different_body_conflicts(api_client, seeded_demo):
    first = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "idempotent-conflict", "mold_ids": ["DEMO-STAMP-FORM"]},
        format="json",
    )
    conflict = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "idempotent-conflict", "mold_ids": ["DEMO-STAMP-PUNCH"]},
        format="json",
    )
    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.data["code"] == "CLIENT_REQUEST_CONFLICT"
    assert Alert.objects.count() == WorkOrder.objects.count() == 1


@pytest.mark.django_db
def test_repeated_normal_report_does_not_repeat_record_or_reset(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, _, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-COUNT-TIME",
        employee_id="DEMO-EMP-INJ",
        suffix="idempotent-report",
    )
    payload = normal_report_payload("idempotent-report", digest)
    first = api_client.post(f"/api/v1/work-orders/{work_order_id}/report", payload, format="json")
    version_after_first = WorkOrder.objects.get(pk=work_order_id).mold.cycle_version
    second = api_client.post(f"/api/v1/work-orders/{work_order_id}/report", payload, format="json")
    assert first.status_code == second.status_code == 200
    assert second.data["data"]["replayed"] is True
    assert MaintenanceRecord.objects.filter(work_order_id=work_order_id).count() == 1
    assert WorkOrder.objects.get(pk=work_order_id).mold.cycle_version == version_after_first
