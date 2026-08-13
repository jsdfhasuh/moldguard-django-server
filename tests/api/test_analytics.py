import pytest

from apps.workorders.models import WorkOrder
from tests.helpers import assigned_with_knowledge, normal_report_payload, scan_work_order


@pytest.mark.django_db
def test_work_hours_filters_and_handles_missing_standard_hours(
    api_client, seeded_demo, knowledge_payload
):
    first_id, _, first_hash = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="analytics-standard",
    )
    first_payload = normal_report_payload("analytics-standard", first_hash)
    first_payload["actual_work_hours"] = "7.00"
    api_client.post(f"/api/v1/work-orders/{first_id}/report", first_payload, format="json")

    second_id, _, second_hash = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-030K",
        employee_id="DEMO-EMP-INJ",
        suffix="analytics-no-standard",
    )
    WorkOrder.objects.filter(pk=second_id).update(standard_hours=None)
    second_payload = normal_report_payload("analytics-no-standard", second_hash)
    second_payload["actual_work_hours"] = "3.00"
    api_client.post(f"/api/v1/work-orders/{second_id}/report", second_payload, format="json")

    response = api_client.get(
        "/api/v1/analytics/work-hours?employee_id=DEMO-EMP-INJ&mold_type=INJECTION"
    )
    assert response.status_code == 200
    data = response.data["data"]
    assert data == {
        "completed_order_count": 2,
        "actual_hours_total": "10.00",
        "actual_hours_average": "5.00",
        "standard_hours_total": "5.00",
        "standard_hours_coverage": 0.5,
        "hours_variance_total": "2.00",
    }
    empty = api_client.get("/api/v1/analytics/work-hours?employee_id=UNKNOWN")
    assert empty.data["data"]["completed_order_count"] == 0
    assert empty.data["data"]["actual_hours_total"] == "0.00"
    assert empty.data["data"]["standard_hours_coverage"] == 0.0


@pytest.mark.django_db
def test_order_completion_counts_v51_statuses_and_date_validation(api_client, seeded_demo):
    completed_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "completion-completed")
    abnormal_id, _ = scan_work_order(api_client, "DEMO-INJ-030K", "completion-abnormal")
    repair_id, _ = scan_work_order(api_client, "DEMO-STAMP-FORM", "completion-repair")
    progress_id, _ = scan_work_order(api_client, "DEMO-STAMP-PUNCH", "completion-progress")
    WorkOrder.objects.filter(pk=completed_id).update(status=WorkOrder.Status.COMPLETED)
    WorkOrder.objects.filter(pk=abnormal_id).update(status=WorkOrder.Status.ABNORMAL_REPORTED)
    WorkOrder.objects.filter(pk=repair_id).update(status=WorkOrder.Status.REPAIR_LINKED)
    WorkOrder.objects.filter(pk=progress_id).update(status=WorkOrder.Status.PAUSED)

    response = api_client.get("/api/v1/analytics/order-completion")
    assert response.status_code == 200
    assert response.data["data"] == {
        "created_count": 4,
        "completed_count": 1,
        "abnormal_count": 1,
        "repair_linked_count": 1,
        "in_progress_count": 1,
        "completion_rate": 0.25,
    }
    invalid = api_client.get(
        "/api/v1/analytics/order-completion?start_date=2026-09-01&end_date=2026-08-01"
    )
    assert invalid.status_code == 400
    assert invalid.data["code"] == "VALIDATION_ERROR"
