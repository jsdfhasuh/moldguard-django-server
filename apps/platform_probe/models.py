import uuid

from django.db import models


def _prefixed_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def new_alert_id():
    return _prefixed_id("ALT")


class Mold(models.Model):
    class MoldType(models.TextChoices):
        INJECTION = "INJECTION", "注塑模具"
        SHEET_METAL = "SHEET_METAL", "钣金模具"

    class Status(models.TextChoices):
        IN_PRODUCTION = "IN_PRODUCTION", "生产中"
        IN_STORAGE = "IN_STORAGE", "库中"
        UNDER_REPAIR = "UNDER_REPAIR", "维修中"
        DISABLED = "DISABLED", "停用"

    class ResetType(models.TextChoices):
        MAINTENANCE_COMPLETED = "MAINTENANCE_COMPLETED", "保养完成"
        REPAIR_COMPLETED = "REPAIR_COMPLETED", "修模完成"
        INSERT_REPLACED = "INSERT_REPLACED", "换镶件完成"
        HISTORY_IMPORTED = "HISTORY_IMPORTED", "历史记录导入"

    mold_id = models.CharField(primary_key=True, max_length=40)
    mold_name = models.CharField(max_length=120)
    mold_type = models.CharField(max_length=20, choices=MoldType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PRODUCTION,
    )
    development_tonnage = models.PositiveIntegerField(null=True, blank=True)
    current_count = models.BigIntegerField(default=0)
    cycle_baseline_count = models.BigIntegerField(default=0)
    cycle_baseline_time = models.DateTimeField()
    cycle_version = models.PositiveIntegerField(default=1)
    last_production_at = models.DateTimeField(null=True, blank=True)
    last_reset_type = models.CharField(
        max_length=40,
        choices=ResetType.choices,
        blank=True,
        default="",
    )
    last_reset_event_id = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["mold_id"]

    def __str__(self):
        return f"{self.mold_id} {self.mold_name}"


class MaintenanceAlert(models.Model):
    class AlertType(models.TextChoices):
        MAINTENANCE_DUE = "MAINTENANCE_DUE", "模次保养到期"
        TWO_MONTH_REMINDER = "TWO_MONTH_REMINDER", "注塑两个月提醒"
        IDLE_AUTO_REMINDER_DISABLED = (
            "IDLE_AUTO_REMINDER_DISABLED",
            "两年无产量停止自动提醒",
        )

    class Status(models.TextChoices):
        OPEN = "OPEN", "开放"
        WORK_ORDER_CREATED = "WORK_ORDER_CREATED", "已创建工单"
        CLOSED = "CLOSED", "关闭"

    alert_id = models.CharField(
        primary_key=True, max_length=40, default=new_alert_id, editable=False
    )
    mold = models.ForeignKey(Mold, on_delete=models.CASCADE, related_name="alerts")
    alert_type = models.CharField(max_length=40, choices=AlertType.choices)
    cycle_version = models.PositiveIntegerField()
    cycle_count_snapshot = models.BigIntegerField(default=0)
    threshold_snapshot = models.PositiveIntegerField(null=True, blank=True)
    trigger_basis_json = models.JSONField(default=dict)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "alert_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["mold", "alert_type", "cycle_version"],
                name="uniq_alert_per_mold_type_cycle",
            )
        ]

    def __str__(self):
        return f"{self.alert_id} {self.mold_id} {self.alert_type}"
