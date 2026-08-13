from datetime import timedelta

import pytest
from django.utils import timezone

from apps.workorders.models import WorkOrder, WorkOrderEvent
from tests.helpers import assign_work_order, scan_work_order


@pytest.mark.django_db
def test_tracking_identifies_deadline_and_abnormal_overdue_and_deduplicates_hour_bucket(
    api_client, seeded_demo, settings
):
    settings.MOLDGUARD_ABNORMAL_OVERDUE_HOURS = 4
    deadline_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "tracking-deadline")
    assign_work_order(api_client, deadline_id, "DEMO-EMP-INJ", "tracking-deadline")
    abnormal_id, _ = scan_work_order(api_client, "DEMO-INJ-030K", "tracking-abnormal")
    now = timezone.now()
    WorkOrder.objects.filter(pk=deadline_id).update(required_finish_at=now - timedelta(hours=2))
    WorkOrder.objects.filter(pk=abnormal_id).update(
        status=WorkOrder.Status.ABNORMAL_REPORTED,
        reported_at=now - timedelta(hours=6),
    )

    first = api_client.post(
        "/api/v1/tracking/scan",
        {"client_request_id": "tracking-scan-first"},
        format="json",
    )
    assert first.status_code == 200
    assert first.data["data"]["overdue_count"] == 2
    by_id = {item["work_order_id"]: item for item in first.data["data"]["results"]}
    assert by_id[deadline_id]["overdue_type"] == "REQUIRED_FINISH_OVERDUE"
    assert by_id[deadline_id]["overdue_duration_minutes"] >= 119
    assert by_id[abnormal_id]["overdue_type"] == "ABNORMAL_UNHANDLED_OVERDUE"
    assert first.data["data"]["created_event_count"] == 2

    second = api_client.post(
        "/api/v1/tracking/scan",
        {"client_request_id": "tracking-scan-second"},
        format="json",
    )
    assert second.status_code == 200
    assert second.data["data"]["overdue_count"] == 2
    assert second.data["data"]["created_event_count"] == 0
    assert WorkOrderEvent.objects.filter(event_type="WORK_ORDER_OVERDUE").count() == 2

    overdue = api_client.get("/api/v1/work-orders/overdue")
    assert overdue.status_code == 200
    assert {item["work_order_id"] for item in overdue.data["data"]["results"]} == {
        deadline_id,
        abnormal_id,
    }
    WorkOrder.objects.filter(pk=deadline_id).update(status=WorkOrder.Status.COMPLETED)
    remaining = api_client.get("/api/v1/work-orders/overdue")
    assert {item["work_order_id"] for item in remaining.data["data"]["results"]} == {abnormal_id}


@pytest.mark.django_db
def test_tracking_ignores_equal_deadline_null_deadline_and_terminal_status(api_client, seeded_demo):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "tracking-boundary")
    assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", "tracking-boundary")
    exact = timezone.now().replace(microsecond=0)
    WorkOrder.objects.filter(pk=work_order_id).update(required_finish_at=exact)
    from unittest.mock import patch

    with patch("apps.workorders.services.tracking_service.timezone.now", return_value=exact):
        response = api_client.get("/api/v1/work-orders/overdue")
    assert response.data["data"]["count"] == 0
