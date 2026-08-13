from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Delete all probe-app records and restore the canonical demo dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        app_config = apps.get_app_config("platform_probe")
        for model in reversed(list(app_config.get_models())):
            model.objects.all().delete()
        call_command("seed_probe_data")
        self.stdout.write(self.style.SUCCESS("Probe demo data reset complete."))
