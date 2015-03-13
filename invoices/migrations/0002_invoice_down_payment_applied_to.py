# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='down_payment_applied_to',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, verbose_name='down payment applied to', blank=True, related_name='+', to='invoices.Invoice', null=True),
        ),
    ]
