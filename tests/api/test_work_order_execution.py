from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.workorders.models import WorkOrder, WorkOrderEvent
from tests.helpers import (
    abnormal_report_payload,
    assigned_with_knowledge,
    normal_report_payload,
)


@pytest.mark.django_db
def test_start_pause_resume_transitions_and_accumulates_pause_seconds(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, _, _ = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="execution",
    )
    base = timezone.now().replace(microsecond=0)
    with patch("apps.workorders.services.execution_service.timezone.now", return_value=base):
        started = api_client.post(
            f"/api/v1/work-orders/{work_order_id}/start",
            {"client_request_id": "execution-start"},
            format="json",
        )
    assert started.status_code == 200
    assert started.data["data"]["new_status"] == WorkOrder.Status.IN_PROGRESS
    assert WorkOrder.objects.get(pk=work_order_id).started_at == base

    replayed = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/start",
        {"client_request_id": "execution-start"},
        format="json",
    )
    assert replayed.status_code == 200
    assert replayed.data["data"]["replayed"] is True
    duplicate = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/start",
        {"client_request_id": "execution-start-again"},
        format="json",
    )
    assert duplicate.status_code == 409

    pause_at = base + timedelta(minutes=5)
    with patch("apps.workorders.services.execution_service.timezone.now", return_value=pause_at):
        paused = api_client.post(
            f"/api/v1/work-orders/{work_order_id}/pause",
            {"client_request_id": "execution-pause-1", "reason": "等待现场隔离"},
            format="json",
        )
    assert paused.status_code == 200
    assert paused.data["data"]["new_status"] == WorkOrder.Status.PAUSED
    repeated_pause = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/pause",
        {"client_request_id": "execution-pause-repeat", "reason": "重复"},
        format="json",
    )
    assert repeated_pause.status_code == 409

    resume_at = pause_at + timedelta(seconds=91)
    with patch("apps.workorders.services.execution_service.timezone.now", return_value=resume_at):
        resumed = api_client.post(
            f"/api/v1/work-orders/{work_order_id}/resume",
            {"client_request_id": "execution-resume-1"},
            format="json",
        )
    assert resumed.status_code == 200
    order = WorkOrder.objects.get(pk=work_order_id)
    assert order.status == WorkOrder.Status.IN_PROGRESS
    assert order.pause_started_at is None
    assert order.paused_seconds == 91

    second_pause_at = resume_at + timedelta(minutes=1)
    with patch(
        "apps.workorders.services.execution_service.timezone.now", return_value=second_pause_at
    ):
        api_client.post(
            f"/api/v1/work-orders/{work_order_id}/pause",
            {"client_request_id": "execution-pause-2", "reason": "更换工具"},
            format="json",
        )
    with patch(
        "apps.workorders.services.execution_service.timezone.now",
        return_value=second_pause_at + timedelta(seconds=29),
    ):
        api_client.post(
            f"/api/v1/work-orders/{work_order_id}/resume",
            {"client_request_id": "execution-resume-2"},
            format="json",
        )
    order.refresh_from_db()
    assert order.paused_seconds == 120
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=work_order_id, event_type="WORK_ORDER_PAUSED"
        ).count()
        == 2
    )
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=work_order_id, event_type="WORK_ORDER_RESUMED"
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_resume_requires_time_later_than_pause_start(api_client, seeded_demo, knowledge_payload):
    work_order_id, _, _ = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="resume-time",
    )
    api_client.post(
        f"/api/v1/work-orders/{work_order_id}/start",
        {"client_request_id": "resume-time-start"},
        format="json",
    )
    now = timezone.now().replace(microsecond=0)
    with patch("apps.workorders.services.execution_service.timezone.now", return_value=now):
        api_client.post(
            f"/api/v1/work-orders/{work_order_id}/pause",
            {"client_request_id": "resume-time-pause", "reason": "测试"},
            format="json",
        )
        response = api_client.post(
            f"/api/v1/work-orders/{work_order_id}/resume",
            {"client_request_id": "resume-time-resume"},
            format="json",
        )
    assert response.status_code == 409
    assert response.data["code"] == "INVALID_PAUSE_INTERVAL"
    assert WorkOrder.objects.get(pk=work_order_id).status == WorkOrder.Status.PAUSED


@pytest.mark.django_db
def test_assigned_normal_allowed_but_paused_normal_rejected(
    api_client, seeded_demo, knowledge_payload
):
    direct_id, _, direct_hash = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-030K",
        employee_id="DEMO-EMP-INJ",
        suffix="assigned-direct-normal",
    )
    direct = api_client.post(
        f"/api/v1/work-orders/{direct_id}/report",
        normal_report_payload("assigned-direct-normal", direct_hash),
        format="json",
    )
    assert direct.status_code == 200
    assert direct.data["data"]["old_status"] == WorkOrder.Status.ASSIGNED

    paused_id, _, paused_hash = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="paused-normal",
    )
    api_client.post(
        f"/api/v1/work-orders/{paused_id}/start",
        {"client_request_id": "paused-normal-start"},
        format="json",
    )
    api_client.post(
        f"/api/v1/work-orders/{paused_id}/pause",
        {"client_request_id": "paused-normal-pause", "reason": "暂停"},
        format="json",
    )
    rejected = api_client.post(
        f"/api/v1/work-orders/{paused_id}/report",
        normal_report_payload("paused-normal", paused_hash),
        format="json",
    )
    assert rejected.status_code == 409
    assert rejected.data["code"] == "INVALID_WORK_ORDER_STATE"
    assert WorkOrder.objects.get(pk=paused_id).status == WorkOrder.Status.PAUSED


@pytest.mark.django_db
def test_paused_abnormal_report_settles_open_pause_interval(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, _, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="paused-abnormal",
    )
    api_client.post(
        f"/api/v1/work-orders/{work_order_id}/start",
        {"client_request_id": "paused-abnormal-start"},
        format="json",
    )
    pause_at = timezone.now().replace(microsecond=0)
    with patch("apps.workorders.services.execution_service.timezone.now", return_value=pause_at):
        api_client.post(
            f"/api/v1/work-orders/{work_order_id}/pause",
            {"client_request_id": "paused-abnormal-pause", "reason": "发现异常"},
            format="json",
        )
    report_at = pause_at + timedelta(seconds=75)
    with patch("apps.workorders.services.report_service.timezone.now", return_value=report_at):
        response = api_client.post(
            f"/api/v1/work-orders/{work_order_id}/report",
            abnormal_report_payload("paused-abnormal", digest),
            format="json",
        )
    assert response.status_code == 200
    order = WorkOrder.objects.get(pk=work_order_id)
    assert order.status == WorkOrder.Status.ABNORMAL_REPORTED
    assert order.pause_started_at is None
    assert order.paused_seconds == 75
