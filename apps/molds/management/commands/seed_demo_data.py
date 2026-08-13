import json
import os
from decimal import Decimal
from pathlib import Path

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.molds.models import Mold
from apps.staff.models import Employee


class Command(BaseCommand):
    help = "Create or update deterministic MoldGuard DEMO molds and employees."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Only seed when both the mold and employee tables are empty.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["if_empty"] and (Mold.objects.exists() or Employee.objects.exists()):
            self.stdout.write("DEMO data already exists; initial seed skipped.")
            return
        path = Path(settings.BASE_DIR) / "data" / "demo" / "demo_data.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        now = timezone.now()
        for item in payload["molds"]:
            values = item.copy()
            mold_id = values.pop("mold_id")
            baseline_months_ago = values.pop("baseline_months_ago")
            first_months_ago = values.pop("first_production_months_ago", None)
            output_months_ago = values.pop("output_months_ago", None)
            values["baseline_maintenance_at"] = now - relativedelta(months=baseline_months_ago)
            values["first_production_at"] = (
                now - relativedelta(months=first_months_ago)
                if first_months_ago is not None
                else None
            )
            values["output_updated_at"] = (
                now - relativedelta(months=output_months_ago)
                if output_months_ago is not None
                else None
            )
            if values.get("development_tonnage") is not None:
                values["development_tonnage"] = Decimal(values["development_tonnage"])
            Mold.objects.update_or_create(mold_id=mold_id, defaults=values)
        for item in payload["employees"]:
            values = item.copy()
            employee_id = values.pop("employee_id")
            email_env = values.pop("email_env")
            email_default = values.pop("email_default")
            values["email"] = os.getenv(email_env, email_default)
            values["current_load"] = Decimal(values["current_load"])
            Employee.objects.update_or_create(employee_id=employee_id, defaults=values)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(payload['molds'])} DEMO molds and "
                f"{len(payload['employees'])} DEMO employees."
            )
        )
