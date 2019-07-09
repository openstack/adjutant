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

from confspirator import exceptions
from confspirator import groups

from adjutant.actions.v1 import models as _action_models
from adjutant.api.v1 import models as _api_models
from adjutant.notifications import models as _notif_models
from adjutant.tasks.v1 import models as _task_models

from adjutant.config.plugin import config_group as _config_group


def register_plugin_config(plugin_group):
    if not isinstance(plugin_group, groups.ConfigGroup):
        raise exceptions.InvalidConfigClass(
            "'%s' is not a valid config group class" % plugin_group)
    _config_group.register_child_config(plugin_group)


def register_plugin_action(action_class, serializer_class):
    _action_models.register_action_class(action_class, serializer_class)


def register_plugin_task(task_class):
    _task_models.register_task_class(task_class)


def register_plugin_delegate_api(url, api_class):
    _api_models.register_delegate_api_class(url, api_class)


def register_notification_handler(notification_handler):
    _notif_models.register_notification_handler(notification_handler)
