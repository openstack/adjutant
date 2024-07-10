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

from django.urls import re_path
from adjutant.api.v1 import views

from adjutant import api
from adjutant.config import CONF

urlpatterns = [
    re_path(r"^status/?$", views.StatusView.as_view()),
    re_path(r"^tasks/(?P<uuid>\w+)/?$", views.TaskDetail.as_view()),
    re_path(r"^tasks/?$", views.TaskList.as_view()),
    re_path(r"^tokens/(?P<id>\w+)", views.TokenDetail.as_view()),
    re_path(r"^tokens/?$", views.TokenList.as_view()),
    re_path(r"^notifications/(?P<uuid>\w+)/?$", views.NotificationDetail.as_view()),
    re_path(r"^notifications/?$", views.NotificationList.as_view()),
]

for active_view in CONF.api.active_delegate_apis:
    delegate_api = api.DELEGATE_API_CLASSES[active_view]

    urlpatterns.append(re_path(delegate_api.url, delegate_api.as_view()))
