# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('api_v1', '0008_auto_20150209_2320'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notes',
            field=jsonfield.fields.JSONField(default={}),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='registration',
            name='errors',
            field=jsonfield.fields.JSONField(default={}),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='registration',
            name='keystone_user',
            field=jsonfield.fields.JSONField(default={}),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='registration',
            name='notes',
            field=jsonfield.fields.JSONField(default={}),
            preserve_default=True,
        ),
    ]
