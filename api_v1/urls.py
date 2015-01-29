# Copyright (C) 2014 Catalyst IT Ltd
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

from django.conf.urls import patterns, url
from api_v1 import views

urlpatterns = patterns(
    '',
    # Examples:
    # url(r'^$', 'user_reg.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^registration/(?P<uuid>\w+)', views.RegistrationDetail.as_view()),
    url(r'^registration', views.RegistrationList.as_view()),
    url(r'^project', views.CreateProject.as_view()),
    url(r'^user', views.AttachUser.as_view()),
    url(r'^reset', views.ResetPassword.as_view()),
    url(r'^token/(?P<id>\w+)', views.TokenDetail.as_view()),
    url(r'^token', views.TokenList.as_view()),
)
