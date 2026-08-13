import pytest

from apps.molds.models import Alert, Mold
from apps.workorders.models import MaintenanceRecord, WorkOrder, WorkOrderEvent
from tests.helpers import (
    abnormal_report_payload,
    assign_work_order,
    assigned_with_knowledge,
    normal_report_payload,
    save_knowledge,
)


def create_and_complete_repair(
    api_client, knowledge_payload, parent_id, parent_hash, *, suffix="repair-api"
):
    abnormal = api_client.post(
        f"/api/v1/work-orders/{parent_id}/report",
        abnormal_report_payload(suffix, parent_hash, next_action="CREATE_REPAIR_TASK"),
        format="json",
    )
    assert abnormal.status_code == 200
    linked = api_client.post(
        f"/api/v1/work-orders/{parent_id}/create-repair-task",
        {"client_request_id": f"{suffix}-create", "remarks": "需拆模维修冷却水路"},
        format="json",
    )
    assert linked.status_code == 200
    repair_id = linked.data["data"]["repair_work_order_id"]
    assign_work_order(api_client, repair_id, "DEMO-EMP-INJ", f"{suffix}-child")
    child_knowledge = save_knowledge(api_client, repair_id, knowledge_payload, f"{suffix}-child")
    child_report = api_client.post(
        f"/api/v1/work-orders/{repair_id}/report",
        normal_report_payload(f"{suffix}-child", child_knowledge["knowledge_package_hash"]),
        format="json",
    )
    assert child_report.status_code == 200
    return repair_id, linked, child_report


@pytest.mark.django_db
def test_repair_task_links_completes_without_reset_and_restores_parent(
    api_client, seeded_demo, knowledge_payload
):
    parent_id, alert_id, parent_hash = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="repair-api",
    )
    mold_before = Mold.objects.get(pk="DEMO-INJ-050K")
    cycle_before = mold_before.cycle_version
    baseline_before = mold_before.baseline_effective_mold_cycles
    repair_id, linked, child_report = create_and_complete_repair(
        api_client, knowledge_payload, parent_id, parent_hash
    )

    parent = WorkOrder.objects.get(pk=parent_id)
    repair = WorkOrder.objects.get(pk=repair_id)
    assert repair.work_order_type == WorkOrder.Type.REPAIR_TASK
    assert repair.parent_work_order_id == parent_id
    assert repair.alert_id is None
    assert repair.reset_count_cycle is False
    assert repair.reset_time_cycle is False
    assert repair.status == WorkOrder.Status.COMPLETED
    assert parent.linked_repair_order_id == repair_id
    assert parent.status == WorkOrder.Status.IN_PROGRESS
    assert parent.assignee_id == "DEMO-EMP-INJ"
    assert child_report.data["data"]["parent_work_order_status"] == WorkOrder.Status.IN_PROGRESS
    mold_mid = Mold.objects.get(pk="DEMO-INJ-050K")
    assert mold_mid.cycle_version == cycle_before
    assert mold_mid.baseline_effective_mold_cycles == baseline_before
    child_record = MaintenanceRecord.objects.get(work_order_id=repair_id)
    assert child_record.record_type == WorkOrder.Type.REPAIR_TASK
    assert child_record.reset_count_cycle is False
    assert child_record.reset_time_cycle is False
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.OPEN
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=parent_id, event_type="REPAIR_COMPLETED"
        ).count()
        == 1
    )

    reused = api_client.post(
        f"/api/v1/work-orders/{parent_id}/create-repair-task",
        {"client_request_id": "repair-api-create-retry", "remarks": "重复创建"},
        format="json",
    )
    assert reused.status_code == 409
    assert WorkOrder.objects.filter(parent_work_order_id=parent_id).count() == 1

    final = api_client.post(
        f"/api/v1/work-orders/{parent_id}/report",
        normal_report_payload("repair-api-parent-final", parent_hash),
        format="json",
    )
    assert final.status_code == 200
    mold_after = Mold.objects.get(pk="DEMO-INJ-050K")
    assert mold_after.cycle_version == cycle_before + 1
    assert MaintenanceRecord.objects.filter(work_order_id=parent_id).count() == 1
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.CLOSED


@pytest.mark.django_db
def test_create_repair_reuses_open_child_and_compat_completion_has_no_duplicate_events(
    api_client, seeded_demo, knowledge_payload
):
    parent_id, _, parent_hash = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="repair-reuse",
    )
    api_client.post(
        f"/api/v1/work-orders/{parent_id}/report",
        abnormal_report_payload("repair-reuse", parent_hash, next_action="CREATE_REPAIR_TASK"),
        format="json",
    )
    first = api_client.post(
        f"/api/v1/work-orders/{parent_id}/create-repair-task",
        {"client_request_id": "repair-reuse-first", "remarks": "需要修模"},
        format="json",
    )
    second = api_client.post(
        f"/api/v1/work-orders/{parent_id}/create-repair-task",
        {"client_request_id": "repair-reuse-second", "remarks": "复用开放子单"},
        format="json",
    )
    repair_id = first.data["data"]["repair_work_order_id"]
    assert second.status_code == 200
    assert second.data["data"]["repair_work_order_id"] == repair_id
    assert second.data["data"]["reused_repair_task"] is True
    assert WorkOrder.objects.filter(parent_work_order_id=parent_id).count() == 1
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=parent_id, event_type="REPAIR_TASK_LINKED"
        ).count()
        == 1
    )

    assign_work_order(api_client, repair_id, "DEMO-EMP-INJ", "repair-reuse-child")
    knowledge = save_knowledge(api_client, repair_id, knowledge_payload, "repair-reuse-child")
    api_client.post(
        f"/api/v1/work-orders/{repair_id}/report",
        normal_report_payload("repair-reuse-child", knowledge["knowledge_package_hash"]),
        format="json",
    )
    confirmed = api_client.post(
        f"/api/v1/work-orders/{repair_id}/repair-completed",
        {"client_request_id": "repair-reuse-confirm"},
        format="json",
    )
    replayed = api_client.post(
        f"/api/v1/work-orders/{repair_id}/repair-completed",
        {"client_request_id": "repair-reuse-confirm"},
        format="json",
    )
    assert confirmed.status_code == replayed.status_code == 200
    assert confirmed.data["data"]["already_completed"] is True
    assert replayed.data["data"]["replayed"] is True
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=parent_id, event_type="REPAIR_COMPLETED"
        ).count()
        == 1
    )
    assert MaintenanceRecord.objects.filter(work_order_id=repair_id).count() == 1
