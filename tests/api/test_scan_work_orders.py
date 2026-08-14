import pytest

from apps.molds.models import Alert, Mold
from apps.workorders.models import WorkOrder


@pytest.mark.django_db
def test_scan_creates_one_merged_alert_and_work_order(api_client, seeded_demo):
    payload = {
        "client_request_id": "scan-merged-first",
        "mold_ids": ["DEMO-INJ-COUNT-TIME"],
    }
    response = api_client.post("/api/v1/alerts/scan", payload, format="json")
    assert response.status_code == 200
    result = response.data["data"]["results"][0]
    assert result["primary_rule_id"] == "INJ-COUNT-030K"
    assert result["matched_rule_ids"] == ["INJ-COUNT-030K", "INJ-TIME-2M"]
    assert result["work_order_type"] == "CYCLE_COUNT_MAINTENANCE"
    assert result["alert_created"] is True
    assert result["work_order_created"] is True
    assert Alert.objects.count() == 1
    assert WorkOrder.objects.count() == 1


@pytest.mark.django_db
def test_scan_without_mold_ids_scans_all_non_disabled_molds(api_client, seeded_demo):
    disabled_mold_id = "DEMO-INJ-050K"
    Mold.objects.filter(pk=disabled_mold_id).update(status=Mold.Status.DISABLED)
    expected_ids = list(
        Mold.objects.exclude(status=Mold.Status.DISABLED)
        .order_by("mold_id")
        .values_list("mold_id", flat=True)
    )

    response = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "scan-all-non-disabled"},
        format="json",
    )

    assert response.status_code == 200
    data = response.data["data"]
    assert data["scanned_count"] == len(expected_ids)
    assert [item["mold_id"] for item in data["results"]] == expected_ids
    assert disabled_mold_id not in expected_ids


@pytest.mark.django_db
def test_repeat_scan_with_different_id_reuses_same_cycle_objects(api_client, seeded_demo):
    first = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "scan-repeat-1", "mold_ids": ["DEMO-STAMP-FORM"]},
        format="json",
    )
    second = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "scan-repeat-2", "mold_ids": ["DEMO-STAMP-FORM"]},
        format="json",
    )
    first_result = first.data["data"]["results"][0]
    second_result = second.data["data"]["results"][0]
    assert first_result["alert_id"] == second_result["alert_id"]
    assert first_result["work_order_id"] == second_result["work_order_id"]
    assert second_result["alert_created"] is False
    assert second_result["work_order_created"] is False
    assert Alert.objects.count() == WorkOrder.objects.count() == 1


@pytest.mark.django_db
def test_full_scan_skips_assigned_work_order_and_exposes_next_pending_one(api_client, seeded_demo):
    first = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "scan-sequential-dispatch-1"},
        format="json",
    )
    assert first.status_code == 200
    first_triggered = [
        item
        for item in first.data["data"]["results"]
        if item["status"] == "TRIGGERED" and item["code"] == "MAINTENANCE_TRIGGERED"
    ]
    assert len(first_triggered) >= 2

    assigned_work_order_id = first_triggered[0]["work_order_id"]
    WorkOrder.objects.filter(pk=assigned_work_order_id).update(status=WorkOrder.Status.ASSIGNED)

    second = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "scan-sequential-dispatch-2"},
        format="json",
    )
    assert second.status_code == 200
    second_results = second.data["data"]["results"]
    assigned_result = next(
        item for item in second_results if item.get("work_order_id") == assigned_work_order_id
    )
    assert assigned_result["status"] == "SKIPPED"
    assert assigned_result["code"] == "MAINTENANCE_WORK_ORDER_NOT_PENDING_ASSIGNMENT"
    assert assigned_result["work_order_status"] == WorkOrder.Status.ASSIGNED

    remaining = [
        item
        for item in second_results
        if item["status"] == "TRIGGERED" and item["code"] == "MAINTENANCE_TRIGGERED"
    ]
    assert remaining
    assert remaining[0]["work_order_id"] != assigned_work_order_id
    assert remaining[0]["work_order_status"] == WorkOrder.Status.PENDING_ASSIGNMENT
    assert second.data["data"]["triggered_count"] == len(remaining)


@pytest.mark.django_db
def test_scan_continues_after_field_error_and_stop_result(api_client, seeded_demo):
    response = api_client.post(
        "/api/v1/alerts/scan",
        {
            "client_request_id": "scan-mixed-results",
            "mold_ids": [
                "DEMO-STAMP-LC109-INVALID",
                "DEMO-INJ-NO-OUTPUT-2Y",
                "DEMO-STAMP-PUNCH",
            ],
        },
        format="json",
    )
    assert response.status_code == 200
    by_id = {item["mold_id"]: item for item in response.data["data"]["results"]}
    assert by_id["DEMO-STAMP-LC109-INVALID"]["code"] == "INVALID_LC109_CATEGORY"
    assert by_id["DEMO-INJ-NO-OUTPUT-2Y"]["status"] == "STOPPED"
    assert by_id["DEMO-STAMP-PUNCH"]["status"] == "TRIGGERED"
    assert WorkOrder.objects.count() == 1
