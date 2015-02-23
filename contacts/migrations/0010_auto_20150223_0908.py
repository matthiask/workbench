# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0009_auto_20150220_1151'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailaddress',
            name='weight',
            field=models.SmallIntegerField(verbose_name='weight', editable=False, default=0),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='phonenumber',
            name='weight',
            field=models.SmallIntegerField(verbose_name='weight', editable=False, default=0),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='postaladdress',
            name='weight',
            field=models.SmallIntegerField(verbose_name='weight', editable=False, default=0),
            preserve_default=True,
        ),
    ]
