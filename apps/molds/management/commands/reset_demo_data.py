from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.common.models import ClientRequestRecord
from apps.molds.models import Alert, Mold
from apps.staff.models import Employee
from apps.workorders.models import MaintenanceRecord, WorkOrder, WorkOrderEvent


class Command(BaseCommand):
    help = "Delete all MoldGuard business data and restore the canonical DEMO dataset."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Confirm DEMO reset.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("reset_demo_data requires --confirm")
        MaintenanceRecord.objects.all().delete()
        WorkOrderEvent.objects.all().delete()
        WorkOrder.objects.all().delete()
        Alert.objects.all().delete()
        Employee.objects.all().delete()
        Mold.objects.all().delete()
        ClientRequestRecord.objects.all().delete()
        call_command("seed_demo_data")
        self.stdout.write(self.style.SUCCESS("MoldGuard DEMO data reset complete."))
