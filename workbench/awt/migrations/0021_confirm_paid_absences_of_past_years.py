import datetime as dt

from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    # Past years are locked, this year's paid leave is reviewed
    Absence = apps.get_model("awt", "Absence")
    Absence.objects.filter(
        reason="paid", starts_on__lt=dt.date(dt.date.today().year, 1, 1)
    ).update(confirmed_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ("awt", "0020_absence_confirmation"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
