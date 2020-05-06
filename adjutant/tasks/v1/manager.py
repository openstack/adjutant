# Copyright (C) 2019 Catalyst IT Ltd
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

from logging import getLogger

from six import string_types

from adjutant import exceptions
from adjutant import tasks
from adjutant.tasks.models import Task
from adjutant.tasks.v1.base import BaseTask


class TaskManager(object):
    def __init__(self, message=None):
        self.logger = getLogger("adjutant")

    def _get_task_class(self, task_type):
        """Get the task class from the given task_type

        If the task_type is a string, it will get the correct class,
        otherwise if it is a valid task class, will return it.
        """
        try:
            return tasks.TASK_CLASSES[task_type]
        except KeyError:
            if task_type in tasks.TASK_CLASSES.values():
                return task_type
        raise exceptions.TaskNotRegistered("Unknown task type: '%s'" % task_type)

    def create_from_request(self, task_type, request):
        task_class = self._get_task_class(task_type)
        task_data = {
            "keystone_user": request.keystone_user,
            "project_id": request.keystone_user.get("project_id"),
        }
        task = task_class(task_data=task_data, action_data=request.data)
        task.prepare()
        return task

    def create_from_data(self, task_type, task_data, action_data):
        task_class = self._get_task_class(task_type)
        task = task_class(task_data=task_data, action_data=action_data)
        task.prepare()
        return task

    def get(self, task):
        if isinstance(task, BaseTask):
            return task
        if isinstance(task, string_types):
            try:
                task = Task.objects.get(uuid=task)
            except Task.DoesNotExist:
                raise exceptions.TaskNotFound(
                    "Task not found with uuid of: '%s'" % task
                )
        if isinstance(task, Task):
            return task.get_task()
        raise exceptions.TaskNotFound("Task not found for value of: '%s'" % task)

    def update(self, task, action_data):
        task = self.get(task)
        task.update(action_data)
        return task

    def approve(self, task, approved_by):
        task = self.get(task)
        task.approve(approved_by)
        return task

    def submit(self, task, token_data, keystone_user=None):
        task = self.get(task)
        task.submit(token_data, keystone_user)
        return task

    def cancel(self, task):
        task = self.get(task)
        task.cancel()
        return task

    def reissue_token(self, task):
        task = self.get(task)
        task.reissue_token()
        return task
