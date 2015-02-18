# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0004_auto_20150214_2303'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='emailaddress',
            options={'verbose_name': 'email address', 'verbose_name_plural': 'email addresses', 'ordering': ('-weight', 'id')},
        ),
        migrations.AlterModelOptions(
            name='phonenumber',
            options={'verbose_name': 'phone number', 'verbose_name_plural': 'phone numbers', 'ordering': ('-weight', 'id')},
        ),
        migrations.AlterModelOptions(
            name='postaladdress',
            options={'verbose_name': 'postal address', 'verbose_name_plural': 'postal addresses', 'ordering': ('-weight', 'id')},
        ),
        migrations.AddField(
            model_name='emailaddress',
            name='weight',
            field=models.PositiveIntegerField(editable=False, verbose_name='weight', default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='phonenumber',
            name='weight',
            field=models.PositiveIntegerField(editable=False, verbose_name='weight', default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='postaladdress',
            name='weight',
            field=models.PositiveIntegerField(editable=False, verbose_name='weight', default=0),
            preserve_default=True,
        ),
    ]
