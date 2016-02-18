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

import hashlib
import json
from datetime import timedelta
from smtplib import SMTPException
from uuid import uuid4

from decorator import decorator

from django.conf import settings
from django.core.exceptions import FieldError
from django.core.mail import send_mail
from django.template import loader
from django.utils import timezone

from rest_framework.response import Response

from stacktask.api.models import Notification, Token


def create_token(task):
    expire = timezone.now() + timedelta(hours=settings.TOKEN_EXPIRE_TIME)

    uuid = uuid4().hex
    token = Token.objects.create(
        task=task,
        token=uuid,
        expires=expire
    )
    token.save()
    return token


def send_email(task, email_conf, token=None):
    if not email_conf:
        return

    template = loader.get_template(email_conf['template'])
    html_template = email_conf.get('html_template', None)
    if html_template:
        html_template = loader.get_template(html_template)

    emails = set()
    actions = {}
    for action in task.actions:
        act = action.get_action()
        email = act.get_email()
        if email:
            emails.add(email)
            actions[unicode(act)] = act

    if len(emails) > 1:
        notes = {
            'errors':
            (("Error: Unable to send token, More than one email for" +
              " task: %s") % task.uuid)
        }
        create_notification(task, notes, error=True)
        return

    if token:
        context = {
            'task': task,
            'actions': actions,
            'tokenurl': settings.TOKEN_SUBMISSION_URL,
            'token': token.token,
        }
    else:
        context = {'task': task, 'actions': actions}

    try:
        message = template.render(context)
        if html_template:
            html_message = html_template.render(context)
            send_mail(
                email_conf['subject'], message, email_conf['reply'],
                [emails.pop()], fail_silently=False, html_message=html_message)
        else:
            send_mail(
                email_conf['subject'], message, email_conf['reply'],
                [emails.pop()], fail_silently=False)
    except SMTPException as e:
        notes = {
            'errors':
                ("Error: '%s' while emailing token for task: %s" %
                    (e, task.uuid))
        }

        errors_conf = settings.TASK_SETTINGS.get(
            task.task_type, {}).get('errors', {}).get(
            "SMTPException", {})

        if errors_conf:
            notification = create_notification(
                task, notes, error=True,
                engines=errors_conf.get('engines', True))

            if errors_conf.get('notification') == "acknowledge":
                notification.acknowledged = True
                notification.save()
        else:
            create_notification(task, notes, error=True)


def create_notification(task, notes, error=False, engines=True):
    notification = Notification.objects.create(
        task=task,
        notes=notes,
        error=error
    )
    notification.save()

    if not engines:
        return notification

    class_conf = settings.TASK_SETTINGS.get(task.task_type, {})

    for note_engine, conf in class_conf.get('notifications', {}).iteritems():
        if error:
            conf = conf.get('error', {})
        else:
            conf = conf.get('standard', {})
        if not conf:
            continue
        engine = settings.NOTIFICATION_ENGINES[note_engine](conf)
        engine.notify(task, notification)

    return notification


def create_task_hash(task_type, action_list):
    hashable_list = [task_type, ]

    for action in action_list:
        hashable_list.append(action['name'])
        # iterate like this to maintain consistent order for hash
        for field in action['action'].required:
            try:
                hashable_list.append(
                    action['serializer'].validated_data[field])
            except KeyError:
                if field is "username" and settings.USERNAME_IS_EMAIL:
                    continue
                else:
                    raise

    return hashlib.sha256(str(hashable_list)).hexdigest()


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
        for field, operations in filters.iteritems():
            for operation, value in operations.iteritems():
                cleaned_filters['%s__%s' % (field, operation)] = value
    except (ValueError, AttributeError):
        return Response(
            {'errors': [
                ("Filters incorrectly formatted. Required format: " +
                 "{'filters': {'fieldname': { 'operation': 'value'}}")
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
