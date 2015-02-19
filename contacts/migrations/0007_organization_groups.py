# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0006_auto_20150218_1257'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='groups',
            field=models.ManyToManyField(verbose_name='groups', related_name='+', to='contacts.Group'),
            preserve_default=True,
        ),
    ]
