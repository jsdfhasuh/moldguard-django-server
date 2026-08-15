import hashlib
import json

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.common.identifiers import new_identifier
from apps.workorders.models import WorkOrder, WorkOrderEvent
from apps.workorders.services.presentation import report_url


def knowledge_hash(package):
    canonical = json.dumps(
        package,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_knowledge_package(payload):
    version = payload.get("knowledge_snapshot_version")
    if version != settings.MOLDGUARD_KNOWLEDGE_VERSION:
        raise BusinessError(
            "KNOWLEDGE_VERSION_MISMATCH",
            f"知识版本必须为{settings.MOLDGUARD_KNOWLEDGE_VERSION}",
            status_code=409,
        )
    title = payload.get("title")
    items = payload.get("items")
    if not isinstance(title, str) or not title.strip():
        raise BusinessError("VALIDATION_ERROR", "知识包title不能为空")
    if not isinstance(items, list) or not items:
        raise BusinessError("VALIDATION_ERROR", "知识包items至少包含一项")
    identifiers = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise BusinessError("VALIDATION_ERROR", f"items[{index}]必须为对象")
        identifier = item.get("knowledge_id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise BusinessError("VALIDATION_ERROR", f"items[{index}].knowledge_id不能为空")
        if not isinstance(item.get("item"), str) or not item["item"].strip():
            raise BusinessError("VALIDATION_ERROR", f"items[{index}].item不能为空")
        if type(item.get("required")) is not bool:
            raise BusinessError("VALIDATION_ERROR", f"items[{index}].required必须是布尔值")
        criteria = item.get("criteria")
        content = item.get("content")
        if not any(isinstance(value, str) and value.strip() for value in (criteria, content)):
            raise BusinessError("VALIDATION_ERROR", f"items[{index}].criteria和content至少填写一个")
        platform_fields = ("title", "knowledge_type", "content", "source")
        if any(field in item for field in platform_fields):
            missing = [
                field
                for field in platform_fields
                if not isinstance(item.get(field), str) or not item[field].strip()
            ]
            if missing:
                raise BusinessError(
                    "VALIDATION_ERROR",
                    f"items[{index}]平台知识字段不完整：{', '.join(missing)}",
                )
        identifiers.append(identifier)
    if len(set(identifiers)) != len(identifiers):
        raise BusinessError("VALIDATION_ERROR", "knowledge_id不允许重复")
    safety_notes = payload.get("safety_notes", [])
    source_documents = payload.get("source_documents", [])
    if not isinstance(safety_notes, list) or not isinstance(source_documents, list):
        raise BusinessError("VALIDATION_ERROR", "safety_notes和source_documents必须为数组")
    return {
        "knowledge_snapshot_version": version,
        "title": title.strip(),
        "items": items,
        "safety_notes": safety_notes,
        "source_documents": source_documents,
    }


@transaction.atomic
def save_knowledge_package(work_order_id, payload, *, client_request_id):
    try:
        work_order = WorkOrder.objects.select_for_update().get(pk=work_order_id)
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None
    if (
        work_order.email_status
        in {
            WorkOrder.EmailStatus.SENDING,
            WorkOrder.EmailStatus.SENT,
            WorkOrder.EmailStatus.OUTCOME_UNKNOWN,
        }
        or work_order.reported_at
    ):
        raise BusinessError("KNOWLEDGE_PACKAGE_LOCKED", "知识包已锁定，不能覆盖", status_code=409)
    package = _validate_knowledge_package(payload)
    digest = knowledge_hash(package)
    work_order.knowledge_snapshot_version = package["knowledge_snapshot_version"]
    work_order.knowledge_package_json = package
    work_order.knowledge_package_hash = digest
    work_order.save(
        update_fields=[
            "knowledge_snapshot_version",
            "knowledge_package_json",
            "knowledge_package_hash",
            "updated_at",
        ]
    )
    WorkOrderEvent.objects.create(
        event_id=new_identifier("EVT"),
        work_order=work_order,
        event_type="KNOWLEDGE_PACKAGE_SAVED",
        event_data_json={
            "knowledge_snapshot_version": work_order.knowledge_snapshot_version,
            "knowledge_package_hash": digest,
        },
        request_key=f"knowledge:{client_request_id}",
        occurred_at=timezone.now(),
    )
    return {
        "work_order_id": work_order.work_order_id,
        "knowledge_snapshot_version": work_order.knowledge_snapshot_version,
        "knowledge_package_hash": digest,
        "item_count": len(package["items"]),
    }


def knowledge_context(work_order):
    mold_type_label = work_order.mold.get_mold_type_display()
    query_keywords = [
        f"{mold_type_label}模具保养步骤",
        f"{mold_type_label}模具点检项目",
    ]
    if work_order.mold.mold_category:
        query_keywords.append(work_order.mold.get_mold_category_display())
    query_keywords.append("清洁 检查 测量 润滑 紧固 调整 复核 记录")

    return {
        "work_order_id": work_order.work_order_id,
        "mold_id": work_order.mold_id,
        "mold_type": work_order.mold.mold_type,
        "mold_category": work_order.mold.mold_category,
        "primary_rule_id": work_order.primary_rule_id,
        "matched_rule_ids": work_order.matched_rule_ids_json,
        "work_order_type": work_order.work_order_type,
        "knowledge_profile_code": work_order.mold.knowledge_profile_code,
        "knowledge_snapshot_version": settings.MOLDGUARD_KNOWLEDGE_VERSION,
        "query_keywords": query_keywords,
        "required_knowledge_types": ["MAINTENANCE_STEPS", "INSPECTION_ITEMS"],
    }


def email_context(work_order):
    if not work_order.assignee_id:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "工单尚未派工", status_code=409)
    if not work_order.knowledge_package_hash or not work_order.knowledge_package_json:
        raise BusinessError("KNOWLEDGE_PACKAGE_REQUIRED", "请先保存知识包", status_code=409)
    return {
        "work_order_id": work_order.work_order_id,
        "assignee_id": work_order.assignee_id,
        "assignee_name": work_order.assignee.employee_name,
        "assignee_email": work_order.assignee.email,
        "email_subject": work_order.email_subject,
        "work_order": {
            "work_order_type": work_order.work_order_type,
            "status": work_order.status,
            "required_finish_at": work_order.required_finish_at.isoformat()
            if work_order.required_finish_at
            else None,
            "standard_hours": str(work_order.standard_hours)
            if work_order.standard_hours is not None
            else None,
        },
        "mold": {
            "mold_id": work_order.mold_id,
            "mold_name": work_order.mold.mold_name,
            "mold_type": work_order.mold.mold_type,
            "mold_category": work_order.mold.mold_category,
        },
        "trigger": {
            "primary_rule_id": work_order.primary_rule_id,
            "matched_rule_ids": work_order.matched_rule_ids_json,
            "trigger_reason": work_order.trigger_reason,
            "cycle_mold_cycles": work_order.cycle_mold_cycles_snapshot,
            "threshold_count": work_order.threshold_count,
        },
        "knowledge_package": work_order.knowledge_package_json,
        "knowledge_snapshot_version": work_order.knowledge_snapshot_version,
        "knowledge_package_hash": work_order.knowledge_package_hash,
        "report_method": work_order.report_method,
        "report_url": report_url(work_order),
        "report_button_text": "提交报工情况",
        "report_form_schema_version": work_order.report_form_schema_version,
    }
