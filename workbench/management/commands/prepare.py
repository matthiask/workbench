from django.core.management.base import BaseCommand

from workbench.awt.models import WorkingTimeModel


class Command(BaseCommand):
    help = "Prepare for the createsuperuser command"

    def handle(self, **options):
        wt = WorkingTimeModel.objects.first()
        if not wt:
            wt = WorkingTimeModel.objects.create(name="Arbeitszeitmodell")
