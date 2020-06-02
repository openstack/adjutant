# -*- coding: utf-8 -*-

from django.db import models, migrations
import jsonfield.fields
import django.utils.timezone
import adjutant.api.models


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                (
                    "uuid",
                    models.CharField(
                        default=adjutant.api.models.hex_uuid,
                        max_length=32,
                        serialize=False,
                        primary_key=True,
                    ),
                ),
                ("notes", jsonfield.fields.JSONField(default={})),
                ("error", models.BooleanField(default=False, db_index=True)),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
                ("acknowledged", models.BooleanField(default=False, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name="Task",
            fields=[
                (
                    "uuid",
                    models.CharField(
                        default=adjutant.api.models.hex_uuid,
                        max_length=32,
                        serialize=False,
                        primary_key=True,
                    ),
                ),
                ("hash_key", models.CharField(max_length=32, db_index=True)),
                ("ip_address", models.GenericIPAddressField()),
                ("keystone_user", jsonfield.fields.JSONField(default={})),
                (
                    "project_id",
                    models.CharField(max_length=32, null=True, db_index=True),
                ),
                ("task_type", models.CharField(max_length=100, db_index=True)),
                ("action_notes", jsonfield.fields.JSONField(default={})),
                ("cancelled", models.BooleanField(default=False, db_index=True)),
                ("approved", models.BooleanField(default=False, db_index=True)),
                ("completed", models.BooleanField(default=False, db_index=True)),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
                ("approved_on", models.DateTimeField(null=True)),
                ("completed_on", models.DateTimeField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Token",
            fields=[
                (
                    "token",
                    models.CharField(max_length=32, serialize=False, primary_key=True),
                ),
                ("created_on", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires", models.DateTimeField(db_index=True)),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="api.Task"
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="notification",
            name="task",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="api.Task"
            ),
        ),
    ]
