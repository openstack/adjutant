# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api_v1', '0002_auto_20150211_2350'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='registration',
            name='errors',
        ),
    ]
