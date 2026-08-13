from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.common.responses import success_response
from apps.common.views import EnvelopeAPIView
from apps.molds.models import Alert, Mold
from apps.workorders.models import MaintenanceRecord, WorkOrder


class MoldRecordsView(EnvelopeAPIView):
    def get(self, request, mold_id):
        if not Mold.objects.filter(pk=mold_id).exists():
            raise BusinessError("MOLD_NOT_FOUND", "模具不存在", status_code=404)
        records = MaintenanceRecord.objects.filter(mold_id=mold_id).order_by("-occurred_at")
        return success_response(
            {
                "mold_id": mold_id,
                "count": records.count(),
                "records": [
                    {
                        "record_id": item.record_id,
                        "work_order_id": item.work_order_id,
                        "record_type": item.record_type,
                        "occurred_at": item.occurred_at.isoformat(),
                        "effective_mold_cycles_snapshot": (item.effective_mold_cycles_snapshot),
                        "baseline_count_before": item.baseline_count_before,
                        "baseline_time_before": item.baseline_time_before.isoformat(),
                        "baseline_count_after": item.baseline_count_after,
                        "baseline_time_after": item.baseline_time_after.isoformat(),
                        "reset_count_cycle": item.reset_count_cycle,
                        "reset_time_cycle": item.reset_time_cycle,
                        "knowledge_snapshot_version": item.knowledge_snapshot_version,
                        "knowledge_package_hash": item.knowledge_package_hash,
                        "standard_hours": str(item.standard_hours)
                        if item.standard_hours is not None
                        else None,
                        "actual_work_hours": str(item.actual_work_hours)
                        if item.actual_work_hours is not None
                        else None,
                        "result": item.result,
                        "note": item.note,
                    }
                    for item in records
                ],
            },
            request=request,
        )


class AnalyticsSummaryView(EnvelopeAPIView):
    def get(self, request):
        counts = WorkOrder.objects.aggregate(
            total=Count("work_order_id"),
            pending=Count("work_order_id", filter=Q(status=WorkOrder.Status.PENDING_ASSIGNMENT)),
            assigned=Count("work_order_id", filter=Q(status=WorkOrder.Status.ASSIGNED)),
            in_progress=Count(
                "work_order_id",
                filter=Q(status__in=[WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.PAUSED]),
            ),
            abnormal=Count("work_order_id", filter=Q(status=WorkOrder.Status.ABNORMAL_REPORTED)),
            completed=Count("work_order_id", filter=Q(status=WorkOrder.Status.COMPLETED)),
            with_standard_hours=Count("work_order_id", filter=Q(standard_hours__isnull=False)),
        )
        total = counts["total"]
        completed = counts["completed"]
        return success_response(
            {
                "mold_count": Mold.objects.count(),
                "open_alert_count": Alert.objects.filter(status=Alert.Status.OPEN).count(),
                "work_order_count": total,
                "pending_assignment_count": counts["pending"],
                "assigned_count": counts["assigned"],
                "in_progress_count": counts["in_progress"],
                "abnormal_count": counts["abnormal"],
                "completed_count": completed,
                "completion_rate": round(completed / total, 4) if total else 0.0,
                "standard_hours_coverage": round(counts["with_standard_hours"] / total, 4)
                if total
                else 0.0,
                "actual_work_hours_total": str(
                    sum(
                        (
                            item.actual_work_hours
                            for item in MaintenanceRecord.objects.exclude(
                                actual_work_hours__isnull=True
                            )
                        ),
                        start=0,
                    )
                ),
            },
            request=request,
        )


def _date_value(request, name):
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise BusinessError(
            "VALIDATION_ERROR", f"{name}必须是YYYY-MM-DD格式", errors={name: ["日期格式错误"]}
        ) from None


def _apply_date_filter(queryset, request, field):
    start_date = _date_value(request, "start_date")
    end_date = _date_value(request, "end_date")
    if start_date and end_date and start_date > end_date:
        raise BusinessError("VALIDATION_ERROR", "start_date不能晚于end_date")
    if start_date:
        start_at = timezone.make_aware(
            datetime.combine(start_date, time.min), timezone.get_current_timezone()
        )
        queryset = queryset.filter(**{f"{field}__gte": start_at})
    if end_date:
        end_at = timezone.make_aware(
            datetime.combine(end_date + timedelta(days=1), time.min),
            timezone.get_current_timezone(),
        )
        queryset = queryset.filter(**{f"{field}__lt": end_at})
    return queryset


def _decimal_string(value):
    return f"{value.quantize(Decimal('0.01')):.2f}"


class WorkHoursAnalyticsView(EnvelopeAPIView):
    def get(self, request):
        records = MaintenanceRecord.objects.select_related("work_order", "mold")
        records = _apply_date_filter(records, request, "occurred_at")
        if request.query_params.get("employee_id"):
            records = records.filter(work_order__assignee_id=request.query_params["employee_id"])
        if request.query_params.get("mold_type"):
            records = records.filter(mold__mold_type=request.query_params["mold_type"])
        rows = list(records)
        completed_count = len(rows)
        actual_total = sum((row.actual_work_hours or Decimal("0") for row in rows), Decimal("0"))
        configured = [row for row in rows if row.standard_hours is not None]
        standard_total = sum((row.standard_hours for row in configured), Decimal("0"))
        variance_total = sum(
            ((row.actual_work_hours or Decimal("0")) - row.standard_hours for row in configured),
            Decimal("0"),
        )
        actual_average = actual_total / completed_count if completed_count else Decimal("0")
        return success_response(
            {
                "completed_order_count": completed_count,
                "actual_hours_total": _decimal_string(actual_total),
                "actual_hours_average": _decimal_string(actual_average),
                "standard_hours_total": _decimal_string(standard_total),
                "standard_hours_coverage": (
                    round(len(configured) / completed_count, 4) if completed_count else 0.0
                ),
                "hours_variance_total": _decimal_string(variance_total),
            },
            request=request,
        )


class OrderCompletionAnalyticsView(EnvelopeAPIView):
    def get(self, request):
        orders = _apply_date_filter(WorkOrder.objects.all(), request, "created_at")
        counts = orders.aggregate(
            created=Count("work_order_id"),
            completed=Count("work_order_id", filter=Q(status=WorkOrder.Status.COMPLETED)),
            abnormal=Count("work_order_id", filter=Q(status=WorkOrder.Status.ABNORMAL_REPORTED)),
            repair_linked=Count("work_order_id", filter=Q(status=WorkOrder.Status.REPAIR_LINKED)),
            in_progress=Count(
                "work_order_id",
                filter=Q(status__in=[WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.PAUSED]),
            ),
        )
        return success_response(
            {
                "created_count": counts["created"],
                "completed_count": counts["completed"],
                "abnormal_count": counts["abnormal"],
                "repair_linked_count": counts["repair_linked"],
                "in_progress_count": counts["in_progress"],
                "completion_rate": (
                    round(counts["completed"] / counts["created"], 4) if counts["created"] else 0.0
                ),
            },
            request=request,
        )
