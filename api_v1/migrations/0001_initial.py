# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('reg_ip', models.GenericIPAddressField()),
                ('notes', models.TextField(default=b'')),
                ('approved', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Token',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('token', models.TextField()),
                ('expires', models.DateTimeField()),
                ('registration', models.ForeignKey(to='api_v1.Registration')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
