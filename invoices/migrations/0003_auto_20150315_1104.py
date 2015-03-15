# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0002_invoice_down_payment_applied_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='due_on',
            field=models.DateField(verbose_name='due on', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='invoiced_on',
            field=models.DateField(verbose_name='invoiced on', blank=True, null=True),
        ),
    ]
