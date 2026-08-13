import pytest

from apps.molds.models import Alert, Mold
from apps.workorders.models import MaintenanceRecord, WorkOrder, WorkOrderEvent
from tests.helpers import abnormal_report_payload, assigned_with_knowledge, normal_report_payload


@pytest.mark.django_db
def test_abnormal_continue_then_normal_preserves_history_and_resets_once(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, alert_id, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="continue-flow",
    )
    mold_before = Mold.objects.get(pk="DEMO-INJ-050K")
    version_before = mold_before.cycle_version
    baseline_before = mold_before.baseline_effective_mold_cycles
    abnormal = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report",
        abnormal_report_payload("continue-flow", digest),
        format="json",
    )
    assert abnormal.status_code == 200

    continued = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/continue-processing",
        {"client_request_id": "continue-flow-action", "remarks": "已疏通水路，重新点检"},
        format="json",
    )
    assert continued.status_code == 200
    assert continued.data["data"]["new_status"] == WorkOrder.Status.IN_PROGRESS
    assert continued.data["data"]["abnormal_history_preserved"] is True
    replay = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/continue-processing",
        {"client_request_id": "continue-flow-action", "remarks": "已疏通水路，重新点检"},
        format="json",
    )
    assert replay.data["data"]["replayed"] is True

    order = WorkOrder.objects.get(pk=work_order_id)
    assert order.assignee_id == "DEMO-EMP-INJ"
    assert order.abnormal_next_action == ""
    assert order.abnormal_items_json[0]["item"] == "冷却水路"
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.OPEN
    mold_mid = Mold.objects.get(pk="DEMO-INJ-050K")
    assert mold_mid.cycle_version == version_before
    assert mold_mid.baseline_effective_mold_cycles == baseline_before
    assert not MaintenanceRecord.objects.filter(work_order_id=work_order_id).exists()

    continue_event = WorkOrderEvent.objects.get(
        work_order_id=work_order_id, event_type="ABNORMAL_PROCESSING_CONTINUED"
    )
    snapshot = continue_event.event_data_json["abnormal_snapshot"]
    assert snapshot["abnormal_items"][0]["description"] == "水路堵塞，需要后续处理"
    assert snapshot["inspection_results"][1]["result"] == "FAIL"

    completed = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report",
        normal_report_payload("continue-flow-final", digest),
        format="json",
    )
    assert completed.status_code == 200
    assert completed.data["data"]["new_status"] == WorkOrder.Status.COMPLETED
    mold_after = Mold.objects.get(pk="DEMO-INJ-050K")
    assert mold_after.cycle_version == version_before + 1
    assert MaintenanceRecord.objects.filter(work_order_id=work_order_id).count() == 1
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.CLOSED
