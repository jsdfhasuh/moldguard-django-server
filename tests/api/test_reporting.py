import pytest

from apps.molds.models import Alert, Mold
from apps.workorders.models import MaintenanceRecord, WorkOrder
from tests.helpers import (
    assigned_with_knowledge,
    normal_report_payload,
)


@pytest.mark.django_db
def test_assigned_work_order_can_submit_normal_report_directly(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, alert_id, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-COUNT-TIME",
        employee_id="DEMO-EMP-INJ",
        suffix="normal-direct",
    )
    mold_before = Mold.objects.get(pk="DEMO-INJ-COUNT-TIME")
    version_before = mold_before.cycle_version
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report",
        normal_report_payload("normal-direct", digest),
        format="json",
    )
    assert response.status_code == 200
    assert response.data["data"]["old_status"] == "ASSIGNED"
    assert response.data["data"]["new_status"] == "COMPLETED"
    mold = Mold.objects.get(pk="DEMO-INJ-COUNT-TIME")
    assert mold.baseline_effective_mold_cycles == mold.effective_mold_cycles
    assert mold.cycle_version == version_before + 1
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.CLOSED
    assert MaintenanceRecord.objects.filter(work_order_id=work_order_id).count() == 1


@pytest.mark.django_db
def test_fail_cannot_be_submitted_as_normal(api_client, seeded_demo, knowledge_payload):
    work_order_id, alert_id, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="normal-fail",
    )
    payload = normal_report_payload("normal-fail", digest)
    payload["inspection_results"][0]["result"] = "FAIL"
    payload["inspection_results"][0]["abnormal_note"] = "发现异常"
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report", payload, format="json"
    )
    assert response.status_code == 400
    assert WorkOrder.objects.get(pk=work_order_id).status == WorkOrder.Status.ASSIGNED
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.OPEN
    assert not MaintenanceRecord.objects.exists()


@pytest.mark.django_db
def test_not_applicable_requires_reason(api_client, seeded_demo, knowledge_payload):
    work_order_id, _, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="normal-na",
    )
    payload = normal_report_payload("normal-na", digest)
    payload["inspection_results"][0]["result"] = "NOT_APPLICABLE"
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report", payload, format="json"
    )
    assert response.status_code == 400
    assert response.data["code"] == "NOT_APPLICABLE_REASON_REQUIRED"


@pytest.mark.django_db
def test_abnormal_report_keeps_alert_open_and_does_not_reset(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, alert_id, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="abnormal",
    )
    mold_before = Mold.objects.get(pk="DEMO-INJ-050K")
    baseline_before = mold_before.baseline_effective_mold_cycles
    version_before = mold_before.cycle_version
    payload = normal_report_payload("abnormal", digest)
    payload.update(
        {
            "report_type": "ABNORMAL",
            "report_summary": "发现冷却水路堵塞",
            "abnormal_items": [{"item": "冷却水路", "description": "水路堵塞，常规保养无法处理"}],
            "abnormal_next_action": "CONTINUE_PROCESSING",
        }
    )
    payload["inspection_results"][1].update({"result": "FAIL", "abnormal_note": "水路不通"})
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report", payload, format="json"
    )
    assert response.status_code == 200
    assert response.data["data"]["new_status"] == "ABNORMAL_REPORTED"
    mold = Mold.objects.get(pk="DEMO-INJ-050K")
    assert mold.baseline_effective_mold_cycles == baseline_before
    assert mold.cycle_version == version_before
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.OPEN
    assert MaintenanceRecord.objects.count() == 0
