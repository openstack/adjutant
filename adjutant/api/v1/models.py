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

from adjutant import api
from adjutant.api.v1 import tasks
from adjutant.api.v1 import openstack
from adjutant.api.v1.base import BaseDelegateAPI
from adjutant import exceptions
from adjutant.config.api import delegate_apis_group as api_config


def register_delegate_api_class(url, api_class):
    if not issubclass(api_class, BaseDelegateAPI):
        raise exceptions.InvalidAPIClass(
            "'%s' is not a built off the BaseDelegateAPI class."
            % api_class.__name__
        )
    data = {}
    data[api_class.__name__] = {
        'class': api_class,
        'url': url}
    api.DELEGATE_API_CLASSES.update(data)
    if api_class.config_group:
        # NOTE(adriant): We copy the config_group before naming it
        # to avoid cases where a subclass inherits but doesn't extend it
        setting_group = api_class.config_group.copy()
        setting_group.set_name(
            api_class.__name__, reformat_name=False)
        api_config.register_child_config(setting_group)


register_delegate_api_class(
    r'^actions/CreateProjectAndUser/?$', tasks.CreateProjectAndUser)
register_delegate_api_class(r'^actions/InviteUser/?$', tasks.InviteUser)
register_delegate_api_class(r'^actions/ResetPassword/?$', tasks.ResetPassword)
register_delegate_api_class(r'^actions/EditUser/?$', tasks.EditUser)
register_delegate_api_class(r'^actions/UpdateEmail/?$', tasks.UpdateEmail)


register_delegate_api_class(
    r'^openstack/users/?$', openstack.UserList)
register_delegate_api_class(
    r'^openstack/users/(?P<user_id>\w+)/?$', openstack.UserDetail)
register_delegate_api_class(
    r'^openstack/users/(?P<user_id>\w+)/roles/?$', openstack.UserRoles)
register_delegate_api_class(
    r'^openstack/roles/?$', openstack.RoleList)
register_delegate_api_class(
    r'^openstack/users/password-reset/?$', openstack.UserResetPassword)
register_delegate_api_class(
    r'^openstack/users/email-update/?$', openstack.UserUpdateEmail)
register_delegate_api_class(
    r'^openstack/sign-up/?$', openstack.SignUp)
register_delegate_api_class(
    r'^openstack/quotas/?$', openstack.UpdateProjectQuotas)
