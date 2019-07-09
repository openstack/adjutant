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

from rest_framework import serializers as drf_serializers

from adjutant import actions
from adjutant.actions.v1 import serializers
from adjutant.actions.v1.base import BaseAction
from adjutant.actions.v1.projects import (
    NewProjectWithUserAction, NewProjectAction,
    AddDefaultUsersToProjectAction)
from adjutant.actions.v1.users import (
    EditUserRolesAction, NewUserAction, ResetUserPasswordAction,
    UpdateUserEmailAction)
from adjutant.actions.v1.resources import (
    NewDefaultNetworkAction, NewProjectDefaultNetworkAction,
    SetProjectQuotaAction, UpdateProjectQuotasAction)
from adjutant.actions.v1.misc import SendAdditionalEmailAction
from adjutant import exceptions
from adjutant.config.workflow import action_defaults_group as action_config


# Update ACTION_CLASSES dict with tuples in the format:
#   (<ActionClass>, <ActionSerializer>)
def register_action_class(action_class, serializer_class):
    if not issubclass(action_class, BaseAction):
        raise exceptions.InvalidActionClass(
            "'%s' is not a built off the BaseAction class."
            % action_class.__name__
        )
    if serializer_class and not issubclass(
            serializer_class, drf_serializers.Serializer):
        raise exceptions.InvalidActionSerializer(
            "serializer for '%s' is not a valid DRF serializer."
            % action_class.__name__
        )
    data = {}
    data[action_class.__name__] = (action_class, serializer_class)
    actions.ACTION_CLASSES.update(data)
    if action_class.config_group:
        # NOTE(adriant): We copy the config_group before naming it
        # to avoid cases where a subclass inherits but doesn't extend it
        setting_group = action_class.config_group.copy()
        setting_group.set_name(
            action_class.__name__, reformat_name=False)
        action_config.register_child_config(setting_group)


# Register Project actions:
register_action_class(
    NewProjectWithUserAction, serializers.NewProjectWithUserSerializer)
register_action_class(NewProjectAction, serializers.NewProjectSerializer)
register_action_class(
    AddDefaultUsersToProjectAction,
    serializers.AddDefaultUsersToProjectSerializer)

# Register User actions:
register_action_class(NewUserAction, serializers.NewUserSerializer)
register_action_class(ResetUserPasswordAction, serializers.ResetUserSerializer)
register_action_class(EditUserRolesAction, serializers.EditUserRolesSerializer)
register_action_class(
    UpdateUserEmailAction, serializers.UpdateUserEmailSerializer)

# Register Resource actions:
register_action_class(
    NewDefaultNetworkAction, serializers.NewDefaultNetworkSerializer)
register_action_class(
    NewProjectDefaultNetworkAction,
    serializers.NewProjectDefaultNetworkSerializer)
register_action_class(
    SetProjectQuotaAction, serializers.SetProjectQuotaSerializer)
register_action_class(
    UpdateProjectQuotasAction, serializers.UpdateProjectQuotasSerializer)

# Register Misc actions:
register_action_class(
    SendAdditionalEmailAction, serializers.SendAdditionalEmailSerializer)
