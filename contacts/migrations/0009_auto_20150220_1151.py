# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0008_organization_notes'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='group',
            options={'verbose_name': 'group', 'verbose_name_plural': 'groups', 'ordering': ('title',)},
        ),
        migrations.AddField(
            model_name='person',
            name='groups',
            field=models.ManyToManyField(verbose_name='groups', related_name='+', to='contacts.Group'),
            preserve_default=True,
        ),
    ]
