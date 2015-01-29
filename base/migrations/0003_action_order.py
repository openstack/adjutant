# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0002_auto_20150125_2239'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='order',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
    ]
