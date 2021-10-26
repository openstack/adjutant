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

from adjutant.tasks.v1.base import BaseTask


class InviteUser(BaseTask):
    duplicate_policy = "block"
    task_type = "invite_user_to_project"
    deprecated_task_types = ["invite_user"]
    default_actions = [
        "NewUserAction",
    ]

    email_config = {
        "initial": None,
        "token": {
            "template": "invite_user_to_project_token.txt",
            "subject": "invite_user_to_project",
        },
        "completed": {
            "template": "invite_user_to_project_completed.txt",
            "subject": "invite_user_to_project",
        },
    }


class ResetUserPassword(BaseTask):
    task_type = "reset_user_password"
    deprecated_task_types = ["reset_password"]
    default_actions = [
        "ResetUserPasswordAction",
    ]

    email_config = {
        "initial": None,
        "token": {
            "template": "reset_user_password_token.txt",
            "subject": "Password Reset for OpenStack",
        },
        "completed": {
            "template": "reset_user_password_completed.txt",
            "subject": "Password Reset for OpenStack",
        },
    }


class EditUserRoles(BaseTask):
    task_type = "edit_user_roles"
    deprecated_task_types = ["edit_user"]
    default_actions = [
        "EditUserRolesAction",
    ]

    email_config = {"initial": None, "token": None, "completed": None}


class UpdateUserEmail(BaseTask):
    task_type = "update_user_email"
    deprecated_task_types = ["update_email"]
    default_actions = [
        "UpdateUserEmailAction",
    ]
    additional_actions = [
        "SendAdditionalEmailAction",
    ]
    action_config = {
        "SendAdditionalEmailAction": {
            "prepare": {
                "subject": "OpenStack Email Update Requested",
                "template": "update_user_email_started.txt",
                "email_current_user": True,
            },
        },
    }
    email_config = {
        "initial": None,
        "token": {
            "subject": "update_user_email_token",
            "template": "update_user_email_token.txt",
        },
        "completed": {
            "subject": "Email Update Complete",
            "template": "update_user_email_completed.txt",
        },
    }
