import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.workorders.models import MaintenanceRecord, ReportSubmission, WorkOrder
from tests.helpers import assigned_with_knowledge, complete_review_payload, report_image


def submit_django_report(work_order, suffix, *, image=None):
    browser = Client(enforce_csrf_checks=True)
    page = browser.get(f"/report/{work_order.work_order_id}")
    csrf_token = page.cookies["csrftoken"].value
    response = browser.post(
        f"/report/{work_order.work_order_id}",
        {
            "csrfmiddlewaretoken": csrf_token,
            "submission_id": f"django-submission-{suffix}",
            "report_form_schema_version": "REPORT-FORM-1.1",
            "knowledge_package_hash": work_order.knowledge_package_hash,
            "report_text": "已完成模具清洁、润滑和冷却水路检查",
            "actual_work_hours": "2.25",
            "images": image or report_image(),
            "parts_replaced_text": "",
            "source_fault_id": "",
        },
    )
    return browser, response


@pytest.mark.django_db
def test_django_image_context_and_ai_review_complete_work_order(
    api_client, seeded_demo, knowledge_payload, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://public.moldguard.example"
    work_order_id, _, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-COUNT-TIME",
        employee_id="DEMO-EMP-INJ",
        suffix="django-review",
    )
    work_order = WorkOrder.objects.get(pk=work_order_id)
    _, created = submit_django_report(work_order, "django-review")
    assert created.status_code == 202
    submission = ReportSubmission.objects.get(work_order_id=work_order_id)
    submission_id = submission.submission_id
    assert submission.status == ReportSubmission.Status.PENDING_REVIEW
    assert WorkOrder.objects.get(pk=work_order_id).status == WorkOrder.Status.ASSIGNED

    context = api_client.get(f"/api/v1/report-submissions/{submission_id}/review-context")
    assert context.status_code == 200
    assert context.data["data"]["submission"]["report_text"].startswith("已完成")
    assert context.data["data"]["knowledge_package_hash"] == digest
    evidence = context.data["data"]["submission"]["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["content_type"] == "image/png"
    image = api_client.get(
        f"/api/v1/report-submissions/{submission_id}/evidence/{evidence[0]['evidence_id']}"
    )
    assert image.status_code == 200
    assert b"".join(image.streaming_content).startswith(b"\x89PNG\r\n\x1a\n")

    review_payload = complete_review_payload("django-review", digest)
    reviewed = api_client.post(
        f"/api/v1/report-submissions/{submission_id}/review",
        review_payload,
        format="json",
    )
    replayed = api_client.post(
        f"/api/v1/report-submissions/{submission_id}/review",
        review_payload,
        format="json",
    )
    assert reviewed.status_code == replayed.status_code == 200
    assert reviewed.data["data"]["work_order_status"] == "COMPLETED"
    assert replayed.data["data"]["replayed"] is True
    work_order.refresh_from_db()
    assert work_order.status == WorkOrder.Status.COMPLETED
    assert len(work_order.photos_json) == 1
    assert work_order.photos_json[0].startswith(
        f"https://public.moldguard.example/api/v1/report-submissions/{submission_id}/evidence/"
    )
    assert MaintenanceRecord.objects.filter(work_order=work_order).count() == 1
    submission.refresh_from_db()
    assert submission.status == ReportSubmission.Status.FINALIZED
    assert submission.review_decision == ReportSubmission.ReviewDecision.COMPLETE


@pytest.mark.django_db
def test_django_submission_webhook_contains_only_locator_fields(
    api_client, seeded_demo, knowledge_payload, settings, monkeypatch, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    settings.MOLDGUARD_PUBLIC_BASE_URL = "https://public.moldguard.example"
    settings.MOLDGUARD_REPORT_REVIEW_WEBHOOK_URL = "https://platform.example/review-hook"
    work_order_id, _, _ = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="django-webhook",
    )
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return 204

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setattr(
        "apps.workorders.services.report_review_service.urllib.request.urlopen",
        fake_urlopen,
    )
    work_order = WorkOrder.objects.get(pk=work_order_id)
    _, created = submit_django_report(work_order, "django-webhook")
    assert created.status_code == 202
    submission = ReportSubmission.objects.get(work_order_id=work_order_id)
    assert submission.webhook_status == ReportSubmission.WebhookStatus.DELIVERED
    assert captured["url"] == settings.MOLDGUARD_REPORT_REVIEW_WEBHOOK_URL
    assert set(captured["payload"]) == {
        "event",
        "submission_id",
        "work_order_id",
        "review_context_url",
        "client_request_id",
    }
    assert captured["payload"]["event"] == "REPORT_SUBMISSION_READY"
    assert "report_text" not in captured["payload"]
    assert "image" not in captured["payload"]


@pytest.mark.django_db
def test_low_confidence_review_cannot_complete_work_order(
    api_client, seeded_demo, knowledge_payload, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    work_order_id, _, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="low-confidence",
    )
    work_order = WorkOrder.objects.get(pk=work_order_id)
    submit_django_report(work_order, "low-confidence")
    submission = ReportSubmission.objects.get(work_order_id=work_order_id)
    review = api_client.post(
        f"/api/v1/report-submissions/{submission.submission_id}/review",
        complete_review_payload("low-confidence", digest, confidence="0.5000"),
        format="json",
    )
    assert review.status_code == 409
    assert review.data["code"] == "AI_REVIEW_CONFIDENCE_TOO_LOW"
    assert WorkOrder.objects.get(pk=work_order_id).status == WorkOrder.Status.ASSIGNED
    submission.refresh_from_db()
    assert submission.status == ReportSubmission.Status.PENDING_REVIEW
    assert not MaintenanceRecord.objects.exists()


@pytest.mark.django_db
def test_needs_more_info_requires_a_new_django_submission(
    api_client, seeded_demo, knowledge_payload, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    work_order_id, _, digest = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="needs-more-info",
    )
    work_order = WorkOrder.objects.get(pk=work_order_id)
    browser, created = submit_django_report(work_order, "needs-more-info")
    assert created.status_code == 202
    first = ReportSubmission.objects.get(work_order_id=work_order_id)
    needs_more_info = api_client.post(
        f"/api/v1/report-submissions/{first.submission_id}/review",
        {
            "client_request_id": "review-needs-more-info",
            "decision": "NEEDS_MORE_INFO",
            "assessment_summary": "图片未覆盖冷却水路点检位置",
            "confidence": "0.4000",
            "knowledge_package_hash": digest,
            "reason_codes": ["IMAGE_EVIDENCE_INCOMPLETE"],
        },
        format="json",
    )
    assert needs_more_info.status_code == 200
    first.refresh_from_db()
    assert first.status == ReportSubmission.Status.NEEDS_MORE_INFO

    supplement_page = browser.get(f"/report/{work_order_id}")
    supplement_content = supplement_page.content.decode()
    assert supplement_page.status_code == 200
    assert "图片未覆盖冷却水路点检位置" in supplement_content
    assert '<form method="post"' in supplement_content

    stale_review = api_client.post(
        f"/api/v1/report-submissions/{first.submission_id}/review",
        complete_review_payload("stale-needs-more-info", digest),
        format="json",
    )
    assert stale_review.status_code == 409
    assert stale_review.data["code"] == "REPORT_REVIEW_NEEDS_NEW_SUBMISSION"

    work_order.refresh_from_db()
    _, supplemented = submit_django_report(work_order, "supplemented")
    assert supplemented.status_code == 202
    assert ReportSubmission.objects.filter(work_order_id=work_order_id).count() == 2
    assert (
        ReportSubmission.objects.filter(
            work_order_id=work_order_id,
            status=ReportSubmission.Status.PENDING_REVIEW,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_platform_submission_endpoint_is_removed(api_client):
    response = api_client.post(
        "/api/v1/work-orders/WO-1/report-submissions",
        {"client_request_id": "removed-platform-submission"},
        format="json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_django_page_rejects_non_image_content(
    api_client, seeded_demo, knowledge_payload, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    work_order_id, _, _ = assigned_with_knowledge(
        api_client,
        knowledge_payload,
        mold_id="DEMO-INJ-050K",
        employee_id="DEMO-EMP-INJ",
        suffix="invalid-image",
    )
    work_order = WorkOrder.objects.get(pk=work_order_id)
    fake_image = SimpleUploadedFile("evidence.jpg", b"not-an-image", content_type="image/jpeg")
    _, response = submit_django_report(work_order, "invalid-image", image=fake_image)
    assert response.status_code == 400
    assert not ReportSubmission.objects.filter(work_order_id=work_order_id).exists()
