from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.common.identifiers import new_identifier
from apps.workorders.models import WorkOrder, WorkOrderEvent


def _locked_work_order(work_order_id):
    try:
        return (
            WorkOrder.objects.select_for_update()
            .select_related("assignee", "mold", "alert")
            .get(pk=work_order_id)
        )
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None


def _event(
    work_order,
    event_type,
    old_status,
    new_status,
    *,
    client_request_id,
    remarks="",
    event_data=None,
):
    WorkOrderEvent.objects.create(
        event_id=new_identifier("EVT"),
        work_order=work_order,
        event_type=event_type,
        from_status=old_status,
        to_status=new_status,
        operator_id=work_order.assignee_id or "",
        remarks=remarks,
        event_data_json=event_data or {},
        request_key=f"{event_type.lower()}:{client_request_id}",
        occurred_at=timezone.now(),
    )


def _result(work_order, old_status):
    return {
        "work_order_id": work_order.work_order_id,
        "old_status": old_status,
        "new_status": work_order.status,
        "started_at": work_order.started_at.isoformat() if work_order.started_at else None,
        "pause_started_at": (
            work_order.pause_started_at.isoformat() if work_order.pause_started_at else None
        ),
        "paused_seconds": work_order.paused_seconds,
        "assignee_id": work_order.assignee_id,
    }


@transaction.atomic
def start_work_order(work_order_id, *, client_request_id):
    work_order = _locked_work_order(work_order_id)
    if not work_order.assignee_id or work_order.status != WorkOrder.Status.ASSIGNED:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "当前工单状态不可开工", status_code=409)
    if work_order.started_at is not None:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "工单已经开工", status_code=409)
    old_status = work_order.status
    now = timezone.now()
    work_order.status = WorkOrder.Status.IN_PROGRESS
    work_order.started_at = now
    work_order.save(update_fields=["status", "started_at", "updated_at"])
    _event(
        work_order,
        "WORK_ORDER_STARTED",
        old_status,
        work_order.status,
        client_request_id=client_request_id,
        event_data={"started_at": now.isoformat()},
    )
    return _result(work_order, old_status)


@transaction.atomic
def pause_work_order(work_order_id, *, client_request_id, reason=""):
    work_order = _locked_work_order(work_order_id)
    if work_order.status != WorkOrder.Status.IN_PROGRESS:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "当前工单状态不可暂停", status_code=409)
    old_status = work_order.status
    now = timezone.now()
    work_order.status = WorkOrder.Status.PAUSED
    work_order.pause_started_at = now
    work_order.save(update_fields=["status", "pause_started_at", "updated_at"])
    _event(
        work_order,
        "WORK_ORDER_PAUSED",
        old_status,
        work_order.status,
        client_request_id=client_request_id,
        remarks=reason,
        event_data={"pause_started_at": now.isoformat(), "reason": reason},
    )
    return _result(work_order, old_status)


@transaction.atomic
def resume_work_order(work_order_id, *, client_request_id):
    work_order = _locked_work_order(work_order_id)
    if work_order.status != WorkOrder.Status.PAUSED or work_order.pause_started_at is None:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "当前工单状态不可恢复", status_code=409)
    now = timezone.now()
    if now <= work_order.pause_started_at:
        raise BusinessError(
            "INVALID_PAUSE_INTERVAL", "恢复时间必须晚于暂停开始时间", status_code=409
        )
    old_status = work_order.status
    interval_seconds = int((now - work_order.pause_started_at).total_seconds())
    work_order.paused_seconds += interval_seconds
    work_order.pause_started_at = None
    work_order.status = WorkOrder.Status.IN_PROGRESS
    work_order.save(update_fields=["paused_seconds", "pause_started_at", "status", "updated_at"])
    _event(
        work_order,
        "WORK_ORDER_RESUMED",
        old_status,
        work_order.status,
        client_request_id=client_request_id,
        event_data={
            "pause_interval_seconds": interval_seconds,
            "paused_seconds_total": work_order.paused_seconds,
            "resumed_at": now.isoformat(),
        },
    )
    return _result(work_order, old_status)


@transaction.atomic
def continue_processing(work_order_id, *, client_request_id, remarks=""):
    work_order = _locked_work_order(work_order_id)
    if work_order.status != WorkOrder.Status.ABNORMAL_REPORTED:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "当前工单状态不可继续处理", status_code=409)
    old_status = work_order.status
    abnormal_snapshot = {
        "report_type": work_order.report_type,
        "report_summary": work_order.report_summary,
        "inspection_results": work_order.inspection_results_json,
        "abnormal_items": work_order.abnormal_items_json,
        "photos": work_order.photos_json,
        "parts_replaced": work_order.parts_replaced_json,
        "source_fault_id": work_order.source_fault_id,
        "actual_work_hours": (
            str(work_order.actual_work_hours) if work_order.actual_work_hours is not None else None
        ),
        "abnormal_next_action": work_order.abnormal_next_action,
        "reported_at": work_order.reported_at.isoformat() if work_order.reported_at else None,
    }
    work_order.status = WorkOrder.Status.IN_PROGRESS
    work_order.abnormal_next_action = ""
    work_order.save(update_fields=["status", "abnormal_next_action", "updated_at"])
    _event(
        work_order,
        "ABNORMAL_PROCESSING_CONTINUED",
        old_status,
        work_order.status,
        client_request_id=client_request_id,
        remarks=remarks,
        event_data={"abnormal_snapshot": abnormal_snapshot, "remarks": remarks},
    )
    return {
        **_result(work_order, old_status),
        "abnormal_next_action": None,
        "alert_status": work_order.alert.status if work_order.alert_id else None,
        "abnormal_history_preserved": True,
    }
