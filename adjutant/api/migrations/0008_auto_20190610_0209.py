# -*- coding: utf-8 -*-
# Generated by Django 1.11.21 on 2019-06-10 02:09

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0005_auto_20190610_0209"),
        ("tasks", "0001_initial"),
        ("actions", "0004_auto_20190610_0209"),
        ("api", "0006_auto_20190610_0209"),
        ("api", "0007_auto_20190610_0209"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name="Task",
                ),
            ],
        ),
    ]
