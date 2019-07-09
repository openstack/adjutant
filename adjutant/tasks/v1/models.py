# Copyright (C) 2019 Catalyst Cloud Ltd
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

from adjutant import exceptions
from adjutant import tasks
from adjutant.config.workflow import tasks_group as tasks_group
from adjutant.tasks.v1 import base
from adjutant.tasks.v1 import projects, users, resources


def register_task_class(task_class):
    if not issubclass(task_class, base.BaseTask):
        raise exceptions.InvalidTaskClass(
            "'%s' is not a built off the BaseTask class."
            % task_class.__name__
        )
    data = {}
    data[task_class.task_type] = task_class
    if task_class.deprecated_task_types:
        for old_type in task_class.deprecated_task_types:
            data[old_type] = task_class
    tasks.TASK_CLASSES.update(data)
    setting_group = base.make_task_config(task_class)
    setting_group.set_name(
        task_class.task_type, reformat_name=False)
    tasks_group.register_child_config(setting_group)


register_task_class(projects.CreateProjectAndUser)

register_task_class(users.EditUserRoles)
register_task_class(users.InviteUser)
register_task_class(users.ResetUserPassword)
register_task_class(users.UpdateUserEmail)

register_task_class(resources.UpdateProjectQuotas)