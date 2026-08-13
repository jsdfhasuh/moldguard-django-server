import pytest
from django.core.management import call_command

from apps.platform_probe.models import Employee, MaintenanceAlert, WorkOrder


@pytest.fixture
def scanned_alerts(db, api_client):
    call_command("seed_probe_data", verbosity=0)
    api_client.post("/api/v1/alerts/scan", {}, format="json")


def due_alert(mold_id):
    return MaintenanceAlert.objects.get(
        mold_id=mold_id,
        alert_type=MaintenanceAlert.AlertType.MAINTENANCE_DUE,
    )


@pytest.mark.django_db
def test_due_alert_creates_exactly_one_work_order(scanned_alerts, api_client):
    alert = due_alert("MOLD-TEST-001")
    request = {"client_request_id": "create-001"}

    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order", request, format="json"
    )
    duplicate = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "create-002"},
        format="json",
    )

    assert created.status_code == 201
    assert created.data["data"]["status"] == "PENDING_ASSIGNMENT"
    assert created.data["data"]["mold"]["mold_id"] == "MOLD-TEST-001"
    assert duplicate.status_code == 409
    assert duplicate.data["code"] == "ALERT_ALREADY_HAS_WORK_ORDER"
    assert WorkOrder.objects.filter(alert=alert).count() == 1


@pytest.mark.django_db
def test_two_month_reminder_cannot_create_work_order(scanned_alerts, api_client):
    alert = MaintenanceAlert.objects.get(
        mold_id="MOLD-TEST-003",
        alert_type=MaintenanceAlert.AlertType.TWO_MONTH_REMINDER,
    )

    response = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "create-reminder"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "REMINDER_NOT_WORK_ORDER_ELIGIBLE"
    assert WorkOrder.objects.count() == 0


@pytest.mark.django_db
def test_candidates_filter_unavailable_and_sort_deterministically(scanned_alerts, api_client):
    alert = due_alert("MOLD-TEST-001")
    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "create-candidates"},
        format="json",
    )
    work_order_id = created.data["data"]["work_order_id"]
    Employee.objects.filter(employee_id="EMP-004").update(current_load=1)

    response = api_client.get(f"/api/v1/work-orders/{work_order_id}/candidates")

    assert response.status_code == 200
    ids = [item["employee_id"] for item in response.data["data"]["candidates"]]
    assert ids == ["EMP-001", "EMP-004"]
    assert "EMP-003" not in ids
    assert "EMP-002" not in ids


@pytest.mark.django_db
def test_auto_assignment_uses_lowest_load_then_employee_id(scanned_alerts, api_client):
    alert = due_alert("MOLD-TEST-001")
    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "create-auto"},
        format="json",
    )
    work_order_id = created.data["data"]["work_order_id"]
    Employee.objects.filter(employee_id__in=["EMP-001", "EMP-004"]).update(current_load=2)

    assigned = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/auto-assign",
        {"client_request_id": "auto-assign-001"},
        format="json",
    )

    assert assigned.status_code == 200
    assert assigned.data["data"]["assigned_employee"]["employee_id"] == "EMP-001"
    assert WorkOrder.objects.get(pk=work_order_id).status == WorkOrder.Status.ASSIGNED
    assert Employee.objects.get(pk="EMP-001").current_load == 3


@pytest.mark.django_db
def test_specified_assignment_rejects_missing_unavailable_and_skill_mismatch(
    scanned_alerts, api_client
):
    alert = due_alert("MOLD-TEST-001")
    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "create-specified"},
        format="json",
    )
    work_order_id = created.data["data"]["work_order_id"]
    url = f"/api/v1/work-orders/{work_order_id}/assign"

    missing = api_client.post(
        url,
        {"employee_id": "EMP-999", "client_request_id": "assign-missing"},
        format="json",
    )
    unavailable = api_client.post(
        url,
        {"employee_id": "EMP-003", "client_request_id": "assign-unavailable"},
        format="json",
    )
    mismatch = api_client.post(
        url,
        {"employee_id": "EMP-002", "client_request_id": "assign-mismatch"},
        format="json",
    )
    assigned = api_client.post(
        url,
        {"employee_id": "EMP-004", "client_request_id": "assign-success"},
        format="json",
    )
    reassign = api_client.post(
        url,
        {"employee_id": "EMP-001", "client_request_id": "reassign"},
        format="json",
    )

    assert missing.data["code"] == "EMPLOYEE_NOT_FOUND"
    assert unavailable.data["code"] == "EMPLOYEE_NOT_AVAILABLE"
    assert mismatch.data["code"] == "EMPLOYEE_NOT_AVAILABLE"
    assert assigned.status_code == 200
    assert assigned.data["data"]["assigned_employee"]["employee_id"] == "EMP-004"
    assert reassign.status_code == 409
    assert reassign.data["code"] == "INVALID_WORK_ORDER_STATE"


@pytest.mark.django_db
def test_work_order_list_detail_and_history(scanned_alerts, api_client):
    alert = due_alert("MOLD-TEST-002")
    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": "create-history"},
        format="json",
    )
    work_order_id = created.data["data"]["work_order_id"]
    api_client.post(
        f"/api/v1/work-orders/{work_order_id}/auto-assign",
        {"client_request_id": "assign-history"},
        format="json",
    )

    listing = api_client.get("/api/v1/work-orders?status=ASSIGNED")
    detail = api_client.get(f"/api/v1/work-orders/{work_order_id}")
    history = api_client.get(f"/api/v1/work-orders/{work_order_id}/history")

    assert len(listing.data["data"]["work_orders"]) == 1
    assert detail.data["data"]["assigned_employee"]["employee_id"] == "EMP-002"
    assert [event["event_type"] for event in history.data["data"]["events"]] == [
        "WORK_ORDER_CREATED",
        "WORK_ORDER_ASSIGNED",
    ]
