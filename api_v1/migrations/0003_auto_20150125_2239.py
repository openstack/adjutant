# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api_v1', '0002_registration_completed'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='token',
            name='id',
        ),
        migrations.AlterField(
            model_name='registration',
            name='notes',
            field=models.TextField(default=b'{}'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='token',
            name='token',
            field=models.TextField(serialize=False, primary_key=True),
            preserve_default=True,
        ),
    ]
