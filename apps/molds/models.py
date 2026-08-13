from django.db import models
from django.db.models import F, Q


class Mold(models.Model):
    class Type(models.TextChoices):
        INJECTION = "INJECTION", "注塑"
        SHEET_METAL = "SHEET_METAL", "钣金"

    class Category(models.TextChoices):
        FORMING = "FORMING", "成型"
        PUNCH_BLANKING = "PUNCH_BLANKING", "冲孔落料"
        CONTINUOUS = "CONTINUOUS", "连续模"
        SIDE_PANEL = "SIDE_PANEL", "边板"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "启用"
        INACTIVE = "INACTIVE", "停用"
        UNDER_REPAIR = "UNDER_REPAIR", "维修中"
        DISABLED = "DISABLED", "禁用"

    mold_id = models.CharField(max_length=64, primary_key=True)
    mold_name = models.CharField(max_length=200)
    mold_type = models.CharField(max_length=32, choices=Type.choices)
    effective_mold_cycles = models.PositiveBigIntegerField()
    baseline_effective_mold_cycles = models.PositiveBigIntegerField()
    baseline_maintenance_at = models.DateTimeField()
    cycle_version = models.PositiveIntegerField(default=1)
    first_production_at = models.DateTimeField(null=True, blank=True)
    development_tonnage = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    mold_category = models.CharField(max_length=40, choices=Category.choices, null=True, blank=True)
    mold_type_code = models.CharField(max_length=32, null=True, blank=True)
    level_1_location = models.CharField(max_length=120, blank=True, default="")
    level_2_location = models.CharField(max_length=120, blank=True, default="")
    production_line = models.CharField(max_length=120, blank=True, default="")
    output_updated_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    knowledge_profile_code = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(effective_mold_cycles__gte=0),
                name="mold_effective_cycles_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(baseline_effective_mold_cycles__gte=0),
                name="mold_baseline_cycles_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(baseline_effective_mold_cycles__lte=F("effective_mold_cycles")),
                name="mold_baseline_lte_effective",
            ),
            models.CheckConstraint(
                condition=Q(cycle_version__gte=1), name="mold_cycle_version_gte_1"
            ),
        ]
        indexes = [
            models.Index(fields=["status", "mold_type"]),
            models.Index(fields=["mold_type_code", "mold_category"]),
        ]

    def __str__(self):
        return f"{self.mold_id} {self.mold_name}"

    @property
    def cycle_mold_cycles(self):
        return self.effective_mold_cycles - self.baseline_effective_mold_cycles


class Alert(models.Model):
    class Type(models.TextChoices):
        FORMAL_MAINTENANCE = "FORMAL_MAINTENANCE", "正式保养"
        MANUAL = "MANUAL", "手工"

    class Status(models.TextChoices):
        OPEN = "OPEN", "开放"
        CLOSED = "CLOSED", "关闭"

    alert_id = models.CharField(max_length=64, primary_key=True)
    mold = models.ForeignKey(Mold, on_delete=models.PROTECT, related_name="alerts")
    primary_rule_id = models.CharField(max_length=100)
    matched_rule_ids_json = models.JSONField(default=list)
    alert_type = models.CharField(max_length=40, choices=Type.choices)
    cycle_version = models.PositiveIntegerField()
    cycle_mold_cycles_snapshot = models.PositiveBigIntegerField(null=True)
    threshold_count = models.PositiveBigIntegerField(null=True)
    trigger_reason = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    dedupe_key = models.CharField(max_length=200, unique=True)
    triggered_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "triggered_at"]),
            models.Index(fields=["mold", "cycle_version"]),
        ]

    def __str__(self):
        return self.alert_id
