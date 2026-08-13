import logging
import smtplib
import socket
from email.utils import make_msgid

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.common.exceptions import BusinessError
from apps.common.idempotency import finalize_external_request, reserve_external_request
from apps.common.identifiers import new_identifier
from apps.common.responses import success_payload
from apps.workorders.models import WorkOrder, WorkOrderEvent
from apps.workorders.services.presentation import report_url

logger = logging.getLogger("moldguard.email")

SEND_EMAIL_ACTION = "SEND_WORK_ORDER_EMAIL"

_EXPLICIT_FAILURES = (
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPRecipientsRefused,
    smtplib.SMTPSenderRefused,
    smtplib.SMTPDataError,
    smtplib.SMTPHeloError,
    smtplib.SMTPNotSupportedError,
    smtplib.SMTPConnectError,
    ConnectionRefusedError,
    socket.gaierror,
)


def _error_payload(code, message, *, current_request_id):
    return {
        "code": code,
        "message": message,
        "data": None,
        "request_id": current_request_id,
    }


def _validate_send_preconditions(work_order):
    if not work_order.assignee_id:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "工单尚未派工", status_code=409)
    if not work_order.assignee.email:
        raise BusinessError("ASSIGNEE_EMAIL_REQUIRED", "被派工人员未配置邮箱", status_code=409)
    if not work_order.knowledge_package_json or not work_order.knowledge_package_hash:
        raise BusinessError("KNOWLEDGE_PACKAGE_REQUIRED", "请先保存知识包", status_code=409)
    if work_order.knowledge_snapshot_version != settings.MOLDGUARD_KNOWLEDGE_VERSION:
        raise BusinessError(
            "KNOWLEDGE_VERSION_MISMATCH",
            f"知识版本必须为{settings.MOLDGUARD_KNOWLEDGE_VERSION}",
            status_code=409,
        )
    if work_order.reported_at is not None:
        raise BusinessError("INVALID_WORK_ORDER_STATE", "工单已报工，不能发送邮件", status_code=409)
    if work_order.email_status == WorkOrder.EmailStatus.SENT:
        raise BusinessError("EMAIL_ALREADY_SENT", "派工邮件已经发送", status_code=409)
    if work_order.email_status == WorkOrder.EmailStatus.SENDING:
        raise BusinessError("EMAIL_SEND_IN_PROGRESS", "派工邮件正在发送", status_code=409)
    if work_order.email_status == WorkOrder.EmailStatus.OUTCOME_UNKNOWN:
        raise BusinessError(
            "EMAIL_SEND_OUTCOME_UNKNOWN",
            "上次邮件发送结果无法确认，禁止自动重发",
            status_code=409,
        )


def _email_template_context(work_order):
    return {
        "work_order": work_order,
        "mold": work_order.mold,
        "assignee": work_order.assignee,
        "knowledge_package": work_order.knowledge_package_json,
        "knowledge_items": work_order.knowledge_package_json.get("items", []),
        "safety_notes": work_order.knowledge_package_json.get("safety_notes", []),
        "knowledge_snapshot_version": work_order.knowledge_snapshot_version,
        "knowledge_package_hash": work_order.knowledge_package_hash,
        "report_url": report_url(work_order),
        "report_button_text": "提交报工情况",
    }


def _reserve_work_order(work_order_id, client_request_id):
    try:
        work_order = (
            WorkOrder.objects.select_for_update()
            .select_related("assignee", "mold")
            .get(pk=work_order_id)
        )
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None

    _validate_send_preconditions(work_order)
    previous_status = work_order.email_status
    work_order.email_status = WorkOrder.EmailStatus.SENDING
    work_order.email_recipient = work_order.assignee.email
    work_order.email_message_id = ""
    work_order.email_sent_at = None
    work_order.email_error = ""
    work_order.save(
        update_fields=[
            "email_status",
            "email_recipient",
            "email_message_id",
            "email_sent_at",
            "email_error",
            "updated_at",
        ]
    )
    return {
        "work_order_id": work_order.work_order_id,
        "previous_email_status": previous_status,
        "recipient": work_order.assignee.email,
        "subject": work_order.email_subject,
        "template_context": _email_template_context(work_order),
    }


@transaction.atomic
def _save_reserved_message_id(work_order_id, message_id):
    work_order = WorkOrder.objects.select_for_update().get(pk=work_order_id)
    if work_order.email_status != WorkOrder.EmailStatus.SENDING:
        raise BusinessError(
            "EMAIL_SEND_OUTCOME_UNKNOWN",
            "邮件发送占位状态发生变化，禁止继续发送",
            status_code=409,
        )
    work_order.email_message_id = message_id
    work_order.save(update_fields=["email_message_id", "updated_at"])


def _safe_failure_message(exc, *, outcome_unknown):
    if outcome_unknown:
        return "SMTP delivery outcome could not be confirmed"
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "SMTP authentication failed"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "SMTP recipient rejected"
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return "SMTP sender rejected"
    if isinstance(exc, smtplib.SMTPDataError):
        return "SMTP message rejected"
    if isinstance(exc, smtplib.SMTPHeloError):
        return "SMTP greeting rejected"
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return "SMTP capability not supported"
    if isinstance(exc, ConnectionRefusedError | socket.gaierror):
        return "SMTP connection failed"
    return "Email delivery failed"


def _result_data(work_order, *, previous_email_status):
    return {
        "work_order_id": work_order.work_order_id,
        "old_email_status": previous_email_status,
        "new_email_status": work_order.email_status,
        "email_message_id": work_order.email_message_id,
        "email_sent_at": work_order.email_sent_at.isoformat() if work_order.email_sent_at else None,
        "email_recipient": work_order.email_recipient,
        "knowledge_snapshot_version": work_order.knowledge_snapshot_version,
        "knowledge_package_hash": work_order.knowledge_package_hash,
        "knowledge_locked_at": work_order.knowledge_locked_at.isoformat()
        if work_order.knowledge_locked_at
        else None,
        "report_url": report_url(work_order),
    }


def _complete_send(
    work_order_id,
    *,
    client_request_id,
    previous_email_status,
    outcome,
    message_id,
    failure_message="",
    current_request_id,
):
    work_order = (
        WorkOrder.objects.select_for_update()
        .select_related("assignee", "mold")
        .get(pk=work_order_id)
    )
    now = timezone.now()
    if outcome == "SENT":
        work_order.email_status = WorkOrder.EmailStatus.SENT
        work_order.email_message_id = message_id
        work_order.email_sent_at = now
        work_order.email_error = ""
        work_order.knowledge_locked_at = now
        event_type = "EMAIL_SENT"
        status_code = 200
    elif outcome == "FAILED":
        work_order.email_status = WorkOrder.EmailStatus.FAILED
        work_order.email_message_id = ""
        work_order.email_sent_at = None
        work_order.email_error = failure_message
        work_order.knowledge_locked_at = None
        event_type = "EMAIL_FAILED"
        status_code = 502
    else:
        work_order.email_status = WorkOrder.EmailStatus.OUTCOME_UNKNOWN
        work_order.email_message_id = message_id
        work_order.email_sent_at = None
        work_order.email_error = failure_message
        work_order.knowledge_locked_at = now
        event_type = "EMAIL_OUTCOME_UNKNOWN"
        status_code = 502
    work_order.save(
        update_fields=[
            "email_status",
            "email_message_id",
            "email_sent_at",
            "email_error",
            "knowledge_locked_at",
            "updated_at",
        ]
    )
    WorkOrderEvent.objects.create(
        event_id=new_identifier("EVT"),
        work_order=work_order,
        event_type=event_type,
        event_data_json={
            "from_email_status": previous_email_status,
            "to_email_status": work_order.email_status,
            "email_message_id": work_order.email_message_id,
            "email_recipient": work_order.email_recipient,
            "knowledge_package_hash": work_order.knowledge_package_hash,
        },
        request_key=f"send-email:{client_request_id}",
        occurred_at=now,
    )
    data = _result_data(work_order, previous_email_status=previous_email_status)
    if outcome == "SENT":
        return status_code, success_payload(data, "派工邮件已发送")
    code = "EMAIL_SEND_FAILED" if outcome == "FAILED" else "EMAIL_SEND_OUTCOME_UNKNOWN"
    message = "派工邮件发送失败" if outcome == "FAILED" else "邮件发送结果无法确认"
    response = _error_payload(code, message, current_request_id=current_request_id)
    response["errors"] = {
        "email_status": work_order.email_status,
        "email_error": work_order.email_error,
    }
    return status_code, response


def _finalize(
    reservation,
    *,
    work_order_id,
    outcome,
    message_id,
    failure_message,
    current_request_id,
):
    return finalize_external_request(
        request_id=reservation["request_id"],
        action=SEND_EMAIL_ACTION,
        object_id=work_order_id,
        request_hash=reservation["request_hash"],
        current_request_id=current_request_id,
        completion_operation=lambda: _complete_send(
            work_order_id,
            client_request_id=reservation["request_id"],
            previous_email_status=reservation["reservation"]["previous_email_status"],
            outcome=outcome,
            message_id=message_id,
            failure_message=failure_message,
            current_request_id=current_request_id,
        ),
    )


def _unpersisted_outcome_unknown_response(*, current_request_id):
    response = _error_payload(
        "EMAIL_SEND_OUTCOME_UNKNOWN",
        "邮件发送结果无法确认",
        current_request_id=current_request_id,
    )
    response["errors"] = {
        "email_status": WorkOrder.EmailStatus.OUTCOME_UNKNOWN,
        "email_error": "SMTP delivery outcome could not be confirmed",
    }
    return 502, response


def _finalize_outcome_unknown_safely(
    reservation,
    *,
    work_order_id,
    message_id,
    failure_message,
    current_request_id,
):
    try:
        return _finalize(
            reservation,
            work_order_id=work_order_id,
            outcome="OUTCOME_UNKNOWN",
            message_id=message_id,
            failure_message=failure_message,
            current_request_id=current_request_id,
        )
    except Exception:
        logger.exception("email outcome-unknown persistence failed work_order_id=%s", work_order_id)
        return _unpersisted_outcome_unknown_response(current_request_id=current_request_id)


def _recover_stale_reservation(reservation, *, work_order_id, current_request_id):
    age_seconds = (timezone.now() - reservation["created_at"]).total_seconds()
    if age_seconds <= settings.EMAIL_TIMEOUT + 5:
        return 409, _error_payload(
            "EMAIL_SEND_IN_PROGRESS",
            "相同client_request_id的邮件正在发送",
            current_request_id=current_request_id,
        )
    try:
        work_order = WorkOrder.objects.only("email_message_id").get(pk=work_order_id)
    except WorkOrder.DoesNotExist:
        raise BusinessError("WORK_ORDER_NOT_FOUND", "工单不存在", status_code=404) from None
    recovered = {
        **reservation,
        "reservation": {"previous_email_status": WorkOrder.EmailStatus.SENDING},
    }
    return _finalize_outcome_unknown_safely(
        recovered,
        work_order_id=work_order_id,
        message_id=work_order.email_message_id,
        failure_message="SMTP delivery outcome could not be confirmed",
        current_request_id=current_request_id,
    )


def send_work_order_email(work_order_id, payload, *, current_request_id):
    reservation = reserve_external_request(
        action=SEND_EMAIL_ACTION,
        object_id=work_order_id,
        payload=payload,
        current_request_id=current_request_id,
        reservation_operation=lambda client_request_id: _reserve_work_order(
            work_order_id, client_request_id
        ),
    )
    if reservation["state"] == "REPLAY":
        return reservation["status_code"], reservation["response"]
    if reservation["state"] == "IN_PROGRESS":
        return _recover_stale_reservation(
            reservation,
            work_order_id=work_order_id,
            current_request_id=current_request_id,
        )

    reserved = reservation["reservation"]
    message_id = make_msgid(domain=settings.EMAIL_MESSAGE_ID_DOMAIN)
    try:
        _save_reserved_message_id(work_order_id, message_id)
        text_body = render_to_string(
            "emails/work_order_assignment.txt", reserved["template_context"]
        )
        html_body = render_to_string(
            "emails/work_order_assignment.html", reserved["template_context"]
        )
        message = EmailMultiAlternatives(
            subject=reserved["subject"],
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[reserved["recipient"]],
            headers={"Message-ID": message_id},
        )
        message.attach_alternative(html_body, "text/html")
    except Exception as exc:
        logger.exception("email rendering failed work_order_id=%s", work_order_id)
        return _finalize(
            reservation,
            work_order_id=work_order_id,
            outcome="FAILED",
            message_id="",
            failure_message=_safe_failure_message(exc, outcome_unknown=False),
            current_request_id=current_request_id,
        )

    try:
        sent_count = message.send(fail_silently=False)
    except _EXPLICIT_FAILURES as exc:
        logger.warning(
            "explicit email delivery failure work_order_id=%s error_type=%s",
            work_order_id,
            type(exc).__name__,
        )
        return _finalize(
            reservation,
            work_order_id=work_order_id,
            outcome="FAILED",
            message_id="",
            failure_message=_safe_failure_message(exc, outcome_unknown=False),
            current_request_id=current_request_id,
        )
    except Exception as exc:
        logger.warning(
            "email delivery outcome unknown work_order_id=%s error_type=%s",
            work_order_id,
            type(exc).__name__,
        )
        return _finalize_outcome_unknown_safely(
            reservation,
            work_order_id=work_order_id,
            message_id=message_id,
            failure_message=_safe_failure_message(exc, outcome_unknown=True),
            current_request_id=current_request_id,
        )

    if sent_count != 1:
        return _finalize_outcome_unknown_safely(
            reservation,
            work_order_id=work_order_id,
            message_id=message_id,
            failure_message="SMTP delivery outcome could not be confirmed",
            current_request_id=current_request_id,
        )

    try:
        return _finalize(
            reservation,
            work_order_id=work_order_id,
            outcome="SENT",
            message_id=message_id,
            failure_message="",
            current_request_id=current_request_id,
        )
    except Exception:
        logger.exception("email sent but result persistence failed work_order_id=%s", work_order_id)
        return _finalize_outcome_unknown_safely(
            reservation,
            work_order_id=work_order_id,
            message_id=message_id,
            failure_message="SMTP delivery outcome could not be confirmed",
            current_request_id=current_request_id,
        )
