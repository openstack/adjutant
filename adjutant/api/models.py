# Copyright (C) 2015 Catalyst IT Ltd
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from django.db import models
from uuid import uuid4
from django.utils import timezone
from jsonfield import JSONField

from adjutant.tasks.models import Task


def hex_uuid():
    return uuid4().hex


class Token(models.Model):
    """
    UUID token object bound to a task.
    """

    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    token = models.CharField(max_length=32, primary_key=True)
    created_on = models.DateTimeField(default=timezone.now)
    expires = models.DateTimeField(db_index=True)

    def to_dict(self):
        return {
            "task": self.task.uuid,
            "task_type": self.task.task_type,
            "token": self.token,
            "created_on": self.created_on,
            "expires": self.expires,
        }

    @property
    def expired(self):
        return self.expires < timezone.now()


class Notification(models.Model):
    """
    Notification linked to a task with some notes.
    """

    uuid = models.CharField(max_length=32, default=hex_uuid, primary_key=True)
    notes = JSONField(default={})
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    error = models.BooleanField(default=False, db_index=True)
    created_on = models.DateTimeField(default=timezone.now)
    acknowledged = models.BooleanField(default=False, db_index=True)

    def to_dict(self):
        return {
            "uuid": self.uuid,
            "notes": self.notes,
            "task": self.task.uuid,
            "error": self.error,
            "acknowledged": self.acknowledged,
            "created_on": self.created_on,
        }
