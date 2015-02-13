# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0002_auto_20150213_1718'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='organization',
            options={'verbose_name_plural': 'organizations', 'verbose_name': 'organization'},
        ),
        migrations.AlterField(
            model_name='person',
            name='organization',
            field=models.ForeignKey(to='contacts.Organization', related_name='people', verbose_name='organization', null=True, blank=True),
            preserve_default=True,
        ),
    ]
