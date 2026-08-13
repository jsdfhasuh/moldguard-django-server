import pytest

from apps.molds.models import Alert, Mold
from apps.workorders.models import MaintenanceRecord, WorkOrder, WorkOrderEvent
from tests.api.test_repair_workflow import create_and_complete_repair
from tests.helpers import assigned_with_knowledge, normal_report_payload


@pytest.mark.django_db
def test_end_to_end_repair_workflow_resets_only_on_parent_final_normal(
    api_client, seeded_demo, knowledge_payload
):
    parent_id, alert_id, parent_hash = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-COUNT-TIME",
        employee_id="DEMO-EMP-INJ",
        suffix="repair-integration",
    )
    before = Mold.objects.get(pk="DEMO-INJ-COUNT-TIME")
    version_before = before.cycle_version
    baseline_before = before.baseline_effective_mold_cycles
    repair_id, _, _ = create_and_complete_repair(
        api_client,
        knowledge_payload,
        parent_id,
        parent_hash,
        suffix="repair-integration",
    )
    middle = Mold.objects.get(pk="DEMO-INJ-COUNT-TIME")
    assert middle.cycle_version == version_before
    assert middle.baseline_effective_mold_cycles == baseline_before
    assert WorkOrder.objects.get(pk=parent_id).status == WorkOrder.Status.IN_PROGRESS
    assert WorkOrder.objects.get(pk=repair_id).status == WorkOrder.Status.COMPLETED
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.OPEN

    payload = normal_report_payload("repair-integration-parent", parent_hash)
    first = api_client.post(f"/api/v1/work-orders/{parent_id}/report", payload, format="json")
    second = api_client.post(f"/api/v1/work-orders/{parent_id}/report", payload, format="json")
    assert first.status_code == second.status_code == 200
    assert second.data["data"]["replayed"] is True
    after = Mold.objects.get(pk="DEMO-INJ-COUNT-TIME")
    assert after.cycle_version == version_before + 1
    assert after.baseline_effective_mold_cycles == after.effective_mold_cycles
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.CLOSED
    assert MaintenanceRecord.objects.filter(work_order_id__in=[parent_id, repair_id]).count() == 2
    assert MaintenanceRecord.objects.get(work_order_id=repair_id).reset_count_cycle is False
    assert MaintenanceRecord.objects.get(work_order_id=parent_id).reset_count_cycle is True
    parent_events = list(
        WorkOrderEvent.objects.filter(work_order_id=parent_id)
        .order_by("occurred_at", "event_id")
        .values_list("event_type", flat=True)
    )
    assert parent_events.count("REPAIR_TASK_LINKED") == 1
    assert parent_events.count("REPAIR_COMPLETED") == 1
    assert parent_events.count("NORMAL_REPORT_COMPLETED") == 1
