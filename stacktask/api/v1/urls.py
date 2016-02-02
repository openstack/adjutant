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

from django.conf.urls import url
from stacktask.api.v1 import views
from stacktask.api.v1 import tasks
from stacktask.api.v1 import openstack
from django.conf import settings


urlpatterns = [
    url(r'^status/?$', views.StatusView.as_view()),
    url(r'^tasks/(?P<uuid>\w+)/?$', views.TaskDetail.as_view()),
    url(r'^tasks/?$', views.TaskList.as_view()),
    url(r'^tokens/(?P<id>\w+)', views.TokenDetail.as_view()),
    url(r'^tokens/?$', views.TokenList.as_view()),
    url(r'^notifications/(?P<uuid>\w+)/?$',
        views.NotificationDetail.as_view()),
    url(r'^notifications/?$', views.NotificationList.as_view()),

    url(r'^openstack/users/(?P<user_id>\w+)/roles/?$',
        openstack.UserRoles.as_view()),
    url(r'^openstack/users/(?P<user_id>\w+)/?$',
        openstack.UserDetail.as_view()),
    url(r'^openstack/users/password-reset?$',
        openstack.UserResetPassword.as_view()),
    url(r'^openstack/users/password-set?$',
        openstack.UserSetPassword.as_view()),
    url(r'^openstack/users/?$', openstack.UserList.as_view()),
    url(r'^openstack/roles/?$', openstack.RoleList.as_view()),
]

if settings.SHOW_ACTION_ENDPOINTS:
    urlpatterns = urlpatterns + [
        url(r'^actions/CreateProject/?$', tasks.CreateProject.as_view()),
        url(r'^actions/InviteUser/?$', tasks.InviteUser.as_view()),
        url(r'^actions/ResetPassword/?$', tasks.ResetPassword.as_view()),
        url(r'^actions/EditUser/?$', tasks.EditUser.as_view()),
    ]
