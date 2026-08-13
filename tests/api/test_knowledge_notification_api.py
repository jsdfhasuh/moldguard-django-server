import pytest
from django.core.management import call_command

from apps.platform_probe.models import KnowledgeSnapshot, MaintenanceAlert, NotificationReceipt


@pytest.fixture
def assigned_work_order(db, api_client):
    call_command("seed_probe_data", verbosity=0)
    api_client.post("/api/v1/alerts/scan", {}, format="json")
    alert = MaintenanceAlert.objects.get(
        mold_id="MOLD-TEST-001",
        alert_type=MaintenanceAlert.AlertType.MAINTENANCE_DUE,
    )
    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "create-knowledge"},
        format="json",
    )
    work_order_id = created.data["data"]["work_order_id"]
    api_client.post(
        f"/api/v1/work-orders/{work_order_id}/assign",
        {"employee_id": "EMP-001", "client_request_id": "assign-knowledge"},
        format="json",
    )
    return work_order_id


@pytest.mark.django_db
def test_knowledge_context_has_search_inputs(assigned_work_order, api_client):
    response = api_client.get(f"/api/v1/work-orders/{assigned_work_order}/knowledge-context")

    assert response.status_code == 200
    data = response.data["data"]
    assert data["mold_type"] == "INJECTION"
    assert data["rule_id"] == "MAINT_TRIGGER_TONNAGE_V1"
    assert data["knowledge_profile_code"] == "INJECTION_PERIODIC_MAINTENANCE"
    assert data["required_types"] == [
        "MAINTENANCE_STANDARD",
        "INSPECTION_STANDARD",
        "SAFETY",
    ]


@pytest.mark.django_db
def test_knowledge_snapshot_saves_nested_item_array(assigned_work_order, api_client):
    payload = {
        "catalog_version": "KB-DEMO-V1",
        "items": [
            {
                "knowledge_id": "KB-INJECTION-001",
                "title": "型腔点检",
                "item": "检查模具表面及型腔",
                "knowledge_type": "INSPECTION_STANDARD",
                "content": "清洁后检查表面和型腔",
                "source": "competition-demo-knowledge-base",
                "required": True,
            },
            {
                "knowledge_id": "KB-INJECTION-002",
                "item": "检查冷却水路",
                "knowledge_type": "INSPECTION_STANDARD",
                "required": True,
            },
        ],
        "client_request_id": "snapshot-001",
    }

    response = api_client.post(
        f"/api/v1/work-orders/{assigned_work_order}/knowledge-snapshot",
        payload,
        format="json",
    )

    assert response.status_code == 201
    assert len(response.data["data"]["items"]) == 2
    snapshot = KnowledgeSnapshot.objects.get(work_order_id=assigned_work_order)
    assert snapshot.items_json[1]["knowledge_id"] == "KB-INJECTION-002"


@pytest.mark.django_db
def test_email_context_requires_snapshot_and_only_targets_assignee(assigned_work_order, api_client):
    url = f"/api/v1/work-orders/{assigned_work_order}/email-context"

    before = api_client.get(url)
    api_client.post(
        f"/api/v1/work-orders/{assigned_work_order}/knowledge-snapshot",
        {
            "catalog_version": "KB-DEMO-V1",
            "items": [
                {
                    "knowledge_id": "KB-INJECTION-001",
                    "item": "检查型腔",
                    "required": True,
                }
            ],
            "client_request_id": "snapshot-email",
        },
        format="json",
    )
    after = api_client.get(url)

    assert before.status_code == 409
    assert before.data["code"] == "KNOWLEDGE_SNAPSHOT_REQUIRED"
    assert after.status_code == 200
    assert after.data["data"]["to"] == ["maintainer-injection@example.com"]
    assert "cc" not in after.data["data"]
    assert "supervisor" not in str(after.data).lower()
    assert after.data["data"]["template_variables"]["trigger_threshold"] == 50_000


@pytest.mark.django_db
def test_notification_receipts_record_success_and_failure(assigned_work_order, api_client):
    url = f"/api/v1/work-orders/{assigned_work_order}/notifications"
    sent = api_client.post(
        url,
        {
            "status": "SENT",
            "message_id": "message-001",
            "sent_at": "2026-08-13T15:00:00+08:00",
            "client_request_id": "notify-sent",
        },
        format="json",
    )
    failed = api_client.post(
        url,
        {
            "status": "FAILED",
            "error_message": "测试邮件平台暂时不可用",
            "client_request_id": "notify-failed",
        },
        format="json",
    )

    assert sent.status_code == 201
    assert sent.data["data"]["recipient"] == "maintainer-injection@example.com"
    assert failed.status_code == 201
    assert failed.data["data"]["error_message"] == "测试邮件平台暂时不可用"
    assert NotificationReceipt.objects.filter(work_order_id=assigned_work_order).count() == 2


@pytest.mark.django_db
def test_notification_rejects_non_assignee_recipient(assigned_work_order, api_client):
    response = api_client.post(
        f"/api/v1/work-orders/{assigned_work_order}/notifications",
        {
            "recipient": "some-supervisor@example.com",
            "status": "SENT",
            "message_id": "message-wrong-recipient",
            "client_request_id": "notify-wrong",
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.data["code"] == "EMPLOYEE_NOT_ASSIGNED"
    assert NotificationReceipt.objects.count() == 0


@pytest.mark.django_db
def test_unassigned_work_order_cannot_use_knowledge_or_email(api_client, db):
    call_command("seed_probe_data", verbosity=0)
    api_client.post("/api/v1/alerts/scan", {}, format="json")
    alert = MaintenanceAlert.objects.get(
        mold_id="MOLD-TEST-002",
        alert_type=MaintenanceAlert.AlertType.MAINTENANCE_DUE,
    )
    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "create-unassigned"},
        format="json",
    )
    work_order_id = created.data["data"]["work_order_id"]

    knowledge = api_client.get(f"/api/v1/work-orders/{work_order_id}/knowledge-context")
    email = api_client.get(f"/api/v1/work-orders/{work_order_id}/email-context")

    assert knowledge.data["code"] == "EMPLOYEE_NOT_ASSIGNED"
    assert email.data["code"] == "EMPLOYEE_NOT_ASSIGNED"
