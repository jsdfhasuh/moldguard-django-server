import pytest

from apps.staff.models import Employee
from apps.workorders.models import WorkOrder, WorkOrderEvent
from tests.helpers import scan_work_order


@pytest.mark.django_db
def test_auto_assign_selects_first_candidate_deterministically_and_replays(api_client, seeded_demo):
    Employee.objects.create(
        employee_id="DEMO-EMP-INJ-A",
        employee_name="演示注塑技师A",
        email="demo-inj-a@example.com",
        production_line="DEMO-LINE-INJ",
        skills_json=["INJECTION"],
        current_load="0.1000",
        on_duty=True,
        available=True,
    )
    Employee.objects.create(
        employee_id="DEMO-EMP-INJ-B",
        employee_name="演示注塑技师B",
        email="demo-inj-b@example.com",
        production_line="DEMO-LINE-INJ",
        skills_json=["INJECTION"],
        current_load="0.1000",
        on_duty=True,
        available=True,
    )
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "auto-assign")
    candidates = api_client.get(f"/api/v1/work-orders/{work_order_id}/candidates")
    first_candidate = candidates.data["data"]["candidates"][0]["employee_id"]
    assert first_candidate == "DEMO-EMP-INJ-A"
    loads_before = dict(Employee.objects.values_list("employee_id", "current_load"))

    payload = {"client_request_id": "auto-assign-request"}
    assigned = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/auto-assign", payload, format="json"
    )
    replayed = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/auto-assign", payload, format="json"
    )
    assert assigned.status_code == replayed.status_code == 200
    assert assigned.data["data"]["assignee_id"] == first_candidate
    assert assigned.data["data"]["auto_assigned"] is True
    assert replayed.data["data"]["replayed"] is True
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=work_order_id, event_type="WORK_ORDER_ASSIGNED"
        ).count()
        == 1
    )
    assert dict(Employee.objects.values_list("employee_id", "current_load")) == loads_before


@pytest.mark.django_db
def test_auto_assign_without_candidate_returns_409_and_keeps_pending(api_client, seeded_demo):
    Employee.objects.filter(skills_json__icontains="INJECTION").update(available=False)
    work_order_id, _ = scan_work_order(api_client, "DEMO-INJ-050K", "auto-none")
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/auto-assign",
        {"client_request_id": "auto-none-request"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "NO_ASSIGNMENT_CANDIDATE"
    order = WorkOrder.objects.get(pk=work_order_id)
    assert order.status == WorkOrder.Status.PENDING_ASSIGNMENT
    assert order.assignee_id is None
