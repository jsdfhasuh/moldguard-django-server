from django.core.management.base import BaseCommand, CommandError

from apps.platform_probe.models import Mold
from apps.platform_probe.services.trigger_service import calculate_maintenance_status


class Command(BaseCommand):
    help = "Verify the canonical probe scenarios are present and internally consistent."

    def handle(self, *args, **options):
        expected_ids = {f"MOLD-TEST-{index:03d}" for index in range(1, 8)}
        actual_ids = set(
            Mold.objects.filter(mold_id__in=expected_ids).values_list("mold_id", flat=True)
        )
        if actual_ids != expected_ids:
            missing = sorted(expected_ids - actual_ids)
            raise CommandError(f"Missing demo molds: {', '.join(missing)}")

        checks = {
            "MOLD-TEST-001": (50_000, True, False),
            "MOLD-TEST-002": (30_000, True, False),
            "MOLD-TEST-003": (50_000, False, True),
            "MOLD-TEST-004": (50_000, False, False),
            "MOLD-TEST-005": (50_000, False, False),
            "MOLD-TEST-007": (30_000, True, False),
        }
        for mold_id, expected in checks.items():
            status = calculate_maintenance_status(Mold.objects.get(mold_id=mold_id))
            actual = (status.threshold, status.maintenance_due, status.two_month_reminder_due)
            if actual != expected:
                raise CommandError(
                    f"Unexpected scenario for {mold_id}: {actual}, expected {expected}"
                )

        idle = calculate_maintenance_status(Mold.objects.get(mold_id="MOLD-TEST-004"))
        if not idle.idle_auto_reminder_disabled:
            raise CommandError("MOLD-TEST-004 must disable automatic reminders")

        self.stdout.write(self.style.SUCCESS("Probe demo data verified successfully."))
