import pytest

from apps.molds.models import Alert, Mold
from apps.workorders.models import MaintenanceRecord, WorkOrder
from tests.helpers import assigned_with_knowledge, normal_report_payload


@pytest.mark.django_db
def test_complete_abnormal_p0_workflow_preserves_cycle_and_alert(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, alert_id, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="integration-abnormal",
    )
    mold_before = Mold.objects.get(pk="DEMO-INJ-050K")
    baseline_count = mold_before.baseline_effective_mold_cycles
    baseline_time = mold_before.baseline_maintenance_at
    cycle_version = mold_before.cycle_version
    payload = normal_report_payload("integration-abnormal", digest)
    payload.update(
        {
            "report_type": "ABNORMAL",
            "report_summary": "发现冷却水路堵塞，常规保养无法处理",
            "abnormal_items": [{"item": "冷却水路", "description": "水路堵塞，需继续处理"}],
            "abnormal_next_action": "CONTINUE_PROCESSING",
            "actual_work_hours": "1.50",
        }
    )
    payload["inspection_results"][1].update({"result": "FAIL", "abnormal_note": "水路不通"})
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report", payload, format="json"
    )
    assert response.status_code == 200
    assert response.data["data"]["new_status"] == "ABNORMAL_REPORTED"
    work_order = WorkOrder.objects.get(pk=work_order_id)
    assert work_order.abnormal_next_action == "CONTINUE_PROCESSING"
    assert work_order.abnormal_items_json[0]["item"] == "冷却水路"
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.OPEN
    assert MaintenanceRecord.objects.filter(work_order_id=work_order_id).count() == 0
    mold = Mold.objects.get(pk="DEMO-INJ-050K")
    assert mold.baseline_effective_mold_cycles == baseline_count
    assert mold.baseline_maintenance_at == baseline_time
    assert mold.cycle_version == cycle_version
    timeline = api_client.get(f"/api/v1/work-orders/{work_order_id}/timeline")
    assert timeline.data["data"]["events"][-1]["event_type"] == ("ABNORMAL_REPORT_SUBMITTED")
