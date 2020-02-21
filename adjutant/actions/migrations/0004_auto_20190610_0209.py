# -*- coding: utf-8 -*-
# Generated by Django 1.11.21 on 2019-06-10 02:09
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0001_initial"),
        ("actions", "0003_auto_20190610_0205"),
    ]

    operations = [
        migrations.AlterField(
            model_name="action",
            name="task",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="tasks.Task"
            ),
        ),
    ]
