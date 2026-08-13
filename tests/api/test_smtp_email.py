import smtplib
from datetime import timedelta
from html import escape

import pytest
import yaml
from django.core import mail
from django.db import OperationalError, connection
from django.utils import timezone

from apps.common.idempotency import canonical_hash
from apps.common.models import ClientRequestRecord
from apps.workorders.models import WorkOrder, WorkOrderEvent
from tests.helpers import assign_work_order, save_knowledge, scan_work_order


def prepare_email(api_client, knowledge_payload, suffix):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", suffix)
    assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", suffix)
    knowledge = save_knowledge(api_client, work_order_id, knowledge_payload, suffix)
    return work_order_id, knowledge


@pytest.mark.django_db
def test_send_email_requires_assignment(api_client, seeded_demo):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "smtp-unassigned")
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email",
        {"client_request_id": "smtp-unassigned-send"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "INVALID_WORK_ORDER_STATE"
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_email_requires_knowledge(api_client, seeded_demo):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "smtp-no-knowledge")
    assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", "smtp-no-knowledge")
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email",
        {"client_request_id": "smtp-no-knowledge-send"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "KNOWLEDGE_PACKAGE_REQUIRED"
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_email_requires_assignee_email(api_client, seeded_demo, knowledge_payload):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-no-recipient")
    work_order = WorkOrder.objects.get(pk=work_order_id)
    work_order.assignee.email = ""
    work_order.assignee.save(update_fields=["email"])
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email",
        {"client_request_id": "smtp-no-recipient-send"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "ASSIGNEE_EMAIL_REQUIRED"
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_email_rejects_knowledge_version_drift(api_client, seeded_demo, knowledge_payload):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-version-drift")
    WorkOrder.objects.filter(pk=work_order_id).update(knowledge_snapshot_version="OLD-KB")
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email",
        {"client_request_id": "smtp-version-drift-send"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "KNOWLEDGE_VERSION_MISMATCH"
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_email_rejects_message_injection_fields(api_client, seeded_demo, knowledge_payload):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-injection")
    for field, value in (
        ("recipient", "attacker@example.com"),
        ("subject", "injected subject"),
        ("body", "injected body"),
        ("html_body", "<b>injected</b>"),
        ("from_email", "attacker@example.com"),
    ):
        response = api_client.post(
            f"/api/v1/work-orders/{work_order_id}/send-email",
            {"client_request_id": f"smtp-injection-{field}", field: value},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["code"] == "VALIDATION_ERROR"
        assert field in response.data["errors"]
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_email_uses_assignee_and_renders_text_html_message(
    api_client, seeded_demo, knowledge_payload, settings
):
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://public.moldguard.example"
    settings.DEFAULT_FROM_EMAIL = "MoldGuard <moldguard@example.com>"
    settings.EMAIL_MESSAGE_ID_DOMAIN = "moldguard.example.com"
    payload = {
        **knowledge_payload,
        "title": "DEMO <unsafe> & knowledge",
        "items": [
            {
                **knowledge_payload["items"][0],
                "criteria": "<script>alert('x')</script> & complete",
            },
            knowledge_payload["items"][1],
        ],
    }
    work_order_id, knowledge = prepare_email(api_client, payload, "smtp-content")
    work_order = WorkOrder.objects.get(pk=work_order_id)
    work_order.email_recipient = "stale-recipient@example.com"
    work_order.save(update_fields=["email_recipient"])

    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email",
        {"client_request_id": "smtp-content-send"},
        format="json",
    )
    assert response.status_code == 200
    result = response.data["data"]
    assert result["new_email_status"] == "SENT"
    assert result["email_recipient"] == "demo-injection@example.com"
    assert result["report_url"] == f"https://public.moldguard.example/report/{work_order_id}"
    assert result["knowledge_package_hash"] == knowledge["knowledge_package_hash"]
    assert result["email_message_id"].endswith("@moldguard.example.com>")
    assert len(mail.outbox) == 1

    message = mail.outbox[0]
    assert message.to == ["demo-injection@example.com"]
    assert message.from_email == "MoldGuard <moldguard@example.com>"
    assert message.extra_headers["Message-ID"] == result["email_message_id"]
    assert message.subject == f"MoldGuard保养工单 {work_order_id}"
    assert work_order_id in message.body
    assert "DEMO注塑小吨位模具" in message.body
    assert "INJ-COUNT-050K" in message.body
    assert f"{work_order.standard_hours} 小时" in message.body
    assert "DEMO <unsafe> & knowledge" in message.body
    assert "CHK-INJ-001" in message.body
    assert "配件齐全" not in message.body
    assert knowledge["knowledge_package_hash"] in message.body
    assert result["report_url"] in message.body

    assert len(message.alternatives) == 1
    html_body, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    assert escape("DEMO <unsafe> & knowledge") in html_body
    assert "<script>alert('x')</script>" not in html_body
    assert escape("<script>alert('x')</script> & complete") in html_body
    assert knowledge["knowledge_package_hash"] in html_body
    assert result["report_url"] in html_body
    assert "提交报工情况" in html_body

    work_order.refresh_from_db()
    assert work_order.email_status == WorkOrder.EmailStatus.SENT
    assert work_order.email_recipient == "demo-injection@example.com"
    assert work_order.email_message_id == result["email_message_id"]
    assert work_order.email_sent_at is not None
    assert work_order.email_error == ""
    assert work_order.knowledge_locked_at is not None
    event = WorkOrderEvent.objects.get(work_order_id=work_order_id, event_type="EMAIL_SENT")
    assert event.event_data_json["email_recipient"] == "demo-injection@example.com"
    assert event.event_data_json["knowledge_package_hash"] == knowledge["knowledge_package_hash"]


@pytest.mark.django_db
def test_same_client_request_id_replays_without_resending(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-replay")
    endpoint = f"/api/v1/work-orders/{work_order_id}/send-email"
    payload = {"client_request_id": "smtp-replay-send"}
    first = api_client.post(endpoint, payload, format="json")
    second = api_client.post(endpoint, payload, format="json")
    assert first.status_code == second.status_code == 200
    assert first.data["data"]["replayed"] is False
    assert second.data["data"]["replayed"] is True
    assert first.data["data"]["email_message_id"] == second.data["data"]["email_message_id"]
    assert len(mail.outbox) == 1
    assert ClientRequestRecord.objects.filter(pk="smtp-replay-send").count() == 1
    assert (
        WorkOrderEvent.objects.filter(work_order_id=work_order_id, event_type="EMAIL_SENT").count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
def test_smtp_network_send_runs_after_reservation_transaction_commits(
    api_client, seeded_demo, knowledge_payload, monkeypatch
):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-transaction")
    observations = []

    def confirm_outside_transaction(message, *args, **kwargs):
        record = ClientRequestRecord.objects.get(pk="smtp-transaction-send")
        order = WorkOrder.objects.get(pk=work_order_id)
        observations.append(
            (
                connection.in_atomic_block,
                record.response_status,
                record.response_json,
                order.email_status,
                order.email_message_id,
            )
        )
        return 1

    monkeypatch.setattr(
        "apps.workorders.services.email_service.EmailMultiAlternatives.send",
        confirm_outside_transaction,
    )
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email",
        {"client_request_id": "smtp-transaction-send"},
        format="json",
    )
    assert response.status_code == 200
    assert observations == [
        (
            False,
            102,
            {"state": "IN_PROGRESS"},
            WorkOrder.EmailStatus.SENDING,
            response.data["data"]["email_message_id"],
        )
    ]


@pytest.mark.django_db
def test_in_progress_request_does_not_send_again(api_client, seeded_demo, knowledge_payload):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-in-progress")
    payload = {"client_request_id": "smtp-in-progress-send"}
    ClientRequestRecord.objects.create(
        client_request_id=payload["client_request_id"],
        action="SEND_WORK_ORDER_EMAIL",
        object_id=work_order_id,
        request_hash=canonical_hash("SEND_WORK_ORDER_EMAIL", work_order_id, payload),
        response_status=102,
        response_json={"state": "IN_PROGRESS"},
    )
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email", payload, format="json"
    )
    assert response.status_code == 409
    assert response.data["code"] == "EMAIL_SEND_IN_PROGRESS"
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_stale_in_progress_request_becomes_outcome_unknown(
    api_client, seeded_demo, knowledge_payload, settings
):
    settings.EMAIL_TIMEOUT = 15
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-stale")
    payload = {"client_request_id": "smtp-stale-send"}
    record = ClientRequestRecord.objects.create(
        client_request_id=payload["client_request_id"],
        action="SEND_WORK_ORDER_EMAIL",
        object_id=work_order_id,
        request_hash=canonical_hash("SEND_WORK_ORDER_EMAIL", work_order_id, payload),
        response_status=102,
        response_json={"state": "IN_PROGRESS"},
    )
    ClientRequestRecord.objects.filter(pk=record.pk).update(
        created_at=timezone.now() - timedelta(seconds=21)
    )
    WorkOrder.objects.filter(pk=work_order_id).update(
        email_status=WorkOrder.EmailStatus.SENDING,
        email_message_id="<stale-send@moldguard.example>",
    )

    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email", payload, format="json"
    )
    assert response.status_code == 502
    assert response.data["code"] == "EMAIL_SEND_OUTCOME_UNKNOWN"
    assert len(mail.outbox) == 0
    work_order = WorkOrder.objects.get(pk=work_order_id)
    assert work_order.email_status == WorkOrder.EmailStatus.OUTCOME_UNKNOWN
    assert work_order.email_message_id == "<stale-send@moldguard.example>"
    assert work_order.knowledge_locked_at is not None
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=work_order_id, event_type="EMAIL_OUTCOME_UNKNOWN"
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_sent_email_rejects_new_send_request(api_client, seeded_demo, knowledge_payload):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-already-sent")
    endpoint = f"/api/v1/work-orders/{work_order_id}/send-email"
    first = api_client.post(
        endpoint, {"client_request_id": "smtp-already-sent-first"}, format="json"
    )
    second = api_client.post(
        endpoint, {"client_request_id": "smtp-already-sent-second"}, format="json"
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.data["code"] == "EMAIL_ALREADY_SENT"
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_explicit_smtp_failure_can_retry_with_new_id(
    api_client, seeded_demo, knowledge_payload, monkeypatch
):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-retry")
    endpoint = f"/api/v1/work-orders/{work_order_id}/send-email"
    original_send = mail.EmailMultiAlternatives.send
    calls = []

    def fail_authentication(message, *args, **kwargs):
        calls.append(message)
        raise smtplib.SMTPAuthenticationError(535, b"secret provider response")

    monkeypatch.setattr(
        "apps.workorders.services.email_service.EmailMultiAlternatives.send",
        fail_authentication,
    )
    failed = api_client.post(endpoint, {"client_request_id": "smtp-retry-failed"}, format="json")
    assert failed.status_code == 502
    assert failed.data["code"] == "EMAIL_SEND_FAILED"
    assert failed.data["errors"]["email_status"] == "FAILED"
    assert failed.data["errors"]["email_error"] == "SMTP authentication failed"
    assert "secret provider response" not in str(failed.data)
    work_order = WorkOrder.objects.get(pk=work_order_id)
    assert work_order.email_status == WorkOrder.EmailStatus.FAILED
    assert work_order.email_sent_at is None
    assert work_order.knowledge_locked_at is None
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=work_order_id, event_type="EMAIL_FAILED"
        ).count()
        == 1
    )

    monkeypatch.setattr(
        "apps.workorders.services.email_service.EmailMultiAlternatives.send", original_send
    )
    sent = api_client.post(endpoint, {"client_request_id": "smtp-retry-success"}, format="json")
    assert sent.status_code == 200
    assert sent.data["data"]["old_email_status"] == "FAILED"
    assert sent.data["data"]["new_email_status"] == "SENT"
    assert len(calls) == 1
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_uncertain_smtp_outcome_is_not_automatically_retried(
    api_client, seeded_demo, knowledge_payload, monkeypatch
):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-unknown")
    endpoint = f"/api/v1/work-orders/{work_order_id}/send-email"

    def disconnect_after_send_started(message, *args, **kwargs):
        raise smtplib.SMTPServerDisconnected("connection lost after DATA")

    monkeypatch.setattr(
        "apps.workorders.services.email_service.EmailMultiAlternatives.send",
        disconnect_after_send_started,
    )
    first = api_client.post(endpoint, {"client_request_id": "smtp-unknown-first"}, format="json")
    same_id = api_client.post(endpoint, {"client_request_id": "smtp-unknown-first"}, format="json")
    new_id = api_client.post(endpoint, {"client_request_id": "smtp-unknown-second"}, format="json")
    assert first.status_code == same_id.status_code == 502
    assert first.data["code"] == same_id.data["code"] == "EMAIL_SEND_OUTCOME_UNKNOWN"
    assert new_id.status_code == 409
    assert new_id.data["code"] == "EMAIL_SEND_OUTCOME_UNKNOWN"
    work_order = WorkOrder.objects.get(pk=work_order_id)
    assert work_order.email_status == WorkOrder.EmailStatus.OUTCOME_UNKNOWN
    assert work_order.email_message_id
    assert work_order.email_sent_at is None
    assert work_order.knowledge_locked_at is not None
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=work_order_id, event_type="EMAIL_OUTCOME_UNKNOWN"
        ).count()
        == 1
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "send_exception",
    [
        smtplib.SMTPResponseException(451, b"provider response must stay private"),
        RuntimeError("custom backend failed after accepting the message"),
    ],
    ids=["unclassified-smtp-response", "unclassified-backend-error"],
)
def test_unclassified_send_exception_is_outcome_unknown(
    api_client, seeded_demo, knowledge_payload, monkeypatch, send_exception
):
    suffix = type(send_exception).__name__.lower()
    work_order_id, _ = prepare_email(api_client, knowledge_payload, suffix)
    endpoint = f"/api/v1/work-orders/{work_order_id}/send-email"

    def raise_unclassified_exception(message, *args, **kwargs):
        raise send_exception

    monkeypatch.setattr(
        "apps.workorders.services.email_service.EmailMultiAlternatives.send",
        raise_unclassified_exception,
    )
    response = api_client.post(
        endpoint,
        {"client_request_id": f"{suffix}-send"},
        format="json",
    )

    assert response.status_code == 502
    assert response.data["code"] == "EMAIL_SEND_OUTCOME_UNKNOWN"
    assert "provider response" not in str(response.data)
    work_order = WorkOrder.objects.get(pk=work_order_id)
    assert work_order.email_status == WorkOrder.EmailStatus.OUTCOME_UNKNOWN
    assert work_order.email_message_id
    assert work_order.knowledge_locked_at is not None


@pytest.mark.django_db
@pytest.mark.parametrize("sent_count", [0, 2])
def test_nonstandard_backend_send_count_is_outcome_unknown(
    api_client, seeded_demo, knowledge_payload, monkeypatch, sent_count
):
    work_order_id, _ = prepare_email(api_client, knowledge_payload, f"smtp-count-{sent_count}")
    endpoint = f"/api/v1/work-orders/{work_order_id}/send-email"
    monkeypatch.setattr(
        "apps.workorders.services.email_service.EmailMultiAlternatives.send",
        lambda *args, **kwargs: sent_count,
    )

    response = api_client.post(
        endpoint,
        {"client_request_id": f"smtp-count-{sent_count}-send"},
        format="json",
    )

    assert response.status_code == 502
    assert response.data["code"] == "EMAIL_SEND_OUTCOME_UNKNOWN"
    work_order = WorkOrder.objects.get(pk=work_order_id)
    assert work_order.email_status == WorkOrder.EmailStatus.OUTCOME_UNKNOWN
    assert work_order.knowledge_locked_at is not None


@pytest.mark.django_db
def test_sent_finalize_replays_sent_if_commit_result_was_unknown(
    api_client, seeded_demo, knowledge_payload, monkeypatch
):
    from apps.workorders.services import email_service

    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-finalize-replay")
    endpoint = f"/api/v1/work-orders/{work_order_id}/send-email"
    actual_finalize = email_service._finalize
    outcomes = []

    def commit_then_report_failure(*args, **kwargs):
        outcomes.append(kwargs["outcome"])
        result = actual_finalize(*args, **kwargs)
        if len(outcomes) == 1:
            raise OperationalError("commit acknowledgement lost")
        return result

    monkeypatch.setattr(email_service, "_finalize", commit_then_report_failure)
    response = api_client.post(
        endpoint,
        {"client_request_id": "smtp-finalize-replay-send"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["new_email_status"] == "SENT"
    assert outcomes == ["SENT", "OUTCOME_UNKNOWN"]
    assert len(mail.outbox) == 1
    assert (
        WorkOrderEvent.objects.filter(work_order_id=work_order_id, event_type="EMAIL_SENT").count()
        == 1
    )
    assert not WorkOrderEvent.objects.filter(
        work_order_id=work_order_id, event_type="EMAIL_OUTCOME_UNKNOWN"
    ).exists()


@pytest.mark.django_db
def test_sent_finalize_rollback_converges_to_outcome_unknown(
    api_client, seeded_demo, knowledge_payload, monkeypatch
):
    from apps.workorders.services import email_service

    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-finalize-rollback")
    endpoint = f"/api/v1/work-orders/{work_order_id}/send-email"
    actual_complete_send = email_service._complete_send
    outcomes = []

    def fail_only_sent_completion(*args, **kwargs):
        outcomes.append(kwargs["outcome"])
        if kwargs["outcome"] == "SENT":
            raise OperationalError("sent transaction rolled back")
        return actual_complete_send(*args, **kwargs)

    monkeypatch.setattr(email_service, "_complete_send", fail_only_sent_completion)
    response = api_client.post(
        endpoint,
        {"client_request_id": "smtp-finalize-rollback-send"},
        format="json",
    )

    assert response.status_code == 502
    assert response.data["code"] == "EMAIL_SEND_OUTCOME_UNKNOWN"
    assert outcomes == ["SENT", "OUTCOME_UNKNOWN"]
    assert len(mail.outbox) == 1
    work_order = WorkOrder.objects.get(pk=work_order_id)
    assert work_order.email_status == WorkOrder.EmailStatus.OUTCOME_UNKNOWN
    assert work_order.email_message_id
    assert work_order.knowledge_locked_at is not None
    assert not WorkOrderEvent.objects.filter(
        work_order_id=work_order_id, event_type="EMAIL_SENT"
    ).exists()
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=work_order_id,
            event_type="EMAIL_OUTCOME_UNKNOWN",
        ).count()
        == 1
    )
    record = ClientRequestRecord.objects.get(pk="smtp-finalize-rollback-send")
    assert record.response_status == 502
    assert record.response_json["code"] == "EMAIL_SEND_OUTCOME_UNKNOWN"


@pytest.mark.django_db
def test_persistence_failure_after_send_returns_stable_outcome_unknown(
    api_client, seeded_demo, knowledge_payload, monkeypatch
):
    from apps.workorders.services import email_service

    work_order_id, _ = prepare_email(api_client, knowledge_payload, "smtp-finalize-fails")
    endpoint = f"/api/v1/work-orders/{work_order_id}/send-email"
    outcomes = []

    def fail_finalize(*args, **kwargs):
        outcomes.append(kwargs["outcome"])
        raise OperationalError("database unavailable")

    monkeypatch.setattr(email_service, "_finalize", fail_finalize)
    response = api_client.post(
        endpoint,
        {"client_request_id": "smtp-finalize-fails-send"},
        format="json",
    )

    assert response.status_code == 502
    assert response.data["code"] == "EMAIL_SEND_OUTCOME_UNKNOWN"
    assert response.data["errors"]["email_status"] == "OUTCOME_UNKNOWN"
    assert outcomes == ["SENT", "OUTCOME_UNKNOWN"]
    assert len(mail.outbox) == 1
    work_order = WorkOrder.objects.get(pk=work_order_id)
    assert work_order.email_status == WorkOrder.EmailStatus.SENDING
    record = ClientRequestRecord.objects.get(pk="smtp-finalize-fails-send")
    assert record.response_status == 102
    assert record.response_json == {"state": "IN_PROGRESS"}
    assert not WorkOrderEvent.objects.filter(
        work_order_id=work_order_id,
        event_type__in=["EMAIL_SENT", "EMAIL_OUTCOME_UNKNOWN"],
    ).exists()


@pytest.mark.django_db
def test_email_result_is_not_a_public_route_or_schema(
    api_client, seeded_demo, django_assert_num_queries
):
    with django_assert_num_queries(0):
        response = api_client.post(
            "/api/v1/work-orders/WO-NOT-USED/email-result",
            {"client_request_id": "forged-result", "status": "SENT"},
            format="json",
        )
    assert response.status_code == 404
    schema = api_client.get("/api/schema")
    assert schema.status_code == 200
    content = schema.content.decode()
    assert "/email-result" not in content
    assert "/send-email" in content
    document = yaml.safe_load(content)
    responses = document["paths"]["/api/v1/work-orders/{work_order_id}/send-email"]["post"][
        "responses"
    ]
    assert {"200", "400", "404", "409", "502"} <= set(responses)
