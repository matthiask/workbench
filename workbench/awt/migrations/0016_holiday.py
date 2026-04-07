from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("awt", "0015_vacationdaysoverride_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="Holiday",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date", models.DateField(verbose_name="date")),
                (
                    "name",
                    models.CharField(blank=True, max_length=200, verbose_name="name"),
                ),
                (
                    "fraction",
                    models.DecimalField(
                        decimal_places=2,
                        default=1,
                        max_digits=5,
                        verbose_name="fraction of day which is free",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("public", "public holiday"),
                            ("company", "company holiday"),
                        ],
                        default="public",
                        max_length=10,
                        verbose_name="kind",
                    ),
                ),
            ],
            options={
                "verbose_name": "holiday",
                "verbose_name_plural": "holidays",
                "ordering": ["-date"],
                "unique_together": {("date", "kind")},
            },
        ),
        migrations.RunSQL(
            "SELECT audit_audit_table('awt_holiday');",
            "",
        ),
    ]
