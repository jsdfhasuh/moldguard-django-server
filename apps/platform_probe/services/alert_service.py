from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.platform_probe.models import MaintenanceAlert, Mold

from .trigger_service import TWO_MONTH_MESSAGE, calculate_maintenance_status


def _create_alert(mold, alert_type, status, now):
    if alert_type == MaintenanceAlert.AlertType.MAINTENANCE_DUE:
        basis = {
            "rule_id": "MAINT_TRIGGER_TONNAGE_V1",
            "development_tonnage": status.development_tonnage,
            "cycle_count": status.cycle_count,
            "threshold": status.threshold,
            "operator": ">=",
        }
        threshold = status.threshold
    elif alert_type == MaintenanceAlert.AlertType.TWO_MONTH_REMINDER:
        basis = {
            "rule_id": "INJECTION_TWO_CALENDAR_MONTHS_V1",
            "next_reminder_at": status.next_two_month_reminder_at,
            "evaluated_at": now.isoformat(),
            "message": TWO_MONTH_MESSAGE,
        }
        threshold = None
    else:
        basis = {
            "rule_id": "IDLE_TWO_YEARS_V1",
            "last_production_at": mold.last_production_at.isoformat(),
            "evaluated_at": now.isoformat(),
            "message": "模具已达到两年无产量条件，自动模次保养提醒已停用。",
        }
        threshold = status.threshold

    try:
        alert, created = MaintenanceAlert.objects.get_or_create(
            mold=mold,
            alert_type=alert_type,
            cycle_version=mold.cycle_version,
            defaults={
                "cycle_count_snapshot": status.cycle_count,
                "threshold_snapshot": threshold,
                "trigger_basis_json": basis,
            },
        )
    except IntegrityError:
        alert = MaintenanceAlert.objects.get(
            mold=mold,
            alert_type=alert_type,
            cycle_version=mold.cycle_version,
        )
        created = False
    return alert, created


@transaction.atomic
def scan_molds(mold_ids=None, now=None):
    now = now or timezone.now()
    queryset = Mold.objects.exclude(status=Mold.Status.DISABLED).order_by("mold_id")
    if mold_ids:
        queryset = queryset.filter(mold_id__in=mold_ids)

    results = []
    created_alert_ids = []
    for mold in queryset.select_for_update():
        try:
            status = calculate_maintenance_status(mold, now)
        except Exception as exc:
            from apps.platform_probe.exceptions import ProbeAPIException

            if not isinstance(exc, ProbeAPIException):
                raise
            results.append(
                {
                    "mold_id": mold.mold_id,
                    "result": exc.probe_code,
                    "message": exc.probe_message,
                    "alert_ids": [],
                }
            )
            continue

        alert_types = []
        result_code = "NO_ALERT_DUE"
        if status.idle_auto_reminder_disabled:
            alert_types = [MaintenanceAlert.AlertType.IDLE_AUTO_REMINDER_DISABLED]
            result_code = "IDLE_AUTO_REMINDER_DISABLED"
        else:
            if status.maintenance_due:
                alert_types.append(MaintenanceAlert.AlertType.MAINTENANCE_DUE)
                result_code = "MAINTENANCE_DUE"
            if status.two_month_reminder_due:
                alert_types.append(MaintenanceAlert.AlertType.TWO_MONTH_REMINDER)
                if result_code == "NO_ALERT_DUE":
                    result_code = "TWO_MONTH_REMINDER"

        mold_alert_ids = []
        for alert_type in alert_types:
            alert, created = _create_alert(mold, alert_type, status, now)
            mold_alert_ids.append(alert.alert_id)
            if created:
                created_alert_ids.append(alert.alert_id)

        results.append(
            {
                "mold_id": mold.mold_id,
                "result": result_code,
                "alert_ids": mold_alert_ids,
                "maintenance_status": status.to_dict(),
            }
        )

    return {"results": results, "created_alert_ids": created_alert_ids}
