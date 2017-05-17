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

from adjutant.api.v1 import tasks
from adjutant.api.v1 import openstack


def register_taskview_class(url, taskview_class):
    data = {}
    data[taskview_class.__name__] = {
        'class': taskview_class,
        'url': url}
    settings.TASKVIEW_CLASSES.update(data)


register_taskview_class(r'^actions/CreateProject/?$', tasks.CreateProject)
register_taskview_class(r'^actions/InviteUser/?$', tasks.InviteUser)
register_taskview_class(r'^actions/ResetPassword/?$', tasks.ResetPassword)
register_taskview_class(r'^actions/EditUser/?$', tasks.EditUser)
register_taskview_class(r'^actions/UpdateEmail/?$', tasks.UpdateEmail)


register_taskview_class(
    r'^openstack/users/?$', openstack.UserList)
register_taskview_class(
    r'^openstack/users/(?P<user_id>\w+)/?$', openstack.UserDetail)
register_taskview_class(
    r'^openstack/users/(?P<user_id>\w+)/roles/?$', openstack.UserRoles)
register_taskview_class(
    r'^openstack/roles/?$', openstack.RoleList)
register_taskview_class(
    r'^openstack/users/password-reset/?$', openstack.UserResetPassword)
register_taskview_class(
    r'^openstack/users/password-set/?$', openstack.UserSetPassword)
register_taskview_class(
    r'^openstack/users/email-update/?$', openstack.UserUpdateEmail)
register_taskview_class(
    r'^openstack/sign-up/?$', openstack.SignUp)
