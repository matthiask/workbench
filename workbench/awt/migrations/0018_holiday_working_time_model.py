import django.db.models.deletion
from django.db import migrations, models


def assign_holidays_to_wtms(apps, schema_editor):
    Holiday = apps.get_model("awt", "Holiday")
    WorkingTimeModel = apps.get_model("awt", "WorkingTimeModel")

    existing = [(h.date, h.name, h.fraction, h.kind) for h in Holiday.objects.all()]
    Holiday.objects.all().delete()

    wtms = list(WorkingTimeModel.objects.all())
    Holiday.objects.bulk_create(
        [
            Holiday(
                date=date,
                name=name,
                fraction=fraction,
                kind=kind,
                working_time_model=wtm,
            )
            for date, name, fraction, kind in existing
            for wtm in wtms
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("awt", "0017_copy_public_holidays"),
        ("planning", "0018_delete_publicholiday"),
    ]

    operations = [
        migrations.AddField(
            model_name="holiday",
            name="working_time_model",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="holidays",
                to="awt.workingtimemodel",
                verbose_name="working time model",
            ),
        ),
        migrations.RunPython(assign_holidays_to_wtms, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="holiday",
            name="working_time_model",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="holidays",
                to="awt.workingtimemodel",
                verbose_name="working time model",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="holiday",
            unique_together={("working_time_model", "date", "kind")},
        ),
    ]
