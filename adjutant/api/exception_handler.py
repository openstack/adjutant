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

from logging import getLogger

from django.http import Http404
from django.utils import timezone

from rest_framework.response import Response

from adjutant import exceptions
from adjutant.notifications.utils import create_notification


LOG = getLogger("adjutant")


def exception_handler(exc, context):
    """Returns the response that should be used for any given exception."""
    now = timezone.now()
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, exceptions.BaseServiceException):
        LOG.exception("(%s) - Internal service error." % now)
        exc = exceptions.ServiceUnavailable()

    if isinstance(exc, exceptions.BaseAPIException):
        if isinstance(exc.message, (list, dict)):
            data = {"errors": exc.message}
        else:
            data = {"errors": [exc.message]}
        note_data = data

        if isinstance(exc, exceptions.TaskActionsFailed):
            if exc.internal_message:
                if isinstance(exc.internal_message, (list, dict)):
                    note_data = {"errors": exc.internal_message}
                else:
                    note_data = {"errors": [exc.internal_message]}
            create_notification(exc.task, note_data, error=True)

        LOG.info("(%s) - %s" % (now, exc))
        return Response(data, status=exc.status_code)

    LOG.exception("(%s) - Internal service error." % now)
    return None
