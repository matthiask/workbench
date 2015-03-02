# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0003_renderedservice'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='renderedservice',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='renderedservice',
            name='rendered_by',
        ),
        migrations.RemoveField(
            model_name='renderedservice',
            name='story',
        ),
        migrations.DeleteModel(
            name='RenderedService',
        ),
    ]
