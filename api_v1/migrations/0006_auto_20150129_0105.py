# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import api_v1.models


class Migration(migrations.Migration):

    dependencies = [
        ('api_v1', '0005_auto_20150126_0043'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='keystone_user',
            field=models.TextField(default=b'{}'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='registration',
            name='uuid',
            field=models.CharField(default=api_v1.models.hex_uuid, max_length=200, serialize=False, primary_key=True),
            preserve_default=True,
        ),
    ]
