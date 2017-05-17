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


def hex_uuid():
    return uuid4().hex


class Task(models.Model):
    """
    Wrapper object for the request and related actions.
    Stores the state of the Task and a log for the
    action.
    """
    uuid = models.CharField(max_length=32, default=hex_uuid,
                            primary_key=True)
    hash_key = models.CharField(max_length=64, db_index=True)

    # who is this:
    ip_address = models.GenericIPAddressField()
    keystone_user = JSONField(default={})
    project_id = models.CharField(max_length=64, db_index=True, null=True)

    # keystone_user for the approver:
    approved_by = JSONField(default={})

    # type of the task, for easy grouping
    task_type = models.CharField(max_length=100, db_index=True)

    # Effectively a log of what the actions are doing.
    action_notes = JSONField(default={})

    cancelled = models.BooleanField(default=False, db_index=True)
    approved = models.BooleanField(default=False, db_index=True)
    completed = models.BooleanField(default=False, db_index=True)

    created_on = models.DateTimeField(default=timezone.now)
    approved_on = models.DateTimeField(null=True)
    completed_on = models.DateTimeField(null=True)

    def __init__(self, *args, **kwargs):
        super(Task, self).__init__(*args, **kwargs)
        # in memory dict to be used for passing data between actions:
        self.cache = {}

    @property
    def actions(self):
        return self.action_set.order_by('order')

    @property
    def tokens(self):
        return self.token_set.all()

    @property
    def notifications(self):
        return self.notification_set.all()

    def _to_dict(self):
        actions = []
        for action in self.actions:
            actions.append({
                "action_name": action.action_name,
                "data": action.action_data,
                "valid": action.valid
            })

        return {
            "uuid": self.uuid,
            "ip_address": self.ip_address,
            "keystone_user": self.keystone_user,
            "approved_by": self.approved_by,
            "project_id": self.project_id,
            "actions": actions,
            "task_type": self.task_type,
            "action_notes": self.action_notes,
            "cancelled": self.cancelled,
            "approved": self.approved,
            "completed": self.completed,
            "created_on": self.created_on,
            "approved_on": self.approved_on,
            "completed_on": self.completed_on,
        }

    def to_dict(self):
        """
        Slightly safer variant of the above for non-admin.
        """
        task_dict = self._to_dict()
        task_dict.pop("ip_address")
        return task_dict

    def add_action_note(self, action, note):
        if action in self.action_notes:
            self.action_notes[action].append(note)
        else:
            self.action_notes[action] = [note]
        self.save()


class Token(models.Model):
    """
    UUID token object bound to a task.
    """

    task = models.ForeignKey(Task)
    token = models.CharField(max_length=32, primary_key=True)
    created_on = models.DateTimeField(default=timezone.now)
    expires = models.DateTimeField(db_index=True)

    def to_dict(self):
        return {
            "task": self.task.uuid,
            "token": self.token,
            "created_on": self.created_on,
            "expires": self.expires
        }

    @property
    def expired(self):
        return self.expires < timezone.now()


class Notification(models.Model):
    """
    Notification linked to a task with some notes.
    """

    uuid = models.CharField(max_length=32, default=hex_uuid,
                            primary_key=True)
    notes = JSONField(default={})
    task = models.ForeignKey(Task)
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
            "created_on": self.created_on
        }
