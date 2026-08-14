from django.shortcuts import render
from django.views import View
from rest_framework.exceptions import ValidationError

from apps.common.exceptions import BusinessError
from apps.common.idempotency import replay_or_execute
from apps.common.responses import success_payload
from apps.workorders.forms import ReportSubmissionForm
from apps.workorders.models import ReportSubmission, WorkOrder
from apps.workorders.serializers import ReportSubmissionCreateSerializer
from apps.workorders.services.report_review_service import (
    active_report_submission,
    create_report_submission,
    dispatch_report_review,
    prepare_uploaded_images,
    submission_idempotency_payload,
)

READ_ONLY_STATUSES = {
    WorkOrder.Status.COMPLETED,
    WorkOrder.Status.ABNORMAL_REPORTED,
    WorkOrder.Status.REPAIR_LINKED,
    WorkOrder.Status.CANCELLED,
}


def _get_work_order(work_order_id):
    try:
        return (
            WorkOrder.objects.select_related("mold", "assignee", "alert", "linked_repair_order")
            .prefetch_related("events")
            .get(pk=work_order_id)
        )
    except WorkOrder.DoesNotExist:
        return None


def _context(work_order, *, form=None, page_error="", result=None, submission=None):
    current_submission = submission or active_report_submission(work_order)
    needs_more_info_submission = (
        work_order.report_submissions.filter(status=ReportSubmission.Status.NEEDS_MORE_INFO)
        .order_by("-reviewed_at", "-created_at")
        .first()
    )
    return {
        "work_order": work_order,
        "form": form,
        "page_error": page_error,
        "result": result,
        "submission": current_submission,
        "needs_more_info_submission": needs_more_info_submission,
        "knowledge_items": work_order.knowledge_package_json.get("items", []),
        "safety_notes": work_order.knowledge_package_json.get("safety_notes", []),
        "read_only": work_order.status in READ_ONLY_STATUSES or current_submission is not None,
    }


class WorkOrderReportPageView(View):
    template_name = "workorders/report_form.html"
    result_template_name = "workorders/report_result.html"

    def get(self, request, work_order_id):
        work_order = _get_work_order(work_order_id)
        if work_order is None:
            return render(
                request,
                self.result_template_name,
                {"not_found": True, "page_error": "工单不存在"},
                status=404,
            )
        if work_order.status in READ_ONLY_STATUSES:
            return render(request, self.result_template_name, _context(work_order))
        submission = active_report_submission(work_order)
        if submission is not None:
            return render(
                request,
                self.result_template_name,
                _context(work_order, submission=submission),
                status=202,
            )
        if not work_order.knowledge_package_hash or not work_order.knowledge_package_json:
            return render(
                request,
                self.template_name,
                _context(work_order, page_error="工单尚未配置知识包，暂不能正式报工"),
                status=409,
            )
        if not work_order.assignee_id:
            return render(
                request,
                self.template_name,
                _context(work_order, page_error="工单尚未派工，暂不能报工"),
                status=409,
            )
        form = ReportSubmissionForm(work_order=work_order)
        return render(request, self.template_name, _context(work_order, form=form))

    def post(self, request, work_order_id):
        work_order = _get_work_order(work_order_id)
        if work_order is None:
            return render(
                request,
                self.result_template_name,
                {"not_found": True, "page_error": "工单不存在"},
                status=404,
            )
        if not work_order.knowledge_package_hash or not work_order.knowledge_package_json:
            return render(
                request,
                self.template_name,
                _context(work_order, page_error="工单尚未配置知识包，暂不能正式报工"),
                status=409,
            )
        form = ReportSubmissionForm(request.POST, request.FILES, work_order=work_order)
        if not form.is_valid():
            return render(request, self.template_name, _context(work_order, form=form), status=400)
        serializer = ReportSubmissionCreateSerializer(data=form.submission_payload())
        try:
            serializer.is_valid(raise_exception=True)
            payload = serializer.validated_data
            prepared_images = prepare_uploaded_images(payload.pop("images", []))
            idempotency_payload = submission_idempotency_payload(payload, prepared_images)

            def operation():
                data = create_report_submission(
                    work_order_id,
                    payload,
                    prepared_images,
                )
                return 202, success_payload(data, "报工材料已提交，等待AI审核", request)

            status_code, response_payload = replay_or_execute(
                action="CREATE_REPORT_SUBMISSION",
                object_id=work_order_id,
                payload=idempotency_payload,
                current_request_id=request.request_id,
                operation=operation,
            )
            dispatch = dispatch_report_review(
                response_payload["data"]["submission_id"],
                retry_failed=bool(response_payload["data"].get("replayed")),
            )
            response_payload["data"]["webhook_delivery_status"] = dispatch[
                "webhook_delivery_status"
            ]
        except (BusinessError, ValidationError) as exc:
            message = getattr(exc, "business_message", "报工内容校验失败")
            if isinstance(exc, ValidationError):
                message = "报工内容校验失败，请检查填写内容"
            work_order = _get_work_order(work_order_id)
            if work_order.status in READ_ONLY_STATUSES:
                return render(
                    request,
                    self.result_template_name,
                    _context(work_order, page_error=message),
                    status=getattr(exc, "status_code", 400),
                )
            form.add_error(None, message)
            status = getattr(exc, "status_code", 400)
            return render(
                request, self.template_name, _context(work_order, form=form), status=status
            )
        work_order = _get_work_order(work_order_id)
        submission = active_report_submission(work_order)
        return render(
            request,
            self.result_template_name,
            _context(
                work_order,
                result=response_payload["data"],
                submission=submission,
            ),
            status=status_code,
        )
