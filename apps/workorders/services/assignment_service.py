from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.common.identifiers import new_identifier
from apps.staff.models import Employee
from apps.workorders.models import WorkOrder, WorkOrderEvent
from apps.workorders.services.presentation import assignee_data, report_url


def eligible_candidates(work_order):
    candidates = []
    queryset = Employee.objects.filter(
        available=True,
        on_duty=True,
        current_load__lt=Decimal("0.8000"),
    ).exclude(email="")
    for employee in queryset:
        if work_order.mold.mold_type not in employee.skills_json:
            continue
        candidates.append(employee)
    return sorted(
        candidates,
        key=lambda item: (
            item.production_line != work_order.mold.production_line,
            item.current_load,
            item.employee_id,
        ),
    )


def candidate_data(work_order):
    return {
        "work_order_id": work_order.work_order_id,
        "required_skill": work_order.mold.mold_type,
        "candidate_count": len(eligible_candidates(work_order)),
        "candidates": [
            {
                **assignee_data(employee),
                "same_production_line": (
                    employee.production_line == work_order.mold.production_line
                ),
            }
            for employee in eligible_candidates(work_order)
        ],
    }


def _validate_candidate(work_order, employee):
    if not employee.available or not employee.on_duty:
        raise BusinessError("EMPLOYEE_NOT_AVAILABLE", "员工当前不可派工", status_code=409)
    if not employee.email:
        raise BusinessError("EMPLOYEE_NOT_AVAILABLE", "员工缺少测试邮箱", status_code=409)
    if employee.current_load >= Decimal("0.8000"):
        raise BusinessError("EMPLOYEE_NOT_AVAILABLE", "员工当前负荷不满足候选条件", status_code=409)
    if work_order.mold.mold_type not in employee.skills_json:
        raise BusinessError("EMPLOYEE_NOT_AVAILABLE", "员工技能不匹配模具类型", status_code=409)


@transaction.atomic
def assign_work_order(work_order_id, employee_id, *, client_request_id):
    try:
        work_order = (
            WorkOrder.objects.select_for_update()
            .select_related("mold", "assignee")
            .get(pk=work_order_id)
        )
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None
    if work_order.status != WorkOrder.Status.PENDING_ASSIGNMENT:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "当前工单状态不可派工", status_code=409)
    try:
        employee = Employee.objects.select_for_update().get(pk=employee_id)
    except Employee.DoesNotExist:
        raise BusinessError("EMPLOYEE_NOT_FOUND", "员工不存在", status_code=404) from None
    _validate_candidate(work_order, employee)
    old_status = work_order.status
    now = timezone.now()
    work_order.assignee = employee
    work_order.assigned_at = now
    work_order.status = WorkOrder.Status.ASSIGNED
    work_order.email_recipient = employee.email
    work_order.email_subject = f"MoldGuard保养工单 {work_order.work_order_id}"
    work_order.save(
        update_fields=[
            "assignee",
            "assigned_at",
            "status",
            "email_recipient",
            "email_subject",
            "updated_at",
        ]
    )
    WorkOrderEvent.objects.create(
        event_id=new_identifier("EVT"),
        work_order=work_order,
        event_type="WORK_ORDER_ASSIGNED",
        from_status=old_status,
        to_status=work_order.status,
        operator_id=employee.employee_id,
        event_data_json={"assignee": assignee_data(employee)},
        request_key=f"assign:{client_request_id}",
        occurred_at=now,
    )
    return {
        "work_order_id": work_order.work_order_id,
        "old_status": old_status,
        "new_status": work_order.status,
        "assignee_id": employee.employee_id,
        "assignee_name": employee.employee_name,
        "assignee_email": employee.email,
        "knowledge_snapshot_version": work_order.knowledge_snapshot_version,
        "knowledge_package_hash": work_order.knowledge_package_hash,
        "report_method": work_order.report_method,
        "report_url": report_url(work_order),
        "report_button_text": "提交报工情况",
        "report_form_schema_version": work_order.report_form_schema_version,
    }


@transaction.atomic
def auto_assign_work_order(work_order_id, *, client_request_id):
    try:
        work_order = (
            WorkOrder.objects.select_for_update().select_related("mold").get(pk=work_order_id)
        )
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None
    if work_order.status != WorkOrder.Status.PENDING_ASSIGNMENT:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "当前工单状态不可派工", status_code=409)
    candidates = eligible_candidates(work_order)
    if not candidates:
        raise BusinessError("NO_ASSIGNMENT_CANDIDATE", "没有符合条件的候选人员", status_code=409)
    result = assign_work_order(
        work_order_id,
        candidates[0].employee_id,
        client_request_id=client_request_id,
    )
    result["auto_assigned"] = True
    return result
