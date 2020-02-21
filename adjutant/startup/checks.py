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

from adjutant.config import CONF
from adjutant import actions, api, tasks
from adjutant.exceptions import ActionNotRegistered, DelegateAPINotRegistered


def check_expected_delegate_apis():
    missing_delegate_apis = list(
        set(CONF.api.active_delegate_apis) - set(api.DELEGATE_API_CLASSES.keys())
    )

    if missing_delegate_apis:
        raise DelegateAPINotRegistered(
            message=(
                "Expected DelegateAPIs are unregistered: %s" % missing_delegate_apis
            )
        )


def check_configured_actions():
    """Check that all the expected actions have been registered."""
    configured_actions = []

    for task in tasks.TASK_CLASSES:
        task_class = tasks.TASK_CLASSES.get(task)

        configured_actions += task_class.default_actions
        configured_actions += CONF.workflow.tasks.get(
            task_class.task_type
        ).additional_actions

    missing_actions = list(set(configured_actions) - set(actions.ACTION_CLASSES.keys()))

    if missing_actions:
        raise ActionNotRegistered(
            "Configured actions are unregistered: %s" % missing_actions
        )
