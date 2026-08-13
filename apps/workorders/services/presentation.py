from django.conf import settings


def report_url(work_order):
    return f"{settings.MOLDGUARD_PUBLIC_BASE_URL}/report/{work_order.work_order_id}"


def assignee_data(employee):
    if employee is None:
        return None
    return {
        "employee_id": employee.employee_id,
        "employee_name": employee.employee_name,
        "email": employee.email,
        "production_line": employee.production_line,
        "skills": employee.skills_json,
        "current_load": str(employee.current_load),
        "on_duty": employee.on_duty,
        "available": employee.available,
    }


def work_order_data(work_order, *, include_knowledge=False):
    data = {
        "work_order_id": work_order.work_order_id,
        "mold_id": work_order.mold_id,
        "alert_id": work_order.alert_id,
        "parent_work_order_id": work_order.parent_work_order_id,
        "linked_repair_order_id": work_order.linked_repair_order_id,
        "primary_rule_id": work_order.primary_rule_id,
        "matched_rule_ids": work_order.matched_rule_ids_json,
        "work_order_type": work_order.work_order_type,
        "status": work_order.status,
        "assignee": assignee_data(work_order.assignee),
        "standard_hours": str(work_order.standard_hours)
        if work_order.standard_hours is not None
        else None,
        "required_finish_at": work_order.required_finish_at.isoformat()
        if work_order.required_finish_at
        else None,
        "effective_mold_cycles_snapshot": work_order.effective_mold_cycles_snapshot,
        "baseline_effective_mold_cycles_before": (work_order.baseline_effective_mold_cycles_before),
        "baseline_maintenance_at_before": (work_order.baseline_maintenance_at_before.isoformat()),
        "cycle_mold_cycles_snapshot": work_order.cycle_mold_cycles_snapshot,
        "threshold_count": work_order.threshold_count,
        "trigger_reason": work_order.trigger_reason,
        "triggered_at": work_order.triggered_at.isoformat(),
        "reset_count_cycle": work_order.reset_count_cycle,
        "reset_time_cycle": work_order.reset_time_cycle,
        "knowledge_snapshot_version": work_order.knowledge_snapshot_version,
        "knowledge_package_hash": work_order.knowledge_package_hash,
        "email_status": work_order.email_status,
        "email_recipient": work_order.email_recipient,
        "email_subject": work_order.email_subject,
        "email_message_id": work_order.email_message_id,
        "email_sent_at": work_order.email_sent_at.isoformat() if work_order.email_sent_at else None,
        "email_error": work_order.email_error,
        "report_method": work_order.report_method,
        "report_url": report_url(work_order),
        "report_button_text": "提交报工情况",
        "report_form_schema_version": work_order.report_form_schema_version,
        "report_type": work_order.report_type,
        "report_summary": work_order.report_summary,
        "actual_work_hours": str(work_order.actual_work_hours)
        if work_order.actual_work_hours is not None
        else None,
        "abnormal_next_action": work_order.abnormal_next_action or None,
        "assigned_at": work_order.assigned_at.isoformat() if work_order.assigned_at else None,
        "reported_at": work_order.reported_at.isoformat() if work_order.reported_at else None,
        "completed_at": work_order.completed_at.isoformat() if work_order.completed_at else None,
        "created_at": work_order.created_at.isoformat(),
        "updated_at": work_order.updated_at.isoformat(),
    }
    if include_knowledge:
        data["knowledge_package"] = work_order.knowledge_package_json
        data["inspection_results"] = work_order.inspection_results_json
        data["abnormal_items"] = work_order.abnormal_items_json
        data["photos"] = work_order.photos_json
        data["parts_replaced"] = work_order.parts_replaced_json
    return data
