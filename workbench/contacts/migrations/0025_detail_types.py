from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0024_organization_phone_number"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emailaddress",
            name="type",
            field=models.CharField(default="Work", max_length=40, verbose_name="type"),
        ),
        migrations.AlterField(
            model_name="phonenumber",
            name="type",
            field=models.CharField(default="Work", max_length=40, verbose_name="type"),
        ),
        migrations.AlterField(
            model_name="postaladdress",
            name="type",
            field=models.CharField(default="Work", max_length=40, verbose_name="type"),
        ),
    ]
