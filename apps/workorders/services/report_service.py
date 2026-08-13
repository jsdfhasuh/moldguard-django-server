from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.common.identifiers import new_identifier
from apps.molds.models import Alert, Mold
from apps.workorders.models import MaintenanceRecord, WorkOrder, WorkOrderEvent


def _validate_common(work_order, payload):
    if not work_order.assignee_id:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "工单尚未派工", status_code=409)
    if not work_order.knowledge_package_hash or not work_order.knowledge_package_json:
        raise BusinessError("KNOWLEDGE_PACKAGE_REQUIRED", "工单尚未保存知识包", status_code=409)
    if payload["knowledge_package_hash"] != work_order.knowledge_package_hash:
        raise BusinessError(
            "KNOWLEDGE_PACKAGE_HASH_MISMATCH",
            "报工知识包哈希与工单不一致",
            status_code=409,
        )
    if work_order.status == WorkOrder.Status.COMPLETED:
        raise BusinessError("REPORT_ALREADY_SUBMITTED", "工单已经完成报工", status_code=409)

    known_items = {
        item["knowledge_id"]: item for item in work_order.knowledge_package_json.get("items", [])
    }
    results = payload["inspection_results"]
    submitted_ids = [item["knowledge_id"] for item in results]
    if len(submitted_ids) != len(set(submitted_ids)):
        raise BusinessError("VALIDATION_ERROR", "点检knowledge_id不允许重复")
    unknown = sorted(set(submitted_ids) - set(known_items))
    if unknown:
        raise BusinessError(
            "VALIDATION_ERROR",
            "点检项不属于当前知识包",
            errors={"unknown_knowledge_ids": unknown},
        )
    for result in results:
        if (
            result["result"] == "NOT_APPLICABLE"
            and not result.get("not_applicable_reason", "").strip()
        ):
            raise BusinessError(
                "NOT_APPLICABLE_REASON_REQUIRED",
                "NOT_APPLICABLE点检项必须填写原因",
            )
        if result["result"] == "FAIL" and not result.get("abnormal_note", "").strip():
            raise BusinessError("ABNORMAL_DESCRIPTION_REQUIRED", "FAIL点检项必须填写异常说明")
    return known_items


def _validate_normal(work_order, payload, known_items):
    if work_order.status not in {WorkOrder.Status.ASSIGNED, WorkOrder.Status.IN_PROGRESS}:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "当前工单状态不可正常报工", status_code=409)
    required_ids = {
        knowledge_id for knowledge_id, item in known_items.items() if item.get("required", False)
    }
    submitted_ids = {item["knowledge_id"] for item in payload["inspection_results"]}
    missing = sorted(required_ids - submitted_ids)
    if missing:
        raise BusinessError(
            "INSPECTION_ITEMS_INCOMPLETE",
            "必检项未全部提交",
            errors={"missing_knowledge_ids": missing},
        )
    if any(item["result"] == "FAIL" for item in payload["inspection_results"]):
        raise BusinessError("VALIDATION_ERROR", "NORMAL报工不允许包含FAIL点检项")
    if payload.get("abnormal_items"):
        raise BusinessError("VALIDATION_ERROR", "NORMAL报工的abnormal_items必须为空")
    if payload.get("abnormal_next_action"):
        raise BusinessError("VALIDATION_ERROR", "NORMAL报工不得提交abnormal_next_action")


def _validate_abnormal(work_order, payload):
    if work_order.status not in {
        WorkOrder.Status.ASSIGNED,
        WorkOrder.Status.IN_PROGRESS,
        WorkOrder.Status.PAUSED,
    }:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "当前工单状态不可异常报工", status_code=409)
    has_fail = any(item["result"] == "FAIL" for item in payload["inspection_results"])
    abnormal_items = payload.get("abnormal_items", [])
    has_described_item = any(
        item.get("item", "").strip() and item.get("description", "").strip()
        for item in abnormal_items
    )
    if not has_fail and not has_described_item:
        raise BusinessError(
            "ABNORMAL_DESCRIPTION_REQUIRED",
            "ABNORMAL报工必须包含FAIL点检项或abnormal_items",
        )


def _next_due(mold, reported_at):
    if mold.mold_type == Mold.Type.INJECTION:
        threshold = 50_000 if mold.development_tonnage < 1000 else 30_000
        return mold.effective_mold_cycles + threshold, reported_at + relativedelta(months=2)
    threshold_by_category = {
        Mold.Category.FORMING: 150_000,
        Mold.Category.PUNCH_BLANKING: 400_000,
        Mold.Category.CONTINUOUS: 400_000,
        Mold.Category.SIDE_PANEL: 400_000,
    }
    threshold = threshold_by_category.get(mold.mold_category)
    next_count = mold.effective_mold_cycles + threshold if threshold is not None else None
    return next_count, None


def _save_report_fields(work_order, payload, now):
    work_order.report_type = payload["report_type"]
    work_order.report_summary = payload["report_summary"]
    work_order.inspection_results_json = payload["inspection_results"]
    work_order.abnormal_items_json = payload.get("abnormal_items", [])
    work_order.photos_json = payload.get("photos", [])
    work_order.parts_replaced_json = payload.get("parts_replaced", [])
    work_order.source_fault_id = payload.get("source_fault_id") or ""
    work_order.actual_work_hours = payload["actual_work_hours"]
    work_order.abnormal_next_action = payload.get("abnormal_next_action") or ""
    work_order.reported_at = now


@transaction.atomic
def submit_report(work_order_id, payload, *, client_request_id):
    try:
        work_order = (
            WorkOrder.objects.select_for_update()
            .select_related("assignee", "mold", "alert")
            .get(pk=work_order_id)
        )
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None
    mold = Mold.objects.select_for_update().get(pk=work_order.mold_id)
    alert = None
    if work_order.alert_id:
        alert = Alert.objects.select_for_update().get(pk=work_order.alert_id)
    parent_work_order = None
    if work_order.parent_work_order_id:
        parent_work_order = (
            WorkOrder.objects.select_for_update()
            .select_related("assignee", "alert")
            .get(pk=work_order.parent_work_order_id)
        )
    known_items = _validate_common(work_order, payload)
    old_status = work_order.status
    now = timezone.now()
    _save_report_fields(work_order, payload, now)

    if payload["report_type"] == "ABNORMAL":
        _validate_abnormal(work_order, payload)
        work_order.status = WorkOrder.Status.ABNORMAL_REPORTED
        if work_order.pause_started_at:
            work_order.paused_seconds += max(
                0, int((now - work_order.pause_started_at).total_seconds())
            )
            work_order.pause_started_at = None
        work_order.save()
        WorkOrderEvent.objects.create(
            event_id=new_identifier("EVT"),
            work_order=work_order,
            event_type="ABNORMAL_REPORT_SUBMITTED",
            from_status=old_status,
            to_status=work_order.status,
            operator_id=work_order.assignee_id,
            event_data_json={
                "report_summary": work_order.report_summary,
                "inspection_results": work_order.inspection_results_json,
                "abnormal_items": work_order.abnormal_items_json,
                "abnormal_next_action": work_order.abnormal_next_action,
                "actual_work_hours": str(work_order.actual_work_hours),
                "knowledge_package_hash": work_order.knowledge_package_hash,
            },
            request_key=f"report:{client_request_id}",
            occurred_at=now,
        )
        return _report_result(work_order, old_status, None, None)

    _validate_normal(work_order, payload, known_items)
    baseline_count_before = mold.baseline_effective_mold_cycles
    baseline_time_before = mold.baseline_maintenance_at
    if work_order.reset_count_cycle:
        mold.baseline_effective_mold_cycles = mold.effective_mold_cycles
    if work_order.reset_time_cycle:
        mold.baseline_maintenance_at = now
    if work_order.reset_count_cycle or work_order.reset_time_cycle:
        mold.cycle_version += 1
    mold.save()

    work_order.status = WorkOrder.Status.COMPLETED
    work_order.completed_at = now
    work_order.abnormal_items_json = []
    work_order.abnormal_next_action = ""
    work_order.save()
    if alert is not None:
        alert.status = Alert.Status.CLOSED
        alert.closed_at = now
        alert.save(update_fields=["status", "closed_at", "updated_at"])
    MaintenanceRecord.objects.create(
        record_id=new_identifier("REC"),
        mold=mold,
        work_order=work_order,
        record_type=work_order.work_order_type,
        occurred_at=now,
        effective_mold_cycles_snapshot=mold.effective_mold_cycles,
        baseline_count_before=baseline_count_before,
        baseline_time_before=baseline_time_before,
        baseline_count_after=mold.baseline_effective_mold_cycles,
        baseline_time_after=mold.baseline_maintenance_at,
        reset_count_cycle=work_order.reset_count_cycle,
        reset_time_cycle=work_order.reset_time_cycle,
        knowledge_snapshot_version=work_order.knowledge_snapshot_version,
        knowledge_package_hash=work_order.knowledge_package_hash,
        standard_hours=work_order.standard_hours,
        actual_work_hours=work_order.actual_work_hours,
        result="NORMAL",
        note=work_order.report_summary,
        request_key=f"report:{client_request_id}",
    )
    WorkOrderEvent.objects.create(
        event_id=new_identifier("EVT"),
        work_order=work_order,
        event_type="NORMAL_REPORT_COMPLETED",
        from_status=old_status,
        to_status=work_order.status,
        operator_id=work_order.assignee_id,
        event_data_json={
            "effective_mold_cycles_snapshot": mold.effective_mold_cycles,
            "baseline_count_before": baseline_count_before,
            "baseline_count_after": mold.baseline_effective_mold_cycles,
            "baseline_time_before": baseline_time_before.isoformat(),
            "baseline_time_after": mold.baseline_maintenance_at.isoformat(),
            "cycle_version_after": mold.cycle_version,
            "knowledge_package_hash": work_order.knowledge_package_hash,
        },
        request_key=f"report-event:{client_request_id}",
        occurred_at=now,
    )
    if work_order.work_order_type == WorkOrder.Type.REPAIR_TASK:
        if parent_work_order is None:
            raise BusinessError(
                "INVALID_REPAIR_RELATION", "修模任务缺少原保养工单", status_code=409
            )
        if parent_work_order.status != WorkOrder.Status.REPAIR_LINKED:
            raise BusinessError(
                "INVALID_WORK_ORDER_STATE",
                "原保养工单不在等待修模完成状态",
                status_code=409,
            )
        parent_old_status = parent_work_order.status
        parent_work_order.status = WorkOrder.Status.IN_PROGRESS
        parent_work_order.abnormal_next_action = ""
        parent_work_order.save(update_fields=["status", "abnormal_next_action", "updated_at"])
        WorkOrderEvent.objects.create(
            event_id=new_identifier("EVT"),
            work_order=parent_work_order,
            event_type="REPAIR_COMPLETED",
            from_status=parent_old_status,
            to_status=parent_work_order.status,
            operator_id=parent_work_order.assignee_id or "",
            event_data_json={
                "repair_work_order_id": work_order.work_order_id,
                "repair_record_id": MaintenanceRecord.objects.get(work_order=work_order).record_id,
                "cycle_reset": False,
            },
            request_key=f"repair-completed:{client_request_id}",
            occurred_at=now,
        )
    next_due_count, next_due_time = _next_due(mold, now)
    result = _report_result(work_order, old_status, next_due_count, next_due_time)
    if parent_work_order is not None:
        result["parent_work_order_id"] = parent_work_order.work_order_id
        result["parent_work_order_status"] = parent_work_order.status
    return result


def _report_result(work_order, old_status, next_due_count, next_due_time):
    return {
        "work_order_id": work_order.work_order_id,
        "old_status": old_status,
        "new_status": work_order.status,
        "report_type": work_order.report_type,
        "reported_at": work_order.reported_at.isoformat(),
        "assignee_id": work_order.assignee_id,
        "assignee_name": work_order.assignee.employee_name,
        "actual_work_hours": str(work_order.actual_work_hours),
        "knowledge_snapshot_version": work_order.knowledge_snapshot_version,
        "knowledge_package_hash": work_order.knowledge_package_hash,
        "reset_count_cycle": work_order.reset_count_cycle
        if work_order.status == WorkOrder.Status.COMPLETED
        else False,
        "reset_time_cycle": work_order.reset_time_cycle
        if work_order.status == WorkOrder.Status.COMPLETED
        else False,
        "next_due_count": next_due_count,
        "next_due_time": next_due_time.isoformat() if next_due_time else None,
    }
