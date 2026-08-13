from django.db import transaction
from django.utils import timezone

from apps.platform_probe.exceptions import ProbeAPIException
from apps.platform_probe.models import Employee, WorkOrder, WorkOrderEvent


def candidates_for(work_order):
    available = Employee.objects.filter(available=True).order_by("current_load", "employee_id")
    return [employee for employee in available if work_order.mold.mold_type in employee.skill_tags]


def _locked_work_order(work_order_id):
    try:
        return (
            WorkOrder.objects.select_for_update()
            .select_related("mold", "assigned_employee", "alert")
            .get(work_order_id=work_order_id)
        )
    except WorkOrder.DoesNotExist as exc:
        raise ProbeAPIException("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from exc


def _ensure_pending(work_order):
    if work_order.status != WorkOrder.Status.PENDING_ASSIGNMENT:
        raise ProbeAPIException("INVALID_WORK_ORDER_STATE", "工单当前状态不能派工", status_code=409)


@transaction.atomic
def assign_employee(work_order_id, employee_id, now=None):
    now = now or timezone.now()
    work_order = _locked_work_order(work_order_id)
    _ensure_pending(work_order)
    try:
        employee = Employee.objects.select_for_update().get(employee_id=employee_id)
    except Employee.DoesNotExist as exc:
        raise ProbeAPIException("EMPLOYEE_NOT_FOUND", "员工不存在", status_code=404) from exc
    if not employee.available:
        raise ProbeAPIException("EMPLOYEE_NOT_AVAILABLE", "员工当前不可用", status_code=409)
    if work_order.mold.mold_type not in employee.skill_tags:
        raise ProbeAPIException(
            "EMPLOYEE_NOT_AVAILABLE", "员工技能与模具类型不匹配", status_code=409
        )

    work_order.assigned_employee = employee
    work_order.assigned_at = now
    work_order.status = WorkOrder.Status.ASSIGNED
    work_order.save(update_fields=["assigned_employee", "assigned_at", "status", "updated_at"])
    employee.current_load += 1
    employee.save(update_fields=["current_load", "updated_at"])
    WorkOrderEvent.objects.create(
        work_order=work_order,
        event_type="WORK_ORDER_ASSIGNED",
        event_data_json={"employee_id": employee.employee_id, "assignment_mode": "SPECIFIED"},
        occurred_at=now,
    )
    return work_order


@transaction.atomic
def auto_assign_employee(work_order_id, now=None):
    now = now or timezone.now()
    work_order = _locked_work_order(work_order_id)
    _ensure_pending(work_order)
    employee = next(
        (
            candidate
            for candidate in Employee.objects.select_for_update()
            .filter(available=True)
            .order_by("current_load", "employee_id")
            if work_order.mold.mold_type in candidate.skill_tags
        ),
        None,
    )
    if employee is None:
        raise ProbeAPIException(
            "NO_ASSIGNMENT_CANDIDATE", "没有可用的技能匹配候选人", status_code=409
        )

    work_order.assigned_employee = employee
    work_order.assigned_at = now
    work_order.status = WorkOrder.Status.ASSIGNED
    work_order.save(update_fields=["assigned_employee", "assigned_at", "status", "updated_at"])
    employee.current_load += 1
    employee.save(update_fields=["current_load", "updated_at"])
    WorkOrderEvent.objects.create(
        work_order=work_order,
        event_type="WORK_ORDER_ASSIGNED",
        event_data_json={"employee_id": employee.employee_id, "assignment_mode": "AUTOMATIC"},
        occurred_at=now,
    )
    return work_order
