from dataclasses import asdict, dataclass

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.platform_probe.exceptions import ProbeAPIException
from apps.platform_probe.models import Mold

TWO_MONTH_MESSAGE = "仅表示已满2个月，不代表模次保养条件已达到。"


@dataclass(frozen=True)
class MaintenanceStatus:
    mold_id: str
    cycle_version: int
    development_tonnage: int
    cycle_count: int
    threshold: int
    next_trigger_count: int
    maintenance_due: bool
    next_two_month_reminder_at: str | None
    two_month_reminder_due: bool
    idle_auto_reminder_disabled: bool

    def to_dict(self):
        return asdict(self)


def threshold_for_tonnage(development_tonnage):
    if development_tonnage is None:
        raise ProbeAPIException(
            "DEVELOPMENT_TONNAGE_NOT_CONFIGURED",
            "模具未配置开发吨位",
        )
    return 50_000 if development_tonnage < 1000 else 30_000


def cycle_count_for(mold):
    cycle_count = mold.current_count - mold.cycle_baseline_count
    if cycle_count < 0:
        raise ProbeAPIException("INVALID_CYCLE_COUNT", "当前模次不能小于周期基准模次")
    return cycle_count


def is_idle(mold, now=None):
    now = now or timezone.now()
    return bool(mold.last_production_at and mold.last_production_at <= now - relativedelta(years=2))


def calculate_maintenance_status(mold, now=None):
    now = now or timezone.now()
    threshold = threshold_for_tonnage(mold.development_tonnage)
    cycle_count = cycle_count_for(mold)
    idle = is_idle(mold, now)

    reminder_at = None
    reminder_due = False
    if mold.mold_type == Mold.MoldType.INJECTION:
        reminder = mold.cycle_baseline_time + relativedelta(months=2)
        reminder_at = reminder.isoformat()
        reminder_due = not idle and now >= reminder

    return MaintenanceStatus(
        mold_id=mold.mold_id,
        cycle_version=mold.cycle_version,
        development_tonnage=mold.development_tonnage,
        cycle_count=cycle_count,
        threshold=threshold,
        next_trigger_count=mold.cycle_baseline_count + threshold,
        maintenance_due=not idle and cycle_count >= threshold,
        next_two_month_reminder_at=reminder_at,
        two_month_reminder_due=reminder_due,
        idle_auto_reminder_disabled=idle,
    )
