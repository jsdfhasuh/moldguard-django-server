from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.common.identifiers import new_identifier
from apps.workorders.models import WorkOrder, WorkOrderEvent


def _repair_result(parent, repair, *, reused):
    return {
        "work_order_id": parent.work_order_id,
        "work_order_status": parent.status,
        "repair_work_order_id": repair.work_order_id,
        "repair_work_order_status": repair.status,
        "reused_repair_task": reused,
    }


@transaction.atomic
def create_repair_task(work_order_id, *, client_request_id, remarks=""):
    try:
        parent = (
            WorkOrder.objects.select_for_update()
            .select_related("mold", "assignee", "linked_repair_order")
            .get(pk=work_order_id)
        )
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None

    linked = parent.linked_repair_order
    if linked and linked.status not in {WorkOrder.Status.COMPLETED, WorkOrder.Status.CANCELLED}:
        return _repair_result(parent, linked, reused=True)
    if parent.status != WorkOrder.Status.ABNORMAL_REPORTED:
        raise BusinessError(
            "INVALID_WORK_ORDER_STATE", "当前工单状态不可创建修模任务", status_code=409
        )

    now = timezone.now()
    abnormal_key = parent.reported_at.isoformat() if parent.reported_at else now.isoformat()
    create_key = f"REPAIR_TASK:{parent.work_order_id}:{abnormal_key}"
    repair = WorkOrder.objects.create(
        work_order_id=new_identifier("WO"),
        alert=None,
        mold=parent.mold,
        parent_work_order=parent,
        primary_rule_id="REPAIR_TASK",
        matched_rule_ids_json=[],
        work_order_type=WorkOrder.Type.REPAIR_TASK,
        status=WorkOrder.Status.PENDING_ASSIGNMENT,
        standard_hours=parent.standard_repair_hours,
        required_finish_at=None,
        create_key=create_key,
        effective_mold_cycles_snapshot=parent.mold.effective_mold_cycles,
        baseline_effective_mold_cycles_before=parent.mold.baseline_effective_mold_cycles,
        baseline_maintenance_at_before=parent.mold.baseline_maintenance_at,
        cycle_mold_cycles_snapshot=parent.mold.cycle_mold_cycles,
        threshold_count=None,
        trigger_reason=remarks or parent.report_summary or "异常报工创建关联修模任务",
        triggered_at=now,
        reset_count_cycle=False,
        reset_time_cycle=False,
        repair_reason=remarks or parent.report_summary,
    )
    old_status = parent.status
    parent.linked_repair_order = repair
    parent.status = WorkOrder.Status.REPAIR_LINKED
    parent.abnormal_next_action = WorkOrder.AbnormalNextAction.CREATE_REPAIR_TASK
    parent.save(
        update_fields=["linked_repair_order", "status", "abnormal_next_action", "updated_at"]
    )
    WorkOrderEvent.objects.create(
        event_id=new_identifier("EVT"),
        work_order=parent,
        event_type="REPAIR_TASK_LINKED",
        from_status=old_status,
        to_status=parent.status,
        operator_id=parent.assignee_id or "",
        remarks=remarks,
        event_data_json={
            "repair_work_order_id": repair.work_order_id,
            "abnormal_reported_at": (
                parent.reported_at.isoformat() if parent.reported_at else None
            ),
        },
        request_key=f"repair-link:{client_request_id}",
        occurred_at=now,
    )
    WorkOrderEvent.objects.create(
        event_id=new_identifier("EVT"),
        work_order=repair,
        event_type="REPAIR_TASK_CREATED",
        to_status=repair.status,
        event_data_json={"parent_work_order_id": parent.work_order_id},
        request_key=f"repair-create:{client_request_id}",
        occurred_at=now,
    )
    return _repair_result(parent, repair, reused=False)


def completed_repair_result(repair):
    if repair.work_order_type != WorkOrder.Type.REPAIR_TASK:
        raise BusinessError("INVALID_WORK_ORDER_TYPE", "目标工单不是修模任务", status_code=409)
    if repair.status != WorkOrder.Status.COMPLETED:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "修模任务尚未正常报工完成", status_code=409)
    parent = repair.parent_work_order
    return {
        "repair_work_order_id": repair.work_order_id,
        "repair_work_order_status": repair.status,
        "parent_work_order_id": parent.work_order_id if parent else None,
        "parent_work_order_status": parent.status if parent else None,
        "already_completed": True,
    }
