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

from adjutant.feature_set import BaseFeatureSet

from adjutant.actions.v1 import misc as misc_actions
from adjutant.actions.v1 import projects as project_actions
from adjutant.actions.v1 import resources as resource_actions
from adjutant.actions.v1 import users as user_actions

from adjutant.api.v1 import openstack as openstack_apis
from adjutant.api.v1 import tasks as task_apis

from adjutant.tasks.v1 import projects as project_tasks
from adjutant.tasks.v1 import resources as resource_tasks
from adjutant.tasks.v1 import users as user_tasks

from adjutant.notifications.v1 import email as email_handlers


class AdjutantCore(BaseFeatureSet):
    """Adjutant's Core feature set."""

    actions = [
        project_actions.NewProjectWithUserAction,
        project_actions.NewProjectAction,
        project_actions.AddDefaultUsersToProjectAction,
        resource_actions.NewDefaultNetworkAction,
        resource_actions.NewProjectDefaultNetworkAction,
        resource_actions.SetProjectQuotaAction,
        resource_actions.UpdateProjectQuotasAction,
        user_actions.NewUserAction,
        user_actions.ResetUserPasswordAction,
        user_actions.EditUserRolesAction,
        user_actions.UpdateUserEmailAction,
        misc_actions.SendAdditionalEmailAction,
    ]

    tasks = [
        project_tasks.CreateProjectAndUser,
        user_tasks.EditUserRoles,
        user_tasks.InviteUser,
        user_tasks.ResetUserPassword,
        user_tasks.UpdateUserEmail,
        resource_tasks.UpdateProjectQuotas,
    ]

    delegate_apis = [
        task_apis.CreateProjectAndUser,
        task_apis.InviteUser,
        task_apis.ResetPassword,
        task_apis.EditUser,
        task_apis.UpdateEmail,
        openstack_apis.UserList,
        openstack_apis.UserDetail,
        openstack_apis.UserRoles,
        openstack_apis.RoleList,
        openstack_apis.UserResetPassword,
        openstack_apis.UserUpdateEmail,
        openstack_apis.SignUp,
        openstack_apis.UpdateProjectQuotas,
    ]

    notification_handlers = [
        email_handlers.EmailNotification,
    ]
