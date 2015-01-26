# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('api_v1', '0004_auto_20150126_0042'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='registration',
            name='id',
        ),
        migrations.AlterField(
            model_name='registration',
            name='uuid',
            field=models.CharField(default=uuid.uuid4, max_length=200, serialize=False, primary_key=True),
            preserve_default=True,
        ),
    ]
