# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
            ],
            options={
                'verbose_name_plural': 'projects',
                'verbose_name': 'project',
                'ordering': ('-id',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProjectManager',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Release',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('title', models.CharField(verbose_name='title', max_length=200)),
                ('is_default', models.BooleanField(default=False, verbose_name='is default')),
                ('position', models.PositiveIntegerField(default=0, verbose_name='position')),
                ('project', models.ForeignKey(to='projects.Project', related_name='releases', verbose_name='project')),
            ],
            options={
                'verbose_name_plural': 'releases',
                'verbose_name': 'release',
                'ordering': ('position', 'id'),
            },
            bases=(models.Model,),
        ),
    ]
