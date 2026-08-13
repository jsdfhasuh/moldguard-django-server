from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.platform_probe.models import (
    ClientRequestRecord,
    MaintenanceAlert,
    MaintenanceHistory,
    WorkOrder,
    WorkReport,
)


@pytest.fixture
def seeded(db):
    call_command("seed_probe_data", verbosity=0)


def scan(api_client, request_id="scan-idempotency"):
    return api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": request_id},
        format="json",
    )


@pytest.mark.django_db
def test_same_client_request_and_content_replays_original_result(seeded, api_client):
    first = scan(api_client)
    second = scan(api_client)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.data["data"]["created_alert_ids"]
    assert second.data["data"]["created_alert_ids"] == first.data["data"]["created_alert_ids"]
    assert second.data["data"]["replayed"] is True
    assert first.data["request_id"] != second.data["request_id"]
    assert ClientRequestRecord.objects.count() == 1


@pytest.mark.django_db
def test_same_client_request_with_different_content_conflicts_before_mutation(seeded, api_client):
    first = scan(api_client, "scan-conflict")
    alert_count = MaintenanceAlert.objects.count()
    conflict = api_client.post(
        "/api/v1/alerts/scan",
        {
            "mold_ids": ["MOLD-TEST-001"],
            "client_request_id": "scan-conflict",
        },
        format="json",
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.data["code"] == "CLIENT_REQUEST_CONFLICT"
    assert MaintenanceAlert.objects.count() == alert_count


@pytest.mark.django_db
def test_create_work_order_replay_does_not_create_second_order(seeded, api_client):
    scan(api_client)
    alert = MaintenanceAlert.objects.get(
        mold_id="MOLD-TEST-001",
        alert_type=MaintenanceAlert.AlertType.MAINTENANCE_DUE,
    )
    url = f"/api/v1/alerts/{alert.alert_id}/create-work-order"
    payload = {"client_request_id": "create-replay"}

    first = api_client.post(url, payload, format="json")
    second = api_client.post(url, payload, format="json")

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.data["data"]["work_order_id"] == first.data["data"]["work_order_id"]
    assert second.data["data"]["replayed"] is True
    assert WorkOrder.objects.filter(alert=alert).count() == 1


def prepare_reporting(api_client):
    scan(api_client)
    alert = MaintenanceAlert.objects.get(
        mold_id="MOLD-TEST-001",
        alert_type=MaintenanceAlert.AlertType.MAINTENANCE_DUE,
    )
    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "create-report-replay"},
        format="json",
    )
    work_order_id = created.data["data"]["work_order_id"]
    api_client.post(
        f"/api/v1/work-orders/{work_order_id}/assign",
        {"employee_id": "EMP-001", "client_request_id": "assign-report-replay"},
        format="json",
    )
    api_client.post(
        f"/api/v1/work-orders/{work_order_id}/knowledge-snapshot",
        {
            "catalog_version": "KB-DEMO-V1",
            "items": [
                {
                    "knowledge_id": "KB-INJECTION-001",
                    "item": "检查模具表面及型腔",
                    "required": True,
                }
            ],
            "client_request_id": "snapshot-report-replay",
        },
        format="json",
    )
    return work_order_id


@pytest.mark.django_db
def test_complete_report_replay_resets_cycle_exactly_once(seeded, api_client):
    work_order_id = prepare_reporting(api_client)
    completed_at = timezone.now()
    payload = {
        "employee_id": "EMP-001",
        "started_at": (completed_at - timedelta(hours=1)).isoformat(),
        "completed_at": completed_at.isoformat(),
        "work_summary": "已完成全部保养项目。",
        "inspection_results": [
            {
                "knowledge_id": "KB-INJECTION-001",
                "item": "检查模具表面及型腔",
                "result": "PASS",
                "note": "正常",
            }
        ],
        "attachments": [],
        "client_request_id": "complete-replay",
    }
    url = f"/api/v1/work-orders/{work_order_id}/report-complete"

    first = api_client.post(url, payload, format="json")
    second = api_client.post(url, payload, format="json")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.data["data"]["report_id"] == first.data["data"]["report_id"]
    assert second.data["data"]["replayed"] is True
    assert WorkReport.objects.filter(work_order_id=work_order_id).count() == 1
    assert MaintenanceHistory.objects.filter(work_order_id=work_order_id).count() == 1
    assert first.data["data"]["cycle_reset"]["cycle_version"] == 2


@pytest.mark.django_db
def test_client_request_id_is_globally_scoped_across_actions(seeded, api_client):
    scan(api_client, "global-request-id")
    alert = MaintenanceAlert.objects.get(
        mold_id="MOLD-TEST-001",
        alert_type=MaintenanceAlert.AlertType.MAINTENANCE_DUE,
    )

    response = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "global-request-id"},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["code"] == "CLIENT_REQUEST_CONFLICT"
    assert WorkOrder.objects.count() == 0


@pytest.mark.django_db
def test_write_endpoint_rejects_missing_client_request_id(seeded, api_client):
    response = api_client.post("/api/v1/alerts/scan", {}, format="json")

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert response.data["data"] is None
    assert response.data["errors"][0]["field"] == "client_request_id"


@pytest.mark.django_db(transaction=True)
def test_concurrent_identical_complete_requests_replay_instead_of_conflicting(seeded, api_client):
    work_order_id = prepare_reporting(api_client)
    completed_at = timezone.now()
    payload = {
        "employee_id": "EMP-001",
        "started_at": (completed_at - timedelta(hours=1)).isoformat(),
        "completed_at": completed_at.isoformat(),
        "work_summary": "并发重放测试。",
        "inspection_results": [
            {
                "knowledge_id": "KB-INJECTION-001",
                "item": "检查模具表面及型腔",
                "result": "PASS",
                "note": "正常",
            }
        ],
        "attachments": [],
        "client_request_id": "complete-concurrent-replay",
    }
    url = f"/api/v1/work-orders/{work_order_id}/report-complete"

    def send_request():
        close_old_connections()
        client = APIClient()
        try:
            response = client.post(url, payload, format="json")
            return response.status_code, response.data
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: send_request(), range(2)))

    assert [status for status, _data in results] == [200, 200]
    report_ids = {data["data"]["report_id"] for _status, data in results}
    assert len(report_ids) == 1
    assert sum(data["data"].get("replayed", False) for _status, data in results) == 1
    assert WorkReport.objects.filter(work_order_id=work_order_id).count() == 1
    assert MaintenanceHistory.objects.filter(work_order_id=work_order_id).count() == 1
