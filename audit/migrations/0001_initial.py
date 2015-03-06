# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import io, os

from django.conf import settings
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunSQL(
            io.open(
                os.path.join(settings.BASE_DIR, 'stuff', 'audit.sql')
            ).read(),
            None,
        ),
    ]
