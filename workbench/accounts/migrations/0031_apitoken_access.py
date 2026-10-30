from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0030_apitoken_expires_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="apitoken",
            name="access",
            # Existing tokens could always read and write
            field=models.CharField(
                choices=[("read", "read only"), ("write", "read and write")],
                default="write",
                max_length=10,
                verbose_name="access",
            ),
            preserve_default=False,
        ),
    ]
