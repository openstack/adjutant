# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="task",
            name="hash_key",
            field=models.CharField(max_length=64, db_index=True),
        ),
    ]
