# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('api_v1', '0003_auto_20150125_2239'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='uuid',
            field=models.CharField(default=uuid.uuid4, max_length=200),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='token',
            name='token',
            field=models.CharField(max_length=200, serialize=False, primary_key=True),
            preserve_default=True,
        ),
    ]
