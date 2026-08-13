from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.platform_probe.models import (
    AbnormalReport,
    MaintenanceAlert,
    MaintenanceHistory,
    Mold,
    WorkOrder,
)

KNOWLEDGE = {
    "INJECTION": [
        {
            "knowledge_id": "KB-INJECTION-001",
            "item": "检查模具表面及型腔",
            "required": True,
        },
        {
            "knowledge_id": "KB-INJECTION-002",
            "item": "检查冷却水路",
            "required": True,
        },
    ],
    "SHEET_METAL": [
        {
            "knowledge_id": "KB-SHEET-001",
            "item": "检查刃口和导向部件",
            "required": True,
        },
        {
            "knowledge_id": "KB-SHEET-002",
            "item": "检查润滑与紧固状态",
            "required": True,
        },
    ],
}


def request_id(label):
    return f"integration-{label}"


def create_assign_and_enrich(api_client, mold_id):
    alert = MaintenanceAlert.objects.get(
        mold_id=mold_id,
        alert_type=MaintenanceAlert.AlertType.MAINTENANCE_DUE,
    )
    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": request_id(f"create-{mold_id}")},
        format="json",
    )
    assert created.status_code == 201
    work_order_id = created.data["data"]["work_order_id"]
    candidates = api_client.get(f"/api/v1/work-orders/{work_order_id}/candidates")
    assert candidates.status_code == 200
    assert candidates.data["data"]["candidates"]
    assigned = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/auto-assign",
        {"client_request_id": request_id(f"assign-{mold_id}")},
        format="json",
    )
    assert assigned.status_code == 200
    employee = assigned.data["data"]["assigned_employee"]
    knowledge_context = api_client.get(f"/api/v1/work-orders/{work_order_id}/knowledge-context")
    assert knowledge_context.status_code == 200
    items = KNOWLEDGE[knowledge_context.data["data"]["mold_type"]]
    snapshot = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/knowledge-snapshot",
        {
            "catalog_version": "INTEGRATION-KB-V1",
            "items": items,
            "client_request_id": request_id(f"snapshot-{mold_id}"),
        },
        format="json",
    )
    assert snapshot.status_code == 201
    email = api_client.get(f"/api/v1/work-orders/{work_order_id}/email-context")
    assert email.data["data"]["to"] == [employee["email"]]
    assert "cc" not in email.data["data"]
    notification = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/notifications",
        {
            "status": "SENT",
            "message_id": f"integration-message-{mold_id}",
            "client_request_id": request_id(f"notify-{mold_id}"),
        },
        format="json",
    )
    assert notification.status_code == 201
    return work_order_id, employee, items


@pytest.mark.django_db
def test_three_consecutive_normal_platform_workflows_reset_three_cycles(api_client):
    call_command("seed_probe_data", verbosity=0)
    scan = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "integration-normal-scan"},
        format="json",
    )
    assert scan.status_code == 200

    completed_ids = []
    for mold_id in ["MOLD-TEST-001", "MOLD-TEST-002", "MOLD-TEST-007"]:
        work_order_id, employee, items = create_assign_and_enrich(api_client, mold_id)
        completed_at = timezone.now()
        response = api_client.post(
            f"/api/v1/work-orders/{work_order_id}/report-complete",
            {
                "employee_id": employee["employee_id"],
                "started_at": (completed_at - timedelta(hours=2)).isoformat(),
                "completed_at": completed_at.isoformat(),
                "work_summary": "集成测试正常闭环完成。",
                "inspection_results": [
                    {
                        "knowledge_id": item["knowledge_id"],
                        "item": item["item"],
                        "result": "PASS",
                        "note": "检查正常",
                    }
                    for item in items
                ],
                "attachments": [],
                "client_request_id": request_id(f"complete-{mold_id}"),
            },
            format="json",
        )
        assert response.status_code == 200
        assert response.data["data"]["status"] == "COMPLETED"
        assert response.data["data"]["cycle_reset"]["performed"] is True
        completed_ids.append(work_order_id)

    assert (
        WorkOrder.objects.filter(
            work_order_id__in=completed_ids, status=WorkOrder.Status.COMPLETED
        ).count()
        == 3
    )
    assert MaintenanceHistory.objects.filter(work_order_id__in=completed_ids).count() == 3
    for mold in Mold.objects.filter(
        mold_id__in=["MOLD-TEST-001", "MOLD-TEST-002", "MOLD-TEST-007"]
    ):
        assert mold.cycle_version == 2
        assert mold.cycle_baseline_count == mold.current_count


@pytest.mark.django_db
def test_abnormal_platform_workflow_preserves_cycle(api_client):
    call_command("seed_probe_data", verbosity=0)
    api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "integration-abnormal-scan"},
        format="json",
    )
    before = Mold.objects.get(pk="MOLD-TEST-001")
    baseline = (before.cycle_baseline_count, before.cycle_baseline_time, before.cycle_version)
    work_order_id, employee, _items = create_assign_and_enrich(api_client, before.mold_id)

    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-abnormal",
        {
            "employee_id": employee["employee_id"],
            "abnormal_type": "COOLING_CHANNEL_BLOCKED",
            "description": "集成测试发现冷却水路堵塞。",
            "inspection_results": [
                {
                    "knowledge_id": "KB-INJECTION-002",
                    "item": "检查冷却水路",
                    "result": "FAIL",
                    "note": "发现堵塞",
                }
            ],
            "client_request_id": "integration-abnormal-report",
        },
        format="json",
    )

    after = Mold.objects.get(pk="MOLD-TEST-001")
    assert response.status_code == 200
    assert response.data["data"]["status"] == "ABNORMAL_REPORTED"
    assert response.data["data"]["cycle_reset"] == {"performed": False}
    assert (after.cycle_baseline_count, after.cycle_baseline_time, after.cycle_version) == baseline
    assert MaintenanceHistory.objects.filter(work_order_id=work_order_id).count() == 0
    assert AbnormalReport.objects.filter(work_order_id=work_order_id).count() == 1
