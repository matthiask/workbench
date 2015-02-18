# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def forwards(apps, schema_editor):
    for model_name in ('EmailAddress', 'PhoneNumber', 'PostalAddress'):
        model = apps.get_model('contacts', model_name)
        for instance in model.objects.all():
            instance.save()


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0005_auto_20150218_1255'),
    ]

    operations = [
        migrations.RunPython(forwards),
    ]
