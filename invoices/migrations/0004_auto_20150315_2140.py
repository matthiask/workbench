# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0003_auto_20150315_1104'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='type',
            field=models.CharField(choices=[('fixed', 'Fixed amount'), ('services', 'Services'), ('down-payment', 'Down payment')], verbose_name='type', max_length=20),
        ),
    ]
