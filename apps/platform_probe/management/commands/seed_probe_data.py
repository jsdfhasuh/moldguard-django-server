import json
import os
from datetime import timedelta
from pathlib import Path

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.platform_probe.models import Employee, Mold


class Command(BaseCommand):
    help = "Create or restore deterministic MoldGuard platform-probe demo data."

    @transaction.atomic
    def handle(self, *args, **options):
        data_path = Path(settings.BASE_DIR) / "data" / "probe_data.json"
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        now = timezone.now()

        for item in payload["molds"]:
            values = item.copy()
            mold_id = values.pop("mold_id")
            baseline_months = values.pop("cycle_baseline_months_ago")
            production_days = values.pop("last_production_days_ago", None)
            production_years = values.pop("last_production_years_ago", None)
            values["cycle_baseline_time"] = now - relativedelta(months=baseline_months)
            if production_years is not None:
                values["last_production_at"] = now - relativedelta(years=production_years)
            elif production_days is not None:
                values["last_production_at"] = now - timedelta(days=production_days)
            Mold.objects.update_or_create(mold_id=mold_id, defaults=values)

        for item in payload["employees"]:
            values = item.copy()
            employee_id = values.pop("employee_id")
            email_env = values.pop("email_env", None)
            default_email = values.pop("default_email")
            values["email"] = os.getenv(email_env, default_email) if email_env else default_email
            Employee.objects.update_or_create(employee_id=employee_id, defaults=values)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(payload['molds'])} demo molds and "
                f"{len(payload['employees'])} demo employees."
            )
        )
