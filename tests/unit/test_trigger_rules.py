from decimal import Decimal

import pytest
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.molds.models import Mold
from apps.molds.services.trigger_service import evaluate_trigger
from apps.workorders.models import WorkOrder


def mold(**overrides):
    now = overrides.pop("now", timezone.now())
    values = {
        "mold_id": "UNIT-MOLD",
        "mold_name": "单元测试模具",
        "mold_type": Mold.Type.INJECTION,
        "effective_mold_cycles": 50_000,
        "baseline_effective_mold_cycles": 0,
        "baseline_maintenance_at": now - relativedelta(months=1),
        "cycle_version": 1,
        "first_production_at": now - relativedelta(years=1),
        "development_tonnage": Decimal("999.99"),
        "output_updated_at": now,
        "status": Mold.Status.ACTIVE,
    }
    values.update(overrides)
    return Mold(**values)


@pytest.mark.parametrize(
    ("tonnage", "cycles", "rule_id", "threshold"),
    [
        ("999.99", 50_000, "INJ-COUNT-050K", 50_000),
        ("1000.00", 30_000, "INJ-COUNT-030K", 30_000),
    ],
)
def test_injection_tonnage_boundary(tonnage, cycles, rule_id, threshold):
    result = evaluate_trigger(
        mold(
            development_tonnage=Decimal(tonnage),
            effective_mold_cycles=cycles,
            baseline_effective_mold_cycles=0,
        )
    )
    assert result["status"] == "TRIGGERED"
    assert result["primary_rule_id"] == rule_id
    assert result["threshold_count"] == threshold


@pytest.mark.parametrize(
    ("tonnage", "cycles"),
    [("999.99", 49_999), ("1000.00", 29_999)],
)
def test_injection_one_cycle_below_threshold_is_not_due(tonnage, cycles):
    result = evaluate_trigger(
        mold(
            development_tonnage=Decimal(tonnage),
            effective_mold_cycles=cycles,
            baseline_effective_mold_cycles=0,
        )
    )
    assert result["status"] == "NOT_DUE"
    assert result["matched_rule_ids"] == []


def test_invalid_cycle_baseline_returns_explicit_error():
    result = evaluate_trigger(mold(effective_mold_cycles=999, baseline_effective_mold_cycles=1_000))
    assert result["status"] == "ERROR"
    assert result["code"] == "INVALID_CYCLE_COUNT"


def test_injection_two_calendar_months_uses_calendar_arithmetic():
    baseline = timezone.datetime(2026, 1, 31, 9, tzinfo=timezone.get_current_timezone())
    now = timezone.datetime(2026, 3, 31, 9, tzinfo=timezone.get_current_timezone())
    result = evaluate_trigger(
        mold(
            now=now,
            effective_mold_cycles=100,
            baseline_maintenance_at=baseline,
            output_updated_at=now,
        ),
        now=now,
    )
    assert result["primary_rule_id"] == "INJ-TIME-2M"
    assert result["work_order_type"] == WorkOrder.Type.CYCLE_TIME


def test_two_year_no_output_stops_auto_creation():
    now = timezone.now()
    result = evaluate_trigger(
        mold(output_updated_at=now - relativedelta(years=2), now=now), now=now
    )
    assert result["status"] == "STOPPED"
    assert result["primary_rule_id"] == "INJ-NO-OUTPUT-2Y"
    assert result["stopped_auto_creation"] is True


@pytest.mark.parametrize(
    ("category", "type_code", "threshold", "rule_id"),
    [
        (Mold.Category.FORMING, "LC102", 150_000, "STAMP-FORM-150K"),
        (Mold.Category.PUNCH_BLANKING, "LC101", 400_000, "STAMP-PUNCH-400K"),
        (Mold.Category.CONTINUOUS, "LC109", 400_000, "STAMP-PROG-400K"),
        (Mold.Category.SIDE_PANEL, "LC109", 400_000, "STAMP-SIDE-400K"),
    ],
)
def test_sheet_metal_final_rules(category, type_code, threshold, rule_id):
    result = evaluate_trigger(
        mold(
            mold_type=Mold.Type.SHEET_METAL,
            development_tonnage=None,
            mold_category=category,
            mold_type_code=type_code,
            effective_mold_cycles=threshold,
        )
    )
    assert result["primary_rule_id"] == rule_id
    assert result["threshold_count"] == threshold


def test_lc109_requires_explicit_valid_category():
    result = evaluate_trigger(
        mold(
            mold_type=Mold.Type.SHEET_METAL,
            development_tonnage=None,
            mold_category=None,
            mold_type_code="LC109",
            effective_mold_cycles=400_000,
        )
    )
    assert result["status"] == "ERROR"
    assert result["code"] == "INVALID_LC109_CATEGORY"


def test_injection_count_and_time_merge_count_as_primary():
    now = timezone.now()
    result = evaluate_trigger(
        mold(
            now=now,
            development_tonnage=Decimal("1000.00"),
            effective_mold_cycles=30_000,
            baseline_maintenance_at=now - relativedelta(months=2),
        ),
        now=now,
    )
    assert result["matched_rule_ids"] == ["INJ-COUNT-030K", "INJ-TIME-2M"]
    assert result["primary_rule_id"] == "INJ-COUNT-030K"
    assert result["work_order_type"] == WorkOrder.Type.CYCLE_COUNT
