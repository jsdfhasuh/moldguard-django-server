from django.shortcuts import render
from django.views import View
from rest_framework.exceptions import ValidationError

from apps.common.exceptions import BusinessError
from apps.common.idempotency import replay_or_execute
from apps.common.responses import success_payload
from apps.workorders.forms import WorkOrderReportForm
from apps.workorders.models import WorkOrder
from apps.workorders.serializers import ReportSerializer
from apps.workorders.services.report_service import submit_report

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


def _context(work_order, *, form=None, page_error="", result=None):
    return {
        "work_order": work_order,
        "form": form,
        "page_error": page_error,
        "result": result,
        "knowledge_items": work_order.knowledge_package_json.get("items", []),
        "safety_notes": work_order.knowledge_package_json.get("safety_notes", []),
        "read_only": work_order.status in READ_ONLY_STATUSES,
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
        form = WorkOrderReportForm(work_order=work_order)
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
        form = WorkOrderReportForm(request.POST, work_order=work_order)
        if not form.is_valid():
            return render(request, self.template_name, _context(work_order, form=form), status=400)
        serializer = ReportSerializer(data=form.report_payload())
        try:
            serializer.is_valid(raise_exception=True)
            payload = serializer.validated_data

            def operation():
                data = submit_report(
                    work_order_id,
                    payload,
                    client_request_id=payload["client_request_id"],
                )
                return 200, success_payload(data, "报工提交成功", request)

            _, response_payload = replay_or_execute(
                action="SUBMIT_WORK_ORDER_REPORT",
                object_id=work_order_id,
                payload=payload,
                current_request_id=request.request_id,
                operation=operation,
            )
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
        return render(
            request,
            self.result_template_name,
            _context(work_order, result=response_payload["data"]),
        )
