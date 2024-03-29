# Generated by Django 4.2.4 on 2023-10-31 12:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0028_auto_20221121_1351"),
        ("accounts", "0022_auto_20220909_2028"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="pinned_projects",
            field=models.ManyToManyField(
                blank=True, to="projects.project", verbose_name="pinned projects"
            ),
        ),
    ]
