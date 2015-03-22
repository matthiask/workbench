# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0008_invoice_closed_at'),
        ('offers', '0006_remove_offer_stories'),
        ('stories', '0010_auto_20150306_1114'),
    ]

    operations = [
        migrations.AddField(
            model_name='renderedservice',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='archived at'),
        ),
        migrations.AddField(
            model_name='renderedservice',
            name='invoice',
            field=models.ForeignKey(blank=True, verbose_name='invoice', to='invoices.Invoice', on_delete=django.db.models.deletion.PROTECT, related_name='+', null=True),
        ),
        migrations.AddField(
            model_name='story',
            name='offer',
            field=models.ForeignKey(blank=True, verbose_name='offer', to='offers.Offer', on_delete=django.db.models.deletion.PROTECT, related_name='stories', null=True),
        ),
    ]
