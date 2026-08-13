import pytest
from django.core import mail
from django.test import Client

from apps.workorders.models import WorkOrder
from tests.helpers import assign_work_order, save_knowledge, scan_work_order
from tests.web.test_report_page import html_normal_payload


@pytest.mark.django_db
def test_django_smtp_mail_link_completes_html_report_workflow(
    api_client, seeded_demo, knowledge_payload, settings
):
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://mail-flow.moldguard.example"
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "smtp-mail-report")
    assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", "smtp-mail-report")
    knowledge = save_knowledge(api_client, work_order_id, knowledge_payload, "smtp-mail-report")

    sent = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email",
        {"client_request_id": "smtp-mail-report-send"},
        format="json",
    )
    assert sent.status_code == 200
    assert len(mail.outbox) == 1
    report_url = sent.data["data"]["report_url"]
    assert report_url == f"https://mail-flow.moldguard.example/report/{work_order_id}"
    assert report_url in mail.outbox[0].body
    assert knowledge["knowledge_package_hash"] in mail.outbox[0].body

    browser = Client(enforce_csrf_checks=True)
    page = browser.get(f"/report/{work_order_id}")
    assert page.status_code == 200
    assert knowledge["knowledge_package_hash"] in page.content.decode()
    csrf_token = page.cookies["csrftoken"].value
    work_order = WorkOrder.objects.get(pk=work_order_id)
    payload = html_normal_payload(work_order, submission_id="smtp-mail-report-submit")
    payload["csrfmiddlewaretoken"] = csrf_token
    completed = browser.post(f"/report/{work_order_id}", payload)
    assert completed.status_code == 200
    assert "报工已完成" in completed.content.decode()
    work_order.refresh_from_db()
    assert work_order.status == WorkOrder.Status.COMPLETED
    assert work_order.email_status == WorkOrder.EmailStatus.SENT
    assert work_order.email_message_id == sent.data["data"]["email_message_id"]
