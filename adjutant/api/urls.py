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

from django.conf.urls import url, include
from django.conf import settings

from rest_framework_swagger.views import get_swagger_view

urlpatterns = [
    url(r'^v1/', include('adjutant.api.v1.urls')),
]

if settings.DEBUG:
    schema_view = get_swagger_view(title='Adjutant API')
    urlpatterns.append(url(r'^docs/', schema_view))
