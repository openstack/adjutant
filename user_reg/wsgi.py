"""
WSGI config for user_reg project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/howto/deployment/wsgi/
"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "user_reg.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

from urlparse import urlparse
from keystonemiddleware.auth_token import AuthProtocol

# TODO(Adriant): Get this data from a conf or settings.
identity_url = urlparse("http://localhost:5000/v2.0")
conf = {
    'admin_user': "admin",
    'admin_password': "openstack",
    'admin_tenant_name': "admin",
    'auth_host': identity_url.hostname,
    'auth_port': identity_url.port,
    'auth_protocol': identity_url.scheme,
    'delay_auth_decision': True,
    'include_service_catalog': False
}
application = AuthProtocol(application, conf)
