# Generated by Django 3.0rc1 on 2019-12-02 20:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contacts", "0011_auto_20190913_0919"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True, verbose_name="date of birth"),
        ),
    ]
