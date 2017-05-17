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

"""
WSGI config for Adjutant.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application
from django.conf import settings
from urlparse import urlparse
from keystonemiddleware.auth_token import AuthProtocol

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "adjutant.settings")


application = get_wsgi_application()

# Here we replace the default application with one wrapped by
# the Keystone Auth Middleware.
identity_url = urlparse(settings.KEYSTONE['auth_url'])
conf = {
    "auth_plugin": "password",
    'username': settings.KEYSTONE['username'],
    'password': settings.KEYSTONE['password'],
    'project_name': settings.KEYSTONE['project_name'],
    "project_domain_id": settings.KEYSTONE.get('domain_id', "default"),
    "user_domain_id": settings.KEYSTONE.get('domain_id', "default"),
    "auth_url": settings.KEYSTONE['auth_url'],
    'delay_auth_decision': True,
    'include_service_catalog': False,
}
application = AuthProtocol(application, conf)
