import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.common.identifiers import new_identifier
from apps.workorders.models import ReportEvidence, ReportSubmission, WorkOrder, WorkOrderEvent
from apps.workorders.serializers import ReportSerializer
from apps.workorders.services.report_service import submit_report

_IMAGE_TYPES = (
    ("image/jpeg", "jpg", lambda head: head.startswith(b"\xff\xd8\xff")),
    ("image/png", "png", lambda head: head.startswith(b"\x89PNG\r\n\x1a\n")),
    (
        "image/webp",
        "webp",
        lambda head: len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WEBP",
    ),
)


def _json_safe(value):
    return json.loads(json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder))


def _api_url(path):
    return f"{settings.MOLDGUARD_PUBLIC_BASE_URL}/api/v1{path}"


def review_context_url(submission_id):
    encoded = quote(submission_id, safe="")
    return _api_url(f"/report-submissions/{encoded}/review-context")


def review_callback_url(submission_id):
    encoded = quote(submission_id, safe="")
    return _api_url(f"/report-submissions/{encoded}/review")


def evidence_download_url(submission_id, evidence_id):
    encoded_submission = quote(submission_id, safe="")
    encoded_evidence = quote(evidence_id, safe="")
    return _api_url(f"/report-submissions/{encoded_submission}/evidence/{encoded_evidence}")


def prepare_uploaded_images(uploaded_files):
    files = list(uploaded_files or [])
    if len(files) > settings.MOLDGUARD_REPORT_MAX_IMAGES:
        raise BusinessError(
            "VALIDATION_ERROR",
            f"报工图片最多{settings.MOLDGUARD_REPORT_MAX_IMAGES}张",
            errors={"images": ["图片数量超过限制"]},
        )

    prepared = []
    for upload in files:
        if upload.size <= 0:
            raise BusinessError(
                "INVALID_REPORT_IMAGE",
                "报工图片不能为空",
                errors={"images": [getattr(upload, "name", "未命名文件")]},
            )
        if upload.size > settings.MOLDGUARD_REPORT_IMAGE_MAX_BYTES:
            raise BusinessError(
                "REPORT_IMAGE_TOO_LARGE",
                "单张报工图片超过大小限制",
                errors={
                    "images": [
                        f"{getattr(upload, 'name', '未命名文件')} 最大允许"
                        f"{settings.MOLDGUARD_REPORT_IMAGE_MAX_BYTES}字节"
                    ]
                },
            )

        head = upload.read(16)
        upload.seek(0)
        detected = next(
            (
                (content_type, extension)
                for content_type, extension, check in _IMAGE_TYPES
                if check(head)
            ),
            None,
        )
        if detected is None:
            raise BusinessError(
                "INVALID_REPORT_IMAGE",
                "只接受JPEG、PNG或WebP报工图片",
                errors={"images": [getattr(upload, "name", "未命名文件")]},
            )

        digest = hashlib.sha256()
        for chunk in upload.chunks():
            digest.update(chunk)
        upload.seek(0)
        content_type, extension = detected
        prepared.append(
            {
                "upload": upload,
                "original_name": Path(getattr(upload, "name", "image")).name[:255],
                "content_type": content_type,
                "extension": extension,
                "byte_size": upload.size,
                "sha256": digest.hexdigest(),
            }
        )
    return prepared


def submission_idempotency_payload(payload, prepared_images):
    result = {key: value for key, value in payload.items() if key != "images"}
    result["images"] = [
        {
            "original_name": item["original_name"],
            "content_type": item["content_type"],
            "byte_size": item["byte_size"],
            "sha256": item["sha256"],
        }
        for item in prepared_images
    ]
    return result


def _get_work_order(work_order_id, *, lock=False):
    queryset = WorkOrder.objects.select_related("mold", "assignee", "alert")
    if lock:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(pk=work_order_id)
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None


def _validate_submission_work_order(work_order, payload):
    if work_order.status not in {
        WorkOrder.Status.ASSIGNED,
        WorkOrder.Status.IN_PROGRESS,
        WorkOrder.Status.PAUSED,
    }:
        raise BusinessError(
            "INVALID_WORK_ORDER_STATE", "当前工单状态不可提交报工材料", status_code=409
        )
    if not work_order.assignee_id:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "工单尚未派工", status_code=409)
    if not work_order.knowledge_package_hash or not work_order.knowledge_package_json:
        raise BusinessError("KNOWLEDGE_PACKAGE_REQUIRED", "工单尚未保存知识包", status_code=409)
    if payload["knowledge_package_hash"] != work_order.knowledge_package_hash:
        raise BusinessError(
            "KNOWLEDGE_PACKAGE_HASH_MISMATCH",
            "报工材料使用的知识包哈希与工单不一致",
            status_code=409,
        )
    if work_order.report_submissions.filter(status=ReportSubmission.Status.PENDING_REVIEW).exists():
        raise BusinessError(
            "REPORT_REVIEW_PENDING",
            "该工单已有等待AI审核的报工材料",
            status_code=409,
        )


def _submission_data(submission):
    return {
        "submission_id": submission.submission_id,
        "work_order_id": submission.work_order_id,
        "submission_status": submission.status,
        "work_order_status": submission.work_order.status,
        "review_decision": submission.review_decision or None,
        "review_context_url": review_context_url(submission.submission_id),
        "review_callback_url": review_callback_url(submission.submission_id),
        "webhook_delivery_status": submission.webhook_status,
        "created_at": submission.created_at.isoformat(),
        "reviewed_at": submission.reviewed_at.isoformat() if submission.reviewed_at else None,
    }


def create_report_submission(work_order_id, payload, prepared_images):
    if not prepared_images:
        raise BusinessError(
            "INVALID_REPORT_IMAGE",
            "至少提交一张报工图片",
            errors={"images": ["至少提交一张图片"]},
        )
    if len(prepared_images) > settings.MOLDGUARD_REPORT_MAX_IMAGES:
        raise BusinessError(
            "VALIDATION_ERROR",
            f"报工图片最多{settings.MOLDGUARD_REPORT_MAX_IMAGES}张",
        )

    stored_files = []
    try:
        with transaction.atomic():
            work_order = _get_work_order(work_order_id, lock=True)
            _validate_submission_work_order(work_order, payload)
            submission = ReportSubmission.objects.create(
                submission_id=new_identifier("RPT"),
                work_order=work_order,
                client_request_id=payload["client_request_id"],
                report_text=payload["report_text"],
                actual_work_hours=payload["actual_work_hours"],
                parts_replaced_json=payload.get("parts_replaced", []),
                source_fault_id=payload.get("source_fault_id") or "",
                knowledge_package_hash=payload["knowledge_package_hash"],
                webhook_status=ReportSubmission.WebhookStatus.PENDING,
            )
            order = 0
            for item in prepared_images:
                evidence_id = new_identifier("IMG")
                upload = item["upload"]
                upload.name = f"{evidence_id}.{item['extension']}"
                evidence = ReportEvidence(
                    evidence_id=evidence_id,
                    submission=submission,
                    original_name=item["original_name"],
                    content_type=item["content_type"],
                    byte_size=item["byte_size"],
                    sha256=item["sha256"],
                    display_order=order,
                )
                evidence.file.save(upload.name, upload, save=False)
                stored_files.append((evidence.file.storage, evidence.file.name))
                evidence.save()
                order += 1
            WorkOrderEvent.objects.create(
                event_id=new_identifier("EVT"),
                work_order=work_order,
                event_type="REPORT_SUBMISSION_CREATED",
                from_status=work_order.status,
                to_status=work_order.status,
                operator_id=work_order.assignee_id,
                event_data_json={
                    "submission_id": submission.submission_id,
                    "evidence_count": order,
                    "knowledge_package_hash": submission.knowledge_package_hash,
                },
                request_key=f"report-submission:{payload['client_request_id']}",
                occurred_at=timezone.now(),
            )
            result = _submission_data(submission)
    except Exception:
        for storage, name in stored_files:
            storage.delete(name)
        raise
    return result


def get_report_submission(submission_id, *, lock=False):
    queryset = ReportSubmission.objects.select_related("work_order__mold", "work_order__assignee")
    if lock:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(pk=submission_id)
    except ReportSubmission.DoesNotExist:
        raise BusinessError(
            "REPORT_SUBMISSION_NOT_FOUND", "报工提交不存在", status_code=404
        ) from None


def active_report_submission(work_order):
    return (
        work_order.report_submissions.filter(status=ReportSubmission.Status.PENDING_REVIEW)
        .order_by("-created_at")
        .first()
    )


def report_review_context(submission_id):
    try:
        submission = (
            ReportSubmission.objects.select_related("work_order__mold", "work_order__assignee")
            .prefetch_related("evidence")
            .get(pk=submission_id)
        )
    except ReportSubmission.DoesNotExist:
        raise BusinessError(
            "REPORT_SUBMISSION_NOT_FOUND", "报工提交不存在", status_code=404
        ) from None
    work_order = submission.work_order
    evidence = []
    for item in submission.evidence.all():
        evidence.append(
            {
                "evidence_id": item.evidence_id,
                "url": evidence_download_url(submission.submission_id, item.evidence_id),
                "content_type": item.content_type,
                "byte_size": item.byte_size,
                "sha256": item.sha256 or None,
                "original_name": item.original_name,
            }
        )
    return {
        "submission": {
            "submission_id": submission.submission_id,
            "status": submission.status,
            "report_text": submission.report_text,
            "actual_work_hours": str(submission.actual_work_hours),
            "parts_replaced": submission.parts_replaced_json,
            "source_fault_id": submission.source_fault_id or None,
            "knowledge_package_hash": submission.knowledge_package_hash,
            "evidence": evidence,
            "created_at": submission.created_at.isoformat(),
        },
        "work_order": {
            "work_order_id": work_order.work_order_id,
            "status": work_order.status,
            "work_order_type": work_order.work_order_type,
            "mold_id": work_order.mold_id,
            "mold_name": work_order.mold.mold_name,
            "mold_type": work_order.mold.mold_type,
            "trigger_reason": work_order.trigger_reason,
            "assignee_id": work_order.assignee_id,
            "assignee_name": work_order.assignee.employee_name,
        },
        "knowledge_package": work_order.knowledge_package_json,
        "knowledge_snapshot_version": work_order.knowledge_snapshot_version,
        "knowledge_package_hash": work_order.knowledge_package_hash,
        "review_callback_url": review_callback_url(submission.submission_id),
        "review_contract": {
            "decisions": ["COMPLETE", "ABNORMAL", "NEEDS_MORE_INFO"],
            "django_is_final_authority": True,
            "complete_requires": "全部必检项有结论、无FAIL且置信度达到阈值",
            "abnormal_requires": "至少一个FAIL或异常项目，并指定后续动作",
        },
    }


def _webhook_event_payload(submission):
    return {
        "event": "REPORT_SUBMISSION_READY",
        "submission_id": submission.submission_id,
        "work_order_id": submission.work_order_id,
        "review_context_url": review_context_url(submission.submission_id),
        "client_request_id": f"review-dispatch-{submission.submission_id}",
    }


def dispatch_report_review(submission_id, *, retry_failed=False):
    webhook_url = settings.MOLDGUARD_REPORT_REVIEW_WEBHOOK_URL
    with transaction.atomic():
        submission = get_report_submission(submission_id, lock=True)
        if submission.webhook_status == ReportSubmission.WebhookStatus.DELIVERED:
            return _submission_data(submission)
        if submission.webhook_status == ReportSubmission.WebhookStatus.SENDING:
            raise BusinessError(
                "REPORT_REVIEW_WEBHOOK_IN_PROGRESS",
                "报工审核Webhook正在触发",
                status_code=409,
            )
        if submission.webhook_status == ReportSubmission.WebhookStatus.FAILED and not retry_failed:
            return _submission_data(submission)
        if not webhook_url:
            submission.webhook_status = ReportSubmission.WebhookStatus.NOT_CONFIGURED
            submission.webhook_error = "review webhook is not configured"
            submission.save(update_fields=["webhook_status", "webhook_error", "updated_at"])
            return _submission_data(submission)
        submission.webhook_status = ReportSubmission.WebhookStatus.SENDING
        submission.webhook_error = ""
        submission.save(update_fields=["webhook_status", "webhook_error", "updated_at"])
        event_payload = _webhook_event_payload(submission)

    error = ""
    delivered = False
    try:
        request = urllib.request.Request(
            webhook_url,
            data=json.dumps(event_payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "MoldGuard-Report-Review/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(
            request, timeout=settings.MOLDGUARD_REPORT_REVIEW_WEBHOOK_TIMEOUT
        ) as response:
            status_code = response.getcode()
            delivered = 200 <= status_code < 300
            if not delivered:
                error = f"webhook returned HTTP {status_code}"
    except urllib.error.HTTPError as exc:
        error = f"webhook returned HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        error = f"webhook delivery failed: {type(exc).__name__}"

    now = timezone.now()
    with transaction.atomic():
        submission = get_report_submission(submission_id, lock=True)
        submission.webhook_status = (
            ReportSubmission.WebhookStatus.DELIVERED
            if delivered
            else ReportSubmission.WebhookStatus.FAILED
        )
        submission.webhook_error = error
        submission.webhook_delivered_at = now if delivered else None
        submission.save(
            update_fields=[
                "webhook_status",
                "webhook_error",
                "webhook_delivered_at",
                "updated_at",
            ]
        )
        WorkOrderEvent.objects.create(
            event_id=new_identifier("EVT"),
            work_order=submission.work_order,
            event_type=(
                "REPORT_REVIEW_WEBHOOK_DELIVERED" if delivered else "REPORT_REVIEW_WEBHOOK_FAILED"
            ),
            from_status=submission.work_order.status,
            to_status=submission.work_order.status,
            operator_id="DJANGO",
            event_data_json={
                "submission_id": submission.submission_id,
                "webhook_status": submission.webhook_status,
            },
            occurred_at=now,
        )
        return _submission_data(submission)


def _evidence_references(submission):
    return [
        evidence_download_url(submission.submission_id, item.evidence_id)
        for item in submission.evidence.all()
    ]


@transaction.atomic
def apply_report_review(submission_id, payload, *, client_request_id):
    submission = (
        ReportSubmission.objects.select_for_update()
        .select_related("work_order__mold", "work_order__assignee")
        .prefetch_related("evidence")
        .filter(pk=submission_id)
        .first()
    )
    if submission is None:
        raise BusinessError("REPORT_SUBMISSION_NOT_FOUND", "报工提交不存在", status_code=404)
    if submission.status == ReportSubmission.Status.FINALIZED:
        raise BusinessError(
            "REPORT_REVIEW_ALREADY_FINALIZED", "该报工提交已经完成Django裁决", status_code=409
        )
    if submission.status == ReportSubmission.Status.NEEDS_MORE_INFO:
        raise BusinessError(
            "REPORT_REVIEW_NEEDS_NEW_SUBMISSION",
            "该批材料已要求补充信息，请员工重新提交新的文字和图片",
            status_code=409,
        )
    work_order = submission.work_order
    if payload["knowledge_package_hash"] != submission.knowledge_package_hash:
        raise BusinessError(
            "KNOWLEDGE_PACKAGE_HASH_MISMATCH",
            "AI审核使用的知识包哈希与报工提交不一致",
            status_code=409,
        )
    if work_order.knowledge_package_hash != submission.knowledge_package_hash:
        raise BusinessError(
            "KNOWLEDGE_PACKAGE_HASH_MISMATCH",
            "工单知识包已变化，不能应用本次AI审核",
            status_code=409,
        )
    if (
        payload["decision"] != ReportSubmission.ReviewDecision.NEEDS_MORE_INFO
        and payload["confidence"] < settings.MOLDGUARD_AI_REVIEW_MIN_CONFIDENCE
    ):
        raise BusinessError(
            "AI_REVIEW_CONFIDENCE_TOO_LOW",
            "AI审核置信度未达到Django允许自动裁决的阈值",
            status_code=409,
        )

    now = timezone.now()
    submission.review_decision = payload["decision"]
    submission.review_confidence = payload["confidence"]
    submission.review_summary = payload["assessment_summary"]
    submission.review_payload_json = _json_safe(payload)
    submission.reviewed_at = now

    if payload["decision"] == ReportSubmission.ReviewDecision.NEEDS_MORE_INFO:
        submission.status = ReportSubmission.Status.NEEDS_MORE_INFO
        submission.save()
        WorkOrderEvent.objects.create(
            event_id=new_identifier("EVT"),
            work_order=work_order,
            event_type="AI_REPORT_REVIEW_NEEDS_MORE_INFO",
            from_status=work_order.status,
            to_status=work_order.status,
            operator_id="AI_PLATFORM",
            remarks=submission.review_summary,
            event_data_json={
                "submission_id": submission.submission_id,
                "decision": submission.review_decision,
                "confidence": str(submission.review_confidence),
                "reason_codes": payload.get("reason_codes", []),
            },
            request_key=f"report-review:{client_request_id}",
            occurred_at=now,
        )
        result = _submission_data(submission)
        result["assessment_summary"] = submission.review_summary
        return result

    report_type = (
        WorkOrder.ReportType.NORMAL
        if payload["decision"] == ReportSubmission.ReviewDecision.COMPLETE
        else WorkOrder.ReportType.ABNORMAL
    )
    report_payload = {
        "client_request_id": client_request_id,
        "report_type": report_type,
        "report_summary": submission.report_text,
        "inspection_results": payload["inspection_results"],
        "abnormal_items": payload.get("abnormal_items", []),
        "photos": _evidence_references(submission),
        "parts_replaced": submission.parts_replaced_json,
        "source_fault_id": submission.source_fault_id or None,
        "actual_work_hours": submission.actual_work_hours,
        "abnormal_next_action": payload.get("abnormal_next_action"),
        "knowledge_package_hash": submission.knowledge_package_hash,
    }
    serializer = ReportSerializer(data=report_payload)
    serializer.is_valid(raise_exception=True)
    final_data = submit_report(
        work_order.work_order_id,
        serializer.validated_data,
        client_request_id=client_request_id,
    )
    work_order.status = final_data["new_status"]
    submission.status = ReportSubmission.Status.FINALIZED
    submission.final_report_data_json = _json_safe(final_data)
    submission.save()
    WorkOrderEvent.objects.create(
        event_id=new_identifier("EVT"),
        work_order=work_order,
        event_type="AI_REPORT_REVIEW_APPLIED",
        from_status=final_data["old_status"],
        to_status=final_data["new_status"],
        operator_id="AI_PLATFORM",
        remarks=submission.review_summary,
        event_data_json={
            "submission_id": submission.submission_id,
            "decision": submission.review_decision,
            "confidence": str(submission.review_confidence),
            "django_final_status": final_data["new_status"],
            "reason_codes": payload.get("reason_codes", []),
        },
        request_key=f"report-review:{client_request_id}",
        occurred_at=now,
    )
    result = _submission_data(submission)
    result["assessment_summary"] = submission.review_summary
    result["final_report"] = final_data
    return result
