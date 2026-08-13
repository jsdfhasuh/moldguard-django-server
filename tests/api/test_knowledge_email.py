import pytest

from apps.workorders.models import WorkOrder
from tests.helpers import assign_work_order, save_knowledge, scan_work_order


@pytest.mark.django_db
def test_knowledge_context_save_and_email_context_share_hash(
    api_client, seeded_demo, knowledge_payload, settings
):
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://moldguard.example.test"
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "knowledge-email")
    assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", "knowledge-email")
    context = api_client.get(f"/api/v1/work-orders/{work_order_id}/knowledge-context")
    assert context.data["data"]["knowledge_snapshot_version"] == "MOLDGUARD-KB-1.2"
    saved = save_knowledge(api_client, work_order_id, knowledge_payload, "knowledge-email")
    email = api_client.get(f"/api/v1/work-orders/{work_order_id}/email-context")
    assert email.status_code == 200
    assert email.data["data"]["knowledge_package_hash"] == saved["knowledge_package_hash"]
    assert email.data["data"]["report_url"] == (
        f"https://moldguard.example.test/report/{work_order_id}"
    )


@pytest.mark.django_db
def test_sent_email_locks_knowledge_package(api_client, seeded_demo, knowledge_payload):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "email-lock")
    assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", "email-lock")
    saved = save_knowledge(api_client, work_order_id, knowledge_payload, "email-lock")
    result = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/email-result",
        {
            "client_request_id": "email-result-sent",
            "status": "SENT",
            "message_id": "DEMO-MAIL-001",
            "sent_at": "2026-08-13T16:00:00+08:00",
            "knowledge_package_hash": saved["knowledge_package_hash"],
            "error_message": "",
        },
        format="json",
    )
    assert result.status_code == 200
    assert result.data["data"]["new_email_status"] == "SENT"
    assert result.data["data"]["knowledge_locked_at"] is not None
    replacement = {
        "client_request_id": "knowledge-after-sent",
        **knowledge_payload,
        "title": "不应覆盖的知识包",
    }
    locked = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/knowledge", replacement, format="json"
    )
    assert locked.status_code == 409
    assert locked.data["code"] == "KNOWLEDGE_PACKAGE_LOCKED"
    assert (
        WorkOrder.objects.get(pk=work_order_id).knowledge_package_hash
        == saved["knowledge_package_hash"]
    )
