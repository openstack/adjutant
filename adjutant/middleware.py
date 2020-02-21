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

from time import time
from logging import getLogger
from django.utils import timezone


class KeystoneHeaderUnwrapper:
    """
    Middleware to build an easy to use dict of important data from
    what the keystone wsgi middleware gives us.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            token_data = {
                "project_domain_id": request.META["HTTP_X_PROJECT_DOMAIN_ID"],
                "project_name": request.META["HTTP_X_PROJECT_NAME"],
                "project_id": request.META["HTTP_X_PROJECT_ID"],
                "roles": request.META["HTTP_X_ROLES"].split(","),
                "user_domain_id": request.META["HTTP_X_USER_DOMAIN_ID"],
                "username": request.META["HTTP_X_USER_NAME"],
                "user_id": request.META["HTTP_X_USER_ID"],
                "authenticated": request.META["HTTP_X_IDENTITY_STATUS"],
            }
        except KeyError:
            token_data = {}
        request.keystone_user = token_data

        response = self.get_response(request)
        return response


class TestingHeaderUnwrapper:
    """
    Replacement for the KeystoneHeaderUnwrapper for testing purposes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            token_data = {
                # TODO(adriant): follow up patch to update all the test
                # headers to provide domain values.
                # Default here is just a temporary measure.
                "project_domain_id": request.META["headers"].get(
                    "project_domain_id", "default"
                ),
                "project_name": request.META["headers"]["project_name"],
                "project_id": request.META["headers"]["project_id"],
                "roles": request.META["headers"]["roles"].split(","),
                "user_domain_id": request.META["headers"].get(
                    "user_domain_id", "default"
                ),
                "username": request.META["headers"]["username"],
                "user_id": request.META["headers"]["user_id"],
                "authenticated": request.META["headers"]["authenticated"],
            }
        except KeyError:
            token_data = {}
        request.keystone_user = token_data

        response = self.get_response(request)
        return response


class RequestLoggingMiddleware:
    """
    Middleware to log the requests and responses.
    Will time the duration of a request and log that.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = getLogger("adjutant")

    def __call__(self, request):
        self.logger.info(
            "(%s) - <%s> %s [%s]",
            timezone.now(),
            request.method,
            request.META["REMOTE_ADDR"],
            request.get_full_path(),
        )
        request.timer = time()

        response = self.get_response(request)

        if hasattr(request, "timer"):
            time_delta = time() - request.timer
        else:
            time_delta = -1
        self.logger.info(
            "(%s) - <%s> [%s] - (%.1fs)",
            timezone.now(),
            response.status_code,
            request.get_full_path(),
            time_delta,
        )
        return response
