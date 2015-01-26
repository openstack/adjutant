# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import api_v1.models
import django.utils.timezone


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
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('uuid', models.CharField(default=api_v1.models.hex_uuid, max_length=200, serialize=False, primary_key=True)),
                ('reg_ip', models.GenericIPAddressField()),
                ('keystone_user', jsonfield.fields.JSONField(default={})),
                ('action_notes', jsonfield.fields.JSONField(default={})),
                ('approved', models.BooleanField(default=False)),
                ('completed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('approved_on', models.DateTimeField(null=True)),
                ('completed_on', models.DateTimeField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Token',
            fields=[
                ('token', models.CharField(max_length=200, serialize=False, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires', models.DateTimeField()),
                ('registration', models.ForeignKey(to='api_v1.Registration')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='notification',
            name='registration',
            field=models.ForeignKey(to='api_v1.Registration'),
            preserve_default=True,
        ),
    ]
