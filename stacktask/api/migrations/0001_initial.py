# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import django.utils.timezone
import stacktask.api.models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('notes', jsonfield.fields.JSONField(default={})),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('acknowledged', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('uuid', models.CharField(default=stacktask.api.models.hex_uuid, max_length=200, serialize=False, primary_key=True)),
                ('reg_ip', models.GenericIPAddressField()),
                ('keystone_user', jsonfield.fields.JSONField(default={})),
                ('action_view', models.CharField(max_length=200)),
                ('action_notes', jsonfield.fields.JSONField(default={})),
                ('approved', models.BooleanField(default=False)),
                ('completed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('approved_on', models.DateTimeField(null=True)),
                ('completed_on', models.DateTimeField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Token',
            fields=[
                ('token', models.CharField(max_length=200, serialize=False, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires', models.DateTimeField()),
                ('registration', models.ForeignKey(to='api.Registration')),
            ],
        ),
        migrations.AddField(
            model_name='notification',
            name='registration',
            field=models.ForeignKey(to='api.Registration'),
        ),
    ]
