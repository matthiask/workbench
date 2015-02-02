# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
        ('stories', '0001_squashed_0003_auto_20150202_2130'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='story',
            options={'verbose_name_plural': 'stories', 'verbose_name': 'story', 'ordering': ('position', 'id')},
        ),
        migrations.AddField(
            model_name='story',
            name='project',
            field=models.ForeignKey(default=1, to='projects.Project', related_name='stories', verbose_name='project'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='story',
            name='release',
            field=models.ForeignKey(related_name='stories', to='projects.Release', null=True, on_delete=django.db.models.deletion.SET_NULL, blank=True, verbose_name='release'),
            preserve_default=True,
        ),
    ]
