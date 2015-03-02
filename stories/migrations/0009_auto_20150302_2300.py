# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0008_renderedservice'),
    ]

    operations = [
        migrations.AlterField(
            model_name='renderedservice',
            name='created_by',
            field=models.ForeignKey(verbose_name='created by', related_name='+', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='renderedservice',
            name='rendered_by',
            field=models.ForeignKey(verbose_name='rendered by', related_name='renderedservices', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='renderedservice',
            name='story',
            field=models.ForeignKey(verbose_name='story', related_name='renderedservices', on_delete=django.db.models.deletion.PROTECT, to='stories.Story'),
        ),
        migrations.AlterField(
            model_name='requiredservice',
            name='service_type',
            field=models.ForeignKey(verbose_name='service type', related_name='+', on_delete=django.db.models.deletion.PROTECT, to='services.ServiceType'),
        ),
        migrations.AlterField(
            model_name='story',
            name='owned_by',
            field=models.ForeignKey(verbose_name='owned by', related_name='+', on_delete=django.db.models.deletion.PROTECT, null=True, to=settings.AUTH_USER_MODEL, blank=True),
        ),
        migrations.AlterField(
            model_name='story',
            name='project',
            field=models.ForeignKey(verbose_name='project', related_name='stories', on_delete=django.db.models.deletion.PROTECT, to='projects.Project'),
        ),
        migrations.AlterField(
            model_name='story',
            name='requested_by',
            field=models.ForeignKey(verbose_name='requested by', related_name='+', on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
    ]
