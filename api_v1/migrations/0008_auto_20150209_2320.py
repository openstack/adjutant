# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api_v1', '0007_auto_20150209_0444'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('notes', models.TextField(default=b'{}')),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('acknowledged', models.BooleanField(default=False)),
                ('registration', models.ForeignKey(to='api_v1.Registration')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='registration',
            name='errors',
            field=models.TextField(default=b'{}'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='token',
            name='created',
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=True,
        ),
    ]
