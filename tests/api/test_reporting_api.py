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
    WorkReport,
)

INSPECTION_ITEMS = [
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
]


def prepare_assigned_work_order(api_client, *, mold_id="MOLD-TEST-001", snapshot=True):
    api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": f"scan-{mold_id}"},
        format="json",
    )
    alert = MaintenanceAlert.objects.get(
        mold_id=mold_id,
        alert_type=MaintenanceAlert.AlertType.MAINTENANCE_DUE,
    )
    created = api_client.post(
        f"/api/v1/alerts/{alert.alert_id}/create-work-order",
        {"client_request_id": f"create-{mold_id}"},
        format="json",
    )
    work_order_id = created.data["data"]["work_order_id"]
    assigned = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/assign",
        {"employee_id": "EMP-001", "client_request_id": f"assign-{mold_id}"},
        format="json",
    )
    assert assigned.status_code == 200
    if snapshot:
        saved = api_client.post(
            f"/api/v1/work-orders/{work_order_id}/knowledge-snapshot",
            {
                "catalog_version": "KB-DEMO-V1",
                "items": INSPECTION_ITEMS,
                "client_request_id": f"snapshot-{mold_id}",
            },
            format="json",
        )
        assert saved.status_code == 201
    return work_order_id


@pytest.fixture
def seeded(db):
    call_command("seed_probe_data", verbosity=0)


def complete_payload(*, request_id="report-complete", started_at=None, completed_at=None):
    started_at = started_at or timezone.now() - timedelta(hours=2)
    completed_at = completed_at or timezone.now()
    return {
        "employee_id": "EMP-001",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "work_summary": "已完成清洁、润滑和水路检查。",
        "inspection_results": [
            {
                "knowledge_id": "KB-INJECTION-001",
                "item": "检查模具表面及型腔",
                "result": "PASS",
                "note": "正常",
            },
            {
                "knowledge_id": "KB-INJECTION-002",
                "item": "检查冷却水路",
                "result": "PASS",
                "note": "畅通",
            },
        ],
        "attachments": [],
        "client_request_id": request_id,
    }


@pytest.mark.django_db
def test_assignee_can_start_pause_resume_and_paused_time_is_deducted(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client)
    started = timezone.now() - timedelta(hours=3)
    paused = started + timedelta(minutes=60)
    resumed = paused + timedelta(minutes=30)
    completed = started + timedelta(hours=2, minutes=30)

    start = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/start",
        {
            "employee_id": "EMP-001",
            "occurred_at": started.isoformat(),
            "client_request_id": "start-001",
        },
        format="json",
    )
    pause = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/pause",
        {
            "employee_id": "EMP-001",
            "occurred_at": paused.isoformat(),
            "reason": "等待冷却",
            "client_request_id": "pause-001",
        },
        format="json",
    )
    resume = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/resume",
        {
            "employee_id": "EMP-001",
            "occurred_at": resumed.isoformat(),
            "client_request_id": "resume-001",
        },
        format="json",
    )
    payload = complete_payload(completed_at=completed, request_id="complete-paused")
    payload.pop("started_at")
    complete = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete", payload, format="json"
    )

    assert start.data["data"]["status"] == "IN_PROGRESS"
    assert pause.data["data"]["status"] == "PAUSED"
    assert resume.data["data"]["status"] == "IN_PROGRESS"
    assert complete.status_code == 200
    assert complete.data["data"]["paused_seconds"] == 1800
    assert complete.data["data"]["actual_minutes"] == 120


@pytest.mark.django_db
def test_one_shot_complete_resets_cycle_and_closes_alert_atomically(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client)
    mold_before = Mold.objects.get(pk="MOLD-TEST-001")
    old_version = mold_before.cycle_version
    current_count = mold_before.current_count
    completed_at = timezone.now()

    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete",
        complete_payload(completed_at=completed_at),
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["status"] == "COMPLETED"
    assert response.data["data"]["cycle_reset"] == {
        "performed": True,
        "baseline_count": current_count,
        "baseline_time": timezone.localtime(completed_at).isoformat(),
        "cycle_version": old_version + 1,
        "next_threshold": 50_000,
        "next_trigger_count": current_count + 50_000,
    }

    work_order = WorkOrder.objects.select_related("alert", "assigned_employee").get(
        pk=work_order_id
    )
    mold = Mold.objects.get(pk="MOLD-TEST-001")
    report = WorkReport.objects.get(work_order=work_order)
    history = MaintenanceHistory.objects.get(work_order=work_order)
    assert work_order.status == WorkOrder.Status.COMPLETED
    assert work_order.alert.status == MaintenanceAlert.Status.CLOSED
    assert work_order.assigned_employee.current_load == 1
    assert report.cycle_reset is True
    assert mold.cycle_baseline_count == current_count
    assert mold.cycle_baseline_time == completed_at
    assert mold.cycle_version == old_version + 1
    assert mold.last_reset_type == Mold.ResetType.MAINTENANCE_COMPLETED
    assert mold.last_reset_event_id == report.report_id
    assert history.cycle_version_before == old_version
    assert history.cycle_version_after == old_version + 1


@pytest.mark.django_db
def test_non_assignee_cannot_start_or_report(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client)
    start = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/start",
        {"employee_id": "EMP-004", "client_request_id": "wrong-start"},
        format="json",
    )
    payload = complete_payload(request_id="wrong-report")
    payload["employee_id"] = "EMP-004"
    report = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete", payload, format="json"
    )

    assert start.status_code == 403
    assert start.data["code"] == "EMPLOYEE_NOT_ASSIGNED"
    assert report.status_code == 403
    assert report.data["code"] == "EMPLOYEE_NOT_ASSIGNED"


@pytest.mark.django_db
def test_complete_requires_all_required_inspection_items(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client)
    payload = complete_payload()
    payload["inspection_results"] = payload["inspection_results"][:1]

    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete", payload, format="json"
    )

    assert response.status_code == 400
    assert response.data["code"] == "INSPECTION_ITEMS_INCOMPLETE"
    assert WorkReport.objects.count() == 0


@pytest.mark.django_db
def test_fail_requires_abnormal_endpoint(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client)
    payload = complete_payload()
    payload["inspection_results"][1]["result"] = "FAIL"

    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete", payload, format="json"
    )

    assert response.status_code == 400
    assert response.data["code"] == "INSPECTION_FAIL_REQUIRES_ABNORMAL_REPORT"
    assert WorkReport.objects.count() == 0


@pytest.mark.django_db
def test_not_applicable_requires_reason(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client)
    payload = complete_payload()
    payload["inspection_results"][1]["result"] = "NOT_APPLICABLE"
    payload["inspection_results"][1].pop("note")

    missing = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete", payload, format="json"
    )
    payload["inspection_results"][1]["reason"] = "本型号无独立冷却水路"
    payload["client_request_id"] = "complete-na-reason"
    accepted = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete", payload, format="json"
    )

    assert missing.data["code"] == "NOT_APPLICABLE_REASON_REQUIRED"
    assert accepted.status_code == 200


@pytest.mark.django_db
def test_one_shot_complete_requires_explicit_valid_time_range(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client)
    payload = complete_payload()
    payload.pop("started_at")
    missing = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete", payload, format="json"
    )

    payload = complete_payload(request_id="bad-time")
    payload["started_at"] = timezone.now().isoformat()
    payload["completed_at"] = (timezone.now() - timedelta(hours=1)).isoformat()
    invalid = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete", payload, format="json"
    )

    assert missing.data["code"] == "INVALID_TIME_RANGE"
    assert invalid.data["code"] == "INVALID_TIME_RANGE"


@pytest.mark.django_db
def test_complete_requires_knowledge_snapshot(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client, snapshot=False)

    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete",
        complete_payload(),
        format="json",
    )

    assert response.status_code == 409
    assert response.data["code"] == "KNOWLEDGE_SNAPSHOT_REQUIRED"


@pytest.mark.django_db
def test_abnormal_report_saves_failure_without_reset_or_closing_alert(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client)
    mold_before = Mold.objects.get(pk="MOLD-TEST-001")
    original = (
        mold_before.cycle_baseline_count,
        mold_before.cycle_baseline_time,
        mold_before.cycle_version,
    )

    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-abnormal",
        {
            "employee_id": "EMP-001",
            "abnormal_type": "COOLING_CHANNEL_BLOCKED",
            "description": "冷却水路堵塞，常规保养无法处理。",
            "inspection_results": [
                {
                    "knowledge_id": "KB-INJECTION-002",
                    "item": "检查冷却水路",
                    "result": "FAIL",
                    "note": "发现堵塞",
                }
            ],
            "client_request_id": "abnormal-001",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["status"] == "ABNORMAL_REPORTED"
    assert response.data["data"]["cycle_reset"] == {"performed": False}
    work_order = WorkOrder.objects.select_related("alert").get(pk=work_order_id)
    mold_after = Mold.objects.get(pk="MOLD-TEST-001")
    report = WorkReport.objects.get(work_order=work_order)
    abnormal = AbnormalReport.objects.get(work_order=work_order)
    assert work_order.status == WorkOrder.Status.ABNORMAL_REPORTED
    assert work_order.alert.status == MaintenanceAlert.Status.WORK_ORDER_CREATED
    assert report.report_type == WorkReport.ReportType.ABNORMAL
    assert report.cycle_reset is False
    assert abnormal.inspection_results_json[0]["result"] == "FAIL"
    assert (
        mold_after.cycle_baseline_count,
        mold_after.cycle_baseline_time,
        mold_after.cycle_version,
    ) == original
    assert MaintenanceHistory.objects.count() == 0


@pytest.mark.django_db
def test_abnormal_report_requires_fail_note_and_description(seeded, api_client):
    work_order_id = prepare_assigned_work_order(api_client)
    base = {
        "employee_id": "EMP-001",
        "abnormal_type": "COOLING_CHANNEL_BLOCKED",
        "description": "异常说明",
        "inspection_results": [
            {
                "knowledge_id": "KB-INJECTION-002",
                "item": "检查冷却水路",
                "result": "FAIL",
                "note": "",
            }
        ],
        "client_request_id": "abnormal-invalid",
    }
    missing_note = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-abnormal", base, format="json"
    )
    base["inspection_results"][0]["note"] = "堵塞"
    base["description"] = ""
    base["client_request_id"] = "abnormal-no-description"
    missing_description = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report-abnormal", base, format="json"
    )

    assert missing_note.data["code"] == "INSPECTION_ITEMS_INCOMPLETE"
    assert missing_description.data["code"] == "ABNORMAL_DESCRIPTION_REQUIRED"
    assert AbnormalReport.objects.count() == 0
