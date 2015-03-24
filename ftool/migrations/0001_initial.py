# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import io
import os

from django.conf import settings
from django.db import models, migrations


with io.open(os.path.join(settings.BASE_DIR, 'stuff', 'audit.sql')) as f:
    sql = f.read()


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunSQL(sql, None),
    ]
