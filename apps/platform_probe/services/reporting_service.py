import math

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.platform_probe.exceptions import ProbeAPIException
from apps.platform_probe.models import (
    AbnormalReport,
    Employee,
    MaintenanceAlert,
    MaintenanceHistory,
    Mold,
    PauseSegment,
    WorkOrder,
    WorkOrderEvent,
    WorkReport,
)

from .trigger_service import threshold_for_tonnage


def _locked_work_order(work_order_id):
    try:
        return (
            WorkOrder.objects.select_for_update()
            .select_related("mold", "alert", "assigned_employee")
            .get(work_order_id=work_order_id)
        )
    except WorkOrder.DoesNotExist as exc:
        raise ProbeAPIException("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from exc


def _validate_assignee(work_order, employee_id):
    if work_order.assigned_employee_id is None:
        raise ProbeAPIException("EMPLOYEE_NOT_ASSIGNED", "工单尚未派工", status_code=409)
    if not Employee.objects.filter(employee_id=employee_id).exists():
        raise ProbeAPIException("EMPLOYEE_NOT_FOUND", "员工不存在", status_code=404)
    if work_order.assigned_employee_id != employee_id:
        raise ProbeAPIException(
            "EMPLOYEE_NOT_ASSIGNED", "只有被派工人员可以执行此操作", status_code=403
        )


def _ensure_not_finished(work_order):
    if work_order.status == WorkOrder.Status.COMPLETED:
        raise ProbeAPIException("WORK_ORDER_ALREADY_COMPLETED", "工单已经完成", status_code=409)


def _release_employee_load(employee_id):
    Employee.objects.filter(employee_id=employee_id, current_load__gt=0).update(
        current_load=F("current_load") - 1,
        updated_at=timezone.now(),
    )


@transaction.atomic
def start_work_order(work_order_id, employee_id, occurred_at=None):
    occurred_at = occurred_at or timezone.now()
    work_order = _locked_work_order(work_order_id)
    _validate_assignee(work_order, employee_id)
    _ensure_not_finished(work_order)
    if work_order.status != WorkOrder.Status.ASSIGNED:
        raise ProbeAPIException(
            "INVALID_WORK_ORDER_STATE", "只有已派工工单可以开工", status_code=409
        )

    work_order.status = WorkOrder.Status.IN_PROGRESS
    work_order.started_at = occurred_at
    work_order.save(update_fields=["status", "started_at", "updated_at"])
    WorkOrderEvent.objects.create(
        work_order=work_order,
        event_type="WORK_ORDER_STARTED",
        event_data_json={"employee_id": employee_id},
        occurred_at=occurred_at,
    )
    return work_order


@transaction.atomic
def pause_work_order(work_order_id, employee_id, reason="", occurred_at=None):
    occurred_at = occurred_at or timezone.now()
    work_order = _locked_work_order(work_order_id)
    _validate_assignee(work_order, employee_id)
    _ensure_not_finished(work_order)
    if work_order.status != WorkOrder.Status.IN_PROGRESS:
        raise ProbeAPIException(
            "INVALID_WORK_ORDER_STATE", "只有进行中的工单可以暂停", status_code=409
        )
    if work_order.started_at and occurred_at < work_order.started_at:
        raise ProbeAPIException("INVALID_TIME_RANGE", "暂停时间不能早于开工时间")
    previous = work_order.pause_segments.select_for_update().order_by("-paused_at").first()
    if previous is not None and (previous.resumed_at is None or occurred_at < previous.resumed_at):
        raise ProbeAPIException("INVALID_TIME_RANGE", "暂停时间不能与已有暂停区间重叠")

    segment = PauseSegment.objects.create(
        work_order=work_order,
        paused_at=occurred_at,
        reason=reason,
    )
    work_order.status = WorkOrder.Status.PAUSED
    work_order.save(update_fields=["status", "updated_at"])
    WorkOrderEvent.objects.create(
        work_order=work_order,
        event_type="WORK_ORDER_PAUSED",
        event_data_json={
            "employee_id": employee_id,
            "reason": reason,
            "pause_id": segment.pause_id,
        },
        occurred_at=occurred_at,
    )
    return work_order


@transaction.atomic
def resume_work_order(work_order_id, employee_id, occurred_at=None):
    occurred_at = occurred_at or timezone.now()
    work_order = _locked_work_order(work_order_id)
    _validate_assignee(work_order, employee_id)
    _ensure_not_finished(work_order)
    if work_order.status != WorkOrder.Status.PAUSED:
        raise ProbeAPIException(
            "INVALID_WORK_ORDER_STATE", "只有暂停中的工单可以恢复", status_code=409
        )
    try:
        segment = work_order.pause_segments.select_for_update().get(resumed_at__isnull=True)
    except PauseSegment.DoesNotExist as exc:
        raise ProbeAPIException("INVALID_WORK_ORDER_STATE", "工单没有开放的暂停记录") from exc
    if occurred_at <= segment.paused_at:
        raise ProbeAPIException("INVALID_TIME_RANGE", "恢复时间必须晚于暂停时间")

    segment.resumed_at = occurred_at
    segment.save(update_fields=["resumed_at"])
    work_order.status = WorkOrder.Status.IN_PROGRESS
    work_order.save(update_fields=["status", "updated_at"])
    WorkOrderEvent.objects.create(
        work_order=work_order,
        event_type="WORK_ORDER_RESUMED",
        event_data_json={"employee_id": employee_id, "pause_id": segment.pause_id},
        occurred_at=occurred_at,
    )
    return work_order


def _validate_inspection_results(work_order, inspection_results):
    snapshot = work_order.knowledge_snapshots.first()
    if snapshot is None:
        raise ProbeAPIException(
            "KNOWLEDGE_SNAPSHOT_REQUIRED", "正常报工前必须回写知识快照", status_code=409
        )

    required_ids = {
        item["knowledge_id"] for item in snapshot.items_json if item.get("required", True)
    }
    submitted = {item["knowledge_id"]: item for item in inspection_results}
    missing = sorted(required_ids - submitted.keys())
    if missing:
        raise ProbeAPIException(
            "INSPECTION_ITEMS_INCOMPLETE",
            "存在未提交的必检项",
            errors=[{"missing_knowledge_ids": missing}],
        )

    if any(item["result"] == "FAIL" for item in inspection_results):
        raise ProbeAPIException(
            "INSPECTION_FAIL_REQUIRES_ABNORMAL_REPORT",
            "存在FAIL点检项，请使用异常报工接口",
        )
    missing_reasons = [
        item["knowledge_id"]
        for item in inspection_results
        if item["result"] == "NOT_APPLICABLE" and not item.get("reason", "").strip()
    ]
    if missing_reasons:
        raise ProbeAPIException(
            "NOT_APPLICABLE_REASON_REQUIRED",
            "NOT_APPLICABLE点检项必须填写原因",
            errors=[{"knowledge_ids": missing_reasons}],
        )


def _paused_seconds(work_order, started_at, completed_at):
    total = 0
    for segment in work_order.pause_segments.select_for_update().all():
        if segment.resumed_at is None:
            raise ProbeAPIException("INVALID_WORK_ORDER_STATE", "工单仍处于暂停状态，必须先恢复")
        overlap_start = max(segment.paused_at, started_at)
        overlap_end = min(segment.resumed_at, completed_at)
        if overlap_end > overlap_start:
            total += int((overlap_end - overlap_start).total_seconds())
    return total


@transaction.atomic
def complete_work_order(work_order_id, payload):
    work_order = _locked_work_order(work_order_id)
    _validate_assignee(work_order, payload["employee_id"])
    _ensure_not_finished(work_order)
    if work_order.status not in {WorkOrder.Status.ASSIGNED, WorkOrder.Status.IN_PROGRESS}:
        raise ProbeAPIException(
            "INVALID_WORK_ORDER_STATE", "工单当前状态不能正常报工", status_code=409
        )
    if hasattr(work_order, "work_report"):
        raise ProbeAPIException(
            "WORK_ORDER_ALREADY_COMPLETED", "工单已经存在报工记录", status_code=409
        )

    if work_order.started_at is None and "started_at" not in payload:
        raise ProbeAPIException("INVALID_TIME_RANGE", "一次性报工必须显式提供started_at")
    started_at = work_order.started_at or payload["started_at"]
    completed_at = payload["completed_at"]
    if completed_at <= started_at:
        raise ProbeAPIException("INVALID_TIME_RANGE", "completed_at必须晚于started_at")

    _validate_inspection_results(work_order, payload["inspection_results"])
    paused_seconds = _paused_seconds(work_order, started_at, completed_at)
    gross_seconds = int((completed_at - started_at).total_seconds())
    active_seconds = max(0, gross_seconds - paused_seconds)
    actual_minutes = math.floor(active_seconds / 60)

    mold = Mold.objects.select_for_update().get(mold_id=work_order.mold_id)
    alert = MaintenanceAlert.objects.select_for_update().get(alert_id=work_order.alert_id)
    version_before = mold.cycle_version
    report = WorkReport.objects.create(
        work_order=work_order,
        employee=work_order.assigned_employee,
        report_type=WorkReport.ReportType.COMPLETE,
        started_at=started_at,
        completed_at=completed_at,
        paused_seconds=paused_seconds,
        actual_minutes=actual_minutes,
        work_summary=payload["work_summary"],
        inspection_results_json=payload["inspection_results"],
        attachments_json=payload.get("attachments", []),
        cycle_reset=True,
        client_request_id=payload["client_request_id"],
    )

    work_order.status = WorkOrder.Status.COMPLETED
    work_order.started_at = started_at
    work_order.completed_at = completed_at
    work_order.save(update_fields=["status", "started_at", "completed_at", "updated_at"])

    mold.cycle_baseline_count = mold.current_count
    mold.cycle_baseline_time = completed_at
    mold.cycle_version = version_before + 1
    mold.last_reset_type = Mold.ResetType.MAINTENANCE_COMPLETED
    mold.last_reset_event_id = report.report_id
    mold.save(
        update_fields=[
            "cycle_baseline_count",
            "cycle_baseline_time",
            "cycle_version",
            "last_reset_type",
            "last_reset_event_id",
            "updated_at",
        ]
    )
    alert.status = MaintenanceAlert.Status.CLOSED
    alert.save(update_fields=["status", "updated_at"])
    _release_employee_load(work_order.assigned_employee_id)

    history = MaintenanceHistory.objects.create(
        mold=mold,
        work_order=work_order,
        event_type=MaintenanceHistory.EventType.MAINTENANCE_COMPLETED,
        count_snapshot=mold.current_count,
        occurred_at=completed_at,
        cycle_version_before=version_before,
        cycle_version_after=mold.cycle_version,
    )
    WorkOrderEvent.objects.create(
        work_order=work_order,
        event_type="WORK_ORDER_COMPLETED",
        event_data_json={
            "employee_id": payload["employee_id"],
            "report_id": report.report_id,
            "history_id": history.history_id,
            "cycle_reset": True,
        },
        occurred_at=completed_at,
    )
    threshold = threshold_for_tonnage(mold.development_tonnage)
    return {
        "work_order_id": work_order.work_order_id,
        "status": work_order.status,
        "report_id": report.report_id,
        "actual_minutes": actual_minutes,
        "paused_seconds": paused_seconds,
        "cycle_reset": {
            "performed": True,
            "baseline_count": mold.cycle_baseline_count,
            "baseline_time": timezone.localtime(mold.cycle_baseline_time).isoformat(),
            "cycle_version": mold.cycle_version,
            "next_threshold": threshold,
            "next_trigger_count": mold.cycle_baseline_count + threshold,
        },
    }


@transaction.atomic
def abnormal_work_order(work_order_id, payload):
    work_order = _locked_work_order(work_order_id)
    _validate_assignee(work_order, payload["employee_id"])
    _ensure_not_finished(work_order)
    if work_order.status not in {
        WorkOrder.Status.ASSIGNED,
        WorkOrder.Status.IN_PROGRESS,
        WorkOrder.Status.PAUSED,
    }:
        raise ProbeAPIException(
            "INVALID_WORK_ORDER_STATE", "工单当前状态不能异常报工", status_code=409
        )
    if not payload["abnormal_type"].strip() or not payload["description"].strip():
        raise ProbeAPIException("ABNORMAL_DESCRIPTION_REQUIRED", "异常类型和异常说明不能为空")
    failed_items = [item for item in payload["inspection_results"] if item["result"] == "FAIL"]
    if not failed_items:
        raise ProbeAPIException("INSPECTION_ITEMS_INCOMPLETE", "异常报工至少需要一个FAIL点检项")
    missing_notes = [
        item["knowledge_id"] for item in failed_items if not item.get("note", "").strip()
    ]
    if missing_notes:
        raise ProbeAPIException(
            "INSPECTION_ITEMS_INCOMPLETE",
            "FAIL点检项必须填写note",
            errors=[{"knowledge_ids": missing_notes}],
        )

    now = timezone.now()
    started_at = work_order.started_at or payload.get("started_at") or work_order.assigned_at or now
    completed_at = payload.get("completed_at") or now
    if completed_at <= started_at:
        raise ProbeAPIException("INVALID_TIME_RANGE", "completed_at必须晚于started_at")
    paused_seconds = 0
    for segment in work_order.pause_segments.select_for_update().all():
        if segment.resumed_at is None:
            if completed_at <= segment.paused_at:
                raise ProbeAPIException("INVALID_TIME_RANGE", "异常报工时间必须晚于暂停时间")
            segment.resumed_at = completed_at
            segment.save(update_fields=["resumed_at"])
        resume_at = segment.resumed_at or completed_at
        overlap_start = max(segment.paused_at, started_at)
        overlap_end = min(resume_at, completed_at)
        if overlap_end > overlap_start:
            paused_seconds += int((overlap_end - overlap_start).total_seconds())
    actual_minutes = math.floor(
        max(0, int((completed_at - started_at).total_seconds()) - paused_seconds) / 60
    )

    abnormal = AbnormalReport.objects.create(
        work_order=work_order,
        employee=work_order.assigned_employee,
        abnormal_type=payload["abnormal_type"],
        description=payload["description"],
        inspection_results_json=payload["inspection_results"],
        client_request_id=payload["client_request_id"],
    )
    report = WorkReport.objects.create(
        work_order=work_order,
        employee=work_order.assigned_employee,
        report_type=WorkReport.ReportType.ABNORMAL,
        started_at=started_at,
        completed_at=completed_at,
        paused_seconds=paused_seconds,
        actual_minutes=actual_minutes,
        work_summary=payload["description"],
        inspection_results_json=payload["inspection_results"],
        attachments_json=[],
        cycle_reset=False,
        client_request_id=payload["client_request_id"],
    )
    work_order.status = WorkOrder.Status.ABNORMAL_REPORTED
    work_order.started_at = started_at
    work_order.completed_at = completed_at
    work_order.save(update_fields=["status", "started_at", "completed_at", "updated_at"])
    _release_employee_load(work_order.assigned_employee_id)
    WorkOrderEvent.objects.create(
        work_order=work_order,
        event_type="WORK_ORDER_ABNORMAL_REPORTED",
        event_data_json={
            "employee_id": payload["employee_id"],
            "report_id": report.report_id,
            "abnormal_report_id": abnormal.abnormal_report_id,
            "cycle_reset": False,
        },
        occurred_at=completed_at,
    )
    return {
        "work_order_id": work_order.work_order_id,
        "status": work_order.status,
        "report_id": report.report_id,
        "abnormal_report_id": abnormal.abnormal_report_id,
        "actual_minutes": actual_minutes,
        "cycle_reset": {"performed": False},
    }
