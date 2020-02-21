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

from datetime import datetime
import time
import sys

from decorator import decorator

from rest_framework.response import Response


def require_roles(roles, func, *args, **kwargs):
    """
    endpoints setup with this decorator require the defined roles.
    """
    request = args[1]
    req_roles = set(roles)
    if not request.keystone_user.get("authenticated", False):
        return Response({"errors": ["Credentials incorrect or none given."]}, 401)

    roles = set(request.keystone_user.get("roles", []))

    if roles & req_roles:
        return func(*args, **kwargs)

    return Response(
        {"errors": ["Must have one of the following roles: %s" % list(req_roles)]}, 403
    )


@decorator
def mod_or_admin(func, *args, **kwargs):
    """
    Require project_mod or project_admin.
    Admin is allowed everything, so is also included.
    """
    return require_roles(
        {"project_admin", "project_mod", "admin"}, func, *args, **kwargs
    )


@decorator
def project_admin(func, *args, **kwargs):
    """
    endpoints setup with this decorator require the admin/project admin role.
    """
    return require_roles({"project_admin", "admin"}, func, *args, **kwargs)


@decorator
def admin(func, *args, **kwargs):
    """
    endpoints setup with this decorator require the admin role.
    """
    return require_roles({"admin"}, func, *args, **kwargs)


@decorator
def authenticated(func, *args, **kwargs):
    """
    endpoints setup with this decorator require the user to be signed in
    """
    request = args[1]
    if not request.keystone_user.get("authenticated", False):
        return Response({"errors": ["Credentials incorrect or none given."]}, 401)

    return func(*args, **kwargs)


@decorator
def minimal_duration(func, min_time=1, *args, **kwargs):
    """
    Make a function (or API call) take at least some time.
    """
    # doesn't apply during tests
    if "test" in sys.argv:
        return func(*args, **kwargs)

    start = datetime.utcnow()
    return_val = func(*args, **kwargs)
    end = datetime.utcnow()
    duration = end - start
    if duration.total_seconds() < min_time:
        time.sleep(min_time - duration.total_seconds())
    return return_val
