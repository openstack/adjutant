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

from adjutant.config import CONF
from adjutant import exceptions
from adjutant import tasks


def hex_uuid():
    return uuid4().hex


class Task(models.Model):
    """
    Wrapper object for the request and related actions.
    Stores the state of the Task and a log for the
    action.
    """

    uuid = models.CharField(max_length=32, default=hex_uuid, primary_key=True)
    hash_key = models.CharField(max_length=64)

    # who is this:
    keystone_user = JSONField(default={})
    project_id = models.CharField(max_length=64, null=True)

    # keystone_user for the approver:
    approved_by = JSONField(default={})

    # type of the task, for easy grouping
    task_type = models.CharField(max_length=100)

    # task level notes
    task_notes = JSONField(default=[])

    # Effectively a log of what the actions are doing.
    action_notes = JSONField(default={})

    cancelled = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)

    created_on = models.DateTimeField(default=timezone.now)
    approved_on = models.DateTimeField(null=True)
    completed_on = models.DateTimeField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=["completed"], name="completed_idx"),
            models.Index(fields=["project_id", "uuid"]),
            models.Index(fields=["project_id", "task_type"]),
            models.Index(fields=["project_id", "task_type", "cancelled"]),
            models.Index(fields=["project_id", "task_type", "completed", "cancelled"]),
            models.Index(fields=["hash_key", "completed", "cancelled"]),
        ]

    def __init__(self, *args, **kwargs):
        super(Task, self).__init__(*args, **kwargs)
        # in memory dict to be used for passing data between actions:
        self.cache = {}

    def get_task(self):
        """Returns self as the appropriate task wrapper type."""
        try:
            return tasks.TASK_CLASSES[self.task_type](task_model=self)
        except KeyError:
            # TODO(adriant): Maybe we should handle this better
            # for older deprecated tasks:
            raise exceptions.TaskNotRegistered(
                "Task type '%s' not registered, "
                "and used for existing task." % self.task_type
            )

    @property
    def config(self):
        try:
            task_conf = CONF.workflow.tasks[self.task_type]
        except KeyError:
            task_conf = {}
        return CONF.workflow.task_defaults.overlay(task_conf)

    @property
    def actions(self):
        return self.action_set.order_by("order")

    @property
    def tokens(self):
        return self.token_set.all()

    @property
    def notifications(self):
        return self.notification_set.all()

    def to_dict(self):
        actions = []
        for action in self.actions:
            actions.append(
                {
                    "action_name": action.action_name,
                    "data": action.action_data,
                    "valid": action.valid,
                }
            )

        return {
            "uuid": self.uuid,
            "keystone_user": self.keystone_user,
            "approved_by": self.approved_by,
            "project_id": self.project_id,
            "actions": actions,
            "task_type": self.task_type,
            "task_notes": self.task_notes,
            "action_notes": self.action_notes,
            "cancelled": self.cancelled,
            "approved": self.approved,
            "completed": self.completed,
            "created_on": self.created_on,
            "approved_on": self.approved_on,
            "completed_on": self.completed_on,
        }

    def add_task_note(self, note):
        self.task_notes.append(note)
        self.save()

    def add_action_note(self, action, note):
        if action in self.action_notes:
            self.action_notes[action].append(note)
        else:
            self.action_notes[action] = [note]
        self.save()
