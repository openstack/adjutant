# -*- coding: utf-8 -*-

from django.db import models, migrations
import django.utils.timezone
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Action",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("action_name", models.CharField(max_length=200)),
                ("action_data", jsonfield.fields.JSONField(default={})),
                ("cache", jsonfield.fields.JSONField(default={})),
                ("state", models.CharField(default=b"default", max_length=200)),
                ("valid", models.BooleanField(default=False)),
                ("need_token", models.BooleanField(default=False)),
                ("order", models.IntegerField()),
                ("created", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="api.Task"
                    ),
                ),
            ],
        ),
    ]
