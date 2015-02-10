# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0005_auto_20150209_0507'),
    ]

    operations = [
        migrations.AlterField(
            model_name='action',
            name='action_data',
            field=jsonfield.fields.JSONField(default={}),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='action',
            name='cache',
            field=jsonfield.fields.JSONField(default={}),
            preserve_default=True,
        ),
    ]
