import pytest

from apps.molds.models import Alert, Mold
from apps.workorders.models import MaintenanceRecord, WorkOrder, WorkOrderEvent
from tests.helpers import (
    assign_work_order,
    normal_report_payload,
    save_knowledge,
    scan_work_order,
)


@pytest.mark.django_db
def test_complete_normal_p0_workflow(api_client, seeded_demo, knowledge_payload, settings):
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://moldguard.example.test"
    work_order_id, alert_id = scan_work_order(
        api_client, "DEMO-INJ-COUNT-TIME", "integration-normal"
    )
    candidates = api_client.get(f"/api/v1/work-orders/{work_order_id}/candidates")
    assert candidates.data["data"]["candidates"][0]["employee_id"] == "DEMO-EMP-INJ"
    assignment = assign_work_order(api_client, work_order_id, "DEMO-EMP-INJ", "integration-normal")
    assert assignment["report_url"].startswith("https://moldguard.example.test/report/")
    knowledge = save_knowledge(api_client, work_order_id, knowledge_payload, "integration-normal")
    email = api_client.get(f"/api/v1/work-orders/{work_order_id}/email-context")
    assert email.data["data"]["knowledge_package_hash"] == knowledge["knowledge_package_hash"]
    sent = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/email-result",
        {
            "client_request_id": "integration-normal-email",
            "status": "SENT",
            "message_id": "DEMO-MAIL-INTEGRATION-NORMAL",
            "sent_at": "2026-08-13T16:00:00+08:00",
            "knowledge_package_hash": knowledge["knowledge_package_hash"],
            "error_message": "",
        },
        format="json",
    )
    assert sent.data["data"]["new_email_status"] == "SENT"
    report = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report",
        normal_report_payload("integration-normal", knowledge["knowledge_package_hash"]),
        format="json",
    )
    assert report.data["data"]["new_status"] == "COMPLETED"
    assert WorkOrder.objects.get(pk=work_order_id).status == WorkOrder.Status.COMPLETED
    assert Alert.objects.get(pk=alert_id).status == Alert.Status.CLOSED
    mold = Mold.objects.get(pk="DEMO-INJ-COUNT-TIME")
    assert mold.baseline_effective_mold_cycles == mold.effective_mold_cycles
    assert MaintenanceRecord.objects.filter(work_order_id=work_order_id).count() == 1
    timeline = api_client.get(f"/api/v1/work-orders/{work_order_id}/timeline")
    assert [item["event_type"] for item in timeline.data["data"]["events"]] == [
        "WORK_ORDER_CREATED",
        "WORK_ORDER_ASSIGNED",
        "KNOWLEDGE_PACKAGE_SAVED",
        "EMAIL_RESULT_RECORDED",
        "NORMAL_REPORT_COMPLETED",
    ]
    assert WorkOrderEvent.objects.filter(work_order_id=work_order_id).count() == 5
    records = api_client.get("/api/v1/molds/DEMO-INJ-COUNT-TIME/records")
    assert records.data["data"]["records"][0]["work_order_id"] == work_order_id
    summary = api_client.get("/api/v1/analytics/summary")
    assert summary.data["data"]["completed_count"] == 1
    assert summary.data["data"]["completion_rate"] == 1.0
