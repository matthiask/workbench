from django.db import migrations


def copy_public_holidays(apps, schema_editor):
    PublicHoliday = apps.get_model("planning", "PublicHoliday")
    Holiday = apps.get_model("awt", "Holiday")
    Holiday.objects.bulk_create(
        [
            Holiday(date=ph.date, name=ph.name, fraction=ph.fraction, kind="public")
            for ph in PublicHoliday.objects.all()
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("awt", "0016_holiday"),
        ("planning", "0017_alter_publicholiday_date"),
    ]

    operations = [
        migrations.RunPython(copy_public_holidays, migrations.RunPython.noop),
    ]
