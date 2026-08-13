from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.molds.models import Mold
from apps.workorders.models import WorkOrder

INJECTION_COUNT_RULES = {
    "LOW_TONNAGE": ("INJ-COUNT-050K", 50_000),
    "HIGH_TONNAGE": ("INJ-COUNT-030K", 30_000),
}
SHEET_RULES = {
    Mold.Category.FORMING: ("STAMP-FORM-150K", 150_000, {"LC102", "LC104", "LC106", "LC107"}),
    Mold.Category.PUNCH_BLANKING: (
        "STAMP-PUNCH-400K",
        400_000,
        {"LC101", "LC103", "LC105"},
    ),
    Mold.Category.CONTINUOUS: ("STAMP-PROG-400K", 400_000, {"LC109"}),
    Mold.Category.SIDE_PANEL: ("STAMP-SIDE-400K", 400_000, {"LC109"}),
}


def _base(mold):
    return {
        "mold_id": mold.mold_id,
        "mold_type": mold.mold_type,
        "cycle_version": mold.cycle_version,
        "effective_mold_cycles": mold.effective_mold_cycles,
        "baseline_effective_mold_cycles": mold.baseline_effective_mold_cycles,
        "cycle_mold_cycles": mold.cycle_mold_cycles,
    }


def _result(mold, status, code, message, **extra):
    return {**_base(mold), "status": status, "code": code, "message": message, **extra}


def _injection_trigger(mold, now):
    if mold.output_updated_at is None:
        return _result(
            mold,
            "ERROR",
            "OUTPUT_UPDATED_AT_NOT_CONFIGURED",
            "注塑模具缺少output_updated_at，无法判断两年停扫条件",
            missing_fields=["output_updated_at"],
        )
    if mold.output_updated_at and now >= mold.output_updated_at + relativedelta(years=2):
        return _result(
            mold,
            "STOPPED",
            "INJ_NO_OUTPUT_2Y",
            "连续两年未更新产量，停止自动建立正式保养工单",
            primary_rule_id="INJ-NO-OUTPUT-2Y",
            matched_rule_ids=["INJ-NO-OUTPUT-2Y"],
            stopped_auto_creation=True,
        )
    if mold.development_tonnage is None:
        return _result(
            mold,
            "ERROR",
            "DEVELOPMENT_TONNAGE_NOT_CONFIGURED",
            "注塑模具缺少development_tonnage",
            missing_fields=["development_tonnage"],
        )
    if mold.development_tonnage < Decimal("1000.00"):
        count_rule, threshold = INJECTION_COUNT_RULES["LOW_TONNAGE"]
    else:
        count_rule, threshold = INJECTION_COUNT_RULES["HIGH_TONNAGE"]

    count_due = mold.cycle_mold_cycles >= threshold
    baseline_time = mold.baseline_maintenance_at or mold.first_production_at
    if baseline_time is None:
        return _result(
            mold,
            "ERROR",
            "MAINTENANCE_BASELINE_NOT_CONFIGURED",
            "注塑模具缺少baseline_maintenance_at和first_production_at",
            missing_fields=["baseline_maintenance_at", "first_production_at"],
            threshold_count=threshold,
            next_due_count=mold.baseline_effective_mold_cycles + threshold,
        )
    time_due_at = baseline_time + relativedelta(months=2)
    time_due = now >= time_due_at
    matched = []
    if count_due:
        matched.append(count_rule)
    if time_due:
        matched.append("INJ-TIME-2M")
    if not matched:
        return _result(
            mold,
            "NOT_DUE",
            "MAINTENANCE_NOT_DUE",
            "未达到注塑模次或两个月时间条件",
            primary_rule_id=count_rule,
            matched_rule_ids=[],
            threshold_count=threshold,
            next_due_count=mold.baseline_effective_mold_cycles + threshold,
            next_due_time=time_due_at.isoformat(),
        )

    primary = count_rule if count_due else "INJ-TIME-2M"
    work_order_type = WorkOrder.Type.CYCLE_COUNT if count_due else WorkOrder.Type.CYCLE_TIME
    reasons = []
    if count_due:
        reasons.append(f"本周期有效模次{mold.cycle_mold_cycles}达到{threshold}模次")
    if time_due:
        reasons.append(f"周期基准时间{baseline_time.isoformat()}起已满两个自然月")
    return _result(
        mold,
        "TRIGGERED",
        "MAINTENANCE_TRIGGERED",
        "；".join(reasons),
        primary_rule_id=primary,
        matched_rule_ids=matched,
        threshold_count=threshold if count_due else None,
        work_order_type=work_order_type,
        trigger_reason="；".join(reasons),
        reset_count_cycle=True,
        reset_time_cycle=True,
        next_due_count=mold.baseline_effective_mold_cycles + threshold,
        next_due_time=time_due_at.isoformat(),
    )


def _sheet_trigger(mold):
    if not mold.mold_category:
        code = (
            "INVALID_LC109_CATEGORY"
            if mold.mold_type_code == "LC109"
            else "MOLD_CATEGORY_NOT_CONFIGURED"
        )
        return _result(
            mold,
            "ERROR",
            code,
            "钣金模具缺少明确且有效的mold_category",
            missing_fields=["mold_category"],
        )
    if not mold.mold_type_code:
        return _result(
            mold,
            "ERROR",
            "MOLD_TYPE_CODE_NOT_CONFIGURED",
            "钣金模具缺少mold_type_code",
            missing_fields=["mold_type_code"],
        )
    if mold.mold_type_code == "LC109" and mold.mold_category not in {
        Mold.Category.CONTINUOUS,
        Mold.Category.SIDE_PANEL,
    }:
        return _result(
            mold,
            "ERROR",
            "INVALID_LC109_CATEGORY",
            "LC109必须明确为CONTINUOUS或SIDE_PANEL",
        )
    rule_config = SHEET_RULES.get(mold.mold_category)
    if rule_config is None:
        return _result(mold, "ERROR", "MOLD_CATEGORY_NOT_CONFIGURED", "钣金模具类别无对应冻结规则")
    rule_id, threshold, allowed_codes = rule_config
    if mold.mold_type_code not in allowed_codes:
        return _result(
            mold,
            "ERROR",
            "MOLD_TYPE_CODE_CATEGORY_MISMATCH",
            "mold_type_code与mold_category不匹配冻结规则",
            primary_rule_id=rule_id,
        )
    if mold.cycle_mold_cycles < threshold:
        return _result(
            mold,
            "NOT_DUE",
            "MAINTENANCE_NOT_DUE",
            "未达到钣金专项保养模次阈值",
            primary_rule_id=rule_id,
            matched_rule_ids=[],
            threshold_count=threshold,
            next_due_count=mold.baseline_effective_mold_cycles + threshold,
            next_due_time=None,
        )
    reason = f"本周期有效模次{mold.cycle_mold_cycles}达到{threshold}模次"
    return _result(
        mold,
        "TRIGGERED",
        "MAINTENANCE_TRIGGERED",
        reason,
        primary_rule_id=rule_id,
        matched_rule_ids=[rule_id],
        threshold_count=threshold,
        work_order_type=WorkOrder.Type.CYCLE_COUNT,
        trigger_reason=reason,
        reset_count_cycle=True,
        reset_time_cycle=True,
        next_due_count=mold.baseline_effective_mold_cycles + threshold,
        next_due_time=None,
    )


def evaluate_trigger(mold, *, now=None):
    now = now or timezone.now()
    if mold.baseline_effective_mold_cycles > mold.effective_mold_cycles:
        return _result(mold, "ERROR", "INVALID_CYCLE_COUNT", "周期基准模次不能大于当前有效模次")
    if mold.status == Mold.Status.DISABLED:
        return _result(mold, "SKIPPED", "MOLD_DISABLED", "禁用模具不参与扫描")
    if mold.status == Mold.Status.INACTIVE:
        return _result(mold, "SKIPPED", "MOLD_INACTIVE", "停用模具不自动建立工单")
    if mold.status == Mold.Status.UNDER_REPAIR:
        return _result(mold, "SKIPPED", "MOLD_UNDER_REPAIR", "维修中模具不自动建立工单")
    if mold.mold_type == Mold.Type.INJECTION:
        return _injection_trigger(mold, now)
    if mold.mold_type == Mold.Type.SHEET_METAL:
        return _sheet_trigger(mold)
    return _result(mold, "ERROR", "INVALID_MOLD_TYPE", "未知模具类型")
