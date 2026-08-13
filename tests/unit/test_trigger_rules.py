from datetime import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.platform_probe.exceptions import ProbeAPIException
from apps.platform_probe.models import Mold
from apps.platform_probe.services.trigger_service import (
    TWO_MONTH_MESSAGE,
    calculate_maintenance_status,
    threshold_for_tonnage,
)


def make_mold(**overrides):
    now = timezone.now()
    values = {
        "mold_id": "MOLD-UNIT",
        "mold_name": "单元测试模具",
        "mold_type": Mold.MoldType.INJECTION,
        "development_tonnage": 999,
        "current_count": 50_000,
        "cycle_baseline_count": 0,
        "cycle_baseline_time": now,
        "last_production_at": now,
    }
    values.update(overrides)
    return Mold(**values)


@pytest.mark.parametrize(
    ("tonnage", "expected"),
    [(1, 50_000), (999, 50_000), (1000, 30_000), (1200, 30_000)],
)
def test_tonnage_threshold_boundary(tonnage, expected):
    assert threshold_for_tonnage(tonnage) == expected


def test_missing_tonnage_is_an_explicit_error():
    with pytest.raises(ProbeAPIException) as captured:
        threshold_for_tonnage(None)

    assert captured.value.probe_code == "DEVELOPMENT_TONNAGE_NOT_CONFIGURED"


@pytest.mark.parametrize(("cycle_count", "due"), [(49_999, False), (50_000, True), (50_001, True)])
def test_threshold_is_inclusive(cycle_count, due):
    mold = make_mold(current_count=cycle_count)

    assert calculate_maintenance_status(mold).maintenance_due is due


def test_negative_cycle_count_is_rejected():
    mold = make_mold(current_count=99, cycle_baseline_count=100)

    with pytest.raises(ProbeAPIException) as captured:
        calculate_maintenance_status(mold)

    assert captured.value.probe_code == "INVALID_CYCLE_COUNT"


def test_injection_uses_two_calendar_months_with_month_end_clamping():
    baseline = timezone.make_aware(datetime(2026, 1, 31, 8, 0))
    before = timezone.make_aware(datetime(2026, 3, 31, 7, 59, 59))
    exact = timezone.make_aware(datetime(2026, 3, 31, 8, 0))
    mold = make_mold(cycle_baseline_time=baseline, current_count=1)

    assert calculate_maintenance_status(mold, before).two_month_reminder_due is False
    assert calculate_maintenance_status(mold, exact).two_month_reminder_due is True
    assert TWO_MONTH_MESSAGE == "仅表示已满2个月，不代表模次保养条件已达到。"


def test_sheet_metal_never_generates_two_month_reminder():
    mold = make_mold(
        mold_type=Mold.MoldType.SHEET_METAL,
        cycle_baseline_time=timezone.make_aware(datetime(2020, 1, 1)),
    )

    status = calculate_maintenance_status(mold)

    assert status.next_two_month_reminder_at is None
    assert status.two_month_reminder_due is False


def test_two_year_idle_mold_disables_both_automatic_reminders():
    now = timezone.make_aware(datetime(2026, 8, 13, 12, 0))
    mold = make_mold(
        last_production_at=timezone.make_aware(datetime(2024, 8, 13, 12, 0)),
        cycle_baseline_time=timezone.make_aware(datetime(2024, 1, 1)),
        current_count=Decimal("99999"),
    )

    status = calculate_maintenance_status(mold, now)

    assert status.idle_auto_reminder_disabled is True
    assert status.maintenance_due is False
    assert status.two_month_reminder_due is False
