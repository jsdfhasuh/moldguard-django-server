from django.core.management.base import BaseCommand, CommandError

from apps.molds.models import Mold
from apps.molds.services.trigger_service import evaluate_trigger
from apps.staff.models import Employee

EXPECTED_RULES = {
    "DEMO-INJ-050K": ("TRIGGERED", "INJ-COUNT-050K"),
    "DEMO-INJ-030K": ("TRIGGERED", "INJ-COUNT-030K"),
    "DEMO-INJ-TIME-2M": ("TRIGGERED", "INJ-TIME-2M"),
    "DEMO-INJ-COUNT-TIME": ("TRIGGERED", "INJ-COUNT-030K"),
    "DEMO-INJ-NO-OUTPUT-2Y": ("STOPPED", "INJ-NO-OUTPUT-2Y"),
    "DEMO-STAMP-FORM": ("TRIGGERED", "STAMP-FORM-150K"),
    "DEMO-STAMP-PUNCH": ("TRIGGERED", "STAMP-PUNCH-400K"),
    "DEMO-STAMP-CONTINUOUS": ("TRIGGERED", "STAMP-PROG-400K"),
    "DEMO-STAMP-SIDE": ("TRIGGERED", "STAMP-SIDE-400K"),
    "DEMO-STAMP-LC109-INVALID": ("ERROR", None),
}


class Command(BaseCommand):
    help = "Verify canonical DEMO IDs, rule outcomes, employee eligibility, and safe data."

    def handle(self, *args, **options):
        errors = []
        if Mold.objects.filter(mold_id__in=EXPECTED_RULES).count() != len(EXPECTED_RULES):
            errors.append("canonical 10 DEMO molds are incomplete")
        employee_ids = {
            "DEMO-EMP-INJ",
            "DEMO-EMP-STAMP",
            "DEMO-EMP-UNAVAILABLE",
            "DEMO-EMP-HIGH-LOAD",
        }
        if Employee.objects.filter(employee_id__in=employee_ids).count() != len(employee_ids):
            errors.append("canonical 4 DEMO employees are incomplete")
        for mold_id, (expected_status, expected_rule) in EXPECTED_RULES.items():
            try:
                result = evaluate_trigger(Mold.objects.get(pk=mold_id))
            except Mold.DoesNotExist:
                continue
            if result["status"] != expected_status:
                errors.append(
                    f"{mold_id} expected status {expected_status}, got {result['status']}"
                )
            if expected_rule and result.get("primary_rule_id") != expected_rule:
                errors.append(
                    f"{mold_id} expected rule {expected_rule}, got {result.get('primary_rule_id')}"
                )
        combined = evaluate_trigger(Mold.objects.get(pk="DEMO-INJ-COUNT-TIME"))
        if combined.get("matched_rule_ids") != ["INJ-COUNT-030K", "INJ-TIME-2M"]:
            errors.append("count+time DEMO mold did not merge both rules in order")
        invalid = evaluate_trigger(Mold.objects.get(pk="DEMO-STAMP-LC109-INVALID"))
        if invalid["code"] != "INVALID_LC109_CATEGORY":
            errors.append("LC109 missing-category DEMO mold did not return expected error")
        if Employee.objects.exclude(email__endswith="@example.com").exists():
            self.stdout.write(
                self.style.WARNING(
                    "DEMO employee email override is active; verify it is a test mailbox."
                )
            )
        if errors:
            raise CommandError("; ".join(errors))
        self.stdout.write(self.style.SUCCESS("MoldGuard DEMO data verified successfully."))
