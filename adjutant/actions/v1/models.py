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

from django.conf import settings

from adjutant.actions.v1 import serializers
from adjutant.actions.v1.projects import (
    NewProjectWithUserAction, AddDefaultUsersToProjectAction)
from adjutant.actions.v1.users import (
    EditUserRolesAction, NewUserAction, ResetUserPasswordAction,
    UpdateUserEmailAction)
from adjutant.actions.v1.resources import (
    NewDefaultNetworkAction, NewProjectDefaultNetworkAction,
    SetProjectQuotaAction)
from adjutant.actions.v1.misc import SendAdditionalEmailAction


# Update settings dict with tuples in the format:
#   (<ActionClass>, <ActionSerializer>)
def register_action_class(action_class, serializer_class):
    data = {}
    data[action_class.__name__] = (action_class, serializer_class)
    settings.ACTION_CLASSES.update(data)


# Register Project actions:
register_action_class(
    NewProjectWithUserAction, serializers.NewProjectWithUserSerializer)
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

# Register Misc actions:
register_action_class(
    SendAdditionalEmailAction, serializers.SendAdditionalEmailSerializer)
