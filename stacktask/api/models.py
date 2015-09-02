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
    uuid = models.CharField(max_length=200, default=hex_uuid,
                            primary_key=True)
    # who is this:
    ip_address = models.GenericIPAddressField()
    keystone_user = JSONField(default={})

    # which ActionView initiated this
    action_view = models.CharField(max_length=200)

    # Effectively a log of what the actions are doing.
    action_notes = JSONField(default={})

    cancelled = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)

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

    def to_dict(self):
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
            "actions": actions,
            "action_view": self.action_view,
            "action_notes": self.action_notes,
            "cancelled": self.cancelled,
            "approved": self.approved,
            "completed": self.completed,
            "created_on": self.created_on,
            "approved_on": self.approved_on,
            "completed_on": self.completed_on,
        }

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
    token = models.CharField(max_length=200, primary_key=True)
    created_on = models.DateTimeField(default=timezone.now)
    expires = models.DateTimeField()

    def to_dict(self):
        return {
            "task": self.task.uuid,
            "token": self.token, "expires": self.expires
        }


class Notification(models.Model):
    """
    Notification linked to a task with some notes.
    """

    notes = JSONField(default={})
    task = models.ForeignKey(Task)
    created_on = models.DateTimeField(default=timezone.now)
    acknowledged = models.BooleanField(default=False)

    def to_dict(self):
        return {
            "pk": self.pk,
            "notes": self.notes,
            "task": self.task.uuid,
            "acknowledged": self.acknowledged,
            "created_on": self.created_on
        }
