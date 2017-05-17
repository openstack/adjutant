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

from copy import deepcopy


def dict_merge(a, b):
    """
    Recursively merges two dicts.
    If both a and b have a key who's value is a dict then dict_merge is called
    on both values and the result stored in the returned dictionary.
    B is the override.
    """
    if not isinstance(b, dict):
        return b
    result = deepcopy(a)
    for k, v in b.iteritems():
        if k in result and isinstance(result[k], dict):
            result[k] = dict_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


def setup_task_settings(task_defaults, action_defaults, task_settings):
    """
    Cascading merge of the default settings, and the
    settings for each task_type.
    """
    new_task_settings = {}
    for task, settings in task_settings.iteritems():
        task_setting = deepcopy(task_defaults)
        task_setting['action_settings'] = deepcopy(action_defaults)
        new_task_settings[task] = dict_merge(task_setting, settings)

    return new_task_settings
