import pytest

from apps.staff.models import Employee
from apps.workorders.models import WorkOrder, WorkOrderEvent
from tests.helpers import scan_work_order


@pytest.mark.django_db
def test_candidates_filter_and_sort_by_line_load_then_id(api_client, seeded_demo):
    Employee.objects.create(
        employee_id="DEMO-EMP-INJ-OTHER-LINE",
        employee_name="演示注塑异线技师",
        email="demo-inj-other@example.com",
        production_line="OTHER-LINE",
        skills_json=["INJECTION"],
        current_load="0.1000",
        on_duty=True,
        available=True,
    )
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-COUNT-TIME", "candidate-order")
    response = api_client.get(f"/api/v1/work-orders/{work_order_id}/candidates")
    identifiers = [item["employee_id"] for item in response.data["data"]["candidates"]]
    assert identifiers == ["DEMO-EMP-INJ", "DEMO-EMP-INJ-OTHER-LINE"]
    assert "DEMO-EMP-UNAVAILABLE" not in identifiers
    assert "DEMO-EMP-HIGH-LOAD" not in identifiers


@pytest.mark.django_db
def test_named_assignment_revalidates_candidate_and_returns_report_url(
    api_client, seeded_demo, settings
):
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://moldguard.example.test"
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "assign-success")
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/assign",
        {
            "client_request_id": "assign-success-request",
            "employee_id": "DEMO-EMP-INJ",
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.data["data"]["new_status"] == "ASSIGNED"
    assert response.data["data"]["report_url"] == (
        f"https://moldguard.example.test/report/{work_order_id}"
    )
    assert response.data["data"]["report_form_schema_version"] == "REPORT-FORM-1.1"
    work_order = WorkOrder.objects.get(pk=work_order_id)
    assert work_order.assignee_id == "DEMO-EMP-INJ"
    assert WorkOrderEvent.objects.filter(event_type="WORK_ORDER_ASSIGNED").count() == 1


@pytest.mark.django_db
def test_named_assignment_rejects_high_load_employee(api_client, seeded_demo):
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "assign-invalid")
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/assign",
        {
            "client_request_id": "assign-invalid-request",
            "employee_id": "DEMO-EMP-HIGH-LOAD",
        },
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "EMPLOYEE_NOT_AVAILABLE"
