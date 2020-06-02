# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_task_approved_by"),
    ]

    operations = [
        migrations.AlterField(
            model_name="task",
            name="project_id",
            field=models.CharField(max_length=64, null=True, db_index=True),
        ),
    ]
