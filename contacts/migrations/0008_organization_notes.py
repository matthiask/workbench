# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0007_organization_groups'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='notes',
            field=models.TextField(verbose_name='notes', blank=True),
            preserve_default=True,
        ),
    ]
