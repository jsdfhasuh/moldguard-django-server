import uuid
from decimal import Decimal

from django import forms
from django.conf import settings

from apps.workorders.models import WorkOrder


class WorkOrderReportForm(forms.Form):
    submission_id = forms.CharField(widget=forms.HiddenInput)
    report_form_schema_version = forms.CharField(widget=forms.HiddenInput)
    knowledge_package_hash = forms.CharField(widget=forms.HiddenInput)
    report_type = forms.ChoiceField(
        label="报工类型",
        choices=WorkOrder.ReportType.choices,
        widget=forms.RadioSelect,
    )
    report_summary = forms.CharField(
        label="完成情况或处理说明",
        min_length=1,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    abnormal_items_text = forms.CharField(
        label="异常项目",
        required=False,
        help_text="每行填写一项，格式：项目 | 异常说明",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "冷却水路 | 水路堵塞"}),
    )
    photos_text = forms.CharField(
        label="照片 URL 或文字引用",
        required=False,
        help_text="每行一个引用，最多10项；不接收二进制文件上传",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    parts_replaced_text = forms.CharField(
        label="更换零件",
        required=False,
        help_text="每行填写一个更换件",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    source_fault_id = forms.CharField(label="故障源表 ID", max_length=100, required=False)
    actual_work_hours = forms.DecimalField(
        label="实际作业工时",
        min_value=Decimal("0.01"),
        max_value=Decimal("999.99"),
        max_digits=5,
        decimal_places=2,
    )
    abnormal_next_action = forms.ChoiceField(
        label="异常后续动作",
        required=False,
        choices=[("", "暂不选择"), *WorkOrder.AbnormalNextAction.choices],
    )

    def __init__(self, *args, work_order, **kwargs):
        self.work_order = work_order
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("submission_id", f"submission-{uuid.uuid4().hex}")
        initial.setdefault("report_form_schema_version", settings.MOLDGUARD_REPORT_SCHEMA_VERSION)
        initial.setdefault("knowledge_package_hash", work_order.knowledge_package_hash)
        super().__init__(*args, **kwargs)
        self.inspection_fields = []
        for index, item in enumerate(work_order.knowledge_package_json.get("items", [])):
            prefix = f"inspection_{index}"
            self.fields[f"{prefix}_result"] = forms.ChoiceField(
                label=item.get("item") or item["knowledge_id"],
                choices=[
                    ("PASS", "合格"),
                    ("FAIL", "不合格"),
                    ("NOT_APPLICABLE", "不适用"),
                ],
                widget=forms.RadioSelect,
            )
            self.fields[f"{prefix}_not_applicable_reason"] = forms.CharField(
                label="不适用原因",
                required=False,
                max_length=2000,
            )
            self.fields[f"{prefix}_abnormal_note"] = forms.CharField(
                label="异常说明",
                required=False,
                max_length=2000,
            )
            self.inspection_fields.append(
                {
                    "prefix": prefix,
                    "knowledge": item,
                    "result_field": self[f"{prefix}_result"],
                    "reason_field": self[f"{prefix}_not_applicable_reason"],
                    "note_field": self[f"{prefix}_abnormal_note"],
                }
            )

    def clean_report_form_schema_version(self):
        value = self.cleaned_data["report_form_schema_version"]
        if value != settings.MOLDGUARD_REPORT_SCHEMA_VERSION:
            raise forms.ValidationError("报工表单版本不匹配，请刷新页面后重试")
        return value

    def clean_knowledge_package_hash(self):
        value = self.cleaned_data["knowledge_package_hash"]
        if value != self.work_order.knowledge_package_hash:
            raise forms.ValidationError("知识包已变化，请刷新页面后重试")
        return value

    @staticmethod
    def _lines(value):
        return [line.strip() for line in (value or "").splitlines() if line.strip()]

    def clean(self):
        cleaned = super().clean()
        photos = self._lines(cleaned.get("photos_text"))
        if len(photos) > 10:
            self.add_error("photos_text", "照片 URL 或文字引用最多10项")
        parts = self._lines(cleaned.get("parts_replaced_text"))
        if len(parts) > 50:
            self.add_error("parts_replaced_text", "更换零件最多50项")
        abnormal_items = []
        for line in self._lines(cleaned.get("abnormal_items_text")):
            if "|" not in line:
                self.add_error("abnormal_items_text", "每项必须使用 项目 | 异常说明 格式")
                continue
            item, description = (part.strip() for part in line.split("|", 1))
            if not item or not description:
                self.add_error("abnormal_items_text", "异常项目和异常说明均不能为空")
                continue
            abnormal_items.append({"item": item, "description": description})
        cleaned["parsed_photos"] = photos
        cleaned["parsed_parts_replaced"] = [{"description": description} for description in parts]
        cleaned["parsed_abnormal_items"] = abnormal_items
        return cleaned

    def report_payload(self):
        inspection_results = []
        for index, item in enumerate(self.work_order.knowledge_package_json.get("items", [])):
            prefix = f"inspection_{index}"
            inspection_results.append(
                {
                    "knowledge_id": item["knowledge_id"],
                    "result": self.cleaned_data[f"{prefix}_result"],
                    "not_applicable_reason": self.cleaned_data[f"{prefix}_not_applicable_reason"],
                    "abnormal_note": self.cleaned_data[f"{prefix}_abnormal_note"],
                }
            )
        return {
            "client_request_id": self.cleaned_data["submission_id"],
            "report_type": self.cleaned_data["report_type"],
            "report_summary": self.cleaned_data["report_summary"],
            "inspection_results": inspection_results,
            "abnormal_items": self.cleaned_data["parsed_abnormal_items"],
            "photos": self.cleaned_data["parsed_photos"],
            "parts_replaced": self.cleaned_data["parsed_parts_replaced"],
            "source_fault_id": self.cleaned_data.get("source_fault_id") or None,
            "actual_work_hours": self.cleaned_data["actual_work_hours"],
            "abnormal_next_action": self.cleaned_data.get("abnormal_next_action") or None,
            "knowledge_package_hash": self.cleaned_data["knowledge_package_hash"],
        }
