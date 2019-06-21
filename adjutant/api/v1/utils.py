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

import json

from decorator import decorator

from django.conf import settings
from django.core.exceptions import FieldError

from rest_framework.response import Response

from adjutant.api.models import Notification


# TODO(adriant): move this to 'adjutant.notifications.utils'
def create_notification(task, notes, error=False, engines=True):
    notification = Notification.objects.create(
        task=task,
        notes=notes,
        error=error
    )
    notification.save()

    if not engines:
        return notification

    class_conf = settings.TASK_SETTINGS.get(
        task.task_type, settings.DEFAULT_TASK_SETTINGS)

    notification_conf = class_conf.get('notifications', {})

    if notification_conf:
        for note_engine, conf in notification_conf.items():
            if error:
                conf = conf.get('error', {})
            else:
                conf = conf.get('standard', {})
            if not conf:
                continue
            engine = settings.NOTIFICATION_ENGINES[note_engine](conf)
            engine.notify(task, notification)

    return notification


# "{'filters': {'fieldname': { 'operation': 'value'}}
@decorator
def parse_filters(func, *args, **kwargs):
    """
    Parses incoming filters paramters and converts them to
    Django usable operations if valid.

    BE AWARE! WILL NOT WORK UNLESS POSITIONAL ARGUMENT 3 IS FILTERS!
    """
    request = args[1]
    filters = request.query_params.get('filters', None)

    if not filters:
        return func(*args, **kwargs)
    cleaned_filters = {}
    try:
        filters = json.loads(filters)
        for field, operations in filters.items():
            for operation, value in operations.items():
                cleaned_filters['%s__%s' % (field, operation)] = value
    except (ValueError, AttributeError):
        return Response(
            {'errors': [
                "Filters incorrectly formatted. Required format: "
                "{'filters': {'fieldname': { 'operation': 'value'}}"
            ]},
            status=400
        )

    try:
        # NOTE(adriant): This feels dirty and unclear, but it works.
        # Positional argument 3 is filters, so we just replace it.
        args = list(args)
        args[2] = cleaned_filters
        return func(*args, **kwargs)
    except FieldError as e:
        return Response({'errors': [str(e)]}, status=400)


def add_task_id_for_roles(request, processed, response_dict, req_roles):
    if request.keystone_user.get('authenticated', False):

        req_roles = set(req_roles)
        roles = set(request.keystone_user.get('roles', []))

        if roles & req_roles:
            response_dict['task'] = processed['task'].uuid
