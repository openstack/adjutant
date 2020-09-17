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
Django settings for Adjutant.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import sys

from adjutant.config import CONF as adj_conf

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Application definition

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_swagger",
    "adjutant.commands",
    "adjutant.actions",
    "adjutant.api",
    "adjutant.notifications",
    "adjutant.tasks",
    "adjutant.startup",
)

MIDDLEWARE = (
    "django.middleware.common.CommonMiddleware",
    "adjutant.middleware.KeystoneHeaderUnwrapper",
    "adjutant.middleware.RequestLoggingMiddleware",
)

if "test" in sys.argv:
    # modify MIDDLEWARE
    MIDDLEWARE = list(MIDDLEWARE)
    MIDDLEWARE.remove("adjutant.middleware.KeystoneHeaderUnwrapper")
    MIDDLEWARE.append("adjutant.middleware.TestingHeaderUnwrapper")

ROOT_URLCONF = "adjutant.urls"

WSGI_APPLICATION = "adjutant.wsgi.application"

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = "/static/"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "NAME": "default",
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "DIRS": ["/etc/adjutant/templates/"],
        "NAME": "include_etc_templates",
    },
]

AUTHENTICATION_BACKENDS = []

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "adjutant.api.exception_handler.exception_handler",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_PERMISSION_CLASSES": [],
}

SECRET_KEY = adj_conf.django.secret_key

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = adj_conf.django.debug
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(
        "rest_framework.renderers.BrowsableAPIRenderer"
    )

ALLOWED_HOSTS = adj_conf.django.allowed_hosts

SECURE_PROXY_SSL_HEADER = (
    adj_conf.django.secure_proxy_ssl_header,
    adj_conf.django.secure_proxy_ssl_header_value,
)

DATABASES = adj_conf.django.databases

if adj_conf.django.logging:
    LOGGING = adj_conf.django.logging
else:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "file": {
                "level": "INFO",
                "class": "logging.FileHandler",
                "filename": adj_conf.django.log_file,
            },
        },
        "loggers": {
            "adjutant": {
                "handlers": ["file"],
                "level": "INFO",
                "propagate": False,
            },
            "django": {
                "handlers": ["file"],
                "level": "INFO",
                "propagate": False,
            },
            "keystonemiddleware": {
                "handlers": ["file"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }


EMAIL_BACKEND = adj_conf.django.email.email_backend
EMAIL_TIMEOUT = adj_conf.django.email.timeout

EMAIL_HOST = adj_conf.django.email.host
EMAIL_PORT = adj_conf.django.email.port
EMAIL_HOST_USER = adj_conf.django.email.host_user
EMAIL_HOST_PASSWORD = adj_conf.django.email.host_password
EMAIL_USE_TLS = adj_conf.django.email.use_tls
EMAIL_USE_SSL = adj_conf.django.email.use_ssl
