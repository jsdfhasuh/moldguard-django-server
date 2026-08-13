from django.db import transaction
from django.utils import timezone

from apps.common.identifiers import new_identifier
from apps.molds.models import Alert, Mold
from apps.molds.services.trigger_service import evaluate_trigger
from apps.workorders.models import WorkOrder, WorkOrderEvent
from apps.workorders.services.defaults_service import resolve_work_order_defaults


def _create_event(work_order, event_type, from_status="", to_status="", data=None):
    return WorkOrderEvent.objects.create(
        event_id=new_identifier("EVT"),
        work_order=work_order,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        event_data_json=data or {},
        occurred_at=timezone.now(),
    )


def _create_or_reuse_formal_work(mold, trigger, now):
    dedupe_key = f"FORMAL_MAINTENANCE:{mold.mold_id}:{mold.cycle_version}"
    alert, alert_created = Alert.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "alert_id": new_identifier("ALT"),
            "mold": mold,
            "primary_rule_id": trigger["primary_rule_id"],
            "matched_rule_ids_json": trigger["matched_rule_ids"],
            "alert_type": Alert.Type.FORMAL_MAINTENANCE,
            "cycle_version": mold.cycle_version,
            "cycle_mold_cycles_snapshot": mold.cycle_mold_cycles,
            "threshold_count": trigger.get("threshold_count"),
            "trigger_reason": trigger["trigger_reason"],
            "status": Alert.Status.OPEN,
            "triggered_at": now,
        },
    )
    standard_hours, required_finish_at = resolve_work_order_defaults(
        mold.mold_id, trigger["primary_rule_id"], now
    )
    work_order, work_order_created = WorkOrder.objects.get_or_create(
        create_key=dedupe_key,
        defaults={
            "work_order_id": new_identifier("WO"),
            "alert": alert,
            "mold": mold,
            "primary_rule_id": trigger["primary_rule_id"],
            "matched_rule_ids_json": trigger["matched_rule_ids"],
            "work_order_type": trigger["work_order_type"],
            "status": WorkOrder.Status.PENDING_ASSIGNMENT,
            "standard_hours": standard_hours,
            "required_finish_at": required_finish_at,
            "effective_mold_cycles_snapshot": mold.effective_mold_cycles,
            "baseline_effective_mold_cycles_before": mold.baseline_effective_mold_cycles,
            "baseline_maintenance_at_before": mold.baseline_maintenance_at,
            "cycle_mold_cycles_snapshot": mold.cycle_mold_cycles,
            "threshold_count": trigger.get("threshold_count"),
            "trigger_reason": trigger["trigger_reason"],
            "triggered_at": now,
            "reset_count_cycle": trigger["reset_count_cycle"],
            "reset_time_cycle": trigger["reset_time_cycle"],
        },
    )
    if work_order_created:
        _create_event(
            work_order,
            "WORK_ORDER_CREATED",
            to_status=WorkOrder.Status.PENDING_ASSIGNMENT,
            data={"primary_rule_id": trigger["primary_rule_id"], "alert_id": alert.alert_id},
        )
    return alert, work_order, alert_created, work_order_created


@transaction.atomic
def scan_molds(*, mold_ids=None, now=None):
    now = now or timezone.now()
    queryset = Mold.objects.select_for_update().order_by("mold_id")
    if mold_ids is not None:
        queryset = queryset.filter(mold_id__in=mold_ids)
    else:
        queryset = queryset.exclude(status=Mold.Status.DISABLED)
    found = {mold.mold_id: mold for mold in queryset}
    ordered_ids = list(mold_ids) if mold_ids is not None else list(found)
    results = []
    for mold_id in ordered_ids:
        mold = found.get(mold_id)
        if mold is None:
            results.append(
                {
                    "mold_id": mold_id,
                    "status": "ERROR",
                    "code": "MOLD_NOT_FOUND",
                    "message": "模具不存在或已禁用",
                }
            )
            continue
        trigger = evaluate_trigger(mold, now=now)
        if trigger["status"] != "TRIGGERED":
            results.append(trigger)
            continue
        alert, work_order, alert_created, work_order_created = _create_or_reuse_formal_work(
            mold, trigger, now
        )
        results.append(
            {
                **trigger,
                "alert_id": alert.alert_id,
                "alert_status": alert.status,
                "work_order_id": work_order.work_order_id,
                "work_order_status": work_order.status,
                "alert_created": alert_created,
                "work_order_created": work_order_created,
            }
        )
    return {
        "scanned_count": len(results),
        "triggered_count": sum(item["status"] == "TRIGGERED" for item in results),
        "created_work_order_count": sum(item.get("work_order_created", False) for item in results),
        "results": results,
    }
