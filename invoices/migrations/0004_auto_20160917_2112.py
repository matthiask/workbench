# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-17 19:12
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("invoices", "0003_invoice_created_at")]

    operations = [migrations.RemoveField(model_name="invoice", name="story_data")]
