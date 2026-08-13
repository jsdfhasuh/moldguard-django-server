import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.utils import timezone


def _load_defaults():
    path = Path(settings.BASE_DIR) / "data" / "demo" / "work_order_defaults.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_work_order_defaults(mold_id, primary_rule_id, triggered_at=None):
    payload = _load_defaults()
    config = payload.get("by_mold", {}).get(mold_id)
    if config is None:
        config = payload.get("by_rule", {}).get(primary_rule_id)
    if config is None:
        return None, None
    standard_hours = config.get("standard_hours")
    finish_hours = config.get("required_finish_hours")
    standard = Decimal(str(standard_hours)) if standard_hours is not None else None
    required_finish = None
    if finish_hours is not None:
        required_finish = (triggered_at or timezone.now()) + timezone.timedelta(
            hours=float(finish_hours)
        )
    return standard, required_finish
