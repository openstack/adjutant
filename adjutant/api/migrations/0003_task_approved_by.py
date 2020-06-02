# -*- coding: utf-8 -*-

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_auto_20160815_2249"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="approved_by",
            field=jsonfield.fields.JSONField(default={}),
        ),
    ]
