from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("awt", "0017_copy_public_holidays"),
        ("planning", "0017_alter_publicholiday_date"),
    ]

    operations = [
        migrations.DeleteModel(name="PublicHoliday"),
    ]
