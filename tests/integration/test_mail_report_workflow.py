import pytest
from django.test import Client

from apps.workorders.models import WorkOrder
from tests.helpers import assign_work_order, save_knowledge, scan_work_order
from tests.web.test_report_page import html_normal_payload


@pytest.mark.django_db
def test_public_mail_link_html_report_and_whitenoise_contract(
    api_client, seeded_demo, knowledge_payload, settings
):
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://public.moldguard.example"
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "mail-report-integration")
    assignment = assign_work_order(
        api_client, work_order_id, "DEMO-EMP-INJ", "mail-report-integration"
    )
    knowledge = save_knowledge(
        api_client, work_order_id, knowledge_payload, "mail-report-integration"
    )
    assert assignment["report_url"] == f"https://public.moldguard.example/report/{work_order_id}"
    email = api_client.get(f"/api/v1/work-orders/{work_order_id}/email-context")
    assert email.data["data"]["report_url"] == assignment["report_url"]
    assert email.data["data"]["knowledge_package_hash"] == knowledge["knowledge_package_hash"]
    sent = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/email-result",
        {
            "client_request_id": "mail-report-integration-sent",
            "status": "SENT",
            "message_id": "DEMO-MAIL-WEB-001",
            "sent_at": "2026-08-13T18:00:00+08:00",
            "knowledge_package_hash": knowledge["knowledge_package_hash"],
            "error_message": "",
        },
        format="json",
    )
    assert sent.status_code == 200
    locked = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/knowledge",
        {
            "client_request_id": "mail-report-integration-replace",
            **knowledge_payload,
            "title": "邮件发送后不得覆盖",
        },
        format="json",
    )
    assert locked.status_code == 409
    assert locked.data["code"] == "KNOWLEDGE_PACKAGE_LOCKED"

    browser = Client(enforce_csrf_checks=True)
    page = browser.get(f"/report/{work_order_id}")
    content = page.content.decode()
    assert knowledge["knowledge_package_hash"] in content
    csrf_token = page.cookies["csrftoken"].value
    work_order = WorkOrder.objects.get(pk=work_order_id)
    payload = html_normal_payload(work_order, submission_id="mail-report-html-submit")
    payload["csrfmiddlewaretoken"] = csrf_token
    result = browser.post(f"/report/{work_order_id}", payload)
    assert result.status_code == 200
    assert WorkOrder.objects.get(pk=work_order_id).status == WorkOrder.Status.COMPLETED

    assert settings.MIDDLEWARE[0] == "django.middleware.security.SecurityMiddleware"
    assert settings.MIDDLEWARE[1] == "whitenoise.middleware.WhiteNoiseMiddleware"
    assert settings.STORAGES["staticfiles"]["BACKEND"] == (
        "whitenoise.storage.CompressedStaticFilesStorage"
    )
    assert settings.STATICFILES_DIRS == [settings.BASE_DIR / "static"]
    assert settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert settings.USE_X_FORWARDED_HOST is True


@pytest.mark.django_db
def test_email_sent_work_order_rejects_late_email_result_after_report(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "mail-late")
    assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", "mail-late")
    knowledge = save_knowledge(api_client, work_order_id, knowledge_payload, "mail-late")
    from tests.helpers import normal_report_payload

    api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report",
        normal_report_payload("mail-late", knowledge["knowledge_package_hash"]),
        format="json",
    )
    late = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/email-result",
        {
            "client_request_id": "mail-late-result",
            "status": "SENT",
            "message_id": "TOO-LATE",
            "sent_at": "2026-08-13T18:00:00+08:00",
            "knowledge_package_hash": knowledge["knowledge_package_hash"],
            "error_message": "",
        },
        format="json",
    )
    assert late.status_code == 409
    assert late.data["code"] == "INVALID_WORK_ORDER_STATE"
