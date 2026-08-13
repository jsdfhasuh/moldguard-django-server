from datetime import UTC

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.identifiers import new_identifier
from apps.workorders.models import WorkOrder, WorkOrderEvent
from apps.workorders.services.presentation import assignee_data

DEADLINE_STATUSES = {
    WorkOrder.Status.ASSIGNED,
    WorkOrder.Status.IN_PROGRESS,
    WorkOrder.Status.PAUSED,
}


def _abnormal_due_at(work_order):
    reference = work_order.reported_at
    if reference is None:
        event = (
            work_order.events.filter(event_type="ABNORMAL_REPORT_SUBMITTED")
            .order_by("-occurred_at")
            .first()
        )
        reference = event.occurred_at if event else None
    if reference is None:
        return None
    return reference + timezone.timedelta(hours=settings.MOLDGUARD_ABNORMAL_OVERDUE_HOURS)


def overdue_item(work_order, now):
    due_at = None
    overdue_type = None
    if (
        work_order.status in DEADLINE_STATUSES
        and work_order.required_finish_at is not None
        and work_order.required_finish_at < now
    ):
        due_at = work_order.required_finish_at
        overdue_type = "REQUIRED_FINISH_OVERDUE"
    elif work_order.status == WorkOrder.Status.ABNORMAL_REPORTED:
        abnormal_due_at = _abnormal_due_at(work_order)
        if abnormal_due_at is not None and abnormal_due_at < now:
            due_at = abnormal_due_at
            overdue_type = "ABNORMAL_UNHANDLED_OVERDUE"
    if due_at is None:
        return None
    return {
        "work_order_id": work_order.work_order_id,
        "mold_id": work_order.mold_id,
        "status": work_order.status,
        "assignee": assignee_data(work_order.assignee),
        "required_finish_at": (
            work_order.required_finish_at.isoformat()
            if work_order.required_finish_at is not None
            else None
        ),
        "overdue_type": overdue_type,
        "overdue_duration_minutes": max(0, int((now - due_at).total_seconds() // 60)),
        "trigger_reason": work_order.trigger_reason,
    }


def list_overdue(*, now=None):
    now = now or timezone.now()
    queryset = WorkOrder.objects.select_related("mold", "assignee").prefetch_related("events")
    results = []
    for work_order in queryset.order_by("work_order_id"):
        item = overdue_item(work_order, now)
        if item is not None:
            results.append(item)
    return {"count": len(results), "scanned_at": now.isoformat(), "results": results}


@transaction.atomic
def scan_overdue(*, now=None):
    now = now or timezone.now()
    queryset = (
        WorkOrder.objects.select_for_update()
        .select_related("mold", "assignee")
        .prefetch_related("events")
        .order_by("work_order_id")
    )
    results = []
    created_event_count = 0
    bucket = now.astimezone(UTC).strftime("%Y%m%d%H")
    for work_order in queryset:
        item = overdue_item(work_order, now)
        if item is None:
            continue
        request_key = f"overdue:{item['overdue_type']}:{work_order.work_order_id}:{bucket}"
        _, created = WorkOrderEvent.objects.get_or_create(
            request_key=request_key,
            defaults={
                "event_id": new_identifier("EVT"),
                "work_order": work_order,
                "event_type": "WORK_ORDER_OVERDUE",
                "from_status": work_order.status,
                "to_status": work_order.status,
                "operator_id": "",
                "event_data_json": item,
                "occurred_at": now,
            },
        )
        item["event_created"] = created
        item["event_dedupe_key"] = request_key
        created_event_count += int(created)
        results.append(item)
    return {
        "scanned_at": now.isoformat(),
        "overdue_count": len(results),
        "created_event_count": created_event_count,
        "results": results,
    }
