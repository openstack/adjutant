# -*- coding: utf-8 -*-
# Generated by Django 1.11.21 on 2019-06-10 02:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("actions", "0002_action_auto_approve"),
    ]

    run_before = [
        ("api", "0005_auto_20190610_0209"),
    ]

    operations = [
        migrations.AlterField(
            model_name="action",
            name="state",
            field=models.CharField(default="default", max_length=200),
        ),
    ]
