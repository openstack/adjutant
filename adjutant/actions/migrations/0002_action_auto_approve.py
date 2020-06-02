# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("actions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="action",
            name="auto_approve",
            field=models.NullBooleanField(default=None),
        ),
    ]
