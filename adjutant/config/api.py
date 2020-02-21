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

from confspirator import groups
from confspirator import fields


config_group = groups.ConfigGroup("api")

config_group.register_child_config(
    fields.ListConfig(
        "active_delegate_apis",
        help_text="List of Active Delegate APIs.",
        required=True,
        default=[
            "UserRoles",
            "UserDetail",
            "UserResetPassword",
            "UserList",
            "RoleList",
        ],
        # NOTE(adriant): for testing purposes we include ALL default APIs
        test_default=[
            "UserRoles",
            "UserDetail",
            "UserResetPassword",
            "UserList",
            "RoleList",
            "SignUp",
            "UpdateProjectQuotas",
            "CreateProjectAndUser",
            "InviteUser",
            "ResetPassword",
            "EditUser",
            "UpdateEmail",
        ],
    )
)

delegate_apis_group = groups.ConfigGroup("delegate_apis", lazy_load=True)
config_group.register_child_config(delegate_apis_group)
