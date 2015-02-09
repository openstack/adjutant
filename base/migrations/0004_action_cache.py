# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0003_action_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='cache',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]
