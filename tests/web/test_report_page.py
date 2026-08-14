import pytest
from django.test import Client

from apps.common.models import ClientRequestRecord
from apps.workorders.models import MaintenanceRecord, ReportSubmission, WorkOrder, WorkOrderEvent
from tests.helpers import assigned_with_knowledge, report_image


def html_normal_payload(work_order, *, submission_id="html-report-001"):
    return {
        "submission_id": submission_id,
        "report_form_schema_version": "REPORT-FORM-1.1",
        "knowledge_package_hash": work_order.knowledge_package_hash,
        "report_text": "网页报工已完成保养并上传现场图片",
        "images": report_image(),
        "parts_replaced_text": "",
        "actual_work_hours": "2.25",
    }


@pytest.mark.django_db
def test_report_page_shows_same_hash_and_no_employee_input(
    api_client, seeded_demo, knowledge_payload
):
    work_order_id, _, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="web-display",
    )
    email = api_client.get(f"/api/v1/work-orders/{work_order_id}/email-context")
    response = Client().get(f"/report/{work_order_id}")
    content = response.content.decode()
    assert response.status_code == 200
    assert work_order_id in content
    assert "DEMO注塑小吨位模具" in content
    assert "演示注塑技师" in content
    assert digest in content
    assert email.data["data"]["knowledge_package_hash"] == digest
    assert "MOLDGUARD-KB-1.2" in content
    assert 'name="employee_id"' not in content
    assert 'name="submission_id"' in content
    assert 'name="images"' in content
    assert 'name="source_fault_id"' not in content
    assert "故障源表 ID" not in content
    assert 'name="csrfmiddlewaretoken"' in content


@pytest.mark.django_db
def test_html_submission_waits_for_ai_review_and_replays_submission_id(
    api_client, seeded_demo, knowledge_payload, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    work_order_id, _, _ = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="web-submit",
    )
    work_order = WorkOrder.objects.get(pk=work_order_id)
    client = Client(enforce_csrf_checks=True)
    page = client.get(f"/report/{work_order_id}")
    csrf_token = page.cookies["csrftoken"].value
    first_payload = html_normal_payload(work_order, submission_id="web-submission-replay")
    first_payload["csrfmiddlewaretoken"] = csrf_token
    second_payload = html_normal_payload(work_order, submission_id="web-submission-replay")
    second_payload["csrfmiddlewaretoken"] = csrf_token

    first = client.post(f"/report/{work_order_id}", first_payload)
    second = client.post(f"/report/{work_order_id}", second_payload)
    assert first.status_code == second.status_code == 202
    assert "报工等待 AI 审核" in first.content.decode()
    order = WorkOrder.objects.get(pk=work_order_id)
    assert order.status == WorkOrder.Status.ASSIGNED
    assert ReportSubmission.objects.filter(work_order_id=work_order_id).count() == 1
    submission = ReportSubmission.objects.get(work_order_id=work_order_id)
    assert submission.status == ReportSubmission.Status.PENDING_REVIEW
    assert submission.evidence.count() == 1
    assert not MaintenanceRecord.objects.filter(work_order_id=work_order_id).exists()
    assert (
        WorkOrderEvent.objects.filter(
            work_order_id=work_order_id, event_type="REPORT_SUBMISSION_CREATED"
        ).count()
        == 1
    )
    request_record = ClientRequestRecord.objects.get(pk="web-submission-replay")
    assert request_record.action == "CREATE_REPORT_SUBMISSION"
    assert request_record.object_id == work_order_id

    read_only = client.get(f"/report/{work_order_id}")
    read_only_content = read_only.content.decode()
    assert read_only.status_code == 202
    assert "报工等待 AI 审核" in read_only_content
    assert '<form method="post"' not in read_only_content


@pytest.mark.django_db
def test_report_page_enforces_csrf(api_client, seeded_demo, knowledge_payload):
    work_order_id, _, _ = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="web-csrf",
    )
    work_order = WorkOrder.objects.get(pk=work_order_id)
    response = Client(enforce_csrf_checks=True).post(
        f"/report/{work_order_id}", html_normal_payload(work_order)
    )
    assert response.status_code == 403
    assert WorkOrder.objects.get(pk=work_order_id).status == WorkOrder.Status.ASSIGNED


@pytest.mark.django_db
def test_report_page_without_knowledge_is_explicitly_disabled(api_client, seeded_demo):
    scan = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": "web-no-knowledge-scan", "mold_ids": ["DEMO-INJ-050K"]},
        format="json",
    )
    work_order_id = scan.data["data"]["results"][0]["work_order_id"]
    api_client.post(
        f"/api/v1/work-orders/{work_order_id}/assign",
        {"client_request_id": "web-no-knowledge-assign", "employee_id": "DEMO-EMP-INJ"},
        format="json",
    )
    response = Client().get(f"/report/{work_order_id}")
    assert response.status_code == 409
    content = response.content.decode()
    assert "尚未配置知识包" in content
    assert '<form method="post"' not in content


@pytest.mark.django_db
def test_abnormal_report_page_is_read_only_and_shows_next_action(
    api_client, seeded_demo, knowledge_payload
):
    from tests.helpers import abnormal_report_payload

    work_order_id, _, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="web-abnormal-result",
    )
    api_client.post(
        f"/api/v1/work-orders/{work_order_id}/report",
        abnormal_report_payload("web-abnormal-result", digest),
        format="json",
    )
    response = Client().get(f"/report/{work_order_id}")
    content = response.content.decode()
    assert response.status_code == 200
    assert "异常已记录" in content
    assert "继续处理" in content
    assert '<form method="post"' not in content
