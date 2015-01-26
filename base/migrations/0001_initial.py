# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api_v1', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action_name', models.CharField(max_length=200)),
                ('action_data', models.TextField()),
                ('valid', models.BooleanField(default=False)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('registration', models.ForeignKey(to='api_v1.Registration')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
