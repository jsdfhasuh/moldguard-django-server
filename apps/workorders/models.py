from pathlib import Path

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.molds.models import Alert, Mold
from apps.staff.models import Employee


class WorkOrder(models.Model):
    class Type(models.TextChoices):
        CYCLE_COUNT = "CYCLE_COUNT_MAINTENANCE", "模次周期保养"
        CYCLE_TIME = "CYCLE_TIME_MAINTENANCE", "时间周期保养"
        REPAIR_SYNC = "REPAIR_SYNC_MAINTENANCE", "修模同步保养"
        REPAIR_TASK = "REPAIR_TASK", "修模任务"
        LIGHTWEIGHT_DAILY = "LIGHTWEIGHT_DAILY", "日常保养"
        LIGHTWEIGHT_PRE = "LIGHTWEIGHT_PRE_PRODUCTION", "生产前保养"
        LIGHTWEIGHT_POST = "LIGHTWEIGHT_POST_PRODUCTION", "生产后保养"
        LIGHTWEIGHT_FIXED = "LIGHTWEIGHT_FIXED_FREQUENCY", "固定频次保养"
        STORAGE = "STORAGE_INSPECTION", "储放检查"

    class Status(models.TextChoices):
        PENDING_ASSIGNMENT = "PENDING_ASSIGNMENT", "待派工"
        ASSIGNED = "ASSIGNED", "已派工"
        IN_PROGRESS = "IN_PROGRESS", "进行中"
        PAUSED = "PAUSED", "暂停"
        ABNORMAL_REPORTED = "ABNORMAL_REPORTED", "异常已报"
        REPAIR_LINKED = "REPAIR_LINKED", "已关联修模"
        COMPLETED = "COMPLETED", "已完成"
        CANCELLED = "CANCELLED", "已取消"

    class EmailStatus(models.TextChoices):
        NOT_SENT = "NOT_SENT", "未发送"
        SENDING = "SENDING", "发送中"
        FAILED = "FAILED", "失败"
        SENT = "SENT", "已发送"
        OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN", "发送结果未知"

    class ReportMethod(models.TextChoices):
        WEB_FORM = "WEB_FORM", "网页或JSON报工"

    class ReportType(models.TextChoices):
        NORMAL = "NORMAL", "正常"
        ABNORMAL = "ABNORMAL", "异常"

    class AbnormalNextAction(models.TextChoices):
        CONTINUE_PROCESSING = "CONTINUE_PROCESSING", "继续处理"
        CREATE_REPAIR_TASK = "CREATE_REPAIR_TASK", "创建修模任务"

    work_order_id = models.CharField(max_length=64, primary_key=True)
    alert = models.ForeignKey(
        Alert, null=True, blank=True, on_delete=models.PROTECT, related_name="work_orders"
    )
    mold = models.ForeignKey(Mold, on_delete=models.PROTECT, related_name="work_orders")
    parent_work_order = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="repair_tasks"
    )
    linked_repair_order = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    primary_rule_id = models.CharField(max_length=100)
    matched_rule_ids_json = models.JSONField(default=list)
    work_order_type = models.CharField(max_length=48, choices=Type.choices)
    status = models.CharField(
        max_length=40, choices=Status.choices, default=Status.PENDING_ASSIGNMENT
    )
    assignee = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.PROTECT, related_name="work_orders"
    )
    standard_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    required_finish_at = models.DateTimeField(null=True, blank=True)
    create_key = models.CharField(max_length=200, unique=True)
    effective_mold_cycles_snapshot = models.PositiveBigIntegerField()
    baseline_effective_mold_cycles_before = models.PositiveBigIntegerField()
    baseline_maintenance_at_before = models.DateTimeField()
    cycle_mold_cycles_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    threshold_count = models.PositiveBigIntegerField(null=True, blank=True)
    trigger_reason = models.TextField()
    triggered_at = models.DateTimeField()
    reset_count_cycle = models.BooleanField(default=False)
    reset_time_cycle = models.BooleanField(default=False)
    knowledge_snapshot_version = models.CharField(max_length=64, default="MOLDGUARD-KB-1.2")
    knowledge_package_json = models.JSONField(default=dict)
    knowledge_package_hash = models.CharField(max_length=64, blank=True, default="")
    knowledge_locked_at = models.DateTimeField(null=True, blank=True)
    inspection_results_json = models.JSONField(default=list)
    email_recipient = models.EmailField(null=True, blank=True)
    email_subject = models.CharField(max_length=240, blank=True, default="")
    email_status = models.CharField(
        max_length=24, choices=EmailStatus.choices, default=EmailStatus.NOT_SENT
    )
    email_message_id = models.CharField(max_length=200, blank=True, default="")
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True, default="")
    report_method = models.CharField(
        max_length=24, choices=ReportMethod.choices, default=ReportMethod.WEB_FORM
    )
    report_form_schema_version = models.CharField(max_length=32, default="REPORT-FORM-1.1")
    report_type = models.CharField(max_length=24, choices=ReportType.choices, null=True, blank=True)
    report_summary = models.TextField(blank=True, default="")
    abnormal_items_json = models.JSONField(default=list)
    photos_json = models.JSONField(default=list)
    parts_replaced_json = models.JSONField(default=list)
    source_fault_id = models.CharField(max_length=100, blank=True, default="")
    fault_type = models.CharField(max_length=120, blank=True, default="")
    fault_description = models.TextField(blank=True, default="")
    standard_repair_hours = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    actual_work_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    abnormal_next_action = models.CharField(
        max_length=40, choices=AbnormalNextAction.choices, blank=True, default=""
    )
    repair_reason = models.TextField(blank=True, default="")
    assigned_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    pause_started_at = models.DateTimeField(null=True, blank=True)
    paused_seconds = models.PositiveBigIntegerField(default=0)
    reported_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["mold", "status"]),
            models.Index(fields=["assignee", "status"]),
        ]

    def __str__(self):
        return self.work_order_id


class WorkOrderEvent(models.Model):
    event_id = models.CharField(max_length=64, primary_key=True)
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=80)
    from_status = models.CharField(max_length=40, blank=True, default="")
    to_status = models.CharField(max_length=40, blank=True, default="")
    operator_id = models.CharField(max_length=80, blank=True, default="")
    remarks = models.TextField(blank=True, default="")
    event_data_json = models.JSONField(default=dict)
    request_key = models.CharField(max_length=200, null=True, blank=True, unique=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["work_order", "occurred_at"])]

    def __str__(self):
        return self.event_id


class MaintenanceRecord(models.Model):
    class Result(models.TextChoices):
        NORMAL = "NORMAL", "正常"

    record_id = models.CharField(max_length=64, primary_key=True)
    mold = models.ForeignKey(Mold, on_delete=models.PROTECT, related_name="maintenance_records")
    work_order = models.OneToOneField(
        WorkOrder, on_delete=models.PROTECT, related_name="maintenance_record"
    )
    record_type = models.CharField(max_length=48, choices=WorkOrder.Type.choices)
    occurred_at = models.DateTimeField()
    effective_mold_cycles_snapshot = models.PositiveBigIntegerField()
    baseline_count_before = models.PositiveBigIntegerField()
    baseline_time_before = models.DateTimeField()
    baseline_count_after = models.PositiveBigIntegerField()
    baseline_time_after = models.DateTimeField()
    reset_count_cycle = models.BooleanField()
    reset_time_cycle = models.BooleanField()
    knowledge_snapshot_version = models.CharField(max_length=64)
    knowledge_package_hash = models.CharField(max_length=64)
    standard_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    actual_work_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    result = models.CharField(max_length=24, choices=Result.choices)
    note = models.TextField(blank=True, default="")
    request_key = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["mold", "occurred_at"])]

    def __str__(self):
        return self.record_id


class ReportSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING_REVIEW = "PENDING_REVIEW", "等待AI审核"
        FINALIZED = "FINALIZED", "已完成Django裁决"
        NEEDS_MORE_INFO = "NEEDS_MORE_INFO", "需要补充材料"

    class ReviewDecision(models.TextChoices):
        COMPLETE = "COMPLETE", "建议完成"
        ABNORMAL = "ABNORMAL", "建议异常报工"
        NEEDS_MORE_INFO = "NEEDS_MORE_INFO", "需要补充材料"

    class WebhookStatus(models.TextChoices):
        PENDING = "PENDING", "等待触发"
        SENDING = "SENDING", "触发中"
        DELIVERED = "DELIVERED", "已送达"
        FAILED = "FAILED", "触发失败"
        NOT_CONFIGURED = "NOT_CONFIGURED", "未配置"

    submission_id = models.CharField(max_length=64, primary_key=True)
    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.CASCADE, related_name="report_submissions"
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING_REVIEW)
    client_request_id = models.CharField(max_length=120, unique=True)
    report_text = models.TextField()
    actual_work_hours = models.DecimalField(max_digits=8, decimal_places=2)
    parts_replaced_json = models.JSONField(default=list)
    source_fault_id = models.CharField(max_length=100, blank=True, default="")
    knowledge_package_hash = models.CharField(max_length=64)
    review_decision = models.CharField(
        max_length=32, choices=ReviewDecision.choices, blank=True, default=""
    )
    review_confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    review_summary = models.TextField(blank=True, default="")
    review_payload_json = models.JSONField(default=dict)
    final_report_data_json = models.JSONField(default=dict)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    webhook_status = models.CharField(
        max_length=32, choices=WebhookStatus.choices, default=WebhookStatus.PENDING
    )
    webhook_error = models.TextField(blank=True, default="")
    webhook_delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["work_order", "status", "created_at"]),
            models.Index(fields=["webhook_status", "created_at"]),
        ]

    def __str__(self):
        return self.submission_id


def report_evidence_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"report-evidence/{instance.submission_id}/{instance.evidence_id}{extension}"


class ReportEvidence(models.Model):
    evidence_id = models.CharField(max_length=64, primary_key=True)
    submission = models.ForeignKey(
        ReportSubmission, on_delete=models.CASCADE, related_name="evidence"
    )
    file = models.FileField(upload_to=report_evidence_upload_to, max_length=500)
    original_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100)
    byte_size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    display_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "created_at", "evidence_id"]

    def __str__(self):
        return self.evidence_id


@receiver(post_delete, sender=ReportEvidence)
def delete_report_evidence_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
