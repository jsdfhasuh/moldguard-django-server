import pytest
from django.core import mail

from apps.common.models import ClientRequestRecord
from apps.workorders.models import WorkOrder, WorkOrderEvent
from tests.helpers import (
    assign_work_order,
    save_knowledge,
    scan_work_order,
    send_assignment_email,
)


def platform_knowledge_payload(client_request_id):
    return {
        "client_request_id": client_request_id,
        "catalog_version": "MOLDGUARD-KB-1.2",
        "items": [
            {
                "knowledge_id": "KB-INJECTION-001",
                "title": "型腔点检",
                "item": "检查模具表面及型腔",
                "knowledge_type": "INSPECTION_STANDARD",
                "content": "清洁后检查模具表面和型腔是否存在异物、损伤或异常。",
                "source": "MOLDGUARD-KB-1.2",
                "required": True,
            }
        ],
    }


@pytest.mark.django_db
def test_knowledge_context_save_and_email_context_share_hash(
    api_client, seeded_demo, knowledge_payload, settings
):
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://moldguard.example.test"
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "knowledge-email")
    assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", "knowledge-email")
    context = api_client.get(f"/api/v1/work-orders/{work_order_id}/knowledge-context")
    context_data = context.data["data"]
    assert context_data["knowledge_snapshot_version"] == "MOLDGUARD-KB-1.2"
    assert context_data["query_keywords"] == [
        "注塑模具保养步骤",
        "注塑模具点检项目",
        "清洁 检查 测量 润滑 紧固 调整 复核 记录",
    ]
    assert context_data["required_knowledge_types"] == [
        "MAINTENANCE_STEPS",
        "INSPECTION_ITEMS",
    ]
    assert context_data["primary_rule_id"] not in context_data["query_keywords"]
    assert context_data["work_order_type"] not in context_data["query_keywords"]
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
    result = send_assignment_email(api_client, work_order_id, "email-lock")
    assert result["knowledge_locked_at"] is not None
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


@pytest.mark.django_db
def test_platform_retrieved_knowledge_package_is_normalized_saved_and_emailed(
    api_client, seeded_demo
):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "platform-knowledge")
    assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", "platform-knowledge")
    payload = platform_knowledge_payload("platform-knowledge-snapshot")

    saved = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/knowledge", payload, format="json"
    )

    assert saved.status_code == 200, saved.data
    work_order = WorkOrder.objects.get(pk=work_order_id)
    package = work_order.knowledge_package_json
    assert package["knowledge_snapshot_version"] == "MOLDGUARD-KB-1.2"
    assert package["title"] == "型腔点检"
    assert package["source_documents"] == ["MOLDGUARD-KB-1.2"]
    assert package["items"][0]["criteria"] == payload["items"][0]["content"]
    assert package["items"][0]["content"] == payload["items"][0]["content"]
    assert package["items"][0]["knowledge_type"] == "INSPECTION_STANDARD"

    send_assignment_email(api_client, work_order_id, "platform-knowledge")
    assert payload["items"][0]["content"] in mail.outbox[0].body


@pytest.mark.django_db
def test_platform_knowledge_package_requires_complete_metadata(api_client, seeded_demo):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "platform-invalid")
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/knowledge",
        {
            "client_request_id": "platform-invalid-snapshot",
            "catalog_version": "MOLDGUARD-KB-1.2",
            "items": [
                {
                    "knowledge_id": "KB-INJECTION-001",
                    "title": "型腔点检",
                    "item": "检查模具表面及型腔",
                    "knowledge_type": "INSPECTION_STANDARD",
                    "source": "MOLDGUARD-KB-1.2",
                    "required": True,
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_canonical_knowledge_package_keeps_its_existing_shape(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "canonical-knowledge")
    save_knowledge(api_client, work_order_id, knowledge_payload, "canonical-knowledge")

    package = WorkOrder.objects.get(pk=work_order_id).knowledge_package_json
    assert package["items"][0] == knowledge_payload["items"][0]
    assert "content" not in package["items"][0]
    assert "knowledge_type" not in package["items"][0]


@pytest.mark.django_db
def test_platform_knowledge_package_requires_json_boolean(api_client, seeded_demo):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "platform-bool")
    payload = platform_knowledge_payload("platform-bool-snapshot")
    payload["items"][0]["required"] = "true"

    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/knowledge", payload, format="json"
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_platform_knowledge_package_replays_and_rejects_changed_payload(api_client, seeded_demo):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "platform-idempotency")
    payload = platform_knowledge_payload("platform-idempotency-snapshot")
    url = f"/api/v1/work-orders/{work_order_id}/knowledge"

    first = api_client.post(url, payload, format="json")
    replay = api_client.post(url, payload, format="json")
    changed = platform_knowledge_payload("platform-idempotency-snapshot")
    changed["items"][0]["content"] = "不同的知识内容"
    conflict = api_client.post(url, changed, format="json")

    assert first.status_code == replay.status_code == 200
    assert first.data["data"]["replayed"] is False
    assert replay.data["data"]["replayed"] is True
    assert conflict.status_code == 409
    assert conflict.data["code"] == "CLIENT_REQUEST_CONFLICT"
    assert ClientRequestRecord.objects.filter(pk="platform-idempotency-snapshot").count() == 1
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=work_order_id,
            event_type="KNOWLEDGE_PACKAGE_SAVED",
        ).count()
        == 1
    )
