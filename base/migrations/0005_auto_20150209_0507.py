# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_action_cache'),
    ]

    operations = [
        migrations.AlterField(
            model_name='action',
            name='cache',
            field=models.TextField(default=b'{}'),
            preserve_default=True,
        ),
    ]
